from __future__ import annotations

import unittest
import json
import tempfile
from itertools import combinations
from pathlib import Path

from scripts import finalize_ko_locked_reuse_benchmark as finalizer
from scripts import generate_ko_identity_candidates as generator


class KOLockedReuseBenchmarkTest(unittest.TestCase):
    def test_real_bundle_has_frozen_denominators_and_claim_boundary(self) -> None:
        marker = finalizer.build_marker(finalizer.DEFAULT_ROOT)

        self.assertEqual(marker["status"], "final")
        self.assertEqual(marker["data_role"], "locked_reuse")
        self.assertIn("not unseen", marker["claim_boundary"])
        self.assertEqual(marker["counts"]["mentions"], 49)
        self.assertEqual(marker["counts"]["canonical_clusters"], 46)
        self.assertEqual(marker["counts"]["same_object_pairs"], 4)
        self.assertEqual(marker["counts"]["nonexact_source_spans"], 14)

    def test_candidate_rules_recover_all_four_identities_and_two_hard_negatives(self) -> None:
        inventory = json.loads((finalizer.DEFAULT_ROOT / "mention_inventory.json").read_text())
        ground_truth = json.loads((finalizer.DEFAULT_ROOT / "ground_truth.json").read_text())
        normalization = json.loads(
            (finalizer.ROOT / "benchmark" / "ko_name_normalization_v0_1.json").read_text()
        )
        aliases = json.loads(
            (finalizer.ROOT / "benchmark" / "ko_aliases_v0_1.json").read_text()
        )
        bundle, _ = generator.build_candidate_bundle(inventory, normalization, aliases)
        selected = {
            frozenset((item["mention_a"]["mention_id"], item["mention_b"]["mention_id"]))
            for item in bundle["candidates"]
        }
        gold_same = {
            frozenset(pair)
            for cluster in ground_truth["clusters"]
            for pair in combinations(cluster["mention_ids"], 2)
        }

        self.assertEqual(bundle["counts"]["selected_candidates"], 6)
        self.assertEqual(len(gold_same), 4)
        self.assertTrue(gold_same <= selected)
        self.assertEqual(len(selected - gold_same), 2)

    def test_cli_accepts_locked_reuse_benchmark_marker(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output_dir = Path(temporary.name) / "candidates"
        source_manifest = json.loads(
            (finalizer.DEFAULT_ROOT / "source_manifest.json").read_text()
        )
        lecture_path = finalizer.ROOT / source_manifest["artifacts"]["lecture_inventory"]["path"]

        return_code = generator.main(
            [
                "--mention-inventory", str(finalizer.DEFAULT_ROOT / "mention_inventory.json"),
                "--lecture-inventory", str(lecture_path),
                "--benchmark-marker", str(finalizer.DEFAULT_ROOT / "benchmark_complete.json"),
                "--output-dir", str(output_dir),
            ]
        )

        self.assertEqual(return_code, 0)


if __name__ == "__main__":
    unittest.main()
