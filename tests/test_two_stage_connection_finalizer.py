from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import finalize_two_stage_connection_run as finalizer


FINALIZER_COMMIT = "d0c0dd3c02694646a816b2868fad3171051f877d"


class TwoStageConnectionFinalizerTests(unittest.TestCase):
    def build_run(self, root: Path, *, tamper_final: bool = False) -> Path:
        run_dir = root / "run"
        gate_path = run_dir / "stage_a/output/direct_gate_predictions.json"
        typed_path = run_dir / "stage_b/output/typed_connection_predictions.json"
        prediction_path = run_dir / "output/canonical_connection_predictions.json"
        metadata_path = run_dir / "metadata/run_metadata.json"
        gate_positive = {
            "canonical_pair_id": "pair_001",
            "ko_a_id": "ko_001",
            "ko_b_id": "ko_002",
            "decision": "DIRECT_CONNECTION",
            "evidence_ids": ["evidence_001"],
            "rationale": "Direct Evidence.",
        }
        gate_negative = {
            "canonical_pair_id": "pair_002",
            "ko_a_id": "ko_003",
            "ko_b_id": "ko_004",
            "decision": "NO_RELATION",
            "evidence_ids": [],
            "rationale": "No direct Evidence.",
        }
        typed = {
            "canonical_pair_id": "pair_001",
            "source_canonical_ko_id": "ko_001",
            "target_canonical_ko_id": "ko_002",
            "relation_type": "APPLIED_IN",
            "evidence_ids": ["evidence_001"],
            "rationale": "Direct Evidence.",
        }
        final_negative = {
            "canonical_pair_id": "pair_002",
            "source_canonical_ko_id": "ko_003",
            "target_canonical_ko_id": "ko_004",
            "relation_type": "NO_RELATION",
            "evidence_ids": [],
            "rationale": "No direct Evidence.",
        }
        if tamper_final:
            final_negative["rationale"] = "Changed rationale."
        finalizer.base.write_json(
            gate_path,
            {
                "artifact_type": "canonical_direct_edge_gate_predictions",
                "version": "v0.1",
                "results": [gate_positive, gate_negative],
            },
        )
        finalizer.base.write_json(
            typed_path,
            {
                "artifact_type": "evidence_constrained_connection_predictions",
                "version": "v0.1",
                "results": [typed],
            },
        )
        finalizer.base.write_json(
            prediction_path,
            {
                "artifact_type": "canonical_connection_predictions",
                "version": "v0.1",
                "results": [typed, final_negative],
            },
        )
        metadata = {
            "run_status": "completed",
            "execution_scope": "full_selected_candidate_set",
            "method_id": "direct_edge_gate_then_relation_typing_v0.1.2",
            "method_commit": FINALIZER_COMMIT,
            "git_commit_at_start": FINALIZER_COMMIT,
            "git_dirty_at_start": False,
            "request_success": True,
            "json_parse_success": True,
            "prediction_schema_valid": True,
            "finish_reason": "stop",
            "candidate_count": 2,
            "stage_a_completed_count": 2,
            "stage_a_positive_count": 1,
            "stage_b_completed_count": 1,
            "prediction": finalizer.base.binding(prediction_path),
            "stage_a_prediction": finalizer.base.binding(gate_path),
            "stage_b_prediction": finalizer.base.binding(typed_path),
        }
        finalizer.base.write_json(metadata_path, metadata)
        return run_dir

    def invoke(self, run_dir: Path) -> int:
        with (
            mock.patch.object(finalizer.base, "git_commit", return_value=FINALIZER_COMMIT),
            mock.patch.object(finalizer.base, "git_dirty", return_value=False),
        ):
            return finalizer.main(
                ["--run-dir", str(run_dir), "--finalizer-commit", FINALIZER_COMMIT]
            )

    def test_finalizer_adds_only_compatible_completion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self.build_run(Path(temporary))
            before = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            self.assertEqual(self.invoke(run_dir), 0)
            after = json.loads((run_dir / "metadata/run_metadata.json").read_text())
            snapshot = json.loads(
                (run_dir / "metadata/run_metadata.pre_finalization.json").read_text()
            )
            marker = json.loads(
                (run_dir / "metadata/run_metadata_finalization.json").read_text()
            )
            self.assertEqual(snapshot, before)
            self.assertEqual(after["completed_candidate_count"], 2)
            self.assertEqual(after["prediction"], before["prediction"])
            self.assertFalse(marker["prediction_content_changed"])
            self.assertEqual(self.invoke(run_dir), 1)

    def test_finalizer_rejects_inconsistent_final_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self.build_run(Path(temporary), tamper_final=True)
            self.assertEqual(self.invoke(run_dir), 1)
            self.assertFalse(
                (run_dir / "metadata/run_metadata.pre_finalization.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
