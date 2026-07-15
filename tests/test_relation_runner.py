from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts import align_predicted_kos as aligner
from scripts import normalize_predicted_kos as normalizer
from scripts import project_recoverable_relation_pairs as projector
from scripts import run_relation_extraction as runner
from tests.predicted_ko_fixture_support import FIXTURES, read_json


ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH = ROOT / "benchmark" / "ground_truth" / "relations_development_v0_1.json"
ARTIFACT_NAME = "relations_development_v0_1"
FREEZE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
PREDICTED_KO_SHARED = FIXTURES / "shared"


class RelationRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def runner_args(self, run_name: str, *extra: str) -> list[str]:
        return [
            "--ground-truth",
            str(GROUND_TRUTH),
            "--run-dir",
            str(self.temporary_root / run_name),
            *extra,
        ]

    def invoke(
        self,
        args: list[str],
        *,
        api_response: dict[str, Any] | None = None,
        api_error: RuntimeError | None = None,
    ) -> tuple[int, mock.Mock]:
        api_mock = mock.Mock()
        if api_error is not None:
            api_mock.side_effect = api_error
        elif api_response is not None:
            api_mock.return_value = api_response
        else:
            api_mock.side_effect = AssertionError(
                "call_deepseek must not be called during this test"
            )

        with (
            mock.patch.object(runner, "git_commit", return_value=FREEZE_COMMIT),
            mock.patch.object(runner, "git_dirty", return_value=False),
            mock.patch.object(runner, "call_deepseek", api_mock),
        ):
            return_code = runner.main(args)
        return return_code, api_mock

    def build_matched_projection(self) -> Path:
        oracle = read_json(PREDICTED_KO_SHARED / "synthetic_oracle_inventory.json")
        predicted = normalizer.normalize_prediction_files(
            [PREDICTED_KO_SHARED / "synthetic_predicted_inventory.json"]
        )
        lectures = read_json(PREDICTED_KO_SHARED / "synthetic_lectures.json")
        for lecture in lectures["lectures"]:
            lecture["text"] = lecture["text"].strip() + "\n"
        relation = read_json(PREDICTED_KO_SHARED / "synthetic_original_ground_truth.json")
        alignment = aligner.align_inventories(
            oracle,
            predicted,
            lectures,
            oracle_inventory_sha256=projector.artifact_sha256(oracle),
            predicted_inventory_sha256=projector.artifact_sha256(predicted),
        )["alignment"]
        projection_dir = self.temporary_root / "projection"
        artifacts = projector.project_artifacts(
            relation,
            oracle,
            predicted,
            alignment,
            lectures,
            matched_ko_path=str(projection_dir / "matched_knowledge_objects.json"),
            relation_prompt_sha256=runner.sha256_file(
                ROOT
                / "experiments"
                / "relation_extraction"
                / "002_prompt_refinement"
                / "prompt.md"
            ),
            relation_schema_sha256=runner.sha256_file(
                ROOT / "docs" / "decisions" / "004-relation-schema.md"
            ),
        )
        projection_dir.mkdir(parents=True)
        for filename, value in artifacts.items():
            (projection_dir / filename).write_text(
                projector.serialize_json(value), encoding="utf-8"
            )
        return projection_dir

    @staticmethod
    def artifact_path(run_dir: Path, artifact_type: str, suffix: str = ".json") -> Path:
        return run_dir / artifact_type / f"{ARTIFACT_NAME}{suffix}"

    @staticmethod
    def read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_model_input_contains_only_allowed_fields(self) -> None:
        relation_ground_truth = runner.load_relation_ground_truth(GROUND_TRUTH)
        registry, lecture_paths, _ = runner.load_knowledge_object_registry(
            relation_ground_truth["knowledge_object_ground_truths"]
        )
        model_input, candidate_members, _ = runner.build_model_input(
            relation_ground_truth,
            registry,
            lecture_paths,
        )
        audit = runner.validate_model_input(model_input, candidate_members)

        self.assertTrue(audit["passed"])
        self.assertEqual(set(model_input), runner.MODEL_INPUT_TOP_LEVEL_KEYS)
        self.assertEqual(len(model_input["candidate_pairs"]), 41)
        self.assertEqual(
            runner.collect_keys(model_input).intersection(
                runner.FORBIDDEN_MODEL_INPUT_KEYS
            ),
            set(),
        )

        for pair in model_input["candidate_pairs"]:
            self.assertEqual(set(pair), {"pair_id", "ko_a", "ko_b"})
            ko_a = (pair["ko_a"]["lecture_id"], pair["ko_a"]["ko_id"])
            ko_b = (pair["ko_b"]["lecture_id"], pair["ko_b"]["ko_id"])
            self.assertLess(ko_a, ko_b)

        gradient_pair = next(
            pair
            for pair in model_input["candidate_pairs"]
            if pair["pair_id"] == "rel_dev_012"
        )
        self.assertEqual(gradient_pair["ko_a"]["ko_id"], "gradient")
        self.assertEqual(gradient_pair["ko_b"]["ko_id"], "gradient_descent")

        for obj in model_input["knowledge_objects"]:
            self.assertEqual(
                set(obj),
                {"lecture_id", "ko_id", "name", "type", "source_spans"},
            )

    def test_dry_run_writes_rendered_input_and_metadata_without_api(self) -> None:
        run_dir = self.temporary_root / "dry_run"
        return_code, api_mock = self.invoke(
            self.runner_args("dry_run", "--dry-run")
        )

        self.assertEqual(return_code, 0)
        api_mock.assert_not_called()
        for directory in ["rendered_inputs", "raw_responses", "output", "metadata"]:
            self.assertTrue((run_dir / directory).is_dir())

        rendered_path = self.artifact_path(run_dir, "rendered_inputs")
        metadata_path = self.artifact_path(run_dir, "metadata")
        self.assertTrue(rendered_path.is_file())
        self.assertTrue(metadata_path.is_file())
        self.assertFalse(self.artifact_path(run_dir, "raw_responses").exists())
        self.assertFalse(self.artifact_path(run_dir, "output").exists())

        payload = self.read_json(rendered_path)
        model_input = json.loads(payload["messages"][1]["content"])
        self.assertEqual(set(model_input), runner.MODEL_INPUT_TOP_LEVEL_KEYS)
        self.assertEqual(
            runner.collect_keys(model_input).intersection(
                runner.FORBIDDEN_MODEL_INPUT_KEYS
            ),
            set(),
        )

        metadata = self.read_json(metadata_path)
        self.assertEqual(metadata["run_status"], "dry_run_complete")
        self.assertTrue(metadata["dry_run"])
        self.assertEqual(metadata["git_commit_at_start"], FREEZE_COMMIT)
        self.assertFalse(metadata["git_dirty_at_start"])
        self.assertTrue(metadata["gold_leakage_audit"]["passed"])
        self.assertEqual(metadata["input_counts"]["candidate_pairs"], 41)
        self.assertEqual(metadata["request_parameters"]["temperature"], 0.0)
        self.assertIn("request_payload_sha256", metadata["hashes"])

    def test_matched_input_dry_run_uses_frozen_b_prime_content(self) -> None:
        projection_dir = self.build_matched_projection()
        run_dir = self.temporary_root / "matched_dry_run"
        ground_truth = projection_dir / "matched_relation_ground_truth.json"
        input_artifact = projection_dir / "predicted_normalized_input.json"
        batch_plan = projection_dir / "batch_plan.json"
        args = [
            "--experiment",
            "002_prompt_refinement",
            "--ground-truth",
            str(ground_truth),
            "--input-artifact",
            str(input_artifact),
            "--batch-plan",
            str(batch_plan),
            "--run-dir",
            str(run_dir),
            "--dry-run",
        ]

        return_code, api_mock = self.invoke(args)

        self.assertEqual(return_code, 0)
        api_mock.assert_not_called()
        artifact_name = ground_truth.stem
        rendered = self.read_json(
            run_dir / "rendered_inputs" / f"{artifact_name}.json"
        )
        rendered_model_input = json.loads(rendered["messages"][1]["content"])
        frozen_input = self.read_json(input_artifact)["model_input"]
        self.assertEqual(rendered_model_input, frozen_input)
        gradient = next(
            item
            for item in rendered_model_input["knowledge_objects"]
            if item["ko_id"] == "ko_slot_001"
        )
        self.assertEqual(gradient["type"], "Method")
        metadata = self.read_json(
            run_dir / "metadata" / f"{artifact_name}.json"
        )
        self.assertEqual(metadata["condition"], "B_prime")
        self.assertEqual(
            metadata["input_artifact_sha256"], runner.sha256_file(input_artifact)
        )
        self.assertEqual(
            metadata["batch_plan_sha256"], runner.sha256_file(batch_plan)
        )

    def test_matched_input_rejects_stale_model_input_hash(self) -> None:
        projection_dir = self.build_matched_projection()
        input_artifact = projection_dir / "predicted_normalized_input.json"
        value = self.read_json(input_artifact)
        value["model_input"]["knowledge_objects"][0]["name"] = "Tampered"
        input_artifact.write_text(json.dumps(value), encoding="utf-8")

        return_code, api_mock = self.invoke([
            "--experiment",
            "002_prompt_refinement",
            "--ground-truth",
            str(projection_dir / "matched_relation_ground_truth.json"),
            "--input-artifact",
            str(input_artifact),
            "--batch-plan",
            str(projection_dir / "batch_plan.json"),
            "--run-dir",
            str(self.temporary_root / "stale_matched_input"),
            "--dry-run",
        ])

        self.assertEqual(return_code, 2)
        api_mock.assert_not_called()

    def test_no_overwrite_rejects_existing_artifacts(self) -> None:
        args = self.runner_args("no_overwrite", "--dry-run")
        first_return_code, _ = self.invoke(args)
        second_return_code, _ = self.invoke(args)

        self.assertEqual(first_return_code, 0)
        self.assertEqual(second_return_code, 2)

    def test_overwrite_removes_stale_output_files(self) -> None:
        run_dir = self.temporary_root / "overwrite"
        first_return_code, _ = self.invoke(
            self.runner_args("overwrite", "--dry-run")
        )
        self.assertEqual(first_return_code, 0)

        stale_raw = self.artifact_path(run_dir, "raw_responses")
        stale_prediction = self.artifact_path(run_dir, "output")
        stale_raw.write_text("{}\n", encoding="utf-8")
        stale_prediction.write_text("{}\n", encoding="utf-8")

        second_return_code, _ = self.invoke(
            self.runner_args("overwrite", "--dry-run", "--overwrite")
        )
        self.assertEqual(second_return_code, 0)
        self.assertFalse(stale_raw.exists())
        self.assertFalse(stale_prediction.exists())
        self.assertTrue(self.artifact_path(run_dir, "rendered_inputs").is_file())
        self.assertTrue(self.artifact_path(run_dir, "metadata").is_file())

    def test_request_failure_is_recorded_without_network(self) -> None:
        run_dir = self.temporary_root / "request_failure"
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            return_code, api_mock = self.invoke(
                self.runner_args("request_failure"),
                api_error=RuntimeError("synthetic request failure"),
            )

        self.assertEqual(return_code, 1)
        api_mock.assert_called_once()
        metadata = self.read_json(self.artifact_path(run_dir, "metadata"))
        self.assertEqual(metadata["run_status"], "request_failed")
        self.assertFalse(metadata["request_success"])
        self.assertEqual(metadata["api_error"], "synthetic request failure")
        self.assertIsNotNone(metadata["latency_ms"])
        self.assertFalse(self.artifact_path(run_dir, "raw_responses").exists())
        self.assertFalse(self.artifact_path(run_dir, "output").exists())

    def test_parse_failure_preserves_raw_response_and_text(self) -> None:
        run_dir = self.temporary_root / "parse_failure"
        api_response = {
            "model": "synthetic-model",
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": "not valid JSON"},
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            return_code, _ = self.invoke(
                self.runner_args("parse_failure"),
                api_response=api_response,
            )

        self.assertEqual(return_code, 1)
        metadata = self.read_json(self.artifact_path(run_dir, "metadata"))
        self.assertEqual(metadata["run_status"], "parse_failed")
        self.assertTrue(metadata["request_success"])
        self.assertFalse(metadata["json_parse_success"])
        self.assertTrue(self.artifact_path(run_dir, "raw_responses").is_file())
        raw_text = self.artifact_path(run_dir, "output", ".raw.txt")
        self.assertEqual(raw_text.read_text(encoding="utf-8"), "not valid JSON")

    def test_prediction_schema_failure_is_recorded(self) -> None:
        run_dir = self.temporary_root / "prediction_schema_failure"
        api_response = {
            "model": "synthetic-model",
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps({
                        "results": [{
                            "pair_id": "rel_dev_001",
                            "source": {
                                "lecture_id": "calculus_001",
                                "ko_id": "gradient",
                            },
                            "target": {
                                "lecture_id": "calculus_001",
                                "ko_id": "partial_derivative",
                            },
                            "relation_type": "INVALID_RELATION",
                            "evidence_spans": [],
                            "rationale": "Synthetic invalid Relation label.",
                        }]
                    })
                },
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            return_code, api_mock = self.invoke(
                self.runner_args("prediction_schema_failure"),
                api_response=api_response,
            )

        self.assertEqual(return_code, 1)
        api_mock.assert_called_once()
        metadata = self.read_json(self.artifact_path(run_dir, "metadata"))
        self.assertEqual(metadata["run_status"], "prediction_schema_failed")
        self.assertTrue(metadata["request_success"])
        self.assertTrue(metadata["json_parse_success"])
        self.assertFalse(metadata["prediction_schema_valid"])
        self.assertTrue(metadata["prediction_schema_error"])
        self.assertTrue(self.artifact_path(run_dir, "raw_responses").is_file())
        prediction_path = self.artifact_path(run_dir, "output")
        self.assertTrue(prediction_path.is_file())
        prediction = self.read_json(prediction_path)
        self.assertEqual(
            prediction["results"][0]["relation_type"],
            "INVALID_RELATION",
        )

    def test_mocked_success_writes_parsed_output(self) -> None:
        run_dir = self.temporary_root / "mocked_success"

        def fake_response(*, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
            self.assertEqual(api_key, "test-key")
            model_input = json.loads(payload["messages"][1]["content"])
            results = []
            for pair in model_input["candidate_pairs"]:
                results.append({
                    "pair_id": pair["pair_id"],
                    "source": pair["ko_a"],
                    "target": pair["ko_b"],
                    "relation_type": "NO_RELATION",
                    "evidence_spans": [],
                    "rationale": "Synthetic schema-valid prediction.",
                })
            return {
                "model": "synthetic-model",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"results": results})},
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        with (
            mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}),
            mock.patch.object(runner, "git_commit", return_value=FREEZE_COMMIT),
            mock.patch.object(runner, "git_dirty", return_value=False),
            mock.patch.object(runner, "call_deepseek", side_effect=fake_response),
        ):
            return_code = runner.main(self.runner_args("mocked_success"))

        self.assertEqual(return_code, 0)
        prediction = self.read_json(self.artifact_path(run_dir, "output"))
        self.assertEqual(len(prediction["results"]), 41)
        metadata = self.read_json(self.artifact_path(run_dir, "metadata"))
        self.assertEqual(metadata["run_status"], "completed")
        self.assertTrue(metadata["request_success"])
        self.assertTrue(metadata["json_parse_success"])
        self.assertTrue(metadata["prediction_schema_valid"])
        self.assertTrue(self.artifact_path(run_dir, "raw_responses").is_file())


if __name__ == "__main__":
    unittest.main()
