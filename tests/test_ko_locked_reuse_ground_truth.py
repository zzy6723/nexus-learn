from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import create_ko_locked_reuse_ground_truth as creator


ROOT = Path(__file__).resolve().parents[1]
LOCKED = ROOT / "benchmark" / "ko_canonicalization" / "locked_reuse_v0_1"


class KOLockedReuseGroundTruthTest(unittest.TestCase):
    def test_reviewed_plan_materializes_complete_type_safe_partition(self) -> None:
        inventory_path = LOCKED / "mention_inventory.json"
        inventory = json.loads(inventory_path.read_text())
        plan = json.loads((LOCKED / "ground_truth_annotation_plan.json").read_text())

        ground_truth = creator.build_ground_truth(inventory, plan, inventory_path)

        clusters = ground_truth["clusters"]
        assigned = [member for cluster in clusters for member in cluster["mention_ids"]]
        self.assertEqual(len(clusters), 46)
        self.assertEqual(len(assigned), 49)
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(
            sorted(len(cluster["mention_ids"]) for cluster in clusters if len(cluster["mention_ids"]) > 1),
            [2, 3],
        )
        self.assertTrue(all(cluster["annotation_status"] == "final" for cluster in clusters))


if __name__ == "__main__":
    unittest.main()
