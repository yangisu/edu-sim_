from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .aihub_loader import AihubSample


def _sample_sort_key(sample: AihubSample) -> tuple[int, str]:
    try:
        return int(sample.sample_id[1:]), sample.sample_id
    except (TypeError, ValueError):
        return 10**9, sample.sample_id


def build_lecture_packages(samples: list[AihubSample]) -> list[dict[str, Any]]:
    buckets: dict[str, list[AihubSample]] = defaultdict(list)
    for sample in samples:
        lecture_key = sample.lecture_id or "unknown_lecture"
        buckets[lecture_key].append(sample)

    packages: list[dict[str, Any]] = []
    for lecture_id, rows in sorted(buckets.items(), key=lambda x: x[0]):
        ordered = sorted(rows, key=_sample_sort_key)
        transcript = " ".join(x.transcript for x in ordered if x.transcript).strip()
        materials = []
        seen_entity: set[str] = set()
        for x in ordered:
            for entity in x.entities:
                word = str(entity.get("1_word", "")).strip()
                desc = str(entity.get("2_desc", "")).strip()
                if not word:
                    continue
                key = f"{word}::{desc}"
                if key in seen_entity:
                    continue
                seen_entity.add(key)
                text = f"{word}: {desc}" if desc else word
                materials.append({"type": "entity_glossary", "text": text})

        duration_minutes = round(sum(x.speech_length_sec for x in ordered) / 60.0, 2)
        subject = ordered[0].major_category if ordered else ""
        package = {
            "lecture_id": lecture_id,
            "lecture_name": ordered[0].lecture_name if ordered else lecture_id,
            "transcript": transcript,
            "materials": materials,
            "metadata": {
                "subject": subject,
                "city": ordered[0].city if ordered else "",
                "university_type": ordered[0].university_type if ordered else "",
                "collection_type": ordered[0].collection_type if ordered else "",
                "duration_minutes": duration_minutes,
                "prerequisites": [],
                "speaker": {
                    "id": ordered[0].speaker_id if ordered else "",
                    "gender": ordered[0].speaker_gender if ordered else "",
                    "age": ordered[0].speaker_age if ordered else "",
                    "role": ordered[0].speaker_role if ordered else "",
                    "dialect": ordered[0].speaker_dialect if ordered else "",
                },
                "num_segments": len(ordered),
            },
            "instructor_objectives": [],
            "segments": [
                {
                    "sample_id": x.sample_id,
                    "audio_path": x.audio_path,
                    "transcript": x.transcript,
                    "speech_length_sec": x.speech_length_sec,
                }
                for x in ordered
            ],
        }
        packages.append(package)
    return packages


def save_lecture_packages(packages: list[dict[str, Any]], output_dir: str | Path) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for pkg in packages:
        lecture_id = str(pkg.get("lecture_id", "unknown"))
        path = out / f"{lecture_id}.lecture_package.json"
        path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.append(path)
    return paths

