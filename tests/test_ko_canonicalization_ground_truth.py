from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import check_ko_canonicalization_ground_truth as checker
from scripts import create_ko_canonicalization_ground_truth as scaffold


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT / "benchmark" / "ko_mentions" / "development_v0_1" / "mention_inventory.json"
)
GROUND_TRUTH = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "ko_canonicalization_development_v0_1.json"
)
COMPLETION_MARKER = GROUND_TRUTH.with_name(
    "ko_canonicalization_development_v0_1_complete.json"
)
SEMANTIC_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "ko_canonicalization"
    / "semantic_identity_cases.json"
)


class KOCanonicalizationGroundTruthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        cls.ground_truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def write_ground_truth(self, value: dict[str, object]) -> Path:
        path = self.temporary_root / "ground_truth.json"
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def validate_mutation(self, value: dict[str, object]) -> list[str]:
        path = self.write_ground_truth(value)
        errors, _ = checker.validate_bundle(
            inventory_path=INVENTORY,
            ground_truth_path=path,
            completion_marker_path=None,
            allow_draft=False,
            require_completion_marker=False,
        )
        return errors

    def test_frozen_real_bundle_is_final_with_expected_counts(self) -> None:
        errors, summary = checker.validate_bundle(
            inventory_path=INVENTORY,
            ground_truth_path=GROUND_TRUTH,
            completion_marker_path=COMPLETION_MARKER,
            allow_draft=False,
            require_completion_marker=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(summary["validation_status"], "final")
        self.assertEqual(summary["mentions"], 39)
        self.assertEqual(summary["canonical_clusters"], 38)
        self.assertEqual(summary["singleton_clusters"], 37)
        self.assertEqual(summary["multi_mention_clusters"], 1)
        self.assertEqual(summary["same_object_pairs"], 1)
        self.assertEqual(summary["distinct_object_pairs"], 740)
        self.assertEqual(summary["cross_lecture_same_object_pairs"], 1)

    def test_scaffold_merge_is_deterministic_and_type_safe(self) -> None:
        clusters = scaffold.build_clusters(
            self.inventory["mentions"],
            raw_merge_groups=["ko_mention_dev_026,ko_mention_dev_035"],
            frozen=True,
        )

        self.assertEqual(len(clusters), 38)
        merged = next(
            item
            for item in clusters
            if item["mention_ids"] == ["ko_mention_dev_026", "ko_mention_dev_035"]
        )
        self.assertEqual(merged["canonical_id"], "canonical_ko_dev_026")
        self.assertEqual(merged["canonical_type"], "Method")
        self.assertTrue(all(item["annotation_status"] == "final" for item in clusters))

        with self.assertRaises(scaffold.CanonicalizationScaffoldError):
            scaffold.build_clusters(
                self.inventory["mentions"],
                raw_merge_groups=["ko_mention_dev_025,ko_mention_dev_026"],
                frozen=True,
            )

    def test_duplicate_membership_is_fatal(self) -> None:
        value = copy.deepcopy(self.ground_truth)
        value["clusters"][1]["mention_ids"].append("ko_mention_dev_001")

        errors = self.validate_mutation(value)

        self.assertTrue(any("assigned more than once" in error for error in errors))

    def test_orphan_mention_is_fatal(self) -> None:
        value = copy.deepcopy(self.ground_truth)
        value["clusters"][0]["mention_ids"] = ["ko_mention_dev_002"]

        errors = self.validate_mutation(value)

        self.assertTrue(any("orphan mentions" in error for error in errors))

    def test_cross_type_merge_is_fatal(self) -> None:
        value = copy.deepcopy(self.ground_truth)
        formula_cluster = next(
            item for item in value["clusters"] if item["mention_ids"] == ["ko_mention_dev_005"]
        )
        method_cluster = next(
            item for item in value["clusters"] if item["mention_ids"] == ["ko_mention_dev_004"]
        )
        formula_cluster["mention_ids"] = ["ko_mention_dev_006"]
        method_cluster["mention_ids"].append("ko_mention_dev_005")

        errors = self.validate_mutation(value)

        self.assertTrue(any("cross-type cluster" in error for error in errors))

    def test_stale_inventory_binding_is_fatal(self) -> None:
        value = copy.deepcopy(self.ground_truth)
        value["mention_inventory"]["sha256"] = "0" * 64

        errors = self.validate_mutation(value)

        self.assertTrue(any("stale SHA-256 binding" in error for error in errors))

    def test_semantic_fixture_covers_required_identity_boundaries(self) -> None:
        fixture = json.loads(SEMANTIC_FIXTURE.read_text(encoding="utf-8"))
        mentions = fixture["mentions"]
        clusters = fixture["gold_clusters"]
        assigned = [member for cluster in clusters for member in cluster["mention_ids"]]

        self.assertEqual(len(mentions), 7)
        self.assertEqual(len(assigned), 7)
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(
            {item["case"] for item in clusters},
            {
                "alias_same_object",
                "abbreviation_same_object",
                "same_name_distinct",
                "cross_type_distinct",
            },
        )
        degree_mentions = [item for item in mentions if item["name"] == "Degree"]
        self.assertEqual(len(degree_mentions), 2)
        cluster_by_mention = {
            mention_id: cluster["canonical_id"]
            for cluster in clusters
            for mention_id in cluster["mention_ids"]
        }
        self.assertNotEqual(
            cluster_by_mention[degree_mentions[0]["mention_id"]],
            cluster_by_mention[degree_mentions[1]["mention_id"]],
        )


if __name__ == "__main__":
    unittest.main()
