#!/usr/bin/env python3
"""Freeze one final 002B-2 Relation evaluation as a snapshot-bound bundle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_candidate_relation_diagnostic as preparer  # noqa: E402
from scripts import project_candidate_pairs_to_relations as projector  # noqa: E402
from scripts import run_candidate_relation_diagnostic as diagnostic_runner  # noqa: E402


DEFAULT_CONTRACT = ROOT / "benchmark" / "candidate_relation_downstream_diagnostic_v0_1.json"
DEFAULT_EXECUTION_ROOT = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "downstream_diagnostic_v0_1"
)
CONDITIONS = {"all_pairs", "rule_filtered_v0_1"}
BASE_EVALUATION_FILENAMES = [
    "metrics.json",
    "matches.json",
    "errors.json",
    "confusion_matrix.json",
    "adjudication_pending.json",
    "summary.md",
]
COPIED_FILENAMES = [
    *BASE_EVALUATION_FILENAMES,
    "predictions.json",
    "run_metadata.json",
]
OPTIONAL_ADJUDICATION_FILENAME = "adjudication_resolved.json"
SNAPSHOT_FILENAME = "evaluation_snapshot.json"


class EvaluationFinalizationError(RuntimeError):
    """Raised when a Relation evaluation cannot be frozen safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze one final Candidate-to-Relation evaluation bundle."
    )
    parser.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT.relative_to(ROOT)))
    parser.add_argument("--prepared-dir")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--evaluation-dir")
    parser.add_argument("--adjudication")
    parser.add_argument("--output-dir")
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    return projector.display_path(path)


def read_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationFinalizationError(
            f"Unable to read {label} {display_path(path)}: {exc}"
        ) from exc


def binding(path: Path) -> dict[str, str]:
    return projector.binding(path)


