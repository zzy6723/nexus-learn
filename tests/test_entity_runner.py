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

    def make_execution_manifest(self) -> Path:
        run_dir = self.run_root / "bound_run"
        entity_dir = run_dir / "entity_predictions"
        source_manifest_path = entity_dir / "source_manifest.json"
        source_manifest = {
            "artifact_type": "entity_prediction_source_manifest",
            "version": "v0.1",
            "status": "prepared_pending_entity_reruns",
            "method_commit": FREEZE_COMMIT,
            "rerun_required_lecture_ids": ["calculus_001"],
        }
        source_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        source_manifest_path.write_text(
            json.dumps(source_manifest, indent=2) + "\n", encoding="utf-8"
        )

        prompt_path = (
            ROOT
            / "experiments"
            / "entity_extraction"
            / "002_prompt_refinement"
            / "prompt.md"
        )
        lecture_path = ROOT / "benchmark" / "lectures" / "development" / "calculus_001.md"
        lecture_text = runner.extract_lecture_body(
            lecture_path.read_text(encoding="utf-8")
        )
        manifest = {
            "artifact_type": "predicted_ko_relation_execution_manifest",
            "version": "v0.1",
            "status": "prepared_pending_entity_reruns",
            "experiment": "002B-1",
            "split": "development_v0_1",
            "method_commit": FREEZE_COMMIT,
            "repository_state": {
                "head_commit": FREEZE_COMMIT,
                "worktree_clean": True,
            },
            "frozen_methods": {
                "entity_prompt": {
                    "path": runner.display_path(prompt_path),
                    "sha256": runner.sha256_file(prompt_path),
                },
                "implementation": [{
                    "path": runner.display_path(Path(runner.__file__).resolve()),
                    "sha256": runner.sha256_file(Path(runner.__file__).resolve()),
                }],
            },
            "entity_execution": {
                "provider": runner.PROVIDER,
                "model": runner.DEFAULT_MODEL,
                "input_split": "development",
                "request_parameters": {
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "max_tokens": 4096,
                    "stream": False,
                    "response_format": {"type": "json_object"},
                    "thinking": {"type": "disabled"},
                },
                "source_manifest": str(source_manifest_path),
                "source_manifest_sha256": runner.sha256_file(source_manifest_path),
                "rerun_required_lecture_ids": ["calculus_001"],
            },
            "benchmark": {
                "lecture_model_text_sha256": {
                    "calculus_001": runner.sha256_text(lecture_text),
                }
            },
        }
        manifest_path = run_dir / "execution_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return manifest_path

    def bound_args(self, manifest_path: Path, *extra: str) -> list[str]:
        return [
            "--experiment",
            "002_prompt_refinement",
            "--split",
            "development",
            "--ground-truth",
            "benchmark/ground_truth/development_v0_1.json",
            "--only",
            "calculus_001",
            "--execution-manifest",
            str(manifest_path),
            *extra,
        ]

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

    def test_manifest_bound_success_uses_frozen_run_directories(self) -> None:
        manifest_path = self.make_execution_manifest()
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code, api_mock = self.invoke(
                self.bound_args(manifest_path),
                response=self.response(self.valid_prediction()),
            )

        self.assertEqual(code, 0)
        api_mock.assert_called_once()
        entity_dir = manifest_path.parent / "entity_predictions"
        metadata = json.loads(
            (entity_dir / "metadata" / "calculus_001.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(metadata["run_status"], "completed")
        self.assertEqual(
            metadata["execution_binding"]["execution_manifest_sha256"],
            runner.sha256_file(manifest_path),
        )
        self.assertEqual(
            metadata["execution_binding"]["method_commit"], FREEZE_COMMIT
        )
        self.assertTrue(
            (entity_dir / "output" / "calculus_001.json").is_file()
        )

    def test_manifest_bound_run_rejects_stale_source_manifest(self) -> None:
        manifest_path = self.make_execution_manifest()
        source_manifest_path = (
            manifest_path.parent / "entity_predictions" / "source_manifest.json"
        )
        source_manifest_path.write_text("{}\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code, api_mock = self.invoke(self.bound_args(manifest_path))

        self.assertEqual(code, 2)
        api_mock.assert_not_called()

    def test_manifest_bound_holdout_run_uses_frozen_input_split(self) -> None:
        manifest_path = self.make_execution_manifest()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["split"] = "locked_reuse_v0_1"
        manifest["entity_execution"]["input_split"] = "holdout"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        ground_truth_path = self.run_root / "locked_reuse_oracle.json"
        ground_truth_path.write_text(
            json.dumps({
                "split": "holdout",
                "lectures": [{
                    "lecture_id": "calculus_001",
                    "path": "benchmark/lectures/development/calculus_001.md",
                }],
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        args = self.bound_args(manifest_path)
        args[args.index("development")] = "holdout"
        args[args.index("benchmark/ground_truth/development_v0_1.json")] = str(
            ground_truth_path
        )

        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code, api_mock = self.invoke(
                args,
                response=self.response(self.valid_prediction()),
            )

        self.assertEqual(code, 0)
        api_mock.assert_called_once()
        metadata_path = (
            manifest_path.parent
            / "entity_predictions"
            / "metadata"
            / "calculus_001.json"
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["split"], "holdout")


if __name__ == "__main__":
    unittest.main()
