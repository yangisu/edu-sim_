from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .interview_engine import InterviewEngine
from .lecture_engine import LectureEngine
from .models import LearningObjective, RubricCriterion
from .repository import Repository
from .rubric_engine import RubricEngine


class PlanValidationError(ValueError):
    pass


class InstructorPlanService:
    """강사 검토/승인용 objective-rubric 플랜 서비스."""

    def __init__(
        self,
        repository: Repository,
        lecture_engine: LectureEngine | None = None,
        rubric_engine: RubricEngine | None = None,
    ) -> None:
        self.repo = repository
        self.lecture_engine = lecture_engine or LectureEngine()
        self.rubric_engine = rubric_engine or RubricEngine()

    def draft_plan(
        self,
        lecture_title: str,
        lecture_content: str,
        max_objectives: int = 5,
    ) -> dict[str, Any]:
        objectives = self.lecture_engine.extract_objectives(lecture_content, max_objectives=max_objectives)
        return self._build_and_save_plan(
            lecture_title=lecture_title,
            lecture_digest=lecture_content[:300],
            objectives=objectives,
        )

    def draft_plan_from_package(
        self,
        lecture_title: str,
        package_raw: dict[str, Any],
        max_objectives: int = 5,
    ) -> dict[str, Any]:
        objectives = self.lecture_engine.extract_objectives_from_package(package_raw, max_objectives=max_objectives)
        digest = str(package_raw.get("transcript", ""))[:300]
        return self._build_and_save_plan(
            lecture_title=lecture_title,
            lecture_digest=digest,
            objectives=objectives,
        )

    def approve_plan(
        self,
        plan: dict[str, Any],
        approved_by: str,
        approval_notes: str = "",
    ) -> dict[str, Any]:
        errors = self.validate(plan)
        if errors:
            joined = "\n".join(f"- {err}" for err in errors)
            raise PlanValidationError(f"plan validation failed:\n{joined}")

        now = datetime.now(timezone.utc).isoformat()
        approved = dict(plan)
        approved["status"] = "approved"
        approved["approved_by"] = approved_by
        approved["approved_at_utc"] = now
        approved["updated_at_utc"] = now
        approved["approval_notes"] = approval_notes
        approved["scoring_standard"] = InterviewEngine.scoring_standard()

        self.repo.save_lecture_plan(approved["plan_id"], approved)
        return approved

    def get_approved_plan(self, plan_id: str) -> dict[str, Any]:
        plan = self.repo.get_lecture_plan(plan_id)
        if plan is None:
            raise PlanValidationError(f"plan_id '{plan_id}' not found")
        if plan.get("status") != "approved":
            raise PlanValidationError(f"plan_id '{plan_id}' is not approved")
        errors = self.validate(plan)
        if errors:
            joined = "\n".join(f"- {err}" for err in errors)
            raise PlanValidationError(f"approved plan is invalid:\n{joined}")
        return plan

    def validate(self, plan: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        objectives = plan.get("objectives", [])
        rubric = plan.get("rubric", [])

        if not plan.get("plan_id"):
            errors.append("plan_id is required")
        if not objectives:
            errors.append("at least one objective is required")
        if not rubric:
            errors.append("at least one rubric criterion is required")

        objective_ids: set[str] = set()
        objective_weight_sum = 0.0
        for idx, obj in enumerate(objectives, start=1):
            obj_id = str(obj.get("id", "")).strip()
            desc = str(obj.get("description", "")).strip()
            keywords = obj.get("keywords", [])
            weight = obj.get("weight", 0)

            if not obj_id:
                errors.append(f"objective[{idx}] id is required")
            if obj_id in objective_ids:
                errors.append(f"duplicate objective id '{obj_id}'")
            objective_ids.add(obj_id)

            if len(desc) < 8:
                errors.append(f"objective[{idx}] description is too short")
            if not isinstance(keywords, list) or len(keywords) < 2:
                errors.append(f"objective[{idx}] needs at least 2 keywords")
            if not self._is_number(weight):
                errors.append(f"objective[{idx}] weight must be numeric")
            else:
                objective_weight_sum += float(weight)

        if objectives and abs(objective_weight_sum - 1.0) > 0.02:
            errors.append(f"objective weights must sum to 1.0 (+/-0.02). current={objective_weight_sum:.4f}")

        criterion_ids: set[str] = set()
        rubric_weight_sum = 0.0
        mapped_objectives: set[str] = set()
        for idx, criterion in enumerate(rubric, start=1):
            cid = str(criterion.get("id", "")).strip()
            oid = str(criterion.get("objective_id", "")).strip()
            metric = str(criterion.get("metric", "")).strip()
            weight = criterion.get("weight", 0)
            score_bands = criterion.get("score_bands", {})

            if not cid:
                errors.append(f"rubric[{idx}] id is required")
            if cid in criterion_ids:
                errors.append(f"duplicate rubric id '{cid}'")
            criterion_ids.add(cid)

            if oid not in objective_ids:
                errors.append(f"rubric[{idx}] objective_id '{oid}' is not in objectives")
            mapped_objectives.add(oid)

            if len(metric) < 10:
                errors.append(f"rubric[{idx}] metric is too short")
            if not self._contains_measure_signal(metric):
                errors.append(
                    f"rubric[{idx}] metric should contain quantitative clues "
                    "(e.g. '3개', '%', '점', '이상')"
                )

            if not isinstance(score_bands, dict):
                errors.append(f"rubric[{idx}] score_bands must be an object with keys 1~5")
            else:
                missing = [str(k) for k in range(1, 6) if str(k) not in score_bands and k not in score_bands]
                if missing:
                    errors.append(f"rubric[{idx}] score_bands missing keys: {', '.join(missing)}")

            if not self._is_number(weight):
                errors.append(f"rubric[{idx}] weight must be numeric")
            else:
                rubric_weight_sum += float(weight)

        if rubric and abs(rubric_weight_sum - 1.0) > 0.02:
            errors.append(f"rubric weights must sum to 1.0 (+/-0.02). current={rubric_weight_sum:.4f}")

        for oid in objective_ids:
            if oid not in mapped_objectives:
                errors.append(f"objective '{oid}' has no rubric mapping")

        return errors

    @staticmethod
    def objective_to_dict(obj: LearningObjective) -> dict[str, Any]:
        return {
            "id": obj.id,
            "description": obj.description,
            "keywords": obj.keywords,
            "weight": obj.weight,
        }

    @staticmethod
    def criterion_to_dict(criterion: RubricCriterion) -> dict[str, Any]:
        return {
            "id": criterion.id,
            "objective_id": criterion.objective_id,
            "title": criterion.title,
            "metric": criterion.metric,
            "weight": criterion.weight,
            "score_bands": {str(k): v for k, v in criterion.score_bands.items()},
            "question": InterviewEngine.build_question(criterion),
        }

    @staticmethod
    def objectives_from_plan(plan: dict[str, Any]) -> list[LearningObjective]:
        objectives: list[LearningObjective] = []
        for row in plan.get("objectives", []):
            objectives.append(
                LearningObjective(
                    id=str(row["id"]),
                    description=str(row["description"]),
                    keywords=[str(x) for x in row.get("keywords", [])],
                    weight=float(row.get("weight", 0)),
                )
            )
        return objectives

    @staticmethod
    def rubric_from_plan(plan: dict[str, Any]) -> list[RubricCriterion]:
        criteria: list[RubricCriterion] = []
        for row in plan.get("rubric", []):
            raw_bands = row.get("score_bands", {})
            score_bands: dict[int, str] = {}
            for key, value in raw_bands.items():
                score_bands[int(key)] = str(value)
            criteria.append(
                RubricCriterion(
                    id=str(row["id"]),
                    objective_id=str(row["objective_id"]),
                    title=str(row.get("title", "")),
                    metric=str(row["metric"]),
                    weight=float(row.get("weight", 0)),
                    score_bands=score_bands,
                )
            )
        return criteria

    def _build_and_save_plan(
        self,
        lecture_title: str,
        lecture_digest: str,
        objectives: list[LearningObjective],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        plan_id = f"plan_{uuid4().hex[:10]}"
        criteria = self.rubric_engine.generate(objectives)
        plan = {
            "plan_id": plan_id,
            "status": "draft",
            "lecture": {
                "title": lecture_title,
                "content_digest_hint": lecture_digest,
            },
            "objectives": [self.objective_to_dict(obj) for obj in objectives],
            "rubric": [self.criterion_to_dict(criterion) for criterion in criteria],
            "created_at_utc": now,
            "updated_at_utc": now,
            "approved_by": None,
            "approved_at_utc": None,
            "approval_notes": "",
            "scoring_standard": InterviewEngine.scoring_standard(),
        }
        self.repo.save_lecture_plan(plan_id, plan)
        return plan

    @staticmethod
    def _is_number(value: Any) -> bool:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _contains_measure_signal(text: str) -> bool:
        signals = ("개", "%", "점", "회", "분", "초", "이상", "이하", ">=", "<=", "at least", "minimum")
        return any(signal in text for signal in signals)

