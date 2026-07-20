import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_connection_pair_universe import build_pair_universe


class ConnectionPairUniverseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        (self.root / "l1.md").write_text("Alpha one. Shared alpha.", encoding="utf-8")
        (self.root / "l2.md").write_text("Beta two. Shared beta.", encoding="utf-8")
        self.manifest_path = self.root / "manifest.json"
        self.inventory_path = self.root / "inventory.json"
        self.manifest = {
            "split": "development",
            "lectures": [
                {
                    "lecture_id": "l1",
                    "course_id": "c1",
                    "topic_id": "t1",
                    "sequence": 1,
                    "path": "l1.md",
                },
                {
                    "lecture_id": "l2",
                    "course_id": "c2",
                    "topic_id": "t2",
                    "sequence": 1,
                    "path": "l2.md",
                },
            ],
        }
        self.inventory = {
            "canonical_objects": [
                {
                    "canonical_ko_id": "a",
                    "canonical_name": "Alpha",
                    "canonical_type": "Concept",
                    "mentions": [
                        {
                            "mention_id": "m1",
                            "lecture_id": "l1",
                            "source_spans": ["Alpha one."],
                        }
                    ],
                },
                {
                    "canonical_ko_id": "b",
                    "canonical_name": "Beta",
                    "canonical_type": "Method",
                    "mentions": [
                        {
                            "mention_id": "m2",
                            "lecture_id": "l2",
                            "source_spans": ["Beta two."],
                        }
                    ],
                },
                {
                    "canonical_ko_id": "shared",
                    "canonical_name": "Shared",
                    "canonical_type": "Formula",
                    "mentions": [
                        {
                            "mention_id": "m3",
                            "lecture_id": "l1",
                            "source_spans": ["Shared alpha."],
                        },
                        {
                            "mention_id": "m4",
                            "lecture_id": "l2",
                            "source_spans": ["Shared beta."],
                        },
                    ],
                },
            ]
        }
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.inventory_path.write_text(json.dumps(self.inventory), encoding="utf-8")

    def build(self):
        return build_pair_universe(
            self.manifest,
            self.inventory,
            repository_root=self.root,
            source_manifest_path=self.manifest_path,
            canonical_inventory_path=self.inventory_path,
        )

    def test_generates_unique_cross_lecture_pairs_and_scope(self) -> None:
        universe = self.build()
        self.assertEqual(universe["counts"]["all_unique_unordered_pairs"], 3)
        self.assertEqual(universe["counts"]["eligible_cross_lecture_pairs"], 3)
        self.assertEqual(universe["counts"]["disjoint_provenance_pairs"], 1)
        self.assertEqual(universe["counts"]["overlap_bridge_pairs"], 2)
        self.assertEqual(universe["counts"]["cross_course_pairs"], 3)
        pair_ids = [pair["canonical_pair_id"] for pair in universe["pairs"]]
        self.assertEqual(len(pair_ids), len(set(pair_ids)))
        self.assertFalse(universe["gold_fields_present"])

    def test_rejects_nonexact_mention_span(self) -> None:
        self.inventory["canonical_objects"][0]["mentions"][0]["source_spans"] = [
            "Not in lecture"
        ]
        with self.assertRaisesRegex(ValueError, "source span is not exact"):
            self.build()


if __name__ == "__main__":
    unittest.main()
