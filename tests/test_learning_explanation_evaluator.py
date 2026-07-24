import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_learning_explanations import evaluate_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests/fixtures/learning_explanation"


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


class LearningExplanationEvaluatorTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.benchmark_path = FIXTURES / "synthetic_benchmark.json"
        self.base_predictions = read_json(FIXTURES / "perfect_predictions.json")
        self.base_reviews = read_json(FIXTURES / "perfect_reviews.json")

    def run_scenario(
        self,
        *,
        predictions=None,
        reviews=None,
        method="002_evidence_grounded",
        bind_review=True,
        name="scenario",
    ):
        predictions = copy.deepcopy(predictions or self.base_predictions)
        reviews = copy.deepcopy(reviews or self.base_reviews)
        predictions["method_id"] = method
        predictions_path = self.root / f"{name}_predictions.json"
        reviews_path = self.root / f"{name}_reviews.json"
        evaluation_dir = self.root / f"{name}_evaluation"
        write_json(predictions_path, predictions)
        if bind_review:
            reviews["prediction_sha256"] = hashlib.sha256(
                predictions_path.read_bytes()
            ).hexdigest()
        write_json(reviews_path, reviews)
        result = evaluate_files(
            benchmark_path=self.benchmark_path,
            predictions_path=predictions_path,
            reviews_path=reviews_path,
            method_id=method,
            evaluation_dir=evaluation_dir,
        )
        return result, evaluation_dir

    def test_perfect_fixture_is_final(self):
        evaluation_dir = self.root / "perfect_evaluation"
        metrics = evaluate_files(
            benchmark_path=self.benchmark_path,
            predictions_path=FIXTURES / "perfect_predictions.json",
            reviews_path=FIXTURES / "perfect_reviews.json",
            method_id="002_evidence_grounded",
            evaluation_dir=evaluation_dir,
        )
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["hard_metrics"]["faithfulness_pass_rate"], 1.0)
        self.assertEqual(
            metrics["hard_metrics"]["direction_faithfulness_rate"], 1.0
        )
        self.assertEqual(
            metrics["hard_metrics"]["exact_evidence_id_validity_rate"], 1.0
        )
        self.assertEqual(metrics["hard_metrics"]["unsupported_claim_rate"], 0.0)
        self.assertEqual(metrics["secondary_metrics"]["denominator"], 4)

    def test_semantic_direction_reversal_is_scored_not_invalid(self):
        reviews = copy.deepcopy(self.base_reviews)
        item = reviews["reviews"][0]
        item["faithfulness"]["direction_faithful"] = False
        item["failure_labels"] = ["DIRECTION_REVERSAL"]
        item["learning_value_scores"] = None
        metrics, _ = self.run_scenario(reviews=reviews, name="direction")
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(
            metrics["hard_metrics"]["relation_faithfulness_rate"], 1.0
        )
        self.assertEqual(
            metrics["hard_metrics"]["direction_faithfulness_rate"], 0.75
        )
        self.assertEqual(
            metrics["hard_metrics"]["direction_reversal_count"], 1
        )

    def test_unsupported_claim_fails_faithfulness(self):
        reviews = copy.deepcopy(self.base_reviews)
        item = reviews["reviews"][1]
        item["claims"][1]["support_label"] = "UNSUPPORTED"
        item["faithfulness"]["evidence_faithful"] = False
        item["failure_labels"] = ["EVIDENCE_OVERREACH"]
        item["learning_value_scores"] = None
        metrics, _ = self.run_scenario(reviews=reviews, name="unsupported")
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertGreater(
            metrics["hard_metrics"]["unsupported_claim_rate"], 0
        )
        self.assertEqual(
            metrics["failure_label_counts"]["EVIDENCE_OVERREACH"], 1
        )
        self.assertEqual(metrics["secondary_metrics"]["denominator"], 3)

    def test_endpoint_drift_is_scored(self):
        reviews = copy.deepcopy(self.base_reviews)
        item = reviews["reviews"][2]
        item["faithfulness"]["endpoint_faithful"] = False
        item["failure_labels"] = ["ENDPOINT_DRIFT"]
        item["learning_value_scores"] = None
        metrics, _ = self.run_scenario(reviews=reviews, name="endpoint")
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(
            metrics["hard_metrics"]["endpoint_faithfulness_rate"], 0.75
        )
        self.assertEqual(metrics["failure_label_counts"]["ENDPOINT_DRIFT"], 1)

    def test_pedagogically_empty_output_remains_faithful(self):
        reviews = copy.deepcopy(self.base_reviews)
        item = reviews["reviews"][3]
        item["failure_labels"] = ["PEDAGOGICALLY_EMPTY"]
        item["learning_value_scores"]["conceptual_mechanism"] = 0
        item["learning_value_scores"]["learning_relevance"] = 0
        metrics, _ = self.run_scenario(reviews=reviews, name="empty")
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["hard_metrics"]["faithfulness_pass_rate"], 1.0)
        self.assertEqual(
            metrics["secondary_metrics"]["pedagogically_non_empty_rate"], 0.75
        )

    def test_unresolved_claim_produces_draft(self):
        reviews = copy.deepcopy(self.base_reviews)
        item = reviews["reviews"][0]
        item["claims"][1]["support_label"] = "UNRESOLVED"
        item["learning_value_scores"] = None
        metrics, _ = self.run_scenario(reviews=reviews, name="unresolved")
        self.assertEqual(
            metrics["evaluation_status"], "draft_pending_adjudication"
        )
        self.assertEqual(
            metrics["counts"]["pending_claim_adjudications"], 1
        )

    def test_unknown_evidence_reference_is_fatal_and_cleans_metrics(self):
        predictions = copy.deepcopy(self.base_predictions)
        predictions["results"][0]["why_connected"]["evidence_refs"] = [
            "unknown_evidence"
        ]
        evaluation_dir = self.root / "invalid_evidence_evaluation"
        evaluation_dir.mkdir()
        (evaluation_dir / "metrics.json").write_text('{"stale": true}\n')

        predictions_path = self.root / "invalid_evidence_predictions.json"
        reviews_path = self.root / "invalid_evidence_reviews.json"
        write_json(predictions_path, predictions)
        reviews = copy.deepcopy(self.base_reviews)
        reviews["prediction_sha256"] = hashlib.sha256(
            predictions_path.read_bytes()
        ).hexdigest()
        write_json(reviews_path, reviews)
        result = evaluate_files(
            benchmark_path=self.benchmark_path,
            predictions_path=predictions_path,
            reviews_path=reviews_path,
            method_id="002_evidence_grounded",
            evaluation_dir=evaluation_dir,
        )
        self.assertEqual(result["evaluation_status"], "invalid")
        self.assertFalse((evaluation_dir / "metrics.json").exists())
        errors = read_json(evaluation_dir / "errors.json")
        self.assertIn(
            "unknown Evidence IDs",
            errors["fatal_errors"][0]["detail"],
        )

    def test_grounded_method_requires_why_connected_evidence(self):
        predictions = copy.deepcopy(self.base_predictions)
        predictions["results"][0]["why_connected"]["evidence_refs"] = []
        result, evaluation_dir = self.run_scenario(
            predictions=predictions,
            name="missing_why_evidence",
        )
        self.assertEqual(result["evaluation_status"], "invalid")
        errors = read_json(evaluation_dir / "errors.json")
        self.assertIn(
            "why_connected omitted Evidence",
            errors["fatal_errors"][0]["detail"],
        )

    def test_source_grounded_claim_requires_field_level_reference(self):
        reviews = copy.deepcopy(self.base_reviews)
        reviews["reviews"][0]["claims"][2][
            "support_label"
        ] = "SOURCE_GROUNDED"
        result, evaluation_dir = self.run_scenario(
            reviews=reviews,
            name="missing_field_reference",
        )
        self.assertEqual(result["evaluation_status"], "invalid")
        errors = read_json(evaluation_dir / "errors.json")
        self.assertIn(
            "SOURCE_GROUNDED claims lack field-level Evidence",
            errors["fatal_errors"][0]["detail"],
        )

    def test_missing_prediction_alignment_is_fatal(self):
        predictions = copy.deepcopy(self.base_predictions)
        predictions["results"].pop()
        result, evaluation_dir = self.run_scenario(
            predictions=predictions,
            name="missing",
        )
        self.assertEqual(result["evaluation_status"], "invalid")
        self.assertFalse((evaluation_dir / "metrics.json").exists())

    def test_stale_review_snapshot_is_fatal(self):
        reviews = copy.deepcopy(self.base_reviews)
        reviews["prediction_sha256"] = "0" * 64
        result, evaluation_dir = self.run_scenario(
            reviews=reviews,
            bind_review=False,
            name="stale",
        )
        self.assertEqual(result["evaluation_status"], "invalid")
        errors = read_json(evaluation_dir / "errors.json")
        self.assertEqual(
            errors["fatal_errors"][0]["error_type"],
            "stale_review_snapshot",
        )

    def test_no_evidence_baseline_uses_null_evidence_metric(self):
        predictions = copy.deepcopy(self.base_predictions)
        reviews = copy.deepcopy(self.base_reviews)
        for result in predictions["results"]:
            for field in (
                "connection_summary",
                "why_connected",
                "learning_value",
            ):
                result[field]["evidence_refs"] = []
        for review in reviews["reviews"]:
            review["faithfulness"]["evidence_faithful"] = None
            for claim in review["claims"]:
                if claim["support_label"] == "SOURCE_GROUNDED":
                    claim["support_label"] = "RELATION_ENTAILED"
        metrics, _ = self.run_scenario(
            predictions=predictions,
            reviews=reviews,
            method="001b_relation_only_llm",
            name="relation_only",
        )
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertIsNone(
            metrics["hard_metrics"][
                "explanation_evidence_faithfulness_rate"
            ]
        )
        self.assertIsNone(
            metrics["hard_metrics"]["exact_evidence_id_validity_rate"]
        )
        self.assertFalse(metrics["method_selectable"])


if __name__ == "__main__":
    unittest.main()
