from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_entity_extraction as runner


ROOT = Path(__file__).resolve().parents[1]
FREEZE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


class EntityRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.run_root = Path(temporary_directory.name)

    def args(self, *extra: str) -> list[str]:
        return [
            "--experiment",
            "002_prompt_refinement",
            "--split",
            "development",
            "--ground-truth",
            "benchmark/ground_truth/development_v0_1.json",
            "--only",
            "calculus_001",
            "--output-dir",
            str(self.run_root / "output"),
            "--rendered-inputs-dir",
            str(self.run_root / "rendered_inputs"),
            "--raw-responses-dir",
            str(self.run_root / "raw_responses"),
            "--metadata-dir",
            str(self.run_root / "metadata"),
            *extra,
        ]

    def invoke(self, args: list[str], *, response=None):
        api_mock = mock.Mock()
        if response is None:
            api_mock.side_effect = AssertionError("API must not be called")
        else:
            api_mock.return_value = response
        with (
            mock.patch.object(runner, "git_commit", return_value=FREEZE_COMMIT),
            mock.patch.object(runner, "git_dirty", return_value=False),
            mock.patch.object(runner, "call_deepseek", api_mock),
        ):
            code = runner.main(args)
        return code, api_mock

    def read(self, directory: str) -> dict:
        return json.loads(
            (self.run_root / directory / "calculus_001.json").read_text(
                encoding="utf-8"
            )
        )

    @staticmethod
    def response(prediction: dict) -> dict:
        return {
            "id": "synthetic-request-id",
            "model": "synthetic-model",
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps(prediction)},
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    @staticmethod
    def valid_prediction() -> dict:
        return {
            "lecture_id": "calculus_001",
            "knowledge_objects": [{
                "id": "gradient",
                "name": "Gradient",
                "type": "Concept",
                "aliases": [],
                "short_definition": "A vector of partial derivatives.",
                "source_span": "The gradient",
            }],
        }

    def test_dry_run_records_complete_prepared_metadata(self) -> None:
        code, api_mock = self.invoke(self.args("--dry-run"))

        self.assertEqual(code, 0)
        api_mock.assert_not_called()
        metadata = self.read("metadata")
        self.assertEqual(metadata["run_status"], "dry_run_complete")
        self.assertEqual(metadata["git_commit_at_start"], FREEZE_COMMIT)
        self.assertFalse(metadata["git_dirty_at_start"])
        self.assertIn("request_payload_sha256", metadata)
        self.assertTrue((self.run_root / "rendered_inputs" / "calculus_001.json").is_file())

    def test_success_records_schema_and_artifact_hashes(self) -> None:
        response = self.response(self.valid_prediction())
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code, api_mock = self.invoke(self.args(), response=response)

        self.assertEqual(code, 0)
        api_mock.assert_called_once()
        metadata = self.read("metadata")
        self.assertEqual(metadata["run_status"], "completed")
        self.assertTrue(metadata["request_success"])
        self.assertTrue(metadata["json_parse_success"])
        self.assertTrue(metadata["prediction_schema_valid"])
        self.assertEqual(metadata["request_id"], "synthetic-request-id")
        self.assertEqual(
            metadata["raw_response_sha256"],
            runner.sha256_file(self.run_root / "raw_responses" / "calculus_001.json"),
        )
        self.assertEqual(
            metadata["prediction_sha256"],
            runner.sha256_file(self.run_root / "output" / "calculus_001.json"),
        )

    def test_schema_failure_preserves_raw_and_parsed_outputs(self) -> None:
        invalid = self.valid_prediction()
        invalid["knowledge_objects"][0]["type"] = "InvalidType"
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code, _ = self.invoke(self.args(), response=self.response(invalid))

        self.assertEqual(code, 1)
        metadata = self.read("metadata")
        self.assertEqual(metadata["run_status"], "prediction_schema_failed")
        self.assertTrue(metadata["request_success"])
        self.assertTrue(metadata["json_parse_success"])
        self.assertFalse(metadata["prediction_schema_valid"])
        self.assertTrue(metadata["prediction_schema_error"])
        self.assertTrue((self.run_root / "raw_responses" / "calculus_001.json").is_file())
        self.assertTrue((self.run_root / "output" / "calculus_001.json").is_file())


if __name__ == "__main__":
    unittest.main()
