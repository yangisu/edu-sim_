import json
import tempfile
import unittest
from pathlib import Path

from edu_sim.models import StudentProfile
from edu_sim.orchestrator import WorkflowService
from edu_sim.repository import Repository
from edu_sim_ml.student_sim_trainer import load_student_sim_model, train_student_sim_model


class StudentSimTrainerTest(unittest.TestCase):
    def _make_train_rows(self) -> list[dict]:
        rows = []
        for i in range(20):
            k = 30 + i * 2
            iq = 35 + i * 2
            pre = 20 + 0.6 * k + 0.1 * iq
            post = min(100.0, pre + 10 + 0.05 * iq)
            rows.append(
                {
                    "knowledge_level_100": k,
                    "intelligence_level_100": iq,
                    "prior_knowledge": k / 100,
                    "focus": iq / 100,
                    "curiosity": 0.5,
                    "adaptability": 0.55,
                    "anxiety": 0.25,
                    "lecture_quality": 0.8,
                    "lecture_difficulty": 0.45,
                    "objective_keyword_count": 3,
                    "objective_text_len": 40,
                    "strengths_count": 1,
                    "weaknesses_count": 0,
                    "pre_score": pre,
                    "post_score": post,
                }
            )
        return rows

    def test_train_and_load_student_model(self) -> None:
        rows = self._make_train_rows()
        with tempfile.TemporaryDirectory() as td:
            train_file = Path(td) / "train.jsonl"
            model_file = Path(td) / "student_model.json"
            with train_file.open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            artifact = train_student_sim_model(train_file=train_file, output_model_file=model_file, l2=0.5)
            loaded = load_student_sim_model(model_file)

        self.assertEqual(artifact.num_samples, len(rows))
        self.assertEqual(loaded.num_samples, len(rows))
        self.assertEqual(len(loaded.feature_names), 13)

    def test_orchestrator_uses_trained_student_model(self) -> None:
        lecture_text = "핵심 개념 설명과 사례 적용을 연습한다."
        students = [
            StudentProfile(
                id="s1",
                name="학생1",
                level="intermediate",
                traits={"knowledge_level_100": 45, "intelligence_level_100": 52},
            ),
            StudentProfile(
                id="s2",
                name="학생2",
                level="intermediate",
                traits={"knowledge_level_100": 75, "intelligence_level_100": 82},
            ),
        ]
        rows = self._make_train_rows()

        with tempfile.TemporaryDirectory() as td:
            train_file = Path(td) / "train.jsonl"
            model_file = Path(td) / "student_model.json"
            with train_file.open("w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            train_student_sim_model(train_file=train_file, output_model_file=model_file)

            repo = Repository(db_path=":memory:")
            service = WorkflowService(repository=repo)
            report = service.run(
                lecture_title="모델 기반 시뮬레이션",
                lecture_content=lecture_text,
                students=students,
                config={"student_model_path": str(model_file)},
            )

        self.assertEqual(report["student_simulator_engine"], "trained_model")
        self.assertEqual(len(report["student_reports"]), 2)


if __name__ == "__main__":
    unittest.main()

