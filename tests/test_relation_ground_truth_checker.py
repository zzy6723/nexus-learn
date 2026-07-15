from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.check_relation_ground_truth import validate_ground_truth


ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_DIR = ROOT / "benchmark" / "ground_truth"
MATCHED_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "predicted_ko_relation"
    / "valid_bundle"
    / "matched_relation_ground_truth.json"
)


def load_ground_truth(name: str) -> dict:
    return json.loads((GROUND_TRUTH_DIR / name).read_text(encoding="utf-8"))


class RelationGroundTruthCheckerTests(unittest.TestCase):
    def test_development_pair_ids_remain_valid(self) -> None:
        data = load_ground_truth("relations_development_v0_1.json")

        errors, summary = validate_ground_truth(data)

        self.assertEqual(errors, [])
        self.assertEqual(summary["pair_count"], 41)

    def test_holdout_pair_ids_are_valid(self) -> None:
        data = load_ground_truth("relations_holdout_v0_1.json")

        errors, summary = validate_ground_truth(data)

        self.assertEqual(errors, [])
        self.assertEqual(summary["pair_count"], 40)
        self.assertEqual(summary["primary_hard_negative_rate"], 0.275)

    def test_holdout_rejects_development_pair_id_prefix(self) -> None:
        data = copy.deepcopy(load_ground_truth("relations_holdout_v0_1.json"))
        for index, pair in enumerate(data["pairs"], start=1):
            pair["pair_id"] = f"rel_dev_{index:03d}"

        errors, _ = validate_ground_truth(data)

        self.assertTrue(
            any(
                "pair_id must match rel_holdout_NNN for split 'holdout'" in error
                for error in errors
            )
        )

    def test_matched_subset_exception_requires_complete_derivation(self) -> None:
        data = json.loads(MATCHED_FIXTURE.read_text(encoding="utf-8"))
        data["pairs"].pop(1)
        data["derivation"].pop("pair_manifest_sha256")

        errors, _ = validate_ground_truth(data)

        self.assertTrue(
            any("invalid derivation hashes" in error for error in errors)
        )
        self.assertTrue(any("pair IDs must be contiguous" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
