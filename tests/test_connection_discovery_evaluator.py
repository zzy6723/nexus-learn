from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import evaluate_connection_discovery as evaluator
from scripts.evaluate_connection_discovery import evaluate, validate_prediction_bundle
from scripts.run_connection_discovery import (
    DEFAULT_CATALOGS, DEFAULT_FREEZE_MANIFEST, DEFAULT_SELECTION, ROOT,
    binding, load_json,
)


GROUND_TRUTH = ROOT / "benchmark/connection_discovery/development_v0_1/ground_truth.json"
SUCCESS = ROOT / "benchmark/connection_discovery_success_criteria_v0_1.json"


class ConnectionDiscoveryEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selection = load_json(DEFAULT_SELECTION)
        cls.ground_truth = load_json(GROUND_TRUTH)
        cls.catalogs = load_json(DEFAULT_CATALOGS)
        cls.success = load_json(SUCCESS)
        cls.truth_map = {item["canonical_pair_id"]: item for item in cls.ground_truth["pairs"]}
        cls.catalog_map = {item["canonical_pair_id"]: item for item in cls.catalogs["catalogs"]}

    def perfect_predictions(self):
        results = []
        for pair in self.selection["selected_pairs"]:
            pair_id = pair["canonical_pair_id"]
            truth = self.truth_map[pair_id]
            if truth["primary_scoring_eligible"] and truth["category"] == "IN_SCHEMA_CONNECTION":
                edge = truth["gold_edge"]
                result = {
                    "canonical_pair_id": pair_id,
                    "source_canonical_ko_id": edge["source_canonical_ko_id"],
                    "target_canonical_ko_id": edge["target_canonical_ko_id"],
                    "relation_type": edge["relation_type"],
                    "evidence_ids": [item["evidence_id"] for item in truth["evidence"]],
                    "rationale": "Frozen perfect fixture.",
                }
            else:
                result = {
                    "canonical_pair_id": pair_id,
                    "source_canonical_ko_id": pair["ko_a"]["canonical_ko_id"],
                    "target_canonical_ko_id": pair["ko_b"]["canonical_ko_id"],
                    "relation_type": "NO_RELATION",
                    "evidence_ids": [],
                    "rationale": "No primary in-schema edge.",
                }
            results.append(result)
        return {"artifact_type": "canonical_connection_predictions", "version": "v0.1", "results": results}

    def score(self, predictions, adjudication=None):
        return evaluate(
            predictions=predictions, selected_pairs=self.selection["selected_pairs"],
            ground_truth=self.ground_truth, catalogs=self.catalogs,
            success_criteria=self.success, adjudication=adjudication,
        )

    def test_perfect_fixture_is_final_and_passes(self) -> None:
        predictions = self.perfect_predictions()
        fatal = validate_prediction_bundle(predictions, selected_pairs=self.selection["selected_pairs"], catalog_map=self.catalog_map)
        self.assertEqual(fatal, [])
        result = self.score(predictions)
        metrics = result["metrics"]
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["gate_assessment"]["outcome"], "passed")
        self.assertEqual(metrics["conditional_metrics"]["positive_typed_edge_recall"], 1.0)
        self.assertEqual(metrics["conditional_metrics"]["no_relation_accuracy"], 1.0)
        self.assertEqual(metrics["counts"]["candidate_misses"], 0)

    def test_all_no_relation_fails_anti_majority_gates(self) -> None:
        predictions = self.perfect_predictions()
        for result in predictions["results"]:
            result["relation_type"] = "NO_RELATION"
            result["evidence_ids"] = []
        scored = self.score(predictions)["metrics"]
        self.assertEqual(scored["conditional_metrics"]["positive_typed_edge_recall"], 0.0)
        self.assertEqual(scored["conditional_metrics"]["no_relation_accuracy"], 1.0)
        self.assertEqual(scored["gate_assessment"]["outcome"], "failed")

    def test_wrong_direction_is_not_wrong_type(self) -> None:
        predictions = self.perfect_predictions()
        target = next(item for item in predictions["results"] if item["relation_type"] == "REQUIRES")
        target["source_canonical_ko_id"], target["target_canonical_ko_id"] = target["target_canonical_ko_id"], target["source_canonical_ko_id"]
        scored = self.score(predictions)
        self.assertEqual(scored["metrics"]["counts"]["wrong_direction"], 1)
        self.assertEqual(scored["metrics"]["counts"]["wrong_relation_type"], 0)

    def test_non_gold_evidence_requires_snapshot_bound_adjudication(self) -> None:
        predictions = self.perfect_predictions()
        target = next(item for item in predictions["results"] if item["relation_type"] != "NO_RELATION")
        pair_id = target["canonical_pair_id"]
        gold_ids = set(target["evidence_ids"])
        alternative = next(item["evidence_id"] for item in self.catalog_map[pair_id]["evidence_items"] if item["evidence_id"] not in gold_ids)
        target["evidence_ids"] = [alternative]
        draft = self.score(predictions)
        self.assertEqual(draft["metrics"]["evaluation_status"], "draft_pending_adjudication")
        pending = draft["adjudication_pending"]
        self.assertEqual(pending["pending_count"], 1)
        adjudication = {
            "artifact_type": "canonical_connection_evidence_adjudication",
            "version": "v0.1",
            "prediction_content_sha256": pending["prediction_content_sha256"],
            "pending_snapshot_sha256": pending["pending_snapshot_sha256"],
            "decisions": [{"canonical_pair_id": pair_id, "decision": "not_supported", "rationale": "The selected block does not establish the predicted edge."}],
        }
        final = self.score(predictions, adjudication)
        self.assertEqual(final["metrics"]["evaluation_status"], "final")
        self.assertEqual(final["metrics"]["counts"]["evidence_not_supported"], 1)

    def test_endpoint_and_unknown_evidence_are_fatal(self) -> None:
        predictions = self.perfect_predictions()
        changed = copy.deepcopy(predictions)
        changed["results"][0]["target_canonical_ko_id"] = "conn_dev_ko_999"
        errors = validate_prediction_bundle(changed, selected_pairs=self.selection["selected_pairs"], catalog_map=self.catalog_map)
        self.assertTrue(any("endpoints changed" in item for item in errors))
        unknown = copy.deepcopy(predictions)
        unknown["results"][0]["evidence_ids"] = ["evidence_999"]
        errors = validate_prediction_bundle(unknown, selected_pairs=self.selection["selected_pairs"], catalog_map=self.catalog_map)
        self.assertTrue(any("unknown Evidence" in item for item in errors))

    def write_fake_run(self, root: Path, predictions: dict) -> Path:
        run_dir = root / "run"
        prediction_path = run_dir / "output/canonical_connection_predictions.json"
        prediction_path.parent.mkdir(parents=True)
        prediction_path.write_text(json.dumps(predictions, indent=2) + "\n")
        metadata = {
            "run_status": "completed",
            "execution_scope": "full_selected_candidate_set",
            "git_dirty_at_start": False,
            "git_commit_at_start": "a" * 40,
            "method_commit": "a" * 40,
            "candidate_count": 125,
            "completed_candidate_count": 125,
            "prediction": binding(prediction_path),
            "inputs": {
                "candidate_selection": binding(DEFAULT_SELECTION),
                "evidence_catalogs": binding(DEFAULT_CATALOGS),
                "freeze_manifest": binding(DEFAULT_FREEZE_MANIFEST),
            },
        }
        metadata_path = run_dir / "metadata/run_metadata.json"
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        return run_dir

    def test_cli_final_and_invalid_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = self.write_fake_run(root, self.perfect_predictions())
            evaluation_dir = root / "evaluation"
            code = evaluator.main
            with mock.patch(
                "sys.argv",
                [
                    "evaluate_connection_discovery.py",
                    "--run-dir", str(run_dir),
                    "--evaluation-dir", str(evaluation_dir),
                ],
            ):
                return_code = code()
            self.assertEqual(return_code, 0)
            marker = json.loads((evaluation_dir / "evaluation_complete.json").read_text())
            self.assertEqual(marker["evaluation_status"], "final")
            with mock.patch(
                "sys.argv",
                [
                    "evaluate_connection_discovery.py",
                    "--run-dir", str(run_dir),
                    "--evaluation-dir", str(evaluation_dir),
                ],
            ):
                self.assertEqual(code(), 1)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = self.perfect_predictions()
            invalid["results"][0]["target_canonical_ko_id"] = "conn_dev_ko_999"
            run_dir = self.write_fake_run(root, invalid)
            evaluation_dir = root / "evaluation"
            with mock.patch(
                "sys.argv",
                [
                    "evaluate_connection_discovery.py",
                    "--run-dir", str(run_dir),
                    "--evaluation-dir", str(evaluation_dir),
                ],
            ):
                self.assertEqual(code(), 1)
            marker = json.loads((evaluation_dir / "evaluation_complete.json").read_text())
            self.assertEqual(marker["evaluation_status"], "invalid")
            self.assertTrue((evaluation_dir / "errors.json").is_file())
            self.assertFalse((evaluation_dir / "metrics.json").exists())


if __name__ == "__main__":
    unittest.main()
