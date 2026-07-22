from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.generate_connection_evidence_windows import (
    EvidenceWindowError,
    build_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    inventory = {
        "artifact_type": "connection_discovery_oracle_canonical_inventory",
        "canonical_objects": [
            {
                "canonical_ko_id": "ko_a",
                "canonical_name": "Gradient",
                "canonical_type": "Concept",
                "aliases": ["gradient vector"],
                "mentions": [
                    {
                        "lecture_id": "lecture_1",
                        "source_spans": ["the gradient of the objective"],
                    }
                ],
            },
            {
                "canonical_ko_id": "ko_b",
                "canonical_name": "Gradient Descent",
                "canonical_type": "Method",
                "aliases": [],
                "mentions": [
                    {
                        "lecture_id": "lecture_1",
                        "source_spans": ["Gradient descent requires the gradient"],
                    }
                ],
            },
            {
                "canonical_ko_id": "ko_c",
                "canonical_name": "Hessian Matrix",
                "canonical_type": "Concept",
                "aliases": ["Hessian"],
                "mentions": [
                    {"lecture_id": "lecture_1", "source_spans": ["the Hessian"]}
                ],
            },
        ],
    }
    selection = {
        "artifact_type": "connection_candidate_selection",
        "split": "synthetic",
        "selected_pairs": [
            {
                "canonical_pair_id": "pair_001",
                "ko_a": {"canonical_ko_id": "ko_a"},
                "ko_b": {"canonical_ko_id": "ko_b"},
            },
            {
                "canonical_pair_id": "pair_002",
                "ko_a": {"canonical_ko_id": "ko_b"},
                "ko_b": {"canonical_ko_id": "ko_c"},
            },
        ],
    }
    catalogs = {
        "artifact_type": "connection_evidence_catalog_bundle",
        "catalogs": [
            {
                "canonical_pair_id": "pair_001",
                "endpoint_ids": ["ko_a", "ko_b"],
                "evidence_items": [
                    {
                        "evidence_id": "evidence_001",
                        "lecture_id": "lecture_1",
                        "block_index": 1,
                        "span": "The gradient of the objective gives a local direction.",
                    },
                    {
                        "evidence_id": "evidence_002",
                        "lecture_id": "lecture_1",
                        "block_index": 2,
                        "span": "Gradient descent requires the gradient and moves opposite to it.",
                    },
                    {
                        "evidence_id": "evidence_003",
                        "lecture_id": "lecture_1",
                        "block_index": 3,
                        "span": "The Hessian supplies curvature.",
                    },
                ],
            },
            {
                "canonical_pair_id": "pair_002",
                "endpoint_ids": ["ko_b", "ko_c"],
                "evidence_items": [
                    {
                        "evidence_id": "evidence_001",
                        "lecture_id": "lecture_1",
                        "block_index": 1,
                        "span": "Gradient descent is a first-order method.",
                    },
                    {
                        "evidence_id": "evidence_002",
                        "lecture_id": "lecture_1",
                        "block_index": 3,
                        "span": "The Hessian supplies curvature.",
                    },
                ],
            },
        ],
    }
    return selection, inventory, catalogs


class ConnectionEvidenceWindowTests(unittest.TestCase):
    def test_minimal_endpoint_linked_windows_are_deterministic(self):
        selection, inventory, catalogs = fixtures()
        first = build_bundle(selection, inventory, catalogs, max_blocks=3)
        second = build_bundle(selection, inventory, catalogs, max_blocks=3)
        self.assertEqual(first, second)
        pair = first["pairs"][0]
        self.assertEqual(pair["window_count"], 1)
        self.assertEqual(pair["windows"][0]["evidence_ids"], ["evidence_002"])
        self.assertFalse(pair["deterministic_no_window"])

    def test_noncontiguous_blocks_do_not_form_a_window(self):
        selection, inventory, catalogs = fixtures()
        bundle = build_bundle(selection, inventory, catalogs, max_blocks=3)
        pair = bundle["pairs"][1]
        self.assertTrue(pair["deterministic_no_window"])
        self.assertEqual(pair["windows"], [])

    def test_gold_fields_are_rejected(self):
        selection, inventory, catalogs = fixtures()
        leaked = copy.deepcopy(selection)
        leaked["selected_pairs"][0]["category"] = "IN_SCHEMA_CONNECTION"
        with self.assertRaisesRegex(EvidenceWindowError, "gold leakage"):
            build_bundle(leaked, inventory, catalogs)

    def test_endpoint_mismatch_is_rejected(self):
        selection, inventory, catalogs = fixtures()
        invalid = copy.deepcopy(catalogs)
        invalid["catalogs"][0]["endpoint_ids"] = ["ko_b", "ko_a"]
        with self.assertRaisesRegex(EvidenceWindowError, "endpoint mismatch"):
            build_bundle(selection, inventory, invalid)

    def test_real_development_bundle_is_gold_free_and_complete(self):
        selection = json.loads(
            (
                ROOT
                / "experiments/connection_discovery/003_1_candidate_generation/runs/"
                "development_v0_1/overlap_bridge/run_01/generation/candidate_selection.json"
            ).read_text()
        )
        inventory = json.loads(
            (
                ROOT
                / "benchmark/connection_discovery/development_v0_1/"
                "oracle_canonical_inventory.json"
            ).read_text()
        )
        catalogs = json.loads(
            (
                ROOT
                / "benchmark/connection_discovery/development_v0_1/"
                "evidence_catalogs.json"
            ).read_text()
        )
        bundle = build_bundle(selection, inventory, catalogs, max_blocks=3)
        self.assertEqual(bundle["counts"]["selected_pair_count"], 125)
        self.assertEqual(len(bundle["pairs"]), 125)
        self.assertFalse(bundle["gold_fields_present"])
        self.assertEqual(
            len({pair["canonical_pair_id"] for pair in bundle["pairs"]}), 125
        )
        self.assertGreater(bundle["counts"]["window_count"], 0)


if __name__ == "__main__":
    unittest.main()
