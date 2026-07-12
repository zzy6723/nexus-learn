from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "scripts" / "evaluate_relation_extraction.py"
FIXTURES = ROOT / "tests" / "fixtures" / "relation_extraction"
SYNTHETIC_GROUND_TRUTH = FIXTURES / "synthetic_ground_truth.json"
SYMMETRIC_GROUND_TRUTH = FIXTURES / "symmetric_ground_truth.json"


class RelationEvaluatorTest(unittest.TestCase):
    def evaluate_fixture(
        self,
        prediction_name: str,
        *,
        ground_truth: Path = SYNTHETIC_GROUND_TRUTH,
        adjudication: Path | None = None,
        expected_returncode: int = 0,
        evaluation_dir: Path | None = None,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        if evaluation_dir is None:
            temporary_directory = tempfile.TemporaryDirectory()
            self.addCleanup(temporary_directory.cleanup)
            evaluation_dir = Path(temporary_directory.name) / "evaluation"

        command = [
            sys.executable,
            str(EVALUATOR),
            "--ground-truth",
            str(ground_truth),
            "--predictions",
            str(FIXTURES / prediction_name),
            "--evaluation-dir",
            str(evaluation_dir),
        ]
        if adjudication is not None:
            command.extend(["--adjudication", str(adjudication)])

        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            expected_returncode,
            msg=(
                f"Unexpected evaluator exit code.\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            ),
        )

        metrics = json.loads(
            (evaluation_dir / "metrics.json").read_text(encoding="utf-8")
        )
        errors = json.loads(
            (evaluation_dir / "errors.json").read_text(encoding="utf-8")
        )
        matches = json.loads(
            (evaluation_dir / "matches.json").read_text(encoding="utf-8")
        )
        adjudication_pending = json.loads(
            (evaluation_dir / "adjudication_pending.json").read_text(
                encoding="utf-8"
            )
        )
        return metrics, errors, matches, adjudication_pending

    @staticmethod
    def error_types(errors: list[dict[str, Any]]) -> list[str]:
        return [error["error_type"] for error in errors]

    def test_perfect_fixture(self) -> None:
        metrics, errors, _, pending = self.evaluate_fixture(
            "perfect_predictions.json"
        )

        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["strict_edge_accuracy"], 1.0)
        self.assertEqual(metrics["relation_type_accuracy_ignoring_direction"], 1.0)
        self.assertEqual(metrics["endpoint_direction_accuracy"], 1.0)
        self.assertEqual(metrics["direction_accuracy_when_type_correct"], 1.0)
        self.assertEqual(metrics["direction_accuracy"], 1.0)
        self.assertEqual(metrics["no_relation_accuracy"], 1.0)
        self.assertEqual(errors, [])
        self.assertEqual(pending, [])

    def test_wrong_direction_fixture(self) -> None:
        metrics, errors, _, pending = self.evaluate_fixture(
            "wrong_direction_predictions.json"
        )

        self.assertLess(metrics["strict_edge_accuracy"], 1.0)
        self.assertEqual(metrics["strict_edge_accuracy"], 0.75)
        self.assertEqual(metrics["relation_type_accuracy_ignoring_direction"], 1.0)
        self.assertEqual(metrics["endpoint_direction_accuracy"], 0.5)
        self.assertEqual(metrics["direction_accuracy_when_type_correct"], 0.5)
        self.assertEqual(self.error_types(errors), ["wrong_direction"])
        self.assertEqual(pending, [])

    def test_overconnection_fixture(self) -> None:
        metrics, errors, _, pending = self.evaluate_fixture(
            "overconnection_predictions.json"
        )

        error_types = self.error_types(errors)
        self.assertEqual(metrics["no_relation_accuracy"], 0.0)
        self.assertEqual(metrics["positive_relation_accuracy"], 1.0)
        self.assertEqual(metrics["related_to_prediction_rate"], 0.5)
        self.assertEqual(error_types.count("false_positive_relation"), 2)
        self.assertEqual(error_types.count("overused_related_to"), 2)
        self.assertEqual(pending, [])

    def test_all_related_to_fixture(self) -> None:
        metrics, _, _, pending = self.evaluate_fixture(
            "all_related_to_predictions.json"
        )

        self.assertEqual(metrics["strict_edge_accuracy"], 0.0)
        self.assertEqual(metrics["related_to_prediction_rate"], 1.0)
        self.assertEqual(metrics["no_relation_accuracy"], 0.0)
        self.assertEqual(metrics["endpoint_direction_accuracy"], 1.0)
        self.assertIsNone(metrics["direction_accuracy_when_type_correct"])
        self.assertEqual(metrics["direction_when_type_correct_scored_count"], 0)
        self.assertEqual(pending, [])

    def test_quality_errors_are_nonfatal(self) -> None:
        metrics, errors, _, pending = self.evaluate_fixture(
            "quality_errors_predictions.json"
        )

        error_types = self.error_types(errors)
        self.assertEqual(
            metrics["evaluation_status"], "draft_pending_adjudication"
        )
        self.assertIn("missing_evidence", error_types)
        self.assertIn("invalid_evidence_span", error_types)
        self.assertIn("evidence_lecture_outside_candidate", error_types)
        self.assertIn("missing_rationale", error_types)
        self.assertEqual(metrics["exact_evidence_span_count"], 4)
        self.assertEqual(metrics["evidence_span_count"], 6)
        self.assertEqual(metrics["evidence_lecture_outside_candidate_count"], 1)
        self.assertEqual(metrics["pending_adjudication_count"], 2)
        self.assertEqual(len(pending), 2)
        self.assertEqual(
            {item["pair_id"] for item in pending},
            {"rel_dev_001", "rel_dev_002"},
        )

    def test_invalid_alignment_is_fatal(self) -> None:
        metrics, errors, matches, pending = self.evaluate_fixture(
            "invalid_alignment_predictions.json",
            expected_returncode=1,
        )

        self.assertEqual(metrics["evaluation_status"], "invalid")
        self.assertFalse(metrics["aggregate_metrics_valid"])
        self.assertNotIn("strict_edge_accuracy", metrics)
        self.assertEqual(matches, [])
        self.assertEqual(pending, [])
        self.assertIn("duplicate_pair_id", self.error_types(errors))
        self.assertIn("candidate_pair_mismatch", self.error_types(errors))
        self.assertIn("unknown_pair_id", self.error_types(errors))
        self.assertIn("missing_predictions", self.error_types(errors))

    def test_empty_evidence_span_is_fatal(self) -> None:
        metrics, errors, matches, pending = self.evaluate_fixture(
            "empty_evidence_span_predictions.json",
            expected_returncode=1,
        )

        self.assertEqual(metrics["evaluation_status"], "invalid")
        self.assertFalse(metrics["aggregate_metrics_valid"])
        self.assertEqual(matches, [])
        self.assertEqual(pending, [])
        self.assertIn("schema_error", self.error_types(errors))

    def test_stale_adjudication_is_fatal_and_overwrites_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            evaluation_dir = Path(temporary_directory) / "evaluation"
            initial_metrics, _, _, initial_pending = self.evaluate_fixture(
                "quality_errors_predictions.json",
                evaluation_dir=evaluation_dir,
            )
            self.assertEqual(
                initial_metrics["evaluation_status"],
                "draft_pending_adjudication",
            )
            self.assertEqual(len(initial_pending), 2)

            metrics, errors, matches, pending = self.evaluate_fixture(
                "quality_errors_predictions.json",
                adjudication=FIXTURES / "stale_adjudication.json",
                expected_returncode=1,
                evaluation_dir=evaluation_dir,
            )

            self.assertEqual(metrics["evaluation_status"], "invalid")
            self.assertFalse(metrics["aggregate_metrics_valid"])
            self.assertNotIn("strict_edge_accuracy", metrics)
            self.assertEqual(matches, [])
            self.assertEqual(pending, [])
            self.assertEqual(
                self.error_types(errors),
                ["stale_or_unused_adjudication"],
            )

    def assert_symmetric_fixture(self, prediction_name: str) -> None:
        metrics, errors, matches, pending = self.evaluate_fixture(
            prediction_name,
            ground_truth=SYMMETRIC_GROUND_TRUTH,
        )

        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["strict_edge_accuracy"], 1.0)
        self.assertEqual(metrics["relation_type_accuracy_ignoring_direction"], 1.0)
        self.assertIsNone(metrics["endpoint_direction_accuracy"])
        self.assertIsNone(metrics["direction_accuracy_when_type_correct"])
        self.assertEqual(metrics["endpoint_direction_scored_count"], 0)
        self.assertEqual(metrics["direction_when_type_correct_scored_count"], 0)
        self.assertEqual(errors, [])
        self.assertEqual(pending, [])
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]["strict_edge_correct"])
        self.assertFalse(matches[0]["direction_eligible"])

    def test_symmetric_forward_fixture(self) -> None:
        self.assert_symmetric_fixture("symmetric_forward_predictions.json")

    def test_symmetric_reverse_fixture(self) -> None:
        self.assert_symmetric_fixture("symmetric_reverse_predictions.json")


if __name__ == "__main__":
    unittest.main()
