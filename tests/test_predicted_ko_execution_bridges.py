from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import finalize_relation_evaluation_bundle as finalizer
from scripts import prepare_predicted_ko_relation_run as preflight


FREEZE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


class PredictedKORunPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def args(self, run_name: str = "run_01"):
        return preflight.parse_args([
            "--method-commit",
            FREEZE_COMMIT,
            "--run-dir",
            str(self.temporary_root / run_name),
        ])

    def test_preflight_composes_inputs_and_audits_historical_sources(self) -> None:
        run_dir = self.temporary_root / "run_01"
        manifest = preflight.prepare_run(self.args())

        self.assertEqual(manifest["method_commit"], FREEZE_COMMIT)
        self.assertEqual(
            manifest["status"], "prepared_pending_entity_reruns"
        )
        self.assertEqual(
            manifest["entity_execution"]["rerun_required_lecture_ids"],
            ["calculus_001", "linear_algebra_001", "optimisation_001"],
        )
        oracle = read_json(run_dir / "oracle_knowledge_objects.json")
        lectures = read_json(run_dir / "lecture_inventory.json")
        source_manifest = read_json(
            run_dir / "entity_predictions" / "source_manifest.json"
        )
        self.assertEqual(len(oracle["lectures"]), 6)
        self.assertEqual(len(lectures["lectures"]), 6)
        self.assertEqual(source_manifest["counts"], {
            "lectures": 6,
            "reused": 3,
            "rerun_required": 3,
        })
        decisions = {
            item["lecture_id"]: item["decision"]
            for item in source_manifest["lectures"]
        }
        self.assertEqual(decisions["calculus_001"], "rerun_required")
        self.assertEqual(decisions["calculus_002"], "reuse")
        self.assertTrue(
            (run_dir / "entity_predictions" / "output" / "calculus_002.json").is_file()
        )
        self.assertFalse(
            (run_dir / "entity_predictions" / "output" / "calculus_001.json").exists()
        )
        self.assertEqual(
            manifest["benchmark"]["oracle_inventory"]["sha256"],
            preflight.sha256_file(run_dir / "oracle_knowledge_objects.json"),
        )

    def test_preflight_is_no_overwrite(self) -> None:
        args = self.args()
        preflight.prepare_run(args)
        with self.assertRaises(preflight.PreflightError):
            preflight.prepare_run(args)

    def test_preflight_rejects_non_commit_placeholder(self) -> None:
        args = self.args("invalid_commit")
        args.method_commit = "CURRENT_HEAD"
        with self.assertRaises(preflight.PreflightError):
            preflight.prepare_run(args)


class RelationEvaluationFinalizerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def make_source(self, *, pending: bool = False) -> tuple[Path, Path, Path]:
        evaluation_dir = self.temporary_root / "base_evaluation"
        predictions_path = self.temporary_root / "predictions_source.json"
        metadata_path = self.temporary_root / "metadata_source.json"
        pair = {
            "pair_id": "rel_dev_001",
            "source": {"lecture_id": "lecture_001", "ko_id": "ko_slot_001"},
            "target": {"lecture_id": "lecture_001", "ko_id": "ko_slot_002"},
            "relation_type": "NO_RELATION",
            "evidence_spans": [],
            "rationale": "Synthetic finalizer fixture.",
        }
        write_json(evaluation_dir / "metrics.json", {
            "evaluation_status": "final",
            "primary_scored_pairs": 1,
        })
        write_json(evaluation_dir / "matches.json", [{
            "pair_id": "rel_dev_001",
            "primary_scored": True,
        }])
        write_json(evaluation_dir / "errors.json", [])
        write_json(
            evaluation_dir / "adjudication_pending.json",
            [{"pair_id": "rel_dev_001"}] if pending else [],
        )
        write_json(predictions_path, {"results": [pair]})
        write_json(metadata_path, {
            "provider": "deepseek",
            "condition": "A_prime",
            "model_requested": "synthetic-model",
            "request_parameters": {"temperature": 0.0},
            "git_commit_at_start": FREEZE_COMMIT,
            "git_dirty_at_start": False,
            "input_artifact_sha256": "a" * 64,
            "batch_plan_sha256": "b" * 64,
            "request_success": True,
            "json_parse_success": True,
            "prediction_schema_valid": True,
            "finish_reason": "stop",
            "run_status": "completed",
        })
        return evaluation_dir, predictions_path, metadata_path

    def test_finalizer_writes_snapshot_last_and_binds_sources(self) -> None:
        evaluation_dir, predictions_path, metadata_path = self.make_source()
        output_dir = self.temporary_root / "final_bundle"

        snapshot = finalizer.finalize_bundle(
            condition="A_prime",
            base_evaluation_dir=evaluation_dir,
            predictions_path=predictions_path,
            run_metadata_path=metadata_path,
            output_dir=output_dir,
            overwrite=False,
        )

        self.assertEqual(snapshot["evaluation_status"], "final")
        self.assertEqual(snapshot["condition"], "A_prime")
        for filename in [*finalizer.COPIED_FILENAMES, finalizer.SNAPSHOT_FILENAME]:
            self.assertTrue((output_dir / filename).is_file())
        packaged_metadata = read_json(output_dir / "run_metadata.json")
        self.assertEqual(
            packaged_metadata["prediction_sha256"],
            finalizer.sha256_file(output_dir / "predictions.json"),
        )
        self.assertEqual(
            snapshot["run_metadata_sha256"],
            finalizer.sha256_file(output_dir / "run_metadata.json"),
        )

    def test_finalizer_rejects_pending_adjudication(self) -> None:
        evaluation_dir, predictions_path, metadata_path = self.make_source(
            pending=True
        )
        with self.assertRaises(finalizer.BundleError):
            finalizer.finalize_bundle(
                condition="A_prime",
                base_evaluation_dir=evaluation_dir,
                predictions_path=predictions_path,
                run_metadata_path=metadata_path,
                output_dir=self.temporary_root / "pending_bundle",
                overwrite=False,
            )


if __name__ == "__main__":
    unittest.main()
