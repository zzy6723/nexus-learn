from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    @staticmethod
    def repository_state():
        return {
            "repository_root": ".",
            "head_commit": FREEZE_COMMIT,
            "branch": "main",
            "worktree_clean": True,
            "status_scope": "tracked_and_non_ignored_untracked",
            "verified_artifacts": [],
        }

    def prepare(self, args):
        with mock.patch.object(
            preflight,
            "verify_repository_state",
            return_value=self.repository_state(),
        ):
            return preflight.prepare_run(args)

    def test_preflight_composes_inputs_and_audits_historical_sources(self) -> None:
        run_dir = self.temporary_root / "run_01"
        manifest = self.prepare(self.args())

        self.assertEqual(manifest["method_commit"], FREEZE_COMMIT)
        self.assertEqual(manifest["repository_state"], self.repository_state())
        self.assertGreater(len(manifest["frozen_methods"]["implementation"]), 0)
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
        self.prepare(args)
        with self.assertRaises(preflight.PreflightError):
            self.prepare(args)

    def test_preflight_supports_locked_reuse_scope(self) -> None:
        run_dir = self.temporary_root / "locked_reuse_run_01"
        args = preflight.parse_args([
            "--method-commit",
            FREEZE_COMMIT,
            "--execution-scope",
            "locked_reuse_v0_1",
            "--run-dir",
            str(run_dir),
            "--relation-ground-truth",
            "benchmark/ground_truth/relations_holdout_v0_1.json",
        ])

        manifest = self.prepare(args)

        self.assertEqual(manifest["split"], "locked_reuse_v0_1")
        self.assertEqual(manifest["benchmark"]["relation_split"], "holdout")
        self.assertEqual(manifest["entity_execution"]["input_split"], "holdout")
        self.assertEqual(
            manifest["claim_boundary"],
            "locked reuse of the previously evaluated 002A holdout",
        )
        self.assertEqual(
            manifest["entity_execution"]["rerun_required_lecture_ids"],
            [
                "statistics_estimation_001",
                "numerical_root_finding_001",
                "differential_equations_001",
                "graph_algorithms_001",
            ],
        )
        source_manifest = read_json(
            run_dir / "entity_predictions" / "source_manifest.json"
        )
        self.assertEqual(source_manifest["execution_scope"], "locked_reuse_v0_1")
        self.assertEqual(source_manifest["input_split"], "holdout")

    def test_preflight_rejects_scope_and_relation_split_mismatch(self) -> None:
        args = preflight.parse_args([
            "--method-commit",
            FREEZE_COMMIT,
            "--run-dir",
            str(self.temporary_root / "split_mismatch"),
            "--relation-ground-truth",
            "benchmark/ground_truth/relations_holdout_v0_1.json",
        ])

        with self.assertRaisesRegex(
            preflight.PreflightError,
            "Execution scope and Relation benchmark split disagree",
        ):
            self.prepare(args)

    def test_locked_reuse_default_run_dir_uses_locked_scope(self) -> None:
        args = preflight.parse_args([
            "--method-commit",
            FREEZE_COMMIT,
            "--execution-scope",
            "locked_reuse_v0_1",
        ])

        self.assertIsNone(args.run_dir)
        self.assertEqual(
            preflight.DEFAULT_RUN_DIR_BY_EXECUTION_SCOPE[args.execution_scope],
            preflight.DEFAULT_RUN_ROOT / "locked_reuse_v0_1" / "run_01",
        )

    def test_preflight_rejects_non_commit_placeholder(self) -> None:
        args = self.args("invalid_commit")
        args.method_commit = "CURRENT_HEAD"
        with self.assertRaises(preflight.PreflightError):
            self.prepare(args)

    def test_repository_verification_accepts_exact_clean_commit(self) -> None:
        artifact = preflight.DEFAULT_ENTITY_PROMPT

        def fake_git(args):
            if args == ["rev-parse", "--show-toplevel"]:
                return str(preflight.ROOT).encode("utf-8") + b"\n"
            if args == ["rev-parse", "--verify", "HEAD"]:
                return FREEZE_COMMIT.encode("ascii") + b"\n"
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return b"main\n"
            if args == ["status", "--porcelain=v1", "--untracked-files=all"]:
                return b""
            if args[:3] == ["ls-files", "--error-unmatch", "--"]:
                return args[3].encode("utf-8") + b"\n"
            if args[0] == "show":
                return artifact.read_bytes()
            raise AssertionError(f"Unexpected Git command: {args}")

        with mock.patch.object(preflight, "run_git", side_effect=fake_git):
            state = preflight.verify_repository_state(
                method_commit=FREEZE_COMMIT,
                required_paths=[artifact],
            )

        self.assertTrue(state["worktree_clean"])
        self.assertEqual(state["head_commit"], FREEZE_COMMIT)
        self.assertEqual(
            state["verified_artifacts"][0]["sha256"],
            preflight.sha256_file(artifact),
        )

    def test_repository_verification_rejects_head_mismatch(self) -> None:
        other_commit = "f" * 40
        with mock.patch.object(
            preflight,
            "run_git",
            side_effect=[
                str(preflight.ROOT).encode("utf-8") + b"\n",
                other_commit.encode("ascii") + b"\n",
            ],
        ):
            with self.assertRaisesRegex(
                preflight.PreflightError, "does not match the current HEAD"
            ):
                preflight.verify_repository_state(
                    method_commit=FREEZE_COMMIT,
                    required_paths=[preflight.DEFAULT_ENTITY_PROMPT],
                )

    def test_repository_verification_rejects_dirty_worktree(self) -> None:
        with mock.patch.object(
            preflight,
            "run_git",
            side_effect=[
                str(preflight.ROOT).encode("utf-8") + b"\n",
                FREEZE_COMMIT.encode("ascii") + b"\n",
                b"main\n",
                b"?? notes.txt\n",
            ],
        ):
            with self.assertRaisesRegex(
                preflight.PreflightError, "requires a clean"
            ):
                preflight.verify_repository_state(
                    method_commit=FREEZE_COMMIT,
                    required_paths=[preflight.DEFAULT_ENTITY_PROMPT],
                )


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
