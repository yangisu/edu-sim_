from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_student_trainset_from_store(
    store_file: str | Path,
    output_file: str | Path,
) -> int:
    store = json.loads(Path(store_file).read_text(encoding="utf-8"))
    students = store.get("students", {})
    runs = store.get("runs", {})
    reports = store.get("reports", {})
    sim_scores = store.get("simulation_scores", [])

    grouped: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in sim_scores:
        key = (str(row["run_id"]), str(row["student_id"]), str(row["objective_id"]))
        phase = str(row["phase"])
        score = float(row["score"])
        grouped.setdefault(key, {})
        grouped[key][phase] = score

    train_rows: list[dict[str, Any]] = []
    for (run_id, student_id, objective_id), scores in grouped.items():
        if "pre" not in scores or "post" not in scores:
            continue
        run = runs.get(run_id, {})
        config = run.get("config", {})
        student = students.get(student_id, {})
        report = reports.get(run_id, {})
        objective_meta = _find_objective_meta(report, objective_id)

        traits = student.get("traits", {})
        train_rows.append(
            {
                "knowledge_level_100": float(traits.get("knowledge_level_100", 50.0)),
                "intelligence_level_100": float(traits.get("intelligence_level_100", 50.0)),
                "prior_knowledge": float(traits.get("prior_knowledge", 0.5)),
                "focus": float(traits.get("focus", 0.5)),
                "curiosity": float(traits.get("curiosity", 0.5)),
                "adaptability": float(traits.get("adaptability", 0.5)),
                "anxiety": float(traits.get("anxiety", 0.3)),
                "lecture_quality": float(config.get("lecture_quality", 0.8)),
                "lecture_difficulty": float(config.get("lecture_difficulty", 0.5)),
                "objective_keyword_count": float(len(objective_meta.get("keywords", []))),
                "objective_text_len": float(len(str(objective_meta.get("description", "")))),
                "strengths_count": float(len(student.get("strengths", []))),
                "weaknesses_count": float(len(student.get("weaknesses", []))),
                "pre_score": float(scores["pre"]),
                "post_score": float(scores["post"]),
            }
        )

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in train_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(train_rows)


def _find_objective_meta(report: dict[str, Any], objective_id: str) -> dict[str, Any]:
    lecture = report.get("lecture", {})
    objectives = lecture.get("objectives", [])
    for obj in objectives:
        if str(obj.get("id")) == objective_id:
            return obj
    return {}

