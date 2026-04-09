from __future__ import annotations

from .models import LearningObjective, RubricCriterion


class RubricEngine:
    """강의 목표를 기반으로 모호하지 않은 정량 평가 기준을 생성한다."""

    def generate(self, objectives: list[LearningObjective]) -> list[RubricCriterion]:
        criteria: list[RubricCriterion] = []
        for i, objective in enumerate(objectives, start=1):
            metric = self._metric_from_keywords(objective.keywords)
            criteria.append(
                RubricCriterion(
                    id=f"RC-{i}",
                    objective_id=objective.id,
                    title=f"{objective.description[:48]}",
                    metric=metric,
                    weight=objective.weight,
                    score_bands={
                        1: "핵심 요소 1개 미만, 오개념 다수",
                        2: "핵심 요소 1개 언급, 설명 불완전",
                        3: "핵심 요소 2개 설명, 기본 적용 가능",
                        4: "핵심 요소 3개 설명, 사례 적용 정확",
                        5: "핵심 요소 3개 이상 + 예외/한계까지 설명",
                    },
                )
            )
        return criteria

    @staticmethod
    def _metric_from_keywords(keywords: list[str]) -> str:
        joined = ", ".join(keywords[:3]) if keywords else "핵심 개념"
        return f"답변 중 '{joined}' 관련 핵심 요소를 최소 3개 정확히 제시"

