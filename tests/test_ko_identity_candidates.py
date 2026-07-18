from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import generate_ko_identity_candidates as generator


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"


class KOIdentityCandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = json.loads(
            (CHALLENGE / "mention_inventory.json").read_text(encoding="utf-8")
        )
        cls.ground_truth = json.loads(
            (CHALLENGE / "ground_truth.json").read_text(encoding="utf-8")
        )
        cls.normalization = json.loads(
            (ROOT / "benchmark" / "ko_name_normalization_v0_1.json").read_text()
        )
        cls.aliases = json.loads(
            (ROOT / "benchmark" / "ko_aliases_v0_1.json").read_text()
        )

    def build(self):
        return generator.build_candidate_bundle(
            self.inventory, self.normalization, self.aliases
        )

    def test_candidates_are_type_safe_gold_blind_and_deterministic(self) -> None:
        first, first_audit = self.build()
        second, second_audit = self.build()

        self.assertEqual(first, second)
        self.assertEqual(first_audit, second_audit)
        for candidate in first["candidates"]:
            self.assertEqual(candidate["mention_a"]["type"], candidate["mention_b"]["type"])
            self.assertFalse(
                {"canonical_id", "gold", "identity_label"} & set(candidate)
            )

    def test_challenge_candidate_recall_is_complete_and_homonym_is_selected(self) -> None:
        bundle, _ = self.build()
        selected = {
            frozenset((item["mention_a"]["mention_id"], item["mention_b"]["mention_id"]))
            for item in bundle["candidates"]
        }
        gold_same = {
            frozenset(pair)
            for cluster in self.ground_truth["clusters"]
            for index, left in enumerate(cluster["mention_ids"])
            for pair in [(left, right) for right in cluster["mention_ids"][index + 1 :]]
        }

        self.assertTrue(gold_same <= selected)
        self.assertIn(
            frozenset(("ko_mention_dev_005", "ko_mention_dev_017")), selected
        )

    def test_cli_is_no_overwrite_and_hash_bound(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "candidates"
        args = ["--output-dir", str(output)]

        self.assertEqual(generator.main(args), 0)
        self.assertEqual(generator.main(args), 1)
        marker = json.loads(
            (output / "candidate_generation_complete.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marker["status"], "final")
        self.assertEqual(set(marker["artifacts"]), {"candidates", "audit", "metadata"})


if __name__ == "__main__":
    unittest.main()
