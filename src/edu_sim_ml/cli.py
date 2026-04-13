from __future__ import annotations

import argparse
from pathlib import Path

from .aihub_loader import load_samples, save_jsonl, split_samples
from .interviewer_finetune import (
    build_interviewer_finetune_dataset,
    start_openai_finetune_job,
)
from .lecture_package_builder import build_lecture_packages, save_lecture_packages
from .student_sim_trainer import train_student_sim_model
from .student_trainset_builder import build_student_trainset_from_store
from .train_whisper_lora import TrainConfig, train_whisper_lora
from .transcribe_openai import transcribe_missing_rows_with_openai


def main() -> None:
    parser = argparse.ArgumentParser(description="edu_sim ML pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    build_manifest = sub.add_parser("build-manifest", help="Build ASR manifest jsonl from AI-Hub dataset")
    build_manifest.add_argument("--dataset-root", required=True)
    build_manifest.add_argument("--output", default="ml_data/manifest.jsonl")
    build_manifest.add_argument("--valid-ratio", type=float, default=0.1)

    build_packages = sub.add_parser(
        "build-lecture-packages",
        help="Build edu_sim lecture_package files from AI-Hub labels",
    )
    build_packages.add_argument("--dataset-root", required=True)
    build_packages.add_argument("--output-dir", default="ml_data/lecture_packages")

    stt = sub.add_parser("stt-openai", help="Fill missing transcripts in a manifest with OpenAI STT")
    stt.add_argument("--manifest-file", required=True)
    stt.add_argument("--output-file", required=True)
    stt.add_argument("--model", required=True)
    stt.add_argument("--api-key", default="")

    train_asr = sub.add_parser("train-whisper-lora", help="Train Whisper ASR model (LoRA optional)")
    train_asr.add_argument("--manifest-file", required=True)
    train_asr.add_argument("--output-dir", default="ml_models/whisper_ko_lora")
    train_asr.add_argument("--model-name", default="openai/whisper-small")
    train_asr.add_argument("--epochs", type=float, default=3.0)
    train_asr.add_argument("--batch-size", type=int, default=2)
    train_asr.add_argument("--eval-batch-size", type=int, default=2)
    train_asr.add_argument("--learning-rate", type=float, default=1e-4)
    train_asr.add_argument("--use-lora", action="store_true")

    build_student_trainset = sub.add_parser(
        "build-student-trainset",
        help="Build student simulator training jsonl from edu_sim_store.json",
    )
    build_student_trainset.add_argument("--store-file", default="edu_sim_store.json")
    build_student_trainset.add_argument("--output-file", default="ml_data/student_sim_train.jsonl")

    train_student_sim = sub.add_parser(
        "train-student-simulator",
        help="Train student simulator regression model",
    )
    train_student_sim.add_argument("--train-file", required=True)
    train_student_sim.add_argument("--output-model", default="ml_models/student_sim_model.json")
    train_student_sim.add_argument("--l2", type=float, default=1.0)

    build_interviewer_ft = sub.add_parser(
        "build-interviewer-ft",
        help="Build chat fine-tuning jsonl for interviewer LLM from edu_sim_store.json",
    )
    build_interviewer_ft.add_argument("--store-file", default="edu_sim_store.json")
    build_interviewer_ft.add_argument("--train-output", default="ml_data/interviewer_ft_train.jsonl")
    build_interviewer_ft.add_argument("--valid-output", default="ml_data/interviewer_ft_valid.jsonl")
    build_interviewer_ft.add_argument("--valid-ratio", type=float, default=0.1)
    build_interviewer_ft.add_argument("--seed", type=int, default=42)

    run_interviewer_ft = sub.add_parser(
        "train-interviewer-ft-openai",
        help="Create OpenAI fine-tuning job for interviewer LLM",
    )
    run_interviewer_ft.add_argument("--train-file", required=True)
    run_interviewer_ft.add_argument("--valid-file", default="")
    run_interviewer_ft.add_argument("--base-model", default="gpt-4o-mini-2024-07-18")
    run_interviewer_ft.add_argument("--suffix", default="evalbuddy-interviewer")
    run_interviewer_ft.add_argument("--api-key", default="")
    run_interviewer_ft.add_argument("--output-info", default="ml_models/interviewer_ft_job.json")

    args = parser.parse_args()

    if args.command == "build-manifest":
        samples = load_samples(args.dataset_root)
        rows = split_samples(samples, valid_ratio=args.valid_ratio)
        save_jsonl(rows, args.output)
        print(f"saved manifest: {args.output}")
        print(f"num_samples: {len(rows)}")
        return

    if args.command == "build-lecture-packages":
        samples = load_samples(args.dataset_root)
        pkgs = build_lecture_packages(samples)
        paths = save_lecture_packages(pkgs, args.output_dir)
        print(f"saved packages: {len(paths)}")
        for p in paths[:5]:
            print(f" - {p}")
        return

    if args.command == "stt-openai":
        transcribe_missing_rows_with_openai(
            manifest_file=args.manifest_file,
            output_file=args.output_file,
            model=args.model,
            api_key=(args.api_key or None),
        )
        print(f"saved manifest with transcripts: {args.output_file}")
        return

    if args.command == "train-whisper-lora":
        cfg = TrainConfig(
            manifest_file=args.manifest_file,
            output_dir=args.output_dir,
            model_name=args.model_name,
            num_train_epochs=args.epochs,
            batch_size=args.batch_size,
            eval_batch_size=args.eval_batch_size,
            learning_rate=args.learning_rate,
            use_lora=bool(args.use_lora),
        )
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        train_whisper_lora(cfg)
        print(f"saved model: {args.output_dir}")
        return

    if args.command == "build-student-trainset":
        count = build_student_trainset_from_store(
            store_file=args.store_file,
            output_file=args.output_file,
        )
        print(f"saved trainset: {args.output_file}")
        print(f"num_rows: {count}")
        return

    if args.command == "train-student-simulator":
        artifact = train_student_sim_model(
            train_file=args.train_file,
            output_model_file=args.output_model,
            l2=args.l2,
        )
        print(f"saved student simulator model: {args.output_model}")
        print(f"num_samples: {artifact.num_samples}")
        return

    if args.command == "build-interviewer-ft":
        valid_output = args.valid_output.strip() or None
        train_count, valid_count = build_interviewer_finetune_dataset(
            store_file=args.store_file,
            train_output_file=args.train_output,
            valid_output_file=valid_output,
            valid_ratio=args.valid_ratio,
            seed=args.seed,
        )
        print(f"saved train jsonl: {args.train_output}")
        if valid_output:
            print(f"saved valid jsonl: {valid_output}")
        print(f"train_rows: {train_count}")
        print(f"valid_rows: {valid_count}")
        return

    if args.command == "train-interviewer-ft-openai":
        valid_file = args.valid_file.strip() or None
        payload = start_openai_finetune_job(
            train_file=args.train_file,
            valid_file=valid_file,
            base_model=args.base_model,
            suffix=args.suffix,
            api_key=(args.api_key or None),
            output_info_file=args.output_info,
        )
        print(f"fine_tune_job_id: {payload['fine_tune_job_id']}")
        print(f"status: {payload['status']}")
        print(f"saved info: {args.output_info}")
        return


if __name__ == "__main__":
    main()
