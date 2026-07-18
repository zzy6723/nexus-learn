from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_ko_identity_candidates as generator
from scripts import run_context_ko_resolution as runner


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"


class ContextKOResolutionRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate_dir = self.root / "candidates"
        self.assertEqual(
            generator.main(["--output-dir", str(self.candidate_dir)]), 0
        )

    def args(self, run_dir: Path, *extra: str):
        return runner.parse_args(
            [
                "--candidate-dir", str(self.candidate_dir),
                "--lecture-inventory", str(CHALLENGE / "lecture_inventory.json"),
                "--method-commit", "a" * 40,
                "--run-dir", str(run_dir),
                *extra,
            ]
        )

    def response_for_payload(self, *, api_key, payload):
        model_input = json.loads(payload["messages"][1]["content"])
        mentions = model_input["unordered_mentions"]
        lecture = model_input["lectures"][0]
        result = {
            "candidate_id": model_input["candidate_id"],
            "mention_a": mentions[0]["mention_id"],
            "mention_b": mentions[1]["mention_id"],
            "decision": "SAME_OBJECT",
            "evidence_spans": [{"lecture_id": lecture["lecture_id"], "span": mentions[0]["source_spans"][0]}],
            "rationale": "The supplied contexts identify the same object.",
        }
        return {
            "id": "mock", "model": "deepseek-v4-flash",
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}],
            "usage": {},
        }

    def test_dry_run_is_candidate_scoped_gold_free_and_no_overwrite(self) -> None:
        run_dir = self.root / "dry"
        args = self.args(run_dir, "--dry-run")

        self.assertEqual(runner.run(args, repository_reader=lambda: ("b" * 40, True)), 0)
        self.assertEqual(runner.run(args, repository_reader=lambda: ("b" * 40, True)), 1)
        rendered = sorted((run_dir / "rendered_inputs" / "pairs").glob("*.json"))
        self.assertEqual(len(rendered), 11)
        text = "\n".join(path.read_text(encoding="utf-8") for path in rendered)
        self.assertNotIn("canonical_ko_dev", text)
        self.assertNotIn("identity_rationale", text)

    def test_mock_success_is_complete_and_hash_bound(self) -> None:
        run_dir = self.root / "success"
        args = self.args(run_dir)
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code = runner.run(
                args,
                api_call=self.response_for_payload,
                repository_reader=lambda: ("a" * 40, False),
            )

        self.assertEqual(code, 0)
        metadata = json.loads((run_dir / "metadata" / "run_metadata.json").read_text())
        self.assertEqual(metadata["run_status"], "completed")
        self.assertTrue(metadata["prediction_schema_valid"])
        self.assertEqual(metadata["completed_candidate_count"], 11)
        marker = json.loads((run_dir / "resolution_complete.json").read_text())
        self.assertEqual(marker["status"], "final")

    def test_endpoint_substitution_is_recorded_as_failure(self) -> None:
        def changed_endpoint(*, api_key, payload):
            response = self.response_for_payload(api_key=api_key, payload=payload)
            content = json.loads(response["choices"][0]["message"]["content"])
            content["mention_b"] = "unknown_mention"
            response["choices"][0]["message"]["content"] = json.dumps(content)
            return response

        run_dir = self.root / "endpoint_failure"
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code = runner.run(
                self.args(run_dir), api_call=changed_endpoint,
                repository_reader=lambda: ("a" * 40, False),
            )

        self.assertEqual(code, 1)
        metadata = json.loads((run_dir / "metadata" / "run_metadata.json").read_text())
        self.assertEqual(metadata["run_status"], "candidate_failed")
        self.assertIn("changed mention_b", metadata["error"])
        self.assertFalse((run_dir / "resolution_complete.json").exists())

    def test_nonexact_evidence_is_rejected(self) -> None:
        def nonexact(*, api_key, payload):
            response = self.response_for_payload(api_key=api_key, payload=payload)
            content = json.loads(response["choices"][0]["message"]["content"])
            content["evidence_spans"][0]["span"] = "paraphrased evidence"
            response["choices"][0]["message"]["content"] = json.dumps(content)
            return response

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code = runner.run(
                self.args(self.root / "nonexact"), api_call=nonexact,
                repository_reader=lambda: ("a" * 40, False),
            )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
