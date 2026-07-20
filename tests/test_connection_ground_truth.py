import json
import unittest
from pathlib import Path

from scripts.check_connection_ground_truth import audit_ground_truth


class ConnectionGroundTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.bundle = cls.root / "benchmark/connection_discovery/development_v0_1"

    def load(self, name):
        path = self.bundle / name
        return path, json.loads(path.read_text(encoding="utf-8"))

    def test_frozen_candidate_ground_truth_is_complete_and_exact(self) -> None:
        manifest_path, manifest = self.load("source_manifest.json")
        inventory_path, inventory = self.load("oracle_canonical_inventory.json")
        universe_path, universe = self.load("pair_universe.json")
        catalogs_path, catalogs = self.load("evidence_catalogs.json")
        ground_truth_path, ground_truth = self.load("ground_truth.json")
        audit = audit_ground_truth(
            manifest,
            inventory,
            universe,
            catalogs,
            ground_truth,
            repository_root=self.root,
            source_manifest_path=manifest_path.relative_to(self.root),
            canonical_inventory_path=inventory_path.relative_to(self.root),
            pair_universe_path=universe_path.relative_to(self.root),
            evidence_catalogs_path=catalogs_path.relative_to(self.root),
            ground_truth_path=ground_truth_path.relative_to(self.root),
        )
        self.assertTrue(audit["freeze_ready"], audit["errors"])
        self.assertEqual(audit["counts"]["all_eligible_pairs"], 387)
        self.assertEqual(audit["counts"]["primary_positive_pairs"], 41)
        self.assertEqual(audit["counts"]["primary_negative_pairs"], 335)
        self.assertEqual(audit["negative_review"]["shared_block_negative_count"], 5)
        self.assertEqual(audit["negative_review"]["unresolved_shared_block_count"], 0)
        self.assertEqual(audit["evidence"]["selected_items"], 99)
        self.assertEqual(audit["evidence"]["exact_catalog_matches"], 99)
        self.assertEqual(audit["positive_scope"]["primary_disjoint_provenance_positives"], 0)
        self.assertEqual(audit["positive_scope"]["diagnostic_disjoint_provenance_positives"], 5)


if __name__ == "__main__":
    unittest.main()
