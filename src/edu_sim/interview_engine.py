from __future__ import annotations

from .assessment_policy import (
    AXIS_WEIGHTS_100,
    clamp,
    scale_100_to_4,
    score_to_band,
    weighted_axis_score_100,
)
from .models import CriterionEvaluation, InterviewResult, RubricCriterion, StudentSimulationResult


class InterviewEngine:
    """학생의 사후 이해도를 행동 기반 정량 척도로 평가한다."""

    def evaluate(
        self,
        student_id: str,
        simulation: StudentSimulationResult,
        criteria: list[RubricCriterion],
    ) -> InterviewResult:
        progress_map = {p.objective_id: p for p in simulation.objective_progress}
        evaluations: list[CriterionEvaluation] = []
        weighted_total_100 = 0.0

        for criterion in criteria:
            objective = progress_map[criterion.objective_id]
            axis_scores = self._build_axis_scores(pre_score=objective.pre_score, post_score=objective.post_score)
            score_100 = weighted_axis_score_100(axis_scores)
            score_5 = self._score_100_to_5(score_100)
            band = score_to_band(score_100)
            confidence = round(min(0.99, 0.55 + objective.post_score / 220.0), 2)
            comment = self._comment(score_5, criterion, band.label, axis_scores)

            evaluations.append(
                CriterionEvaluation(
                    criterion_id=criterion.id,
                    score_5_scale=score_5,
                    score_100=score_100,
                    axis_scores=axis_scores,
                    proficiency_level=band.label,
                    confidence=confidence,
                    comment=comment,
                )
            )
            weighted_total_100 += score_100 * criterion.weight

        total_score_100 = round(weighted_total_100, 2)
        total_band = score_to_band(total_score_100)
        return InterviewResult(
            student_id=student_id,
            total_score_100=total_score_100,
            proficiency_level=total_band.label,
            evaluations=evaluations,
        )

    @staticmethod
    def build_question(criterion: RubricCriterion) -> str:
        return (
            f"[{criterion.id}] {criterion.metric}를 만족하도록 설명하세요. "
            "필수: 개념 정확성, 절차, 사례 적용, 근거 제시."
        )

    @staticmethod
    def _score_100_to_5(score_100: float) -> float:
        value = 1.0 + (clamp(score_100, 0.0, 100.0) / 100.0) * 4.0
        return round(value, 2)

    @staticmethod
    def _build_axis_scores(pre_score: float, post_score: float) -> dict[str, float]:
        gain = post_score - pre_score
        base = scale_100_to_4(post_score)

        concept_accuracy = clamp(base + gain / 120.0, 0.0, 4.0)
        procedure_execution = clamp(base + gain / 160.0 - 0.1, 0.0, 4.0)
        case_application = clamp(base - 0.2 + gain / 140.0, 0.0, 4.0)
        evidence_based_explanation = clamp(base - 0.35 + gain / 180.0, 0.0, 4.0)

        return {
            "concept_accuracy": round(concept_accuracy, 2),
            "procedure_execution": round(procedure_execution, 2),
            "case_application": round(case_application, 2),
            "evidence_based_explanation": round(evidence_based_explanation, 2),
        }

    @staticmethod
    def _comment(
        score_5: float,
        criterion: RubricCriterion,
        level_label: str,
        axis_scores: dict[str, float],
    ) -> str:
        band_key = max(1, min(5, round(score_5)))
        descriptor = criterion.score_bands.get(band_key, "")
        axis_note = (
            f"축점수(0~4): 개념 {axis_scores['concept_accuracy']}, "
            f"절차 {axis_scores['procedure_execution']}, "
            f"적용 {axis_scores['case_application']}, "
            f"근거 {axis_scores['evidence_based_explanation']}"
        )
        return f"{descriptor} | 성취수준: {level_label} | {axis_note}"

    @staticmethod
    def scoring_standard() -> dict[str, object]:
        return {
            "axis_weights_100": AXIS_WEIGHTS_100,
            "proficiency_bands": [
                {"range": "0-39", "label": "입문 미도달"},
                {"range": "40-59", "label": "기초"},
                {"range": "60-79", "label": "적용"},
                {"range": "80-100", "label": "숙련"},
            ],
        }

