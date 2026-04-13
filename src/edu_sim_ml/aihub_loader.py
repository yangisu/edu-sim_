from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class AihubSample:
    sample_id: str
    lecture_id: str
    lecture_name: str
    audio_path: str
    label_path: str
    transcript: str
    entities: list[dict[str, Any]]
    speech_length_sec: float
    city: str
    university_type: str
    major_category: str
    collection_type: str
    speaker_id: str
    speaker_gender: str
    speaker_age: str
    speaker_role: str
    speaker_dialect: str


def _read_json_with_fallback(path: Path) -> dict[str, Any]:
    encodings = ("utf-8", "utf-8-sig", "cp949", "euc-kr")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return json.loads(path.read_text(encoding=encoding))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"failed to read json file: {path}") from last_error


def _find_data_dir(root: Path, prefix: str) -> Path:
    matches = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith(prefix)])
    if matches:
        return matches[0]
    raise FileNotFoundError(f"cannot find directory with prefix '{prefix}' under '{root}'")


def iter_label_files(dataset_root: str | Path) -> Iterable[Path]:
    root = Path(dataset_root)
    label_root = _find_data_dir(root, "02.")
    yield from sorted(label_root.rglob("*.json"))


def parse_label_file(dataset_root: str | Path, label_file: str | Path) -> AihubSample:
    root = Path(dataset_root)
    label_path = Path(label_file)
    raw = _read_json_with_fallback(label_path)

    label_root = _find_data_dir(root, "02.")
    source_root = _find_data_dir(root, "01.")
    relative = label_path.relative_to(label_root)
    audio_path = (source_root / relative).with_suffix(".wav")

    dataset = raw.get("01_dataset", {})
    srcinfo = raw.get("02_srcinfo", {})
    lectureinfo = raw.get("03_lectureinfo", {})
    speakerinfo = raw.get("05_speakerinfo", {})
    transcription = raw.get("06_transcription", {})

    speech_length = dataset.get("9_speech_length", 0)
    try:
        speech_length_sec = float(speech_length)
    except (TypeError, ValueError):
        speech_length_sec = 0.0

    entities = transcription.get("2_entity", [])
    if not isinstance(entities, list):
        entities = []

    return AihubSample(
        sample_id=label_path.stem,
        lecture_id=str(srcinfo.get("1_id", "")),
        lecture_name=str(dataset.get("2_name", "")),
        audio_path=str(audio_path),
        label_path=str(label_path),
        transcript=str(transcription.get("1_text", "")).strip(),
        entities=entities,
        speech_length_sec=speech_length_sec,
        city=str(lectureinfo.get("1_city", "")),
        university_type=str(lectureinfo.get("2_university_type", "")),
        major_category=str(lectureinfo.get("3_major_category", "")),
        collection_type=str(lectureinfo.get("5_collection_type", "")),
        speaker_id=str(speakerinfo.get("1_id", "")),
        speaker_gender=str(speakerinfo.get("2_gender", "")),
        speaker_age=str(speakerinfo.get("3_age", "")),
        speaker_role=str(speakerinfo.get("4_role", "")),
        speaker_dialect=str(speakerinfo.get("5_dialect", "")),
    )


def load_samples(dataset_root: str | Path) -> list[AihubSample]:
    return [parse_label_file(dataset_root, path) for path in iter_label_files(dataset_root)]


def split_samples(samples: list[AihubSample], valid_ratio: float = 0.1) -> list[dict[str, Any]]:
    if not samples:
        return []
    valid_every = max(2, int(round(1.0 / max(1e-6, valid_ratio))))
    rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples):
        row = asdict(sample)
        row["split"] = "validation" if (idx % valid_every == 0) else "train"
        rows.append(row)
    return rows


def save_jsonl(rows: list[dict[str, Any]], output_file: str | Path) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
