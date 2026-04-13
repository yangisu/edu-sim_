from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_interviewer_finetune_dataset(
    store_file: str | Path,
    train_output_file: str | Path,
    valid_output_file: str | Path | None = None,
    valid_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[int, int]:
    store = json.loads(Path(store_file).read_text(encoding="utf-8"))
    students = store.get("students", {})
    rubrics = store.get("rubrics", {})
    interviews = store.get("interviews", {})
    reports = store.get("reports", {})

    rows: list[dict[str, Any]] = []
    for key, interview_row in interviews.items():
        run_id = str(interview_row.get("run_id", ""))
        student_id = str(interview_row.get("student_id", ""))
        detail = interview_row.get("detail", {})
        evaluations = detail.get("evaluations", [])
        if not isinstance(evaluations, list) or not evaluations:
            continue

        rubric_table = _rubric_table(rubrics.get(run_id, {}))
        student_report = _find_student_report(reports.get(run_id, {}), student_id)
        progress_table = _objective_progress_table(student_report)
        traits = students.get(student_id, {}).get("traits", {})

        for ev in evaluations:
            criterion_id = str(ev.get("criterion_id", "")).strip()
            if not criterion_id:
                continue
            criterion = rubric_table.get(criterion_id, {})
            objective_id = str(criterion.get("objective_id", ""))
            progress = progress_table.get(objective_id, {})
            axis = _normalize_axis_scores(ev)
            confidence = _to_float(ev.get("confidence", 0.6), default=0.6)
            confidence = max(0.0, min(confidence, 1.0))
            comment = str(ev.get("comment", "")).strip() or "no_comment"

            user_payload = {
                "student_id": student_id,
                "student_traits": traits,
                "criterion": {
                    "criterion_id": criterion_id,
                    "objective_id": objective_id,
                    "title": criterion.get("title", ""),
                    "metric": criterion.get("metric", ""),
                    "weight": criterion.get("weight", 0.0),
                },
                "objective_progress": progress,
                "response_schema": {
                    "criterion_id": "string",
                    "axis_scores": {
                        "concept_accuracy": "0~4",
                        "procedure_execution": "0~4",
                        "case_application": "0~4",
                        "evidence_based_explanation": "0~4",
                    },
                    "confidence": "0~1",
                    "comment": "short evidence-based note",
                },
            }
            assistant_payload = {
                "criterion_id": criterion_id,
                "axis_scores": axis,
                "confidence": round(confidence, 2),
                "comment": comment,
            }
            rows.append(
                {
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an education evaluator. "
                                "Score objectively and return only JSON."
                            ),
                        },
                        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                        {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
                    ]
                }
            )

    if not rows:
        raise SystemExit("no interview rows found in store file")

    rng = random.Random(seed)
    rng.shuffle(rows)
    valid_count = max(1, int(len(rows) * valid_ratio)) if valid_output_file else 0
    if valid_count >= len(rows):
        valid_count = max(0, len(rows) - 1)
    valid_rows = rows[:valid_count]
    train_rows = rows[valid_count:]
    if not train_rows:
        raise SystemExit("train rows became empty; reduce valid_ratio")

    _save_jsonl(train_output_file, train_rows)
    if valid_output_file:
        _save_jsonl(valid_output_file, valid_rows)
    return len(train_rows), len(valid_rows)


def start_openai_finetune_job(
    train_file: str | Path,
    output_info_file: str | Path,
    base_model: str = "gpt-4o-mini-2024-07-18",
    valid_file: str | Path | None = None,
    suffix: str = "evalbuddy-interviewer",
    api_key: str | None = None,
) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for fine-tuning") from exc

    resolved_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client = OpenAI(api_key=resolved_key)
    with Path(train_file).open("rb") as f:
        train_upload = client.files.create(file=f, purpose="fine-tune")

    valid_upload = None
    if valid_file:
        with Path(valid_file).open("rb") as f:
            valid_upload = client.files.create(file=f, purpose="fine-tune")

    kwargs: dict[str, Any] = {
        "training_file": train_upload.id,
        "model": base_model,
        "suffix": suffix,
    }
    if valid_upload is not None:
        kwargs["validation_file"] = valid_upload.id

    job = client.fine_tuning.jobs.create(**kwargs)
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_model": base_model,
        "suffix": suffix,
        "training_file_id": train_upload.id,
        "validation_file_id": valid_upload.id if valid_upload is not None else None,
        "fine_tune_job_id": job.id,
        "fine_tuned_model": getattr(job, "fine_tuned_model", None),
        "status": getattr(job, "status", "created"),
    }
    out = Path(output_info_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _save_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _find_student_report(report: dict[str, Any], student_id: str) -> dict[str, Any]:
    rows = report.get("student_reports", [])
    if isinstance(rows, list):
        for row in rows:
            if str(row.get("student_id", "")) == student_id:
                return row
    return {}


def _objective_progress_table(student_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    breakdown = student_report.get("objective_breakdown", [])
    if not isinstance(breakdown, list):
        return result
    for row in breakdown:
        oid = str(row.get("objective_id", "")).strip()
        if not oid:
            continue
        result[oid] = {
            "objective_id": oid,
            "pre": _to_float(row.get("pre", 0.0), default=0.0),
            "post": _to_float(row.get("post", 0.0), default=0.0),
            "gain": _to_float(row.get("gain", 0.0), default=0.0),
        }
    return result


def _rubric_table(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rubric.get("criteria", [])
    table: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return table
    for row in rows:
        cid = str(row.get("id", "")).strip()
        if cid:
            table[cid] = row
    return table


def _normalize_axis_scores(ev: dict[str, Any]) -> dict[str, float]:
    axis = ev.get("axis_scores", {})
    if not isinstance(axis, dict):
        axis = {}
    if axis:
        return {
            "concept_accuracy": round(_clamp(_to_float(axis.get("concept_accuracy", 2.0), 2.0), 0.0, 4.0), 2),
            "procedure_execution": round(
                _clamp(_to_float(axis.get("procedure_execution", 2.0), 2.0), 0.0, 4.0),
                2,
            ),
            "case_application": round(_clamp(_to_float(axis.get("case_application", 2.0), 2.0), 0.0, 4.0), 2),
            "evidence_based_explanation": round(
                _clamp(_to_float(axis.get("evidence_based_explanation", 2.0), 2.0), 0.0, 4.0),
                2,
            ),
        }

    score_100 = _clamp(_to_float(ev.get("score_100", 50.0), 50.0), 0.0, 100.0)
    base = round(score_100 / 25.0, 2)
    base = _clamp(base, 0.0, 4.0)
    return {
        "concept_accuracy": base,
        "procedure_execution": base,
        "case_application": base,
        "evidence_based_explanation": base,
    }


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))
