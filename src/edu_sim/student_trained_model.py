from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import LearningObjective, StudentProfile


@dataclass(slots=True)
class StudentModelArtifact:
    feature_names: list[str]
    pre_intercept: float
    pre_weights: list[float]
    gain_intercept: float
    gain_weights: list[float]
    l2: float
    num_samples: int

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "StudentModelArtifact":
        return cls(
            feature_names=[str(x) for x in raw.get("feature_names", [])],
            pre_intercept=float(raw.get("pre_intercept", 0.0)),
            pre_weights=[float(x) for x in raw.get("pre_weights", [])],
            gain_intercept=float(raw.get("gain_intercept", 0.0)),
            gain_weights=[float(x) for x in raw.get("gain_weights", [])],
            l2=float(raw.get("l2", 1.0)),
            num_samples=int(raw.get("num_samples", 0)),
        )


@dataclass(slots=True)
class StudentModelPredictor:
    artifact: StudentModelArtifact

    @classmethod
    def from_file(cls, model_file: str) -> "StudentModelPredictor":
        raw = json.loads(Path(model_file).read_text(encoding="utf-8"))
        return cls(artifact=StudentModelArtifact.from_dict(raw))

    def predict_pre_post(
        self,
        student: StudentProfile,
        objective: LearningObjective,
        lecture_quality: float,
        lecture_difficulty: float,
    ) -> tuple[float, float]:
        x = self._features(student, objective, lecture_quality, lecture_difficulty)
        pre = self.artifact.pre_intercept + self._dot(x, self.artifact.pre_weights)
        gain = self.artifact.gain_intercept + self._dot(x, self.artifact.gain_weights)
        pre = max(0.0, min(pre, 100.0))
        gain = max(1.0, min(gain, 60.0))
        post = max(0.0, min(pre + gain, 100.0))
        return pre, post

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        return float(sum(x * y for x, y in zip(a, b, strict=False)))

    @staticmethod
    def _features(
        student: StudentProfile,
        objective: LearningObjective,
        lecture_quality: float,
        lecture_difficulty: float,
    ) -> list[float]:
        traits = student.traits
        knowledge = float(traits.get("knowledge_level_100", 50.0))
        intelligence = float(traits.get("intelligence_level_100", 50.0))
        prior = float(traits.get("prior_knowledge", 0.5))
        focus = float(traits.get("focus", 0.5))
        curiosity = float(traits.get("curiosity", 0.5))
        adaptability = float(traits.get("adaptability", 0.5))
        anxiety = float(traits.get("anxiety", 0.3))

        return [
            knowledge,
            intelligence,
            prior,
            focus,
            curiosity,
            adaptability,
            anxiety,
            float(lecture_quality),
            float(lecture_difficulty),
            float(len(objective.keywords)),
            float(len(objective.description)),
            float(len(student.strengths)),
            float(len(student.weaknesses)),
        ]
