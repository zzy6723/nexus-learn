from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_connection_candidate_validation import (
    DEFAULT_FREEZE_MANIFEST,
    DEFAULT_RUNS_ROOT,
    METHODS,
    FinalizationError,
    build_comparison,
    load_method_result,
    write_finalization,
)


METHOD_COMMIT = "f8ba8291fdd9d71eb09ba3ab42f7b6198c64ccb7"


class ConnectionCandidateFinalizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = [
            load_method_result(DEFAULT_RUNS_ROOT, method, METHOD_COMMIT)
            for method in METHODS
        ]
        cls.comparison = build_comparison(
            rows=cls.rows,
            method_commit=METHOD_COMMIT,
            freeze_manifest_path=DEFAULT_FREEZE_MANIFEST,
        )

    def test_comparison_selects_limited_primary_route(self) -> None:
        decision = self.comparison["decision"]
        self.assertEqual(decision["selected_method"], "overlap_bridge_v0.1")
        self.assertIn("provenance shortcut", decision["scope_limit"])
        rows = {item["method"]: item for item in self.comparison["methods"]}
        self.assertEqual(rows["overlap_bridge"]["selected_pairs"], 125)
        self.assertEqual(
            rows["lexical_only"]["diagnostic_compositional_positive_recall"],
            0.8,
        )

    def test_completion_is_hash_bound_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            comparison_path, completion_path = write_finalization(
                output_dir=output_dir,
                comparison=self.comparison,
                method_commit=METHOD_COMMIT,
                freeze_manifest_path=DEFAULT_FREEZE_MANIFEST,
            )
            completion = json.loads(completion_path.read_text())
            self.assertEqual(completion["status"], "complete_with_scope_limitation")
            self.assertTrue(comparison_path.is_file())
            with self.assertRaises(FinalizationError):
                write_finalization(
                    output_dir=output_dir,
                    comparison=self.comparison,
                    method_commit=METHOD_COMMIT,
                    freeze_manifest_path=DEFAULT_FREEZE_MANIFEST,
                )


if __name__ == "__main__":
    unittest.main()
