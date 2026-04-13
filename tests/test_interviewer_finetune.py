import json
import tempfile
import unittest
from pathlib import Path

from edu_sim_ml.interviewer_finetune import build_interviewer_finetune_dataset


class InterviewerFineTuneDatasetTest(unittest.TestCase):
    def test_build_interviewer_finetune_dataset(self) -> None:
        store = {
            "students": {
                "stu_1": {
                    "id": "stu_1",
                    "traits": {"knowledge_level_100": 55.0, "intelligence_level_100": 62.0},
                }
            },
            "rubrics": {
                "run_1": {
                    "criteria": [
                        {
                            "id": "RC-1",
                            "objective_id": "OBJ-1",
                            "title": "개념 이해",
                            "metric": "핵심 개념 설명",
                            "weight": 1.0,
                        }
                    ]
                }
            },
            "interviews": {
                "run_1:stu_1": {
                    "run_id": "run_1",
                    "student_id": "stu_1",
                    "detail": {
                        "evaluations": [
                            {
                                "criterion_id": "RC-1",
                                "axis_scores": {
                                    "concept_accuracy": 2.5,
                                    "procedure_execution": 2.0,
                                    "case_application": 2.2,
                                    "evidence_based_explanation": 1.8,
                                },
                                "confidence": 0.7,
                                "comment": "기본 개념은 설명 가능하나 적용 근거가 약함",
                            }
                        ]
                    },
                }
            },
            "reports": {
                "run_1": {
                    "student_reports": [
                        {
                            "student_id": "stu_1",
                            "objective_breakdown": [
                                {"objective_id": "OBJ-1", "pre": 40, "post": 66, "gain": 26}
                            ],
                        }
                    ]
                }
            },
        }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_file = root / "store.json"
            train_file = root / "train.jsonl"
            valid_file = root / "valid.jsonl"
            store_file.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

            train_count, valid_count = build_interviewer_finetune_dataset(
                store_file=store_file,
                train_output_file=train_file,
                valid_output_file=valid_file,
                valid_ratio=0.5,
                seed=1,
            )

            self.assertEqual(train_count + valid_count, 1)
            self.assertTrue(train_file.exists())
            self.assertTrue(valid_file.exists())

            lines = [x for x in train_file.read_text(encoding="utf-8").splitlines() if x.strip()]
            if not lines:
                lines = [x for x in valid_file.read_text(encoding="utf-8").splitlines() if x.strip()]
            payload = json.loads(lines[0])
            self.assertIn("messages", payload)
            self.assertEqual(len(payload["messages"]), 3)
            self.assertEqual(payload["messages"][0]["role"], "system")


if __name__ == "__main__":
    unittest.main()
