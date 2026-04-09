import unittest
from pathlib import Path

from edu_sim.cli import _load_students
from edu_sim.orchestrator import WorkflowService
from edu_sim.repository import Repository


class WorkflowTest(unittest.TestCase):
    def test_workflow_end_to_end(self) -> None:
        lecture_text = (
            "전처리와 시각화의 차이를 설명하고, 상관관계와 인과관계를 구분하는 방법을 다룬다. "
            "결측치 처리 기준과 이상치 판단 절차를 실습한다."
        )
        students_file = Path(__file__).resolve().parents[1] / "sample_data" / "students.json"
        students = _load_students(students_file)

        repo = Repository(db_path=":memory:")
        service = WorkflowService(repository=repo)
        report = service.run(
            lecture_title="테스트 강의",
            lecture_content=lecture_text,
            students=students,
            config={"lecture_quality": 0.85, "lecture_difficulty": 0.4, "max_objectives": 4},
        )

        self.assertTrue(report["run_id"].startswith("run_"))
        self.assertGreater(report["lecture"]["objective_count"], 0)
        self.assertEqual(len(report["student_reports"]), len(students))
        self.assertTrue(report["group_summary"])

        for student in report["student_reports"]:
            self.assertGreaterEqual(student["post_avg"], student["pre_avg"])
            self.assertGreaterEqual(student["interview_score"], 0)
            self.assertLessEqual(student["interview_score"], 100)


if __name__ == "__main__":
    unittest.main()
