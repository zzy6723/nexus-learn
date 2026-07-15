from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import finalize_entity_prediction_bundle as finalizer
from scripts import prepare_predicted_ko_relation_run as preflight


FREEZE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class EntityBundleFinalizerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name)

    @staticmethod
    def prediction(lecture_id: str) -> dict:
        return {
            "lecture_id": lecture_id,
            "knowledge_objects": [{
                "id": "gradient",
                "name": "Gradient",
                "type": "Concept",
                "aliases": [],
                "short_definition": "A derivative vector.",
                "source_span": "The gradient",
            }],
        }

    @staticmethod
    def raw_response(prediction: dict) -> dict:
        return {
            "id": "synthetic-request",
            "model": "deepseek-v4-flash",
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps(prediction)},
            }],
        }

    def make_fixture(self) -> tuple[Path, Path]:
        run_dir = self.root / "run_02"
        entity_dir = run_dir / "entity_predictions"
        prompt_path = (
            preflight.ROOT
            / "experiments"
            / "entity_extraction"
            / "002_prompt_refinement"
            / "prompt.md"
        )
        lecture_texts = {
            "lecture_reused": "The gradient is a derivative vector.\n",
            "lecture_rerun": "The gradient gives the steepest direction.\n",
        }
        parameters = {
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 4096,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }
        entity_execution = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "request_parameters": parameters,
        }

        artifact_paths: dict[str, dict[str, Path]] = {}
        for lecture_id, lecture_text in lecture_texts.items():
            prediction = self.prediction(lecture_id)
            raw_response = self.raw_response(prediction)
            rendered = preflight.expected_entity_payload(
                prompt_path=prompt_path,
                lecture_id=lecture_id,
                lecture_text=lecture_text,
                model=entity_execution["model"],
                temperature=parameters["temperature"],
                top_p=parameters["top_p"],
                max_tokens=parameters["max_tokens"],
            )
            paths = {
                "output": entity_dir / "output" / f"{lecture_id}.json",
                "metadata": entity_dir / "metadata" / f"{lecture_id}.json",
                "raw_response": entity_dir / "raw_responses" / f"{lecture_id}.json",
                "rendered_input": entity_dir / "rendered_inputs" / f"{lecture_id}.json",
            }
            artifact_paths[lecture_id] = paths
            write_json(paths["output"], prediction)
            write_json(paths["raw_response"], raw_response)
            write_json(paths["rendered_input"], rendered)
            metadata = {
                "provider": "deepseek",
                "lecture_id": lecture_id,
                "model_requested": "deepseek-v4-flash",
                "model_returned": "deepseek-v4-flash",
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 4096,
                "prompt_sha256": preflight.sha256_file(prompt_path),
                "input_sha256": preflight.sha256_text(lecture_text),
                "request_payload_sha256": preflight.sha256_json(rendered),
                "request_success": True,
                "json_parse_success": True,
                "finish_reason": "stop",
                "run_timestamp": "2026-07-15T00:00:00+00:00",
            }
            write_json(paths["metadata"], metadata)

        reused_paths = artifact_paths["lecture_reused"]
        source_manifest = {
            "artifact_type": "entity_prediction_source_manifest",
            "version": "v0.1",
            "status": "prepared_pending_entity_reruns",
            "method_commit": FREEZE_COMMIT,
            "counts": {
                "lectures": 2,
                "reused": 1,
                "rerun_required": 1,
            },
            "rerun_required_lecture_ids": ["lecture_rerun"],
            "lectures": [
                {
                    "lecture_id": "lecture_reused",
                    "decision": "reuse",
                    "source_run": "synthetic_prior_run",
                    "source_sha256": {
                        name: preflight.sha256_file(path)
                        for name, path in reused_paths.items()
                    },
                },
                {
                    "lecture_id": "lecture_rerun",
                    "decision": "rerun_required",
                    "source_run": None,
                    "source_sha256": {},
                },
            ],
        }
        source_manifest_path = entity_dir / "source_manifest.json"
        write_json(source_manifest_path, source_manifest)

        lecture_inventory = {
            "artifact_type": "predicted_ko_relation_lecture_inventory",
            "version": "v0.1",
            "split": "development",
            "lectures": [
                {"lecture_id": lecture_id, "text": lecture_text}
                for lecture_id, lecture_text in lecture_texts.items()
            ],
        }
        lecture_inventory_path = run_dir / "lecture_inventory.json"
        write_json(lecture_inventory_path, lecture_inventory)

        finalizer_path = Path(finalizer.__file__).resolve()
        execution = {
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
                    "path": str(prompt_path),
                    "sha256": preflight.sha256_file(prompt_path),
                },
                "implementation": [{
                    "path": str(finalizer_path),
                    "sha256": preflight.sha256_file(finalizer_path),
                }],
            },
            "entity_execution": {
                **entity_execution,
                "source_manifest": str(source_manifest_path),
                "source_manifest_sha256": preflight.sha256_file(
                    source_manifest_path
                ),
                "rerun_required_lecture_ids": ["lecture_rerun"],
            },
            "benchmark": {
                "lecture_ids": list(lecture_texts),
                "lecture_inventory": {
                    "path": str(lecture_inventory_path),
                    "sha256": preflight.sha256_file(lecture_inventory_path),
                },
                "lecture_model_text_sha256": {
                    lecture_id: preflight.sha256_text(lecture_text)
                    for lecture_id, lecture_text in lecture_texts.items()
                },
            },
        }
        execution_path = run_dir / "execution_manifest.json"
        write_json(execution_path, execution)

        rerun_paths = artifact_paths["lecture_rerun"]
        rerun_metadata = read_json(rerun_paths["metadata"])
        rerun_metadata.update({
            "run_status": "completed",
            "prediction_schema_valid": True,
            "git_commit_at_start": FREEZE_COMMIT,
            "git_dirty_at_start": False,
            "retry_count": 0,
            "repair_status": "not_attempted",
            "raw_response_sha256": preflight.sha256_file(
                rerun_paths["raw_response"]
            ),
            "prediction_sha256": preflight.sha256_file(rerun_paths["output"]),
            "execution_binding": {
                "execution_manifest": finalizer.display_path(execution_path),
                "execution_manifest_sha256": preflight.sha256_file(execution_path),
                "method_commit": FREEZE_COMMIT,
                "source_manifest": finalizer.display_path(source_manifest_path),
                "source_manifest_sha256": preflight.sha256_file(
                    source_manifest_path
                ),
                "expected_input_sha256": preflight.sha256_text(
                    lecture_texts["lecture_rerun"]
                ),
            },
        })
        write_json(rerun_paths["metadata"], rerun_metadata)
        return execution_path, rerun_paths["metadata"]

    def test_finalizer_writes_hash_bound_source_bundle(self) -> None:
        execution_path, _ = self.make_fixture()
        entity_dir = execution_path.parent / "entity_predictions"
        source_manifest_path = entity_dir / "source_manifest.json"
        source_hash_before = preflight.sha256_file(source_manifest_path)

        marker = finalizer.finalize_entity_bundle(execution_path)

        self.assertEqual(marker["status"], "final")
        self.assertEqual(marker["counts"]["lectures"], 2)
        self.assertEqual(marker["counts"]["reused"], 1)
        self.assertEqual(marker["counts"]["new_reruns"], 1)
        self.assertEqual(
            preflight.sha256_file(source_manifest_path), source_hash_before
        )
        bundle_path = entity_dir / finalizer.BUNDLE_FILENAME
        marker_path = entity_dir / finalizer.MARKER_FILENAME
        self.assertTrue(bundle_path.is_file())
        self.assertTrue(marker_path.is_file())
        self.assertEqual(
            marker["entity_source_bundle_sha256"],
            preflight.sha256_file(bundle_path),
        )

    def test_finalizer_accepts_an_all_reused_source_plan(self) -> None:
        execution_path, _ = self.make_fixture()
        entity_dir = execution_path.parent / "entity_predictions"
        source_manifest_path = entity_dir / "source_manifest.json"
        source_manifest = read_json(source_manifest_path)
        source_manifest["status"] = "prepared_all_reused"
        source_manifest["counts"] = {
            "lectures": 2,
            "reused": 2,
            "rerun_required": 0,
        }
        source_manifest["rerun_required_lecture_ids"] = []
        for record in source_manifest["lectures"]:
            if record["lecture_id"] != "lecture_rerun":
                continue
            record["decision"] = "reuse"
            record["source_run"] = "synthetic_prior_run"
            record["source_sha256"] = {
                name: preflight.sha256_file(
                    entity_dir / directory / "lecture_rerun.json"
                )
                for name, directory in finalizer.MANAGED_DIRECTORIES.items()
            }
        write_json(source_manifest_path, source_manifest)

        execution = read_json(execution_path)
        execution["status"] = "prepared_entity_sources_complete"
        execution["entity_execution"]["rerun_required_lecture_ids"] = []
        execution["entity_execution"]["source_manifest_sha256"] = (
            preflight.sha256_file(source_manifest_path)
        )
        write_json(execution_path, execution)

        marker = finalizer.finalize_entity_bundle(execution_path)

        self.assertEqual(marker["status"], "final")
        self.assertEqual(marker["counts"]["reused"], 2)
        self.assertEqual(marker["counts"]["new_reruns"], 0)

    def test_finalizer_rejects_stale_rerun_binding(self) -> None:
        execution_path, metadata_path = self.make_fixture()
        metadata = read_json(metadata_path)
        metadata["execution_binding"]["execution_manifest_sha256"] = "f" * 64
        write_json(metadata_path, metadata)

        with self.assertRaisesRegex(
            finalizer.EntityBundleError, "not bound to the current execution plan"
        ):
            finalizer.finalize_entity_bundle(execution_path)

    def test_finalizer_is_no_overwrite(self) -> None:
        execution_path, _ = self.make_fixture()
        finalizer.finalize_entity_bundle(execution_path)

        with self.assertRaisesRegex(
            finalizer.EntityBundleError, "already exists"
        ):
            finalizer.finalize_entity_bundle(execution_path)


if __name__ == "__main__":
    unittest.main()
