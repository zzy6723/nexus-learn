from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_two_stage_connection_discovery as runner


METHOD_COMMIT = "91857e274114959d0297f1224d2b9ab39bf6e125"


def api_response(result: dict, *, tokens: int = 5) -> dict:
    return {
        "choices": [
            {
                "message": {"content": json.dumps({"result": result})},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": tokens},
    }


class TwoStageConnectionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        args = runner.parse_args([
            "--method-commit", METHOD_COMMIT,
            "--run-dir", "unused",
        ])
        _, cls.items = runner.load_items(args)

    def invoke(self, run_dir: Path, *extra: str, responses: list[dict] | None = None):
        api = mock.Mock()
        if responses is None:
            api.side_effect = AssertionError("API must not be called")
        else:
            api.side_effect = responses
        with (
            mock.patch.object(runner.base, "git_commit", return_value=METHOD_COMMIT),
            mock.patch.object(runner.base, "git_dirty", return_value=False),
            mock.patch.object(runner.base, "call_deepseek", api),
            mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}),
        ):
            code = runner.main([
                "--method-commit", METHOD_COMMIT,
                "--run-dir", str(run_dir),
                *extra,
            ])
        return code, api

    def gate_result(
        self,
        item: dict,
        decision: str,
        evidence_ids: list[str],
    ) -> dict:
        return {
            "canonical_pair_id": item["canonical_pair_id"],
            "ko_a_id": item["endpoint_ids"][0],
            "ko_b_id": item["endpoint_ids"][1],
            "decision": decision,
            "evidence_ids": evidence_ids,
            "rationale": "The selected Evidence directly connects the endpoints."
            if decision == "DIRECT_CONNECTION"
            else "No supplied Evidence directly connects the endpoints.",
        }

    def typed_result(
        self,
        item: dict,
        relation_type: str,
        evidence_ids: list[str],
    ) -> dict:
        return {
            "canonical_pair_id": item["canonical_pair_id"],
            "source_canonical_ko_id": item["endpoint_ids"][0],
            "target_canonical_ko_id": item["endpoint_ids"][1],
            "relation_type": relation_type,
            "evidence_ids": evidence_ids,
            "rationale": "The selected Evidence establishes the typed edge.",
        }

    def test_gate_inputs_are_candidate_scoped_and_gold_free(self) -> None:
        self.assertEqual(len(self.items), 125)
        for item in self.items:
            model_input = runner.gate_model_input(item)
            self.assertEqual(set(model_input), {"candidate_pair", "evidence_catalog"})
            self.assertFalse(
                runner.base._collect_keys(model_input)
                & runner.base.FORBIDDEN_MODEL_KEYS
            )

    def test_direct_cli_help_is_available(self) -> None:
        result = subprocess.run(
            [sys.executable, str(runner.ROOT / "scripts/run_two_stage_connection_discovery.py"), "--help"],
            cwd=runner.ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("two-stage direct-edge gating", result.stdout)

    def test_dry_run_renders_only_stage_a(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "dry"
            item = self.items[0]
            code, api = self.invoke(
                run_dir,
                "--only", item["canonical_pair_id"],
                "--dry-run",
            )
            self.assertEqual(code, 0)
            api.assert_not_called()
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "dry_run_complete")
            self.assertEqual(metadata["candidate_count"], 1)
            self.assertIsNone(metadata["stage_b_request_payload_set_sha256"])
            self.assertEqual(
                len(list((run_dir / "stage_a/rendered_inputs/pairs").glob("*.json"))),
                1,
            )
            self.assertEqual(
                len(list((run_dir / "stage_b/rendered_inputs/pairs").glob("*.json"))),
                0,
            )

    def test_negative_gate_skips_typing_and_emits_no_relation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "negative"
            item = self.items[0]
            gate = self.gate_result(item, "NO_RELATION", [])
            code, api = self.invoke(
                run_dir,
                "--only", item["canonical_pair_id"],
                responses=[api_response(gate)],
            )
            self.assertEqual(code, 0)
            self.assertEqual(api.call_count, 1)
            output = json.loads(
                (run_dir / "output/canonical_connection_predictions.json").read_text()
            )
            self.assertEqual(output["results"][0]["relation_type"], "NO_RELATION")
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["stage_a_positive_count"], 0)
            self.assertEqual(metadata["stage_b_completed_count"], 0)

    def test_positive_gate_limits_stage_b_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "positive"
            item = self.items[0]
            evidence_id = item["model_input"]["evidence_catalog"][0]["evidence_id"]
            gate = self.gate_result(item, "DIRECT_CONNECTION", [evidence_id])
            typed = self.typed_result(item, "APPLIED_IN", [evidence_id])
            code, api = self.invoke(
                run_dir,
                "--only", item["canonical_pair_id"],
                responses=[api_response(gate), api_response(typed)],
            )
            self.assertEqual(code, 0)
            self.assertEqual(api.call_count, 2)
            rendered = json.loads(
                next((run_dir / "stage_b/rendered_inputs/pairs").glob("*.json")).read_text()
            )
            model_input = json.loads(rendered["messages"][1]["content"])
            self.assertEqual(set(model_input), {"candidate_pair", "selected_evidence"})
            self.assertEqual(
                [item["evidence_id"] for item in model_input["selected_evidence"]],
                [evidence_id],
            )
            self.assertNotIn("rationale", model_input)
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "completed_subset")
            self.assertEqual(metadata["stage_a_positive_count"], 1)
            self.assertEqual(metadata["stage_b_completed_count"], 1)

    def test_positive_gate_without_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "invalid_gate"
            item = self.items[0]
            gate = self.gate_result(item, "DIRECT_CONNECTION", [])
            code, _ = self.invoke(
                run_dir,
                "--only", item["canonical_pair_id"],
                responses=[api_response(gate)],
            )
            self.assertEqual(code, 1)
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "stage_a_failed")
            self.assertFalse(metadata["prediction_schema_valid"])

    def test_stage_b_cannot_expand_gate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "invalid_typed"
            item = self.items[0]
            evidence = item["model_input"]["evidence_catalog"]
            self.assertGreaterEqual(len(evidence), 2)
            gate_id = evidence[0]["evidence_id"]
            extra_id = evidence[1]["evidence_id"]
            gate = self.gate_result(item, "DIRECT_CONNECTION", [gate_id])
            typed = self.typed_result(item, "APPLIED_IN", [extra_id])
            code, _ = self.invoke(
                run_dir,
                "--only", item["canonical_pair_id"],
                responses=[api_response(gate), api_response(typed)],
            )
            self.assertEqual(code, 1)
            metadata = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(metadata["run_status"], "stage_b_failed")
            self.assertFalse(metadata["prediction_schema_valid"])

    def test_no_overwrite_and_dirty_state_fail_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary) / "existing"
            existing.mkdir()
            code, api = self.invoke(existing, "--dry-run")
            self.assertEqual(code, 1)
            api.assert_not_called()
            dirty = Path(temporary) / "dirty"
            with (
                mock.patch.object(runner.base, "git_commit", return_value=METHOD_COMMIT),
                mock.patch.object(runner.base, "git_dirty", return_value=True),
            ):
                code = runner.main([
                    "--method-commit", METHOD_COMMIT,
                    "--run-dir", str(dirty),
                    "--dry-run",
                ])
            self.assertEqual(code, 1)
            self.assertFalse(dirty.exists())


if __name__ == "__main__":
    unittest.main()
