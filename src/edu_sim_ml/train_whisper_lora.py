from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _require_ml_packages() -> None:
    missing = []
    for pkg in ("torch", "datasets", "transformers", "evaluate", "numpy", "soundfile", "scipy"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        raise SystemExit(f"missing packages: {', '.join(missing)}")


@dataclass(slots=True)
class TrainConfig:
    manifest_file: str
    output_dir: str
    model_name: str = "openai/whisper-small"
    language: str = "Korean"
    task: str = "transcribe"
    learning_rate: float = 1e-4
    num_train_epochs: float = 3.0
    batch_size: int = 2
    eval_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 50
    logging_steps: int = 10
    eval_steps: int = 25
    save_steps: int = 25
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    use_lora: bool = False


def train_whisper_lora(config: TrainConfig) -> None:
    _require_ml_packages()
    import evaluate
    import numpy as np
    import soundfile as sf
    import torch
    from datasets import Dataset
    from scipy.signal import resample_poly
    from transformers import (
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
        WhisperForConditionalGeneration,
        WhisperProcessor,
    )

    rows = _load_manifest(config.manifest_file)
    if not rows:
        raise SystemExit("manifest has no rows")
    train_rows = [r for r in rows if r.get("split") != "validation"]
    valid_rows = [r for r in rows if r.get("split") == "validation"]
    if not valid_rows:
        valid_rows = rows[: max(1, len(rows) // 10)]

    processor = WhisperProcessor.from_pretrained(
        config.model_name,
        language=config.language,
        task=config.task,
    )
    model = WhisperForConditionalGeneration.from_pretrained(config.model_name)
    model.config.forced_decoder_ids = processor.get_decoder_prompt_ids(language=config.language, task=config.task)
    model.config.suppress_tokens = []

    if config.use_lora:
        try:
            from peft import LoraConfig, TaskType, get_peft_model
        except ImportError as exc:
            raise SystemExit("peft package is required when --use-lora is enabled") from exc
        lora_cfg = LoraConfig(
            r=config.lora_r,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            target_modules=["q_proj", "v_proj"],
            task_type=TaskType.SEQ_2_SEQ_LM,
        )
        model = get_peft_model(model, lora_cfg)
        model.print_trainable_parameters()

    train_ds = Dataset.from_list(train_rows)
    valid_ds = Dataset.from_list(valid_rows)

    def prepare(batch: dict[str, Any]) -> dict[str, Any]:
        audio_path = str(batch["audio_path"])
        arr, sr = sf.read(audio_path)
        if getattr(arr, "ndim", 1) > 1:
            arr = arr.mean(axis=1)
        if sr != 16000:
            arr = resample_poly(arr, 16000, sr)
        arr = np.asarray(arr, dtype="float32")
        features = processor.feature_extractor(arr, sampling_rate=16000).input_features[0]
        labels = processor.tokenizer(str(batch["transcript"])).input_ids
        return {"input_features": features, "labels": labels}

    train_ds = train_ds.map(prepare, remove_columns=train_ds.column_names)
    valid_ds = valid_ds.map(prepare, remove_columns=valid_ds.column_names)

    @dataclass
    class DataCollatorSpeechSeq2SeqWithPadding:
        processor: Any

        def __call__(self, features: list[dict[str, Any]]) -> dict[str, Any]:
            input_features = [{"input_features": f["input_features"]} for f in features]
            batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")
            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
            labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
            if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
                labels = labels[:, 1:]
            batch["labels"] = labels
            return batch

    metric_wer = evaluate.load("wer")
    metric_cer = evaluate.load("cer")

    def compute_metrics(pred) -> dict[str, float]:
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
        pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        return {
            "wer": metric_wer.compute(predictions=pred_str, references=label_str),
            "cer": metric_cer.compute(predictions=pred_str, references=label_str),
        }

    args = Seq2SeqTrainingArguments(
        output_dir=config.output_dir,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_steps=config.warmup_steps,
        num_train_epochs=config.num_train_epochs,
        evaluation_strategy="steps",
        predict_with_generate=True,
        generation_max_length=225,
        fp16=torch.cuda.is_available(),
        logging_steps=config.logging_steps,
        eval_steps=config.eval_steps,
        save_steps=config.save_steps,
        report_to=[],
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
    )

    trainer = Seq2SeqTrainer(
        args=args,
        model=model,
        train_dataset=train_ds,
        eval_dataset=valid_ds,
        data_collator=DataCollatorSpeechSeq2SeqWithPadding(processor=processor),
        tokenizer=processor.feature_extractor,
        compute_metrics=compute_metrics,
    )
    trainer.train()
    trainer.save_model(config.output_dir)
    processor.save_pretrained(config.output_dir)


def _load_manifest(manifest_file: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = Path(manifest_file)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        transcript = str(row.get("transcript", "")).strip()
        audio_path = str(row.get("audio_path", "")).strip()
        if transcript and audio_path:
            rows.append({"audio_path": audio_path, "transcript": transcript, "split": row.get("split", "train")})
    return rows

