from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import StudentProfile


class Repository:
    def __init__(self, db_path: str | Path = "edu_sim_store.json") -> None:
        self.db_path = str(db_path)
        self._in_memory = self.db_path == ":memory:"
        self.path = Path(self.db_path) if not self._in_memory else None
        self.data: dict[str, Any] = self._load_or_init()

    def _empty_store(self) -> dict[str, Any]:
        return {
            "lectures": {},
            "students": {},
            "runs": {},
            "simulation_scores": [],
            "rubrics": {},
            "interviews": {},
            "reports": {},
        }

    def _load_or_init(self) -> dict[str, Any]:
        if self._in_memory:
            return self._empty_store()

        assert self.path is not None
        if self.path.exists():
            text = self.path.read_text(encoding="utf-8").strip()
            if text:
                return json.loads(text)
        self.path.write_text(json.dumps(self._empty_store(), ensure_ascii=False, indent=2), encoding="utf-8")
        return self._empty_store()

    def _flush(self) -> None:
        if self._in_memory:
            return
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_lecture(self, lecture_id: str, title: str, content: str, created_at: str) -> None:
        self.data["lectures"][lecture_id] = {
            "id": lecture_id,
            "title": title,
            "content": content,
            "created_at": created_at,
        }
        self._flush()

    def upsert_students(self, students: list[StudentProfile], created_at: str) -> None:
        for student in students:
            self.data["students"][student.id] = {
                "id": student.id,
                "name": student.name,
                "level": student.level,
                "traits": student.traits,
                "strengths": student.strengths,
                "weaknesses": student.weaknesses,
                "created_at": created_at,
            }
        self._flush()

    def create_run(self, run_id: str, lecture_id: str, config: dict[str, Any], created_at: str) -> None:
        self.data["runs"][run_id] = {
            "id": run_id,
            "lecture_id": lecture_id,
            "config": config,
            "created_at": created_at,
        }
        self._flush()

    def save_simulation_scores(self, rows: list[tuple[str, str, str, str, float]]) -> None:
        for run_id, student_id, objective_id, phase, score in rows:
            self.data["simulation_scores"].append(
                {
                    "run_id": run_id,
                    "student_id": student_id,
                    "objective_id": objective_id,
                    "phase": phase,
                    "score": score,
                }
            )
        self._flush()

    def save_rubric(self, run_id: str, rubric: dict[str, Any]) -> None:
        self.data["rubrics"][run_id] = rubric
        self._flush()

    def save_interview(self, run_id: str, student_id: str, total_score: float, detail: dict[str, Any]) -> None:
        key = f"{run_id}:{student_id}"
        self.data["interviews"][key] = {
            "run_id": run_id,
            "student_id": student_id,
            "total_score": total_score,
            "detail": detail,
        }
        self._flush()

    def save_report(self, run_id: str, report: dict[str, Any]) -> None:
        self.data["reports"][run_id] = report
        self._flush()

    def get_report(self, run_id: str) -> dict[str, Any] | None:
        report = self.data["reports"].get(run_id)
        return report if report is not None else None
