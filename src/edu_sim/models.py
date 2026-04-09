from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StudentProfile:
    id: str
    name: str
    level: str
    traits: dict[str, float] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Lecture:
    id: str
    title: str
    content: str


@dataclass(slots=True)
class LearningObjective:
    id: str
    description: str
    keywords: list[str]
    weight: float


@dataclass(slots=True)
class ObjectiveProgress:
    objective_id: str
    pre_score: float
    post_score: float

    @property
    def gain(self) -> float:
        return self.post_score - self.pre_score


@dataclass(slots=True)
class StudentSimulationResult:
    student_id: str
    objective_progress: list[ObjectiveProgress]

    @property
    def pre_avg(self) -> float:
        return sum(o.pre_score for o in self.objective_progress) / len(self.objective_progress)

    @property
    def post_avg(self) -> float:
        return sum(o.post_score for o in self.objective_progress) / len(self.objective_progress)

    @property
    def gain_avg(self) -> float:
        return self.post_avg - self.pre_avg


@dataclass(slots=True)
class RubricCriterion:
    id: str
    objective_id: str
    title: str
    metric: str
    weight: float
    score_bands: dict[int, str]


@dataclass(slots=True)
class CriterionEvaluation:
    criterion_id: str
    score_5_scale: float
    confidence: float
    comment: str


@dataclass(slots=True)
class InterviewResult:
    student_id: str
    total_score_100: float
    evaluations: list[CriterionEvaluation]


JSONLike = dict[str, Any] | list[Any] | str | int | float | bool | None

