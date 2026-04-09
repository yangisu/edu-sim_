from __future__ import annotations

import hashlib
import random

from .models import LearningObjective, ObjectiveProgress, StudentProfile, StudentSimulationResult


class StudentSimulator:
    """학생 수준/특성에 따라 사전-사후 이해도를 시뮬레이션한다."""

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
    ) -> StudentSimulationResult:
        baseline = self._LEVEL_BASELINE.get(student.level, 55.0)
        focus = float(student.traits.get("focus", 0.5))
        curiosity = float(student.traits.get("curiosity", 0.5))
        prior = float(student.traits.get("prior_knowledge", 0.5))
        anxiety = float(student.traits.get("anxiety", 0.3))
        adaptability = float(student.traits.get("adaptability", 0.5))

        progress: list[ObjectiveProgress] = []
        for objective in objectives:
            rng = random.Random(self._seed(student.id, objective.id))

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
            gain += objective_fit
            gain += rng.uniform(-2.5, 2.5)
            gain = max(gain, 2.0)

            post = self._clamp(pre + gain, 0.0, 100.0)
            progress.append(
                ObjectiveProgress(
                    objective_id=objective.id,
                    pre_score=round(pre, 2),
                    post_score=round(post, 2),
                )
            )

        return StudentSimulationResult(student_id=student.id, objective_progress=progress)

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

