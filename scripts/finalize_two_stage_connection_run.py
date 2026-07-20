#!/usr/bin/env python3
"""Add evaluator-compatible completion metadata after strict run validation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import run_connection_discovery as base
except ModuleNotFoundError:  # Direct execution via `python3 scripts/...`.
    import run_connection_discovery as base


FINALIZER_VERSION = "two_stage_connection_metadata_finalizer_v0.1"


class FinalizationError(RuntimeError):
    """Raised when a two-stage run cannot be finalized safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--finalizer-commit", required=True)
    return parser.parse_args(argv)


def _load(path: Path) -> dict[str, Any]:
    value = base.load_json(path)
    if not isinstance(value, dict):
        raise FinalizationError(f"Expected JSON object: {base.display_path(path)}")
    return value


def _result_map(bundle: dict[str, Any], artifact_type: str) -> dict[str, dict[str, Any]]:
    if bundle.get("artifact_type") != artifact_type or bundle.get("version") != "v0.1":
        raise FinalizationError(f"Unexpected {artifact_type} identity")
    results = bundle.get("results")
    if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
        raise FinalizationError(f"Invalid {artifact_type} results")
    pair_ids = [item.get("canonical_pair_id") for item in results]
    if any(not isinstance(pair_id, str) for pair_id in pair_ids):
        raise FinalizationError(f"Invalid {artifact_type} pair ID")
    if len(pair_ids) != len(set(pair_ids)):
        raise FinalizationError(f"Duplicate {artifact_type} pair ID")
    return dict(zip(pair_ids, results))


def validate_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    prediction_path = run_dir / "output" / "canonical_connection_predictions.json"
    gate_path = run_dir / "stage_a" / "output" / "direct_gate_predictions.json"
    typed_path = run_dir / "stage_b" / "output" / "typed_connection_predictions.json"
    metadata = _load(metadata_path)
    prediction = _load(prediction_path)
    gate = _load(gate_path)
    typed = _load(typed_path)

    if metadata.get("run_status") != "completed":
        raise FinalizationError("Run is not a completed full execution")
    if metadata.get("execution_scope") != "full_selected_candidate_set":
        raise FinalizationError("Run execution scope is not full")
    if metadata.get("method_id") != "direct_edge_gate_then_relation_typing_v0.1.2":
        raise FinalizationError("Run method is not two-stage v0.1.2")
    if metadata.get("request_success") is not True:
        raise FinalizationError("Run request status is not successful")
    if metadata.get("json_parse_success") is not True:
        raise FinalizationError("Run parse status is not successful")
    if metadata.get("prediction_schema_valid") is not True:
        raise FinalizationError("Run prediction schema is not valid")
    if metadata.get("finish_reason") != "stop":
        raise FinalizationError("Run finish reason is not stop")
    if metadata.get("git_dirty_at_start") is not False:
        raise FinalizationError("Run did not start from a clean repository")
    if metadata.get("git_commit_at_start") != metadata.get("method_commit"):
        raise FinalizationError("Run method commit binding is inconsistent")

    candidate_count = metadata.get("candidate_count")
    stage_a_count = metadata.get("stage_a_completed_count")
    positive_count = metadata.get("stage_a_positive_count")
    stage_b_count = metadata.get("stage_b_completed_count")
    if not isinstance(candidate_count, int) or candidate_count <= 0:
        raise FinalizationError("Candidate count is invalid")
    if stage_a_count != candidate_count:
        raise FinalizationError("Stage-A completion count is incomplete")
    if not isinstance(positive_count, int) or stage_b_count != positive_count:
        raise FinalizationError("Stage-B completion count is incomplete")

    final_map = _result_map(prediction, "canonical_connection_predictions")
    gate_map = _result_map(gate, "canonical_direct_edge_gate_predictions")
    typed_map = _result_map(typed, "evidence_constrained_connection_predictions")
    if len(final_map) != candidate_count or set(final_map) != set(gate_map):
        raise FinalizationError("Final and Stage-A candidate sets differ")
    positive_ids = {
        pair_id
        for pair_id, item in gate_map.items()
        if item.get("decision") == "DIRECT_CONNECTION"
    }
    if len(positive_ids) != positive_count or set(typed_map) != positive_ids:
        raise FinalizationError("Stage-B pair set does not equal Stage-A positives")
    for pair_id, gate_result in gate_map.items():
        final_result = final_map[pair_id]
        if pair_id in positive_ids:
            if final_result != typed_map[pair_id]:
                raise FinalizationError(f"Final typed result mismatch for {pair_id}")
        elif (
            final_result.get("relation_type") != "NO_RELATION"
            or final_result.get("evidence_ids") != []
            or final_result.get("rationale") != gate_result.get("rationale")
        ):
            raise FinalizationError(f"Final negative result mismatch for {pair_id}")

    bindings = {
        "prediction": (metadata.get("prediction"), prediction_path),
        "stage_a_prediction": (metadata.get("stage_a_prediction"), gate_path),
        "stage_b_prediction": (metadata.get("stage_b_prediction"), typed_path),
    }
    for name, (observed, path) in bindings.items():
        if observed != base.binding(path):
            raise FinalizationError(f"Stale run binding: {name}")
    return metadata, {"candidate_count": candidate_count}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = base.resolve_path(args.run_dir)
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    snapshot_path = run_dir / "metadata" / "run_metadata.pre_finalization.json"
    marker_path = run_dir / "metadata" / "run_metadata_finalization.json"
    if base.SHA1_RE.fullmatch(args.finalizer_commit) is None:
        print("Two-stage finalization failed: finalizer commit must be a 40-character SHA-1")
        return 1
    if snapshot_path.exists() or marker_path.exists():
        print("Two-stage finalization failed: finalization artifacts already exist")
        return 1
    commit = base.git_commit()
    dirty = base.git_dirty()
    if commit != args.finalizer_commit or dirty is not False:
        print("Two-stage finalization failed: repository must be clean at the finalizer commit")
        return 1
    try:
        metadata, validated = validate_run(run_dir)
    except (base.ConnectionRunError, FinalizationError, OSError) as exc:
        print(f"Two-stage finalization failed: {exc}")
        return 1

    base.write_json(snapshot_path, metadata)
    finalized = {
        **metadata,
        "completed_candidate_count": validated["candidate_count"],
        "metadata_finalization": {
            "method_id": "add_completed_candidate_count_after_strict_two_stage_validation_v0.1",
            "finalizer_commit": args.finalizer_commit,
            "finalizer": {
                "path": base.display_path(Path(__file__)),
                "sha256": base.sha256_file(Path(__file__)),
                "version": FINALIZER_VERSION,
            },
            "pre_finalization_metadata": base.binding(snapshot_path),
            "finalized_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    base.write_json(metadata_path, finalized)
    marker = {
        "artifact_type": "two_stage_connection_metadata_finalization",
        "version": "v0.1",
        "status": "complete",
        "reason": "additive evaluator metadata compatibility",
        "prediction_content_changed": False,
        "pre_finalization_metadata": base.binding(snapshot_path),
        "finalized_metadata": base.binding(metadata_path),
        "completed_candidate_count": validated["candidate_count"],
        "finalizer_commit": args.finalizer_commit,
    }
    base.write_json(marker_path, marker)
    print(
        f"Finalized two-stage metadata for {validated['candidate_count']} candidates "
        f"at {base.display_path(metadata_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
