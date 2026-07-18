from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import finalize_ko_resolution_challenge as finalizer


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_ROOT = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"


class KOResolutionChallengeTest(unittest.TestCase):
    def test_frozen_real_bundle_is_final_and_hash_bound(self) -> None:
        return_code = finalizer.main(
            ["--challenge-root", str(CHALLENGE_ROOT), "--check"]
        )

        self.assertEqual(return_code, 0)
        marker = json.loads(
            (CHALLENGE_ROOT / "challenge_complete.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marker["status"], "final")
        self.assertEqual(marker["data_role"], "authored_development_challenge")
        self.assertEqual(
            marker["counts"],
            {
                "mentions": 21,
                "canonical_clusters": 13,
                "singleton_clusters": 7,
                "multi_mention_clusters": 6,
                "same_object_pairs": 10,
                "distinct_object_pairs": 200,
                "multi_mention_coverage_cases": 6,
                "hard_negative_coverage_cases": 3,
                "exact_source_spans": 21,
            },
        )

    def test_stale_challenge_artifact_is_rejected(self) -> None:
        marker = json.loads(
            (CHALLENGE_ROOT / "challenge_complete.json").read_text(encoding="utf-8")
        )
        marker["artifacts"]["challenge_protocol"]["sha256"] = "0" * 64
        paths = {
            name: CHALLENGE_ROOT / filename
            for name, filename in finalizer.REQUIRED_FILES.items()
        }

        with self.assertRaisesRegex(
            finalizer.ChallengeFinalizationError,
            "stale binding for challenge_protocol",
        ):
            finalizer.validate_completion_marker(marker, paths=paths)

    def test_semantic_coverage_includes_same_name_same_type_homonym(self) -> None:
        inventory = json.loads(
            (CHALLENGE_ROOT / "mention_inventory.json").read_text(encoding="utf-8")
        )
        ground_truth = json.loads(
            (CHALLENGE_ROOT / "ground_truth.json").read_text(encoding="utf-8")
        )
        coverage = json.loads(
            (CHALLENGE_ROOT / "coverage_manifest.json").read_text(encoding="utf-8")
        )

        counts = finalizer.validate_semantic_coverage(
            inventory, ground_truth, coverage
        )

        self.assertEqual(counts["multi_mention_coverage_cases"], 6)
        self.assertEqual(counts["hard_negative_coverage_cases"], 3)

    def test_homonym_case_must_be_same_name_and_same_type(self) -> None:
        inventory = json.loads(
            (CHALLENGE_ROOT / "mention_inventory.json").read_text(encoding="utf-8")
        )
        ground_truth = json.loads(
            (CHALLENGE_ROOT / "ground_truth.json").read_text(encoding="utf-8")
        )
        coverage = json.loads(
            (CHALLENGE_ROOT / "coverage_manifest.json").read_text(encoding="utf-8")
        )
        homonym = next(
            item
            for item in coverage["hard_negative_cases"]
            if item["case"] == "same_name_same_type_different_referent"
        )
        changed_id = homonym["mention_ids"][1]
        changed_mention = next(
            item for item in inventory["mentions"] if item["mention_id"] == changed_id
        )
        changed_mention["name"] = "Different Degree Name"

        with self.assertRaisesRegex(
            finalizer.ChallengeFinalizationError,
            "not same-name and same-type",
        ):
            finalizer.validate_semantic_coverage(inventory, ground_truth, coverage)


if __name__ == "__main__":
    unittest.main()
