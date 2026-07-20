from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.create_ko_identity_evidence_review_set import build_review_set
from scripts.finalize_ko_identity_evidence_audit import EvidenceAuditError, finalize_audit


class KOIdentityEvidenceReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.prediction = self.root / "predictions.json"
        self.prediction.write_text('{"results": []}\n')
        self.candidates = {
            "candidates": [
                {
                    "candidate_id": "candidate_001",
                    "mention_a": {"mention_id": "m1", "lecture_id": "l1", "name": "Gradient", "type": "Concept"},
                    "mention_b": {"mention_id": "m2", "lecture_id": "l2", "name": "Gradient", "type": "Concept"},
                }
            ]
        }
        self.decisions = {
            "results": [
                {
                    "candidate_id": "candidate_001", "mention_a": "m1", "mention_b": "m2",
                    "decision": "SAME_OBJECT", "evidence_ids": ["evidence_001"],
                    "evidence_spans": [{"lecture_id": "l1", "span": "The gradient is a vector."}],
                    "rationale": "Both mentions denote the gradient.",
                }
            ]
        }

    def test_review_set_is_gold_method_and_metric_blind(self) -> None:
        package = build_review_set(self.candidates, self.decisions, self.prediction)
        self.assertEqual(package["review_item_count"], 1)
        forbidden = {"method_id", "model", "run_id", "prompt", "gold", "metrics"}
        self.assertFalse(forbidden & set(package))
        for item in package["items"]:
            self.assertFalse(forbidden & set(item))

    def test_final_audit_is_snapshot_bound_and_complete(self) -> None:
        review_set = build_review_set(self.candidates, self.decisions, self.prediction)
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review_set))
        adjudication = {
            "prediction_sha256": hashlib.sha256(self.prediction.read_bytes()).hexdigest(),
            "review_set_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
            "decisions": [{"review_item_id": "ko_evidence_review_001", "decision": "supported", "rationale": ""}],
        }
        audit = finalize_audit(
            prediction_path=self.prediction, review_path=review_path,
            review_set=review_set, adjudication=adjudication,
        )
        self.assertEqual(audit["status"], "final")
        self.assertEqual(audit["counts"]["supported"], 1)
        self.assertEqual(audit["counts"]["stale_decisions"], 0)

    def test_stale_or_incomplete_adjudication_fails(self) -> None:
        review_set = build_review_set(self.candidates, self.decisions, self.prediction)
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review_set))
        with self.assertRaises(EvidenceAuditError):
            finalize_audit(
                prediction_path=self.prediction, review_path=review_path,
                review_set=review_set,
                adjudication={"prediction_sha256": "stale", "review_set_sha256": "stale", "decisions": []},
            )


if __name__ == "__main__":
    unittest.main()
