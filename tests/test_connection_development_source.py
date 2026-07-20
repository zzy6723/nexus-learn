import json
import unittest
from pathlib import Path

from scripts.generate_connection_pair_universe import build_pair_universe


class ConnectionDevelopmentSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.bundle = cls.root / "benchmark/connection_discovery/development_v0_1"
        cls.manifest_path = cls.bundle / "source_manifest.json"
        cls.inventory_path = cls.bundle / "oracle_canonical_inventory.json"
        cls.universe_path = cls.bundle / "pair_universe.json"

    def test_stored_pair_universe_matches_deterministic_generation(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        inventory = json.loads(self.inventory_path.read_text(encoding="utf-8"))
        stored = json.loads(self.universe_path.read_text(encoding="utf-8"))
        regenerated = build_pair_universe(
            manifest,
            inventory,
            repository_root=self.root,
            source_manifest_path=self.manifest_path.relative_to(self.root),
            canonical_inventory_path=self.inventory_path.relative_to(self.root),
        )
        self.assertEqual(regenerated, stored)

    def test_source_meets_003_0b_structural_targets(self) -> None:
        universe = json.loads(self.universe_path.read_text(encoding="utf-8"))
        counts = universe["counts"]
        self.assertEqual(counts["lectures"], 6)
        self.assertEqual(counts["courses"], 3)
        self.assertEqual(counts["topics"], 6)
        self.assertEqual(counts["canonical_knowledge_objects"], 29)
        self.assertEqual(counts["mentions"], 44)
        self.assertEqual(counts["source_spans"], 44)
        self.assertEqual(counts["eligible_cross_lecture_pairs"], 387)
        self.assertGreater(counts["disjoint_provenance_pairs"], 0)
        self.assertGreater(counts["overlap_bridge_pairs"], 0)
        self.assertGreater(counts["same_course_cross_lecture_pairs"], 0)
        self.assertGreater(counts["cross_course_pairs"], 0)
        self.assertFalse(universe["gold_fields_present"])


if __name__ == "__main__":
    unittest.main()
