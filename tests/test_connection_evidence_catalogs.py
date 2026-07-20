import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_connection_evidence_catalogs import build_catalogs, semantic_blocks


class ConnectionEvidenceCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.lecture = self.root / "lecture.md"
        self.lecture.write_text(
            "# Title\n\n**Course:** C\n\n---\n\nFirst block.\n\n\\[\nx=1.\n\\]\n",
            encoding="utf-8",
        )
        self.manifest_path = self.root / "manifest.json"
        self.universe_path = self.root / "universe.json"
        self.manifest = {
            "lectures": [
                {
                    "lecture_id": "l1",
                    "path": "lecture.md",
                    "course_id": "c1",
                    "topic_id": "t1",
                    "sequence": 1,
                }
            ]
        }
        self.universe = {
            "split": "development",
            "gold_fields_present": False,
            "pairs": [
                {
                    "canonical_pair_id": "p1",
                    "ko_a": {"canonical_ko_id": "a", "lecture_ids": ["l1"]},
                    "ko_b": {"canonical_ko_id": "b", "lecture_ids": ["l1"]},
                }
            ],
        }
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.universe_path.write_text(json.dumps(self.universe), encoding="utf-8")

    def test_semantic_blocks_preserve_exact_markdown(self) -> None:
        text = self.lecture.read_text(encoding="utf-8")
        blocks = semantic_blocks(text)
        self.assertEqual(blocks, ["First block.", "\\[\nx=1.\n\\]"])
        self.assertTrue(all(block in text for block in blocks))

    def test_catalog_is_pair_scoped_and_gold_free(self) -> None:
        result = build_catalogs(
            self.manifest,
            self.universe,
            repository_root=self.root,
            source_manifest_path=self.manifest_path,
            pair_universe_path=self.universe_path,
        )
        self.assertEqual(result["counts"]["catalogs"], 1)
        self.assertEqual(result["counts"]["evidence_items"], 2)
        self.assertEqual(
            [item["evidence_id"] for item in result["catalogs"][0]["evidence_items"]],
            ["evidence_001", "evidence_002"],
        )
        self.assertFalse(result["gold_fields_present"])


if __name__ == "__main__":
    unittest.main()
