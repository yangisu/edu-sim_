from __future__ import annotations

import hashlib
import random

from .models import LearningObjective, ObjectiveProgress, StudentProfile, StudentSimulationResult
from .student_profile_factory import clamp01
from .student_trained_model import StudentModelPredictor


class StudentSimulator:
    """학생 수준/특성 기반 시뮬레이터. 학습모델이 있으면 해당 예측을 우선 사용한다."""

    _LEVEL_BASELINE = {
        "beginner": 42.0,
        "intermediate": 58.0,
        "advanced": 73.0,
    }

    def simulate(
        self,
        student: StudentProfile,
        objectives: list[LearningObjective],
        lecture_quality: float = 0.8,
        lecture_difficulty: float = 0.5,
        model_predictor: StudentModelPredictor | None = None,
    ) -> StudentSimulationResult:
        baseline, focus, curiosity, prior, anxiety, adaptability, iq_boost = self._resolve_student_state(student)

        progress: list[ObjectiveProgress] = []
        for objective in objectives:
            rng = random.Random(self._seed(student.id, objective.id))

            if model_predictor is None:
                pre = baseline
                pre += (prior - 0.5) * 25.0
                pre += (focus - 0.5) * 8.0
                pre -= lecture_difficulty * 8.0
                pre += rng.uniform(-4.0, 4.0)
                pre = self._clamp(pre, 0.0, 100.0)

                objective_fit = self._objective_fit(student, objective)
                gain = 8.0
                gain += lecture_quality * 18.0
                gain += (focus - 0.5) * 10.0
                gain += (curiosity - 0.5) * 8.0
                gain += (adaptability - 0.5) * 10.0
                gain -= anxiety * 7.0
                gain += iq_boost
                gain += objective_fit
                gain += rng.uniform(-2.5, 2.5)
                gain = max(gain, 2.0)

                post = self._clamp(pre + gain, 0.0, 100.0)
            else:
                pre, post = model_predictor.predict_pre_post(
                    student=student,
                    objective=objective,
                    lecture_quality=lecture_quality,
                    lecture_difficulty=lecture_difficulty,
                )
                pre = self._clamp(pre + rng.uniform(-1.5, 1.5), 0.0, 100.0)
                post = self._clamp(post + rng.uniform(-1.5, 1.5), 0.0, 100.0)
                if post < pre:
                    post = pre

            progress.append(
                ObjectiveProgress(
                    objective_id=objective.id,
                    pre_score=round(pre, 2),
                    post_score=round(post, 2),
                )
            )

        return StudentSimulationResult(student_id=student.id, objective_progress=progress)

    def _resolve_student_state(
        self,
        student: StudentProfile,
    ) -> tuple[float, float, float, float, float, float, float]:
        baseline = self._LEVEL_BASELINE.get(student.level, 55.0)

        focus = float(student.traits.get("focus", 0.5))
        curiosity = float(student.traits.get("curiosity", 0.5))
        prior = float(student.traits.get("prior_knowledge", 0.5))
        anxiety = float(student.traits.get("anxiety", 0.3))
        adaptability = float(student.traits.get("adaptability", 0.5))
        iq_boost = 0.0

        if "knowledge_level_100" in student.traits:
            knowledge = float(student.traits["knowledge_level_100"])
            knowledge = max(0.0, min(knowledge, 100.0))
            baseline = 18.0 + 0.72 * knowledge
            prior = clamp01(knowledge / 100.0)

        if "intelligence_level_100" in student.traits:
            intelligence = float(student.traits["intelligence_level_100"])
            intelligence = max(0.0, min(intelligence, 100.0))
            iq01 = intelligence / 100.0
            focus = clamp01(max(focus, 0.2 + 0.65 * iq01))
            curiosity = clamp01(max(curiosity, 0.25 + 0.55 * iq01))
            adaptability = clamp01(max(adaptability, 0.2 + 0.6 * iq01))
            anxiety = clamp01(min(anxiety, 0.75 - 0.6 * iq01))
            iq_boost = (intelligence - 50.0) / 20.0

        return baseline, focus, curiosity, prior, anxiety, adaptability, iq_boost

    @staticmethod
    def _seed(student_id: str, objective_id: str) -> int:
        digest = hashlib.sha256(f"{student_id}:{objective_id}".encode("utf-8")).hexdigest()
        return int(digest[:16], 16)

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min(value, max_value), min_value)

    @staticmethod
    def _objective_fit(student: StudentProfile, objective: LearningObjective) -> float:
        text = objective.description
        strength_bonus = 0.0
        weakness_penalty = 0.0

        for strength in student.strengths:
            if strength and strength in text:
                strength_bonus += 2.5

        for weakness in student.weaknesses:
            if weakness and weakness in text:
                weakness_penalty += 2.0

        return strength_bonus - weakness_penalty

