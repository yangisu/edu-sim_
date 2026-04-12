import json
import unittest
from pathlib import Path

from edu_sim.cli import _load_students
from edu_sim.orchestrator import WorkflowService
from edu_sim.plan_service import InstructorPlanService, PlanValidationError
from edu_sim.repository import Repository


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.students = _load_students(root / "sample_data" / "students.json")
        self.lecture_package = json.loads((root / "sample_data" / "lecture_package.json").read_text(encoding="utf-8"))

    def test_workflow_end_to_end_auto(self) -> None:
        lecture_text = (
            "전처리와 시각화의 차이를 설명하고, 상관관계와 인과관계를 구분하는 방법을 다룬다. "
            "결측치 처리 기준과 이상치 판단 절차를 실습한다."
        )
        repo = Repository(db_path=":memory:")
        service = WorkflowService(repository=repo)
        report = service.run(
            lecture_title="테스트 강의",
            lecture_content=lecture_text,
            students=self.students,
            config={"lecture_quality": 0.85, "lecture_difficulty": 0.4, "max_objectives": 4},
        )

        self.assertTrue(report["run_id"].startswith("run_"))
        self.assertEqual(report["lecture"]["input_format"], "plain_text")
        self.assertGreater(report["lecture"]["objective_count"], 0)
        self.assertEqual(len(report["student_reports"]), len(self.students))
        self.assertIn("scoring_standard", report)
        self.assertIsNone(report["approved_plan_id"])

        first_student = report["student_reports"][0]
        self.assertIn("pre_proficiency", first_student)
        self.assertIn("interview_proficiency", first_student)
        self.assertGreaterEqual(first_student["interview_score"], 0)
        self.assertLessEqual(first_student["interview_score"], 100)

    def test_workflow_with_lecture_package(self) -> None:
        repo = Repository(db_path=":memory:")
        service = WorkflowService(repository=repo)
        report = service.run(
            lecture_title="패키지 강의",
            lecture_content=self.lecture_package["transcript"],
            students=self.students,
            config={"lecture_quality": 0.8, "lecture_difficulty": 0.45, "max_objectives": 5},
            lecture_package=self.lecture_package,
        )

        self.assertEqual(report["lecture"]["input_format"], "lecture_package")
        self.assertTrue(report["lecture"]["metadata"])
        self.assertGreater(report["lecture"]["objective_count"], 0)

    def test_workflow_with_approved_plan(self) -> None:
        lecture_text = (
            "문제 정의를 먼저 하고 데이터 수집과 정제를 수행한다. "
            "시각화로 분포를 확인하고, 해석 시 상관과 인과를 분리한다."
        )
        repo = Repository(db_path=":memory:")
        planner = InstructorPlanService(repository=repo)
        service = WorkflowService(repository=repo)

        draft = planner.draft_plan(lecture_title="승인 플랜 테스트", lecture_content=lecture_text, max_objectives=3)
        approved = planner.approve_plan(plan=draft, approved_by="qa_instructor", approval_notes="test approval")

        report = service.run(
            lecture_title="승인 플랜 테스트",
            lecture_content=lecture_text,
            students=self.students,
            config={"approved_plan_id": approved["plan_id"], "lecture_quality": 0.8, "lecture_difficulty": 0.4},
        )

        self.assertEqual(report["approved_plan_id"], approved["plan_id"])
        self.assertEqual(report["lecture"]["objective_count"], len(approved["objectives"]))

    def test_invalid_plan_rejected(self) -> None:
        lecture_text = "핵심 개념을 설명하고 사례 적용을 평가한다."
        repo = Repository(db_path=":memory:")
        planner = InstructorPlanService(repository=repo)
        draft = planner.draft_plan(lecture_title="검증 실패 테스트", lecture_content=lecture_text, max_objectives=2)

        draft["rubric"][0]["score_bands"] = {"1": "bad"}
        with self.assertRaises(PlanValidationError):
            planner.approve_plan(plan=draft, approved_by="qa_instructor")


if __name__ == "__main__":
    unittest.main()

