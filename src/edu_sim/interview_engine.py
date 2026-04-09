from __future__ import annotations

from .models import CriterionEvaluation, InterviewResult, RubricCriterion, StudentSimulationResult


class InterviewEngine:
    """학생의 사후 이해도를 기반으로 AI 면접 결과를 수치화한다."""

    def evaluate(
        self,
        student_id: str,
        simulation: StudentSimulationResult,
        criteria: list[RubricCriterion],
    ) -> InterviewResult:
        progress_map = {p.objective_id: p for p in simulation.objective_progress}
        evaluations: list[CriterionEvaluation] = []
        weighted_total = 0.0

        for criterion in criteria:
            objective = progress_map[criterion.objective_id]
            raw_5 = self._score_to_5_scale(objective.post_score)
            confidence = min(0.99, 0.5 + objective.post_score / 200.0)
            comment = self._comment(raw_5, criterion)
            evaluations.append(
                CriterionEvaluation(
                    criterion_id=criterion.id,
                    score_5_scale=raw_5,
                    confidence=round(confidence, 2),
                    comment=comment,
                )
            )
            weighted_total += raw_5 * criterion.weight

        total_score_100 = round((weighted_total / 5.0) * 100.0, 2)
        return InterviewResult(
            student_id=student_id,
            total_score_100=total_score_100,
            evaluations=evaluations,
        )

    @staticmethod
    def build_question(criterion: RubricCriterion) -> str:
        return f"[{criterion.id}] {criterion.metric}를 만족하도록 해당 개념을 실제 사례와 함께 설명하세요."

    @staticmethod
    def _score_to_5_scale(score_100: float) -> float:
        value = 1.0 + (score_100 / 100.0) * 4.0
        return round(max(1.0, min(value, 5.0)), 2)

    @staticmethod
    def _comment(score_5: float, criterion: RubricCriterion) -> str:
        band = round(score_5)
        band = max(1, min(band, 5))
        descriptor = criterion.score_bands.get(band, "")
        return f"{descriptor} (기준: {criterion.metric})"

