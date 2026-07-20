from __future__ import annotations

import unittest

from scripts import evaluate_direct_edge_gate as evaluator


class DirectEdgeGateEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = {
            "selected_pairs": [
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000001",
                    "ko_a": {"canonical_ko_id": "ko_a", "canonical_name": "A", "canonical_type": "Concept"},
                    "ko_b": {"canonical_ko_id": "ko_b", "canonical_name": "B", "canonical_type": "Method"},
                },
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000002",
                    "ko_a": {"canonical_ko_id": "ko_c", "canonical_name": "C", "canonical_type": "Concept"},
                    "ko_b": {"canonical_ko_id": "ko_d", "canonical_name": "D", "canonical_type": "Concept"},
                },
            ]
        }
        self.ground_truth = {
            "pairs": [
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000001",
                    "category": "IN_SCHEMA_CONNECTION",
                    "primary_scoring_eligible": True,
                    "evidence": [{"evidence_id": "evidence_001"}],
                },
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000002",
                    "category": "NO_IN_SCHEMA_CONNECTION",
                    "primary_scoring_eligible": True,
                    "evidence": [],
                },
            ]
        }
        self.catalogs = {
            "catalogs": [
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000001",
                    "evidence_items": [{"evidence_id": "evidence_001", "lecture_id": "lecture_1", "span": "A is used in B."}],
                },
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000002",
                    "evidence_items": [{"evidence_id": "evidence_001", "lecture_id": "lecture_1", "span": "C and D are mentioned separately."}],
                },
            ]
        }

    @staticmethod
    def result(pair_id: str, ko_a: str, ko_b: str, decision: str, evidence: list[str]) -> dict:
        return {
            "canonical_pair_id": pair_id,
            "ko_a_id": ko_a,
            "ko_b_id": ko_b,
            "decision": decision,
            "evidence_ids": evidence,
            "rationale": "The supplied Evidence directly connects the endpoints." if decision == "DIRECT_CONNECTION" else "No direct connection is established.",
        }

    def predictions(self, *, overconnect: bool = False) -> dict:
        return {
            "artifact_type": "canonical_direct_edge_gate_predictions",
            "version": "v0.1",
            "results": [
                self.result("conn_dev_pair_0000000000000001", "ko_a", "ko_b", "DIRECT_CONNECTION", ["evidence_001"]),
                self.result(
                    "conn_dev_pair_0000000000000002",
                    "ko_c",
                    "ko_d",
                    "DIRECT_CONNECTION" if overconnect else "NO_RELATION",
                    ["evidence_001"] if overconnect else [],
                ),
            ],
        }

    def test_perfect_gate_is_final(self) -> None:
        artifacts = evaluator.evaluate(
            self.predictions(), self.selection, self.ground_truth, self.catalogs, None
        )
        metrics = artifacts["metrics.json"]
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["metrics"]["direct_edge_precision"], 1.0)
        self.assertEqual(metrics["metrics"]["direct_edge_recall"], 1.0)
        self.assertEqual(metrics["metrics"]["primary_negative_accuracy"], 1.0)
        self.assertEqual(metrics["metrics"]["semantic_evidence_support_rate"], 1.0)

    def test_non_gold_positive_requires_snapshot_bound_adjudication(self) -> None:
        predictions = self.predictions(overconnect=True)
        draft = evaluator.evaluate(
            predictions, self.selection, self.ground_truth, self.catalogs, None
        )
        pending = draft["adjudication_pending.json"]
        self.assertEqual(draft["metrics.json"]["evaluation_status"], "draft_pending_adjudication")
        self.assertEqual(pending["pending_count"], 1)
        adjudication = {
            "artifact_type": "direct_edge_evidence_adjudication",
            "version": "v0.1",
            "prediction_content_sha256": pending["prediction_content_sha256"],
            "pending_snapshot_sha256": pending["pending_snapshot_sha256"],
            "decisions": [
                {
                    "canonical_pair_id": "conn_dev_pair_0000000000000002",
                    "decision": "not_supported",
                    "rationale": "The block only mentions the endpoints separately.",
                }
            ],
        }
        final = evaluator.evaluate(
            predictions, self.selection, self.ground_truth, self.catalogs, adjudication
        )
        metrics = final["metrics.json"]
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["counts"]["false_positive_gates"], 1)
        self.assertEqual(metrics["counts"]["evidence_not_supported"], 1)
        self.assertEqual(metrics["metrics"]["direct_edge_precision"], 0.5)
        self.assertEqual(metrics["metrics"]["semantic_evidence_support_rate"], 0.5)

    def test_stale_adjudication_is_rejected(self) -> None:
        predictions = self.predictions(overconnect=True)
        draft = evaluator.evaluate(
            predictions, self.selection, self.ground_truth, self.catalogs, None
        )
        pending = draft["adjudication_pending.json"]
        adjudication = {
            "artifact_type": "direct_edge_evidence_adjudication",
            "version": "v0.1",
            "prediction_content_sha256": "0" * 64,
            "pending_snapshot_sha256": pending["pending_snapshot_sha256"],
            "decisions": [],
        }
        with self.assertRaises(evaluator.DirectGateEvaluationError):
            evaluator.evaluate(
                predictions, self.selection, self.ground_truth, self.catalogs, adjudication
            )

    def test_changed_endpoint_is_fatal(self) -> None:
        predictions = self.predictions()
        predictions["results"][0]["ko_b_id"] = "changed"
        with self.assertRaises(evaluator.DirectGateEvaluationError):
            evaluator.evaluate(
                predictions, self.selection, self.ground_truth, self.catalogs, None
            )


if __name__ == "__main__":
    unittest.main()
