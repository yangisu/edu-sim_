import json
import tempfile
import unittest
from pathlib import Path

from edu_sim_ml.aihub_loader import load_samples, save_jsonl, split_samples
from edu_sim_ml.lecture_package_builder import build_lecture_packages, save_lecture_packages


class AihubMlPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset_root = Path("D:/KIT/edu_sim/Sample/Sample")
        if not self.dataset_root.exists():
            self.skipTest("sample dataset path does not exist")

    def test_load_samples_and_manifest(self) -> None:
        samples = load_samples(self.dataset_root)
        self.assertGreater(len(samples), 0)
        self.assertTrue(samples[0].audio_path.endswith(".wav"))
        self.assertTrue(samples[0].label_path.endswith(".json"))
        self.assertTrue(isinstance(samples[0].transcript, str))

        rows = split_samples(samples, valid_ratio=0.1)
        self.assertEqual(len(rows), len(samples))
        splits = {r["split"] for r in rows}
        self.assertIn("train", splits)
        self.assertIn("validation", splits)

        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "manifest.jsonl"
            save_jsonl(rows, manifest)
            content = manifest.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(content), len(rows))
            first = json.loads(content[0])
            self.assertIn("audio_path", first)
            self.assertIn("transcript", first)

    def test_build_lecture_packages(self) -> None:
        samples = load_samples(self.dataset_root)
        packages = build_lecture_packages(samples)
        self.assertGreater(len(packages), 0)
        pkg = packages[0]
        self.assertIn("transcript", pkg)
        self.assertIn("metadata", pkg)
        self.assertIn("segments", pkg)

        with tempfile.TemporaryDirectory() as td:
            paths = save_lecture_packages(packages, td)
            self.assertGreater(len(paths), 0)
            loaded = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertIn("lecture_id", loaded)
            self.assertIn("transcript", loaded)


if __name__ == "__main__":
    unittest.main()