def prepare_output(output_dir: Path) -> None:
    managed = [
        *(output_dir / name for name in COPIED_FILENAMES),
        output_dir / OPTIONAL_ADJUDICATION_FILENAME,
        output_dir / SNAPSHOT_FILENAME,
    ]
    existing = [display_path(path) for path in managed if path.exists()]
    if existing:
        raise EvaluationFinalizationError(
            "Evaluation snapshot already contains managed artifacts; use a new "
            f"directory: {existing}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def validate_run_bundle(
    *,
    condition: str,
    contract_path: Path,
    prepared: dict[str, Any],
    run_dir: Path,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    run_marker_path = run_dir / diagnostic_runner.RUN_MARKER_NAME
    run_marker = read_json(run_marker_path, label="diagnostic run marker")
    if (
        not isinstance(run_marker, dict)
        or run_marker.get("artifact_type")
        != "candidate_relation_diagnostic_run_complete"
        or run_marker.get("version") != "v0.1"
        or run_marker.get("status") != "completed"
        or run_marker.get("condition") != condition
    ):
        raise EvaluationFinalizationError(
            "Diagnostic run marker is not a completed formal run for this condition."
        )
    if run_marker.get("contract") != binding(contract_path):
        raise EvaluationFinalizationError("Diagnostic run marker has a stale contract binding.")
    if run_marker.get("preparation") != binding(prepared["marker_path"]):
        raise EvaluationFinalizationError(
            "Diagnostic run marker has a stale preparation binding."
        )
    if run_marker.get("implementation") != binding(Path(diagnostic_runner.__file__).resolve()):
        raise EvaluationFinalizationError("Diagnostic runner implementation binding is stale.")

    artifacts = run_marker.get("artifacts")
    expected_artifacts = {
        "execution_batch_plan",
        "aggregate_metadata",
        "predictions",
    }
    if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
        raise EvaluationFinalizationError("Diagnostic run marker artifact set is invalid.")
    artifact_paths = {
        name: projector.validate_binding(value, label=f"run {name}")
        for name, value in artifacts.items()
    }
    prediction_path = artifact_paths["predictions"]
    metadata_path = artifact_paths["aggregate_metadata"]
    if prediction_path.parent.resolve() != (run_dir / "output").resolve():
        raise EvaluationFinalizationError("Prediction artifact is outside the formal run.")
    if metadata_path.parent.resolve() != (run_dir / "metadata").resolve():
        raise EvaluationFinalizationError("Metadata artifact is outside the formal run.")

    metadata = read_json(metadata_path, label="aggregate run metadata")
    if not isinstance(metadata, dict):
        raise EvaluationFinalizationError("Aggregate run metadata must be an object.")
    if (
        metadata.get("condition") != condition
        or metadata.get("run_status") != "completed"
        or metadata.get("request_success") is not True
        or metadata.get("json_parse_success") is not True
        or metadata.get("prediction_schema_valid") is not True
        or metadata.get("finish_reason") != "stop"
        or metadata.get("git_dirty_at_start") is not False
    ):
        raise EvaluationFinalizationError("Formal run metadata is incomplete, invalid, or dirty.")
    method_commit = run_marker.get("method_commit")
    if metadata.get("git_commit_at_start") != method_commit:
        raise EvaluationFinalizationError("Run marker and metadata method commits differ.")
    if metadata.get("input_artifact_sha256") != projector.sha256_file(
        prepared["paths"]["model_input"]
    ):
        raise EvaluationFinalizationError("Run metadata has a stale model-input hash.")
    if metadata.get("batch_plan_sha256") != projector.sha256_file(
        prepared["paths"]["batch_plan"]
    ):
        raise EvaluationFinalizationError("Run metadata has a stale batch-plan hash.")
    if metadata.get("prediction_sha256") != projector.sha256_file(prediction_path):
        raise EvaluationFinalizationError("Run metadata has a stale prediction hash.")
    expected_count = len(prepared["model_input"]["candidate_pairs"])
    if (
        metadata.get("batch_count") != expected_count
        or metadata.get("completed_batch_count") != expected_count
        or len(metadata.get("batch_results", [])) != expected_count
    ):
        raise EvaluationFinalizationError("Candidate-scoped execution is incomplete.")

    predictions = read_json(prediction_path, label="Relation predictions")
    results = predictions.get("results") if isinstance(predictions, dict) else None
    if not isinstance(results, list):
        raise EvaluationFinalizationError("Relation predictions must contain results.")
    expected_ids = [
        item["pair_id"] for item in prepared["selected_gt"].get("pairs", [])
    ]
    prediction_ids = [
        item.get("pair_id") for item in results if isinstance(item, dict)
    ]
    if prediction_ids != expected_ids or len(prediction_ids) != len(set(prediction_ids)):
        raise EvaluationFinalizationError(
            "Predictions differ from the frozen selected pair order."
        )
    return prediction_path, predictions, metadata_path, metadata


def validate_evaluation(
    *,
    evaluation_dir: Path,
    expected_pair_ids: list[str],
    predictions_path: Path,
    adjudication_path: Path | None,
) -> tuple[dict[str, Path], dict[str, Any]]:
    paths = {name: evaluation_dir / name for name in BASE_EVALUATION_FILENAMES}
    missing = [display_path(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise EvaluationFinalizationError(
            f"Final Relation evaluation is missing artifacts: {missing}"
        )
    metrics = read_json(paths["metrics.json"], label="Relation metrics")
    matches = read_json(paths["matches.json"], label="Relation matches")
    errors = read_json(paths["errors.json"], label="Relation errors")
    pending = read_json(
        paths["adjudication_pending.json"], label="pending adjudication"
    )
    if not isinstance(metrics, dict) or metrics.get("evaluation_status") != "final":
        raise EvaluationFinalizationError("Relation evaluation is not final.")
    if not isinstance(pending, list) or pending:
        raise EvaluationFinalizationError("Relation evaluation still has pending cases.")
    if not isinstance(matches, list) or not isinstance(errors, list):
        raise EvaluationFinalizationError("Relation matches or errors have invalid shape.")
    match_ids = [item.get("pair_id") for item in matches if isinstance(item, dict)]
    if match_ids != expected_pair_ids or len(match_ids) != len(set(match_ids)):
        raise EvaluationFinalizationError(
            "Final matches differ from the frozen selected pair order."
        )
    if metrics.get("total_pairs") != len(expected_pair_ids):
        raise EvaluationFinalizationError("Relation total-pair denominator is stale.")
    if metrics.get("primary_scored_pairs") != sum(
        item.get("primary_scored") is True for item in matches
    ):
        raise EvaluationFinalizationError("Relation primary denominator is stale.")

    predictions = read_json(predictions_path, label="Relation predictions")
    prediction_ids = [
        item.get("pair_id")
        for item in predictions.get("results", [])
        if isinstance(item, dict)
    ]
    if prediction_ids != match_ids:
        raise EvaluationFinalizationError("Predictions and matches differ in pair order.")

    manual_count = metrics.get("manual_adjudication_count")
    if not isinstance(manual_count, int) or manual_count < 0:
        raise EvaluationFinalizationError("manual_adjudication_count is invalid.")
    if manual_count and adjudication_path is None:
        raise EvaluationFinalizationError(
            "A resolved adjudication artifact is required for manual decisions."
        )
    if not manual_count and adjudication_path is not None:
        raise EvaluationFinalizationError(
            "An adjudication artifact was supplied but no manual decisions were used."
        )
    if adjudication_path is not None:
        adjudication = read_json(adjudication_path, label="resolved adjudication")
        if not isinstance(adjudication, dict) or not isinstance(
            adjudication.get("decisions"), list
        ):
            raise EvaluationFinalizationError("Resolved adjudication has invalid shape.")
        if len(adjudication["decisions"]) != manual_count:
            raise EvaluationFinalizationError(
                "Resolved adjudication count differs from final metrics."
            )
    return paths, metrics


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def finalize_evaluation(
    *,
    condition: str,
    contract_path: Path,
    prepared_dir: Path,
    run_dir: Path,
    evaluation_dir: Path,
    adjudication_path: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    contract = projector.read_json(contract_path, label="diagnostic contract")
    projector.validate_contract(contract)
    prepared = diagnostic_runner.validate_preparation(
        prepared_dir=prepared_dir,
        contract_path=contract_path,
        condition=condition,
    )
    prediction_path, _, metadata_path, metadata = validate_run_bundle(
        condition=condition,
        contract_path=contract_path,
        prepared=prepared,
        run_dir=run_dir,
    )
    expected_pair_ids = [
        item["pair_id"] for item in prepared["selected_gt"].get("pairs", [])
    ]
    evaluation_paths, metrics = validate_evaluation(
        evaluation_dir=evaluation_dir,
        expected_pair_ids=expected_pair_ids,
        predictions_path=prediction_path,
        adjudication_path=adjudication_path,
    )
    prepare_output(output_dir)

    for filename, source in evaluation_paths.items():
        copy_file(source, output_dir / filename)
    copy_file(prediction_path, output_dir / "predictions.json")
    copy_file(metadata_path, output_dir / "run_metadata.json")
    if adjudication_path is not None:
        copy_file(adjudication_path, output_dir / OPTIONAL_ADJUDICATION_FILENAME)

    artifact_names = list(COPIED_FILENAMES)
    if adjudication_path is not None:
        artifact_names.append(OPTIONAL_ADJUDICATION_FILENAME)
    artifacts = {
        name: projector.sha256_file(output_dir / name)
        for name in sorted(artifact_names)
    }
    snapshot = {
        "artifact_type": "candidate_relation_evaluation_snapshot",
        "version": "v0.1",
        "evaluation_status": "final",
        "condition": condition,
        "method_commit": metadata["git_commit_at_start"],
        "contract": binding(contract_path),
        "preparation": binding(prepared["marker_path"]),
        "run_completion": binding(run_dir / diagnostic_runner.RUN_MARKER_NAME),
        "implementation": binding(Path(__file__).resolve()),
        "artifacts": artifacts,
        "counts": {
            "pairs": len(expected_pair_ids),
            "primary_pairs": metrics["primary_scored_pairs"],
            "manual_adjudications": metrics["manual_adjudication_count"],
            "pending_adjudications": metrics["pending_adjudication_count"],
        },
        "source": {
            "evaluation_dir": display_path(evaluation_dir),
            "predictions": binding(prediction_path),
            "run_metadata": binding(metadata_path),
            "adjudication": binding(adjudication_path)
            if adjudication_path is not None
            else None,
        },
    }
    projector.atomic_write(output_dir / SNAPSHOT_FILENAME, snapshot)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = resolve_path(args.run_dir)
    prepared_dir = (
        resolve_path(args.prepared_dir)
        if args.prepared_dir
        else diagnostic_runner.DEFAULT_PREPARATION_ROOT / args.condition
    )
    evaluation_dir = (
        resolve_path(args.evaluation_dir)
        if args.evaluation_dir
        else run_dir / "evaluation"
    )
    output_dir = (
        resolve_path(args.output_dir)
        if args.output_dir
        else run_dir / "relation_evaluation"
    )
    adjudication_path = resolve_path(args.adjudication) if args.adjudication else None
    try:
        snapshot = finalize_evaluation(
            condition=args.condition,
            contract_path=resolve_path(args.contract),
            prepared_dir=prepared_dir,
            run_dir=run_dir,
            evaluation_dir=evaluation_dir,
            adjudication_path=adjudication_path,
            output_dir=output_dir,
        )
    except (
        EvaluationFinalizationError,
        diagnostic_runner.DiagnosticRunError,
        preparer.PreparationError,
        projector.ProjectionError,
        RuntimeError,
    ) as exc:
        print(f"Candidate Relation evaluation finalization failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Finalized {snapshot['condition']} Relation evaluation: "
        f"{snapshot['counts']['pairs']} pairs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
