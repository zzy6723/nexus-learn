from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_connection_discovery as runner


METHOD_COMMIT = "200b0d87d8a48077e6aa03da2cc6d87304512b0f"


class ConnectionDiscoveryRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selection = runner.load_json(runner.DEFAULT_SELECTION)
        cls.inventory = runner.load_json(runner.DEFAULT_INVENTORY)
        cls.catalogs = runner.load_json(runner.DEFAULT_CATALOGS)
        cls.items = runner.build_execution_items(cls.selection, cls.inventory, cls.catalogs)

    def invoke(self, run_dir: Path, *extra: str, response: dict | None = None):
        api = mock.Mock()
        if response is None:
            api.side_effect = AssertionError("API must not be called")
        else:
            api.return_value = response
        args = [
            "--method-commit", METHOD_COMMIT,
            "--run-dir", str(run_dir),
            *extra,
        ]
        with (
            mock.patch.object(runner, "git_commit", return_value=METHOD_COMMIT),
            mock.patch.object(runner, "git_dirty", return_value=False),
            mock.patch.object(runner, "call_deepseek", api),
        ):
            return runner.main(args), api

    def test_model_inputs_are_candidate_scoped_and_gold_free(self) -> None:
        self.assertEqual(len(self.items), 125)
        for item in self.items:
            model_input = item["model_input"]
            self.assertEqual(set(model_input), {"candidate_pair", "evidence_catalog"})
            self.assertEqual(
                runner._collect_keys(model_input) & runner.FORBIDDEN_MODEL_KEYS,
                set(),
            )
            pair = model_input["candidate_pair"]
            self.assertEqual(
                {pair["ko_a"]["canonical_ko_id"], pair["ko_b"]["canonical_ko_id"]},
                set(item["endpoint_ids"]),
            )

    def test_subset_dry_run_writes_no_api_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "dry"
            pair_id = self.items[0]["canonical_pair_id"]
            code, api = self.invoke(run_dir, "--only", pair_id, "--dry-run")
            self.assertEqual(code, 0)
            api.assert_not_called()
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "dry_run_complete")
            self.assertEqual(metadata["candidate_count"], 1)
            self.assertFalse(metadata["git_dirty_at_start"])
            rendered = list((run_dir / "rendered_inputs/pairs").glob("*.json"))
            self.assertEqual(len(rendered), 1)
            self.assertFalse(any((run_dir / "output/pairs").iterdir()))

    def test_valid_subset_response_completes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "formal"
            item = self.items[0]
            result = {
                "canonical_pair_id": item["canonical_pair_id"],
                "source_canonical_ko_id": item["endpoint_ids"][0],
                "target_canonical_ko_id": item["endpoint_ids"][1],
                "relation_type": "NO_RELATION",
                "evidence_ids": [],
                "rationale": "The supplied Evidence does not establish an edge.",
            }
            response = {
                "choices": [{"message": {"content": json.dumps({"result": result})}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            with mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                code, api = self.invoke(run_dir, "--only", item["canonical_pair_id"], response=response)
            self.assertEqual(code, 0)
            api.assert_called_once()
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "completed_subset")
            self.assertTrue(metadata["prediction_schema_valid"])

    def test_changed_endpoint_is_recorded_as_schema_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "invalid"
            item = self.items[0]
            result = {
                "canonical_pair_id": item["canonical_pair_id"],
                "source_canonical_ko_id": item["endpoint_ids"][0],
                "target_canonical_ko_id": "conn_dev_ko_999",
                "relation_type": "NO_RELATION",
                "evidence_ids": [],
                "rationale": "Invalid fixture.",
            }
            response = {"choices": [{"message": {"content": json.dumps({"result": result})}, "finish_reason": "stop"}]}
            with mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                code, _ = self.invoke(run_dir, "--only", item["canonical_pair_id"], response=response)
            self.assertEqual(code, 1)
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "prediction_schema_failed")
            self.assertEqual(metadata["completed_candidate_count"], 0)

    def test_no_overwrite_and_dirty_repository_fail_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "existing"
            run_dir.mkdir()
            code, _ = self.invoke(run_dir, "--dry-run")
            self.assertEqual(code, 1)
            fresh = Path(temporary) / "dirty"
            with (
                mock.patch.object(runner, "git_commit", return_value=METHOD_COMMIT),
                mock.patch.object(runner, "git_dirty", return_value=True),
            ):
                code = runner.main([
                    "--method-commit", METHOD_COMMIT,
                    "--run-dir", str(fresh),
                    "--dry-run",
                ])
            self.assertEqual(code, 1)
            self.assertFalse(fresh.exists())


if __name__ == "__main__":
    unittest.main()
