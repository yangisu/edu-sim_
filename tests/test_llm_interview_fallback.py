import unittest

from edu_sim.models import StudentProfile
from edu_sim.orchestrator import WorkflowService
from edu_sim.repository import Repository


class LlmInterviewFallbackTest(unittest.TestCase):
    def test_llm_mode_fallbacks_to_rule_when_key_missing(self) -> None:
        service = WorkflowService(repository=Repository(db_path=":memory:"))
        students = [
            StudentProfile(
                id="stu_001",
                name="테스트학생",
                level="intermediate",
                traits={"knowledge_level_100": 60, "intelligence_level_100": 62},
            )
        ]
        report = service.run(
            lecture_title="LLM fallback test",
            lecture_content="핵심 개념을 설명하고 사례에 적용한다.",
            students=students,
            config={"interview_mode": "llm", "llm_model": "gpt-4o-mini"},
        )
        self.assertEqual(report["interview_engine_used"], "rule")
        self.assertIn("fallback", report["interview_engine_note"])


if __name__ == "__main__":
    unittest.main()

