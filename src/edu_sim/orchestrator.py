from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .assessment_policy import PROFICIENCY_BANDS, score_to_band
from .interview_engine import InterviewEngine
from .lecture_engine import LectureEngine
from .llm_interview_engine import LlmInterviewEngine
from .models import StudentProfile
from .plan_service import InstructorPlanService
from .repository import Repository
from .rubric_engine import RubricEngine
from .student_simulator import StudentSimulator
from .student_trained_model import StudentModelPredictor


class WorkflowService:
    """강의 입력부터 학생 시뮬레이션/평가까지 end-to-end 실행."""

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
        self.plan_service = InstructorPlanService(
            repository=self.repo,
            lecture_engine=self.lecture_engine,
            rubric_engine=self.rubric_engine,
        )

    def run(
        self,
        lecture_title: str,
        lecture_content: str,
        students: list[StudentProfile],
        config: dict[str, Any] | None = None,
        lecture_package: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config or {}
        now = datetime.now(timezone.utc).isoformat()
        lecture_id = f"lec_{uuid4().hex[:10]}"
        run_id = f"run_{uuid4().hex[:10]}"

        self.repo.save_lecture(lecture_id, lecture_title, lecture_content, now)
        self.repo.upsert_students(students, now)
        self.repo.create_run(run_id, lecture_id, config, now)

        plan_id_used: str | None = config.get("approved_plan_id")
        if plan_id_used:
            approved_plan = self.plan_service.get_approved_plan(plan_id_used)
            objectives = self.plan_service.objectives_from_plan(approved_plan)
            criteria = self.plan_service.rubric_from_plan(approved_plan)
        else:
            if lecture_package:
                objectives = self.lecture_engine.extract_objectives_from_package(
                    lecture_package,
                    max_objectives=int(config.get("max_objectives", 5)),
                )
            else:
                objectives = self.lecture_engine.extract_objectives(
                    lecture_content,
                    max_objectives=int(config.get("max_objectives", 5)),
                )
            criteria = self.rubric_engine.generate(objectives)

        model_predictor = self._load_student_model_predictor(config)
        interview_mode, llm_engine, interview_note = self._build_interview_engine(config)
        interview_mode_used = interview_mode

        all_sim_rows: list[tuple[str, str, str, str, float]] = []
        student_reports: list[dict[str, Any]] = []
        group_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for student in students:
            sim = self.simulator.simulate(
                student=student,
                objectives=objectives,
                lecture_quality=float(config.get("lecture_quality", 0.8)),
                lecture_difficulty=float(config.get("lecture_difficulty", 0.5)),
                model_predictor=model_predictor,
            )

            interview_used = interview_mode
            if interview_mode == "llm" and llm_engine is not None:
                try:
                    interview = llm_engine.evaluate(
                        student=student,
                        simulation=sim,
                        criteria=criteria,
                        lecture_title=lecture_title,
                    )
                except Exception as exc:  # noqa: BLE001
                    interview = self.interview_engine.evaluate(
                        student_id=student.id,
                        simulation=sim,
                        criteria=criteria,
                    )
                    interview_used = "rule_fallback"
                    interview_mode_used = "rule_fallback"
                    interview_note = f"llm failed and fallback applied: {exc}"
            else:
                interview = self.interview_engine.evaluate(
                    student_id=student.id,
                    simulation=sim,
                    criteria=criteria,
                )

            for p in sim.objective_progress:
                all_sim_rows.append((run_id, student.id, p.objective_id, "pre", p.pre_score))
                all_sim_rows.append((run_id, student.id, p.objective_id, "post", p.post_score))

            interview_payload = {
                "engine": interview_used,
                "proficiency_level": interview.proficiency_level,
                "evaluations": [
                    {
                        "criterion_id": e.criterion_id,
                        "score_5_scale": e.score_5_scale,
                        "score_100": e.score_100,
                        "axis_scores": e.axis_scores,
                        "proficiency_level": e.proficiency_level,
                        "confidence": e.confidence,
                        "comment": e.comment,
                        "question": self._criterion_question(e.criterion_id, criteria),
                    }
                    for e in interview.evaluations
                ],
            }
            self.repo.save_interview(run_id, student.id, interview.total_score_100, interview_payload)

            pre_band = score_to_band(sim.pre_avg)
            post_band = score_to_band(sim.post_avg)
            interview_band = score_to_band(interview.total_score_100)
            learning_effectiveness = round(sim.gain_avg * 0.6 + interview.total_score_100 * 0.4, 2)

            student_report = {
                "student_id": student.id,
                "student_name": student.name,
                "level": student.level,
                "pre_avg": round(sim.pre_avg, 2),
                "post_avg": round(sim.post_avg, 2),
                "gain_avg": round(sim.gain_avg, 2),
                "pre_proficiency": pre_band.label,
                "post_proficiency": post_band.label,
                "interview_score": interview.total_score_100,
                "interview_proficiency": interview_band.label,
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
                    "pre_band_key": pre_band.key,
                    "post_band_key": post_band.key,
                    "interview_band_key": interview_band.key,
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
                ],
                "scoring_standard": self.interview_engine.scoring_standard(),
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
                "input_format": "lecture_package" if lecture_package else "plain_text",
                "metadata": lecture_package.get("metadata", {}) if lecture_package else {},
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
            "scoring_standard": self.interview_engine.scoring_standard(),
            "group_summary": group_summary,
            "student_reports": student_reports,
            "config": config,
            "approved_plan_id": plan_id_used,
            "student_simulator_engine": "trained_model" if model_predictor is not None else "rule",
            "interview_engine_used": interview_mode_used,
            "interview_engine_note": interview_note,
            "execution_meta": {
                "student_simulator": {
                    "code": "trained_model" if model_predictor is not None else "rule",
                    "label": "학습 기반 학생 시뮬레이터" if model_predictor is not None else "규칙 기반 학생 시뮬레이터",
                    "description": (
                        "저장된 학생 모델 가중치로 pre/post를 예측"
                        if model_predictor is not None
                        else "학생 특성 규칙으로 pre/post를 계산"
                    ),
                },
                "interviewer": {
                    "code": interview_mode_used,
                    "label": self._interview_engine_label(interview_mode_used),
                    "description": interview_note,
                },
            },
            "result_format": {
                "version": "evalbuddy.report.v2",
                "description": "group_summary(집단 통계), student_reports(개별 결과), execution_meta(실행 방식 설명)",
            },
            "generated_at_utc": now,
        }
        self.repo.save_report(run_id, report)
        return report

    def _load_student_model_predictor(self, config: dict[str, Any]) -> StudentModelPredictor | None:
        model_path = str(config.get("student_model_path", "")).strip()
        if not model_path:
            return None
        return StudentModelPredictor.from_file(model_path)

    def _build_interview_engine(
        self,
        config: dict[str, Any],
    ) -> tuple[str, LlmInterviewEngine | None, str]:
        mode = str(config.get("interview_mode", "rule")).strip().lower()
        if mode != "llm":
            return "rule", None, "rule-based interview engine"

        llm_model = str(config.get("llm_model", "gpt-4o-mini"))
        llm_api_key = str(config.get("llm_api_key", "")).strip() or None
        try:
            engine = LlmInterviewEngine(model=llm_model, api_key=llm_api_key)
            return "llm", engine, f"llm interview engine model={llm_model}"
        except Exception as exc:  # noqa: BLE001
            return "rule", None, f"llm init failed, fallback to rule engine: {exc}"

    @staticmethod
    def _summarize_group(level: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(rows)
        pre_dist = WorkflowService._distribution(rows, "pre_band_key")
        post_dist = WorkflowService._distribution(rows, "post_band_key")
        interview_dist = WorkflowService._distribution(rows, "interview_band_key")
        return {
            "level": level,
            "count": count,
            "pre_avg": round(sum(r["pre"] for r in rows) / count, 2),
            "post_avg": round(sum(r["post"] for r in rows) / count, 2),
            "gain_avg": round(sum(r["gain"] for r in rows) / count, 2),
            "interview_avg": round(sum(r["interview"] for r in rows) / count, 2),
            "effectiveness_avg": round(sum(r["effectiveness"] for r in rows) / count, 2),
            "pre_proficiency_distribution": pre_dist,
            "post_proficiency_distribution": post_dist,
            "interview_proficiency_distribution": interview_dist,
        }

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
        labels = {band.key: band.label for band in PROFICIENCY_BANDS}
        result: dict[str, int] = {label: 0 for label in labels.values()}
        for row in rows:
            band_key = row.get(key)
            label = labels.get(band_key)
            if label:
                result[label] += 1
        return result

    @staticmethod
    def _interview_engine_label(code: str) -> str:
        if code == "llm":
            return "LLM 면접 평가"
        if code == "rule_fallback":
            return "LLM 실패 후 규칙 평가 fallback"
        return "규칙 기반 면접 평가"

    @staticmethod
    def _criterion_question(criterion_id: str, criteria: list[Any]) -> str:
        for criterion in criteria:
            if criterion.id == criterion_id:
                return InterviewEngine.build_question(criterion)
        return "해당 개념을 실제 사례와 함께 설명하세요."

