from __future__ import annotations

from .models import LearningObjective, RubricCriterion


class RubricEngine:
    """학습 목표를 행동 기반 정량 루브릭으로 변환한다."""

    def generate(self, objectives: list[LearningObjective]) -> list[RubricCriterion]:
        criteria: list[RubricCriterion] = []
        for i, objective in enumerate(objectives, start=1):
            metric = self._metric_from_keywords(objective.keywords)
            criteria.append(
                RubricCriterion(
                    id=f"RC-{i}",
                    objective_id=objective.id,
                    title=objective.description[:64],
                    metric=metric,
                    weight=objective.weight,
                    score_bands={
                        1: "핵심 요소 1개 미만 제시, 오류 다수",
                        2: "핵심 요소 1개 제시, 절차 누락",
                        3: "핵심 요소 2개 이상 제시, 기본 적용 가능",
                        4: "핵심 요소 3개 이상 제시, 사례 적용 정확",
                        5: "핵심 요소 3개 이상 + 예외/한계까지 설명",
                    },
                )
            )
        return criteria

    @staticmethod
    def _metric_from_keywords(keywords: list[str]) -> str:
        target = ", ".join(keywords[:3]) if keywords else "핵심 개념"
        return f"답변에서 '{target}' 관련 핵심 요소를 최소 3개 이상 정확히 제시"

