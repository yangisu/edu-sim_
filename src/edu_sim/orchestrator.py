from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .interview_engine import InterviewEngine
from .lecture_engine import LectureEngine
from .models import StudentProfile
from .repository import Repository
from .rubric_engine import RubricEngine
from .student_simulator import StudentSimulator


class WorkflowService:
    """강의 입력부터 시뮬레이션/평가까지 end-to-end를 수행하는 서비스."""

    def __init__(
        self,
        repository: Repository,
        lecture_engine: LectureEngine | None = None,
        simulator: StudentSimulator | None = None,
        rubric_engine: RubricEngine | None = None,
        interview_engine: InterviewEngine | None = None,
    ) -> None:
        self.repo = repository
        self.lecture_engine = lecture_engine or LectureEngine()
        self.simulator = simulator or StudentSimulator()
        self.rubric_engine = rubric_engine or RubricEngine()
        self.interview_engine = interview_engine or InterviewEngine()

    def run(
        self,
        lecture_title: str,
        lecture_content: str,
        students: list[StudentProfile],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config or {}
        now = datetime.now(timezone.utc).isoformat()
        lecture_id = f"lec_{uuid4().hex[:10]}"
        run_id = f"run_{uuid4().hex[:10]}"

        self.repo.save_lecture(lecture_id, lecture_title, lecture_content, now)
        self.repo.upsert_students(students, now)
        self.repo.create_run(run_id, lecture_id, config, now)

        objectives = self.lecture_engine.extract_objectives(
            lecture_content,
            max_objectives=int(config.get("max_objectives", 5)),
        )
        criteria = self.rubric_engine.generate(objectives)

        all_sim_rows: list[tuple[str, str, str, str, float]] = []
        student_reports: list[dict[str, Any]] = []
        group_bucket: dict[str, list[dict[str, float]]] = defaultdict(list)

        for student in students:
            sim = self.simulator.simulate(
                student=student,
                objectives=objectives,
                lecture_quality=float(config.get("lecture_quality", 0.8)),
                lecture_difficulty=float(config.get("lecture_difficulty", 0.5)),
            )
            interview = self.interview_engine.evaluate(
                student_id=student.id,
                simulation=sim,
                criteria=criteria,
            )

            for p in sim.objective_progress:
                all_sim_rows.append((run_id, student.id, p.objective_id, "pre", p.pre_score))
                all_sim_rows.append((run_id, student.id, p.objective_id, "post", p.post_score))

            interview_payload = {
                "evaluations": [
                    {
                        "criterion_id": e.criterion_id,
                        "score_5_scale": e.score_5_scale,
                        "confidence": e.confidence,
                        "comment": e.comment,
                        "question": self._criterion_question(e.criterion_id, criteria),
                    }
                    for e in interview.evaluations
                ]
            }
            self.repo.save_interview(run_id, student.id, interview.total_score_100, interview_payload)

            learning_effectiveness = round(sim.gain_avg * 0.6 + interview.total_score_100 * 0.4, 2)
            student_report = {
                "student_id": student.id,
                "student_name": student.name,
                "level": student.level,
                "pre_avg": round(sim.pre_avg, 2),
                "post_avg": round(sim.post_avg, 2),
                "gain_avg": round(sim.gain_avg, 2),
                "interview_score": interview.total_score_100,
                "learning_effectiveness": learning_effectiveness,
                "objective_breakdown": [
                    {
                        "objective_id": p.objective_id,
                        "pre": p.pre_score,
                        "post": p.post_score,
                        "gain": round(p.gain, 2),
                    }
                    for p in sim.objective_progress
                ],
            }
            student_reports.append(student_report)
            group_bucket[student.level].append(
                {
                    "pre": sim.pre_avg,
                    "post": sim.post_avg,
                    "gain": sim.gain_avg,
                    "interview": interview.total_score_100,
                    "effectiveness": learning_effectiveness,
                }
            )

        self.repo.save_simulation_scores(all_sim_rows)
        self.repo.save_rubric(
            run_id,
            {
                "criteria": [
                    {
                        "id": c.id,
                        "objective_id": c.objective_id,
                        "title": c.title,
                        "metric": c.metric,
                        "weight": c.weight,
                        "score_bands": c.score_bands,
                        "question": self.interview_engine.build_question(c),
                    }
                    for c in criteria
                ]
            },
        )

        group_summary = {
            level: self._summarize_group(level, metrics) for level, metrics in sorted(group_bucket.items())
        }

        report = {
            "run_id": run_id,
            "lecture": {
                "lecture_id": lecture_id,
                "title": lecture_title,
                "objective_count": len(objectives),
                "objectives": [
                    {
                        "id": o.id,
                        "description": o.description,
                        "keywords": o.keywords,
                        "weight": o.weight,
                    }
                    for o in objectives
                ],
            },
            "group_summary": group_summary,
            "student_reports": student_reports,
            "config": config,
            "generated_at_utc": now,
        }
        self.repo.save_report(run_id, report)
        return report

    @staticmethod
    def _summarize_group(level: str, rows: list[dict[str, float]]) -> dict[str, Any]:
        count = len(rows)
        return {
            "level": level,
            "count": count,
            "pre_avg": round(sum(r["pre"] for r in rows) / count, 2),
            "post_avg": round(sum(r["post"] for r in rows) / count, 2),
            "gain_avg": round(sum(r["gain"] for r in rows) / count, 2),
            "interview_avg": round(sum(r["interview"] for r in rows) / count, 2),
            "effectiveness_avg": round(sum(r["effectiveness"] for r in rows) / count, 2),
        }

    @staticmethod
    def _criterion_question(criterion_id: str, criteria: list[Any]) -> str:
        for criterion in criteria:
            if criterion.id == criterion_id:
                return InterviewEngine.build_question(criterion)
        return "관련 개념을 실제 사례와 함께 설명하세요."
