from __future__ import annotations

import copy
import unittest

from scripts import create_ko_locked_reuse_source_manifest as creator


class KOLockedReuseSourceManifestTest(unittest.TestCase):
    def test_selected_source_is_final_and_explicitly_not_unseen(self) -> None:
        manifest = creator.build_manifest(creator.DEFAULT_SOURCE_RUN)

        self.assertEqual(manifest["status"], "final")
        self.assertEqual(manifest["data_role"], "locked_reuse")
        self.assertIn("not an unseen holdout", manifest["claim_boundary"])
        self.assertTrue(
            manifest["selection_order"]["selected_before_context_resolver_execution"]
        )
        self.assertEqual(manifest["counts"]["lectures"], 6)
        self.assertEqual(manifest["counts"]["knowledge_object_mentions"], 49)
        self.assertEqual(manifest["counts"]["entity_outputs"], 6)

    def test_changed_manifest_is_rejected(self) -> None:
        expected = creator.build_manifest(creator.DEFAULT_SOURCE_RUN)
        changed = copy.deepcopy(expected)
        changed["data_role"] = "unseen_holdout"

        with self.assertRaisesRegex(creator.SourceManifestError, "stale or changed"):
            creator.validate_existing(changed, expected)


if __name__ == "__main__":
    unittest.main()
