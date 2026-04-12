from __future__ import annotations

from dataclasses import dataclass


AXIS_WEIGHTS_100: dict[str, float] = {
    "concept_accuracy": 30.0,
    "procedure_execution": 30.0,
    "case_application": 25.0,
    "evidence_based_explanation": 15.0,
}


@dataclass(frozen=True, slots=True)
class ProficiencyBand:
    key: str
    label: str
    min_score: float
    max_score: float
    description: str


PROFICIENCY_BANDS: list[ProficiencyBand] = [
    ProficiencyBand(
        key="not_achieved",
        label="입문 미도달",
        min_score=0.0,
        max_score=39.99,
        description="핵심 개념을 단편적으로만 재진술하며, 과제 적용이 어렵다.",
    ),
    ProficiencyBand(
        key="basic",
        label="기초",
        min_score=40.0,
        max_score=59.99,
        description="정의와 절차를 설명할 수 있으나 적용 오류가 잦다.",
    ),
    ProficiencyBand(
        key="applied",
        label="적용",
        min_score=60.0,
        max_score=79.99,
        description="전형 문제 해결이 가능하며 설명 근거를 제시할 수 있다.",
    ),
    ProficiencyBand(
        key="proficient",
        label="숙련",
        min_score=80.0,
        max_score=100.0,
        description="비전형 사례와 한계, 예외 조건까지 설명할 수 있다.",
    ),
]


def score_to_band(score_100: float) -> ProficiencyBand:
    score = clamp(score_100, 0.0, 100.0)
    for band in PROFICIENCY_BANDS:
        if band.min_score <= score <= band.max_score:
            return band
    return PROFICIENCY_BANDS[-1]


def scale_100_to_4(score_100: float) -> float:
    score = clamp(score_100, 0.0, 100.0)
    return round((score / 100.0) * 4.0, 2)


def weighted_axis_score_100(axis_scores_0_to_4: dict[str, float]) -> float:
    total = 0.0
    for axis, weight in AXIS_WEIGHTS_100.items():
        axis_score = clamp(axis_scores_0_to_4.get(axis, 0.0), 0.0, 4.0)
        normalized = axis_score / 4.0
        total += normalized * weight
    return round(total, 2)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))

