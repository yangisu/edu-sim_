import json
import tempfile
import unittest
from pathlib import Path

from edu_sim.cli import _load_students
from edu_sim.student_profile_factory import (
    create_specific_student_row,
    create_synthetic_students,
    parse_student_row,
)
from edu_sim.student_simulator import StudentSimulator
from edu_sim.models import LearningObjective


class StudentModesTest(unittest.TestCase):
    def test_specific_student_row_and_parse(self) -> None:
        row = create_specific_student_row(
            student_id="stu_specific_01",
            name="특정학생",
            knowledge_level_100=62,
            intelligence_level_100=74,
            strengths=["개념이해"],
            weaknesses=["응용"],
        )
        profile = parse_student_row(row)
        self.assertEqual(profile.id, "stu_specific_01")
        self.assertEqual(profile.traits["student_mode"], "specific")
        self.assertIn("knowledge_level_100", profile.traits)
        self.assertIn("intelligence_level_100", profile.traits)

    def test_synthetic_students_generation(self) -> None:
        rows = create_synthetic_students(
            count=5,
            base_knowledge_level_100=50,
            base_intelligence_level_100=55,
            seed=7,
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["mode"], "synthetic")
        parsed = parse_student_row(rows[0])
        self.assertEqual(parsed.traits["student_mode"], "synthetic")

    def test_cli_load_students_with_quant_modes(self) -> None:
        rows = [
            create_specific_student_row("stu1", "A", 30, 35),
            create_specific_student_row("stu2", "B", 70, 85),
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "students.json"
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            students = _load_students(path)
        self.assertEqual(len(students), 2)
        self.assertEqual(students[0].traits["student_mode"], "specific")

    def test_quant_levels_affect_simulation(self) -> None:
        simulator = StudentSimulator()
        objective = LearningObjective(id="OBJ-1", description="핵심개념 설명", keywords=["핵심"], weight=1.0)

        low = parse_student_row(create_specific_student_row("low", "저수준", 20, 25))
        high = parse_student_row(create_specific_student_row("high", "고수준", 80, 85))

        low_result = simulator.simulate(low, [objective], lecture_quality=0.8, lecture_difficulty=0.5)
        high_result = simulator.simulate(high, [objective], lecture_quality=0.8, lecture_difficulty=0.5)
        self.assertGreater(high_result.pre_avg, low_result.pre_avg)
        self.assertGreater(high_result.post_avg, low_result.post_avg)


if __name__ == "__main__":
    unittest.main()

