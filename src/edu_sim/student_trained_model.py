from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from edu_sim_ml.student_sim_trainer import StudentSimModelArtifact, load_student_sim_model

from .models import LearningObjective, StudentProfile


@dataclass(slots=True)
class StudentModelPredictor:
    artifact: StudentSimModelArtifact

    @classmethod
    def from_file(cls, model_file: str) -> "StudentModelPredictor":
        return cls(artifact=load_student_sim_model(model_file))

    def predict_pre_post(
        self,
        student: StudentProfile,
        objective: LearningObjective,
        lecture_quality: float,
        lecture_difficulty: float,
    ) -> tuple[float, float]:
        x = self._features(student, objective, lecture_quality, lecture_difficulty)
        pre = self.artifact.pre_intercept + float(np.dot(x, np.asarray(self.artifact.pre_weights)))
        gain = self.artifact.gain_intercept + float(np.dot(x, np.asarray(self.artifact.gain_weights)))
        pre = max(0.0, min(pre, 100.0))
        gain = max(1.0, min(gain, 60.0))
        post = max(0.0, min(pre + gain, 100.0))
        return pre, post

    @staticmethod
    def _features(
        student: StudentProfile,
        objective: LearningObjective,
        lecture_quality: float,
        lecture_difficulty: float,
    ) -> np.ndarray:
        traits = student.traits
        knowledge = float(traits.get("knowledge_level_100", 50.0))
        intelligence = float(traits.get("intelligence_level_100", 50.0))
        prior = float(traits.get("prior_knowledge", 0.5))
        focus = float(traits.get("focus", 0.5))
        curiosity = float(traits.get("curiosity", 0.5))
        adaptability = float(traits.get("adaptability", 0.5))
        anxiety = float(traits.get("anxiety", 0.3))

        vec = [
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
        return np.asarray(vec, dtype=np.float64)

