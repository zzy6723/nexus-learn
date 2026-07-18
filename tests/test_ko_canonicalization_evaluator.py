from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import evaluate_ko_canonicalization as evaluator
from scripts import run_deterministic_ko_canonicalization as runner


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "benchmark" / "ko_name_normalization_v0_1.json"
ALIASES_PATH = ROOT / "benchmark" / "ko_aliases_v0_1.json"
INVENTORY_PATH = (
    ROOT / "benchmark" / "ko_mentions" / "development_v0_1" / "mention_inventory.json"
)
GROUND_TRUTH_PATH = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "ko_canonicalization_development_v0_1.json"
)
SEMANTIC_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "ko_canonicalization"
    / "semantic_identity_cases.json"
)


class KOCanonicalizationEvaluatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
        cls.inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        cls.ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(SEMANTIC_FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def synthetic_ground_truth(self) -> dict[str, object]:
        return {"clusters": self.fixture["gold_clusters"]}

    def synthetic_inventory(self) -> dict[str, object]:
        return {
            "benchmark_split": "development",
            "mentions": self.fixture["mentions"],
        }

    def test_exact_fixture_exposes_false_merge_and_alias_false_splits(self) -> None:
        inventory = self.synthetic_inventory()
        prediction, _, audit = runner.build_prediction(
            inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )

        metrics, _, _, _, errors = evaluator.evaluate_partitions(
            inventory,
            self.synthetic_ground_truth(),
            prediction,
            audit,
        )

        self.assertEqual(metrics["pairwise_identity"]["false_positive_same_object"], 1)
        self.assertEqual(metrics["pairwise_identity"]["false_negative_same_object"], 2)
        self.assertEqual(metrics["error_counts"]["same_name_false_merge"], 1)
        self.assertEqual(metrics["error_counts"]["alias_false_split"], 2)
        self.assertTrue(any(item["error_type"] == "singleton_absorbed" for item in errors))

    def test_alias_fixture_repairs_alias_splits_but_not_homonym_merge(self) -> None:
        inventory = self.synthetic_inventory()
        prediction, _, audit = runner.build_prediction(
            inventory,
            method_id="alias_aware_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=self.aliases,
        )

        metrics, _, _, _, _ = evaluator.evaluate_partitions(
            inventory,
            self.synthetic_ground_truth(),
            prediction,
            audit,
        )

        self.assertEqual(metrics["pairwise_identity"]["same_object_recall"], 1.0)
        self.assertEqual(metrics["pairwise_identity"]["false_positive_same_object"], 1)
        self.assertEqual(metrics["error_counts"], {
            "same_name_false_merge": 1,
            "singleton_absorbed": 2,
        })

    def test_real_exact_method_reaches_final_metrics_without_pairwise_accuracy(self) -> None:
        prediction, assignments, audit = runner.build_prediction(
            self.inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )
        run_dir = self.temporary_root / "run"
        evaluation_dir = self.temporary_root / "evaluation"
        runner.write_run(
            output_dir=run_dir,
            inventory_path=INVENTORY_PATH,
            normalization_path=CONFIG_PATH,
            alias_path=None,
            method_id="exact_name_same_type_v0_1",
            method_commit="a" * 40,
            git_commit_at_start="a" * 40,
            git_dirty_at_start=False,
            run_id="run_01",
            prediction=prediction,
            assignments=assignments,
            audit=audit,
            overwrite=False,
        )

        return_code = evaluator.main(
            [
                "--prediction-dir",
                str(run_dir),
                "--evaluation-dir",
                str(evaluation_dir),
            ]
        )

        self.assertEqual(return_code, 0)
        metrics = json.loads((evaluation_dir / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["pairwise_identity"]["same_object_precision"], 1.0)
        self.assertEqual(metrics["pairwise_identity"]["same_object_recall"], 1.0)
        self.assertEqual(metrics["cluster_quality"]["b_cubed_f1"], 1.0)
        self.assertTrue(metrics["success_criteria"]["passed"])
        self.assertNotIn("pairwise_accuracy", metrics["pairwise_identity"])

    def test_lost_provenance_makes_evaluation_invalid(self) -> None:
        prediction, assignments, audit = runner.build_prediction(
            self.inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )
        prediction["clusters"][0]["mention_provenance"][0]["name"] = "Changed"
        run_dir = self.temporary_root / "run"
        evaluation_dir = self.temporary_root / "evaluation"
        runner.write_run(
            output_dir=run_dir,
            inventory_path=INVENTORY_PATH,
            normalization_path=CONFIG_PATH,
            alias_path=None,
            method_id="exact_name_same_type_v0_1",
            method_commit="a" * 40,
            git_commit_at_start="a" * 40,
            git_dirty_at_start=False,
            run_id="run_01",
            prediction=prediction,
            assignments=assignments,
            audit=audit,
            overwrite=False,
        )

        return_code = evaluator.main(
            [
                "--prediction-dir",
                str(run_dir),
                "--evaluation-dir",
                str(evaluation_dir),
            ]
        )

        self.assertEqual(return_code, 1)
        errors = json.loads((evaluation_dir / "errors.json").read_text(encoding="utf-8"))
        self.assertEqual(errors["evaluation_status"], "invalid")
        self.assertTrue(any("lost provenance" in item for item in errors["fatal_errors"]))
        self.assertFalse((evaluation_dir / "metrics.json").exists())


if __name__ == "__main__":
    unittest.main()
