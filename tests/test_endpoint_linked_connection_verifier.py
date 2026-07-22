from __future__ import annotations

import copy
import unittest

from scripts.run_endpoint_linked_connection_verifier import (
    EndpointVerifierError,
    aggregate_predictions,
    build_execution_items,
    validate_window_decision,
)


def bundle():
    return {
        "artifact_type": "connection_evidence_window_bundle",
        "version": "v0.1",
        "gold_fields_present": False,
        "counts": {"selected_pair_count": 2, "window_count": 1},
        "pairs": [
            {
                "canonical_pair_id": "pair_001",
                "endpoint_ids": ["ko_a", "ko_b"],
                "endpoint_objects": [
                    {"canonical_ko_id": "ko_a", "canonical_name": "Gradient", "canonical_type": "Concept"},
                    {"canonical_ko_id": "ko_b", "canonical_name": "Gradient Descent", "canonical_type": "Method"},
                ],
                "window_count": 1,
                "deterministic_no_window": False,
                "windows": [
                    {
                        "window_id": "window_001",
                        "lecture_id": "lecture_1",
                        "evidence_ids": ["evidence_001"],
                        "evidence_blocks": [
                            {"evidence_id": "evidence_001", "lecture_id": "lecture_1", "span": "Gradient descent requires the gradient."}
                        ],
                    }
                ],
            },
            {
                "canonical_pair_id": "pair_002",
                "endpoint_ids": ["ko_a", "ko_c"],
                "endpoint_objects": [
                    {"canonical_ko_id": "ko_a", "canonical_name": "Gradient", "canonical_type": "Concept"},
                    {"canonical_ko_id": "ko_c", "canonical_name": "Step Size", "canonical_type": "Concept"},
                ],
                "window_count": 0,
                "deterministic_no_window": True,
                "windows": [],
            },
        ],
    }


def direct_decision(**updates):
    value = {
        "canonical_pair_id": "pair_001",
        "window_id": "window_001",
        "support_decision": "DIRECT_IN_SCHEMA",
        "source_canonical_ko_id": "ko_b",
        "target_canonical_ko_id": "ko_a",
        "relation_type": "REQUIRES",
        "evidence_ids": ["evidence_001"],
        "rationale": "Gradient descent requires the gradient.",
    }
    value.update(updates)
    return value


class EndpointLinkedVerifierTests(unittest.TestCase):
    def test_model_input_is_window_scoped_and_gold_free(self):
        items = build_execution_items(bundle())
        self.assertEqual(len(items), 1)
        model_input = items[0]["model_input"]
        self.assertEqual(model_input["window_id"], "window_001")
        self.assertEqual(len(model_input["evidence_window"]), 1)
        self.assertNotIn("category", str(model_input))
        self.assertNotIn("gold_edge", str(model_input))

    def test_direct_decision_is_valid(self):
        item = build_execution_items(bundle())[0]
        self.assertEqual(validate_window_decision(direct_decision(), item), direct_decision())

    def test_non_direct_decision_cannot_emit_edge(self):
        item = build_execution_items(bundle())[0]
        invalid = direct_decision(support_decision="MEDIATED_OR_CONTEXTUAL")
        with self.assertRaisesRegex(EndpointVerifierError, "non-direct"):
            validate_window_decision(invalid, item)

    def test_direct_evidence_must_stay_inside_window(self):
        item = build_execution_items(bundle())[0]
        with self.assertRaisesRegex(EndpointVerifierError, "outside"):
            validate_window_decision(direct_decision(evidence_ids=["evidence_999"]), item)

    def test_unique_edge_and_no_window_aggregate_deterministically(self):
        predictions, diagnostics = aggregate_predictions(bundle(), [direct_decision()])
        self.assertEqual(predictions["results"][0]["relation_type"], "REQUIRES")
        self.assertEqual(predictions["results"][1]["relation_type"], "NO_RELATION")
        self.assertEqual(diagnostics[1]["aggregation_outcome"], "no_direct_edge")

    def test_conflicting_direct_edges_fail_closed(self):
        test_bundle = copy.deepcopy(bundle())
        second_window = copy.deepcopy(test_bundle["pairs"][0]["windows"][0])
        second_window["window_id"] = "window_002"
        test_bundle["pairs"][0]["windows"].append(second_window)
        test_bundle["pairs"][0]["window_count"] = 2
        test_bundle["counts"]["window_count"] = 2
        conflict = direct_decision(
            window_id="window_002",
            source_canonical_ko_id="ko_a",
            target_canonical_ko_id="ko_b",
            relation_type="APPLIED_IN",
        )
        predictions, diagnostics = aggregate_predictions(
            test_bundle, [direct_decision(), conflict]
        )
        self.assertEqual(predictions["results"][0]["relation_type"], "NO_RELATION")
        self.assertEqual(diagnostics[0]["aggregation_outcome"], "conflicting_direct_edges")


if __name__ == "__main__":
    unittest.main()
