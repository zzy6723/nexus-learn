import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_learning_explanation_benchmark import validate_benchmark
from scripts.create_learning_explanation_benchmark import create_benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LearningExplanationBenchmarkTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output_dir = Path(temporary.name) / "development_v0_1"

    def create(self):
        return create_benchmark(
            project_root=PROJECT_ROOT,
            selection_path=PROJECT_ROOT
            / "benchmark/learning_explanation/development_v0_1/selection_spec.json",
            annotation_path=PROJECT_ROOT
            / (
                "benchmark/learning_explanation/development_v0_1/"
                "annotation_scaffold_spec.json"
            ),
            ground_truth_path=PROJECT_ROOT
            / "benchmark/connection_discovery/development_v0_1/ground_truth.json",
            inventory_path=PROJECT_ROOT
            / (
                "benchmark/connection_discovery/development_v0_1/"
                "oracle_canonical_inventory.json"
            ),
            lecture_dir=PROJECT_ROOT
            / "benchmark/connection_discovery/development_v0_1/lectures",
            output_dir=self.output_dir,
            overwrite=False,
        )

    def test_creator_and_checker_pass(self):
        complete = self.create()
        self.assertEqual(complete["counts"]["instances"], 21)
        self.assertFalse(complete["model_execution_authorized"])

        counts = validate_benchmark(PROJECT_ROOT, self.output_dir)
        self.assertEqual(counts["instances"], 21)
        self.assertEqual(counts["evidence_items"], 40)
        self.assertEqual(counts["relation_support"]["FORMALIZES"], 4)
        self.assertEqual(counts["relation_support"]["CONTRASTS_WITH"], 1)

    def test_creator_refuses_overwrite(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "already exist"):
            self.create()

    def test_checker_rejects_endpoint_change(self):
        self.create()
        bundle_path = self.output_dir / "connection_instances.json"
        bundle = json.loads(bundle_path.read_text())
        bundle["instances"][0]["source_ko"]["canonical_ko_id"] = "changed"
        bundle_path.write_text(json.dumps(bundle, indent=2) + "\n")

        complete_path = self.output_dir / "benchmark_complete.json"
        complete = json.loads(complete_path.read_text())
        import hashlib

        complete["artifacts"]["connection_instances"]["sha256"] = hashlib.sha256(
            bundle_path.read_bytes()
        ).hexdigest()
        complete_path.write_text(json.dumps(complete, indent=2) + "\n")

        with self.assertRaisesRegex(ValueError, "source endpoint changed"):
            validate_benchmark(PROJECT_ROOT, self.output_dir)

    def test_checker_rejects_annotation_alignment_change(self):
        self.create()
        scaffold_path = self.output_dir / "annotation_scaffold.json"
        scaffold = json.loads(scaffold_path.read_text())
        scaffold["annotations"][0]["source_connection_pair_id"] = "changed"
        scaffold_path.write_text(json.dumps(scaffold, indent=2) + "\n")

        complete_path = self.output_dir / "benchmark_complete.json"
        complete = json.loads(complete_path.read_text())
        import hashlib

        complete["artifacts"]["annotation_scaffold"]["sha256"] = hashlib.sha256(
            scaffold_path.read_bytes()
        ).hexdigest()
        complete_path.write_text(json.dumps(complete, indent=2) + "\n")

        with self.assertRaisesRegex(ValueError, "pair alignment changed"):
            validate_benchmark(PROJECT_ROOT, self.output_dir)


if __name__ == "__main__":
    unittest.main()
