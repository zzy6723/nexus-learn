#!/usr/bin/env python3
"""Bind a final base Relation evaluation to predictions and run metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = {"A0", "A_prime", "B_prime"}
COPIED_FILENAMES = [
    "metrics.json",
    "matches.json",
    "errors.json",
    "predictions.json",
    "run_metadata.json",
]
SNAPSHOT_FILENAME = "evaluation_snapshot.json"


class BundleError(RuntimeError):
    """A fatal final Relation evaluation bundle error."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the snapshot-bound Relation evaluation bundle consumed by "
            "the 002B-1 pipeline evaluator."
        )
    )
    parser.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    parser.add_argument(
        "--base-evaluation-dir",
        required=True,
        help="Final output directory from evaluate_relation_extraction.py.",
    )
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--run-metadata", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"Unable to read {label} {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_source_bundle(
    *,
    condition: str,
    base_evaluation_dir: Path,
    predictions_path: Path,
    run_metadata_path: Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    source_paths = {
        "metrics": base_evaluation_dir / "metrics.json",
        "matches": base_evaluation_dir / "matches.json",
        "errors": base_evaluation_dir / "errors.json",
        "pending": base_evaluation_dir / "adjudication_pending.json",
        "predictions": predictions_path,
        "run_metadata": run_metadata_path,
    }
    missing = [path for path in source_paths.values() if not path.is_file()]
    if missing:
        raise BundleError(f"Missing source artifacts: {[str(path) for path in missing]}")
    metrics = read_json(source_paths["metrics"], label="Relation metrics")
    matches = read_json(source_paths["matches"], label="Relation matches")
    errors = read_json(source_paths["errors"], label="Relation errors")
    pending = read_json(source_paths["pending"], label="Relation pending adjudication")
    predictions = read_json(predictions_path, label="Relation predictions")
    metadata = read_json(run_metadata_path, label="Relation run metadata")
    if not isinstance(metrics, dict) or metrics.get("evaluation_status") != "final":
        raise BundleError("Base Relation evaluation is not final.")
    if not isinstance(pending, list) or pending:
        raise BundleError("Base Relation evaluation still has pending adjudication.")
    if not isinstance(matches, list) or not isinstance(errors, list):
        raise BundleError("Base Relation matches/errors have invalid shapes.")
    if not isinstance(predictions, dict) or not isinstance(
        predictions.get("results"), list
    ):
        raise BundleError("Relation predictions have an invalid shape.")
    if not isinstance(metadata, dict):
        raise BundleError("Relation run metadata must be an object.")
    if (
        metadata.get("run_status") != "completed"
        or metadata.get("request_success") is not True
        or metadata.get("json_parse_success") is not True
        or metadata.get("prediction_schema_valid") is not True
        or metadata.get("finish_reason") != "stop"
    ):
        raise BundleError("Relation run metadata is not a completed valid execution.")
    if condition in {"A_prime", "B_prime"}:
        if metadata.get("condition") != condition:
            raise BundleError("Matched Relation metadata condition is incorrect.")
        for field in ["input_artifact_sha256", "batch_plan_sha256"]:
            value = metadata.get(field)
            if not isinstance(value, str) or len(value) != 64:
                raise BundleError(f"Matched Relation metadata is missing {field}.")
        if metadata.get("request_partitioning") == (
            "one_candidate_pair_per_request_v0_1"
        ):
            for field in [
                "execution_manifest_sha256",
                "execution_batch_plan_sha256",
            ]:
                value = metadata.get(field)
                if not isinstance(value, str) or len(value) != 64:
                    raise BundleError(
                        f"Candidate-scoped Relation metadata is missing {field}."
                    )
            if (
                metadata.get("batch_count")
                != metadata.get("completed_batch_count")
                or metadata.get("batch_count")
                != len(metadata.get("batch_results", []))
            ):
                raise BundleError(
                    "Candidate-scoped Relation execution is incomplete."
                )

    prediction_ids = [
        item.get("pair_id") for item in predictions["results"] if isinstance(item, dict)
    ]
    match_ids = [item.get("pair_id") for item in matches if isinstance(item, dict)]
    if (
        len(prediction_ids) != len(predictions["results"])
        or len(match_ids) != len(matches)
        or len(prediction_ids) != len(set(prediction_ids))
        or len(match_ids) != len(set(match_ids))
        or set(prediction_ids) != set(match_ids)
    ):
        raise BundleError("Predictions and evaluated matches differ in pair IDs.")
    if metrics.get("primary_scored_pairs") != sum(
        item.get("primary_scored") is True for item in matches
    ):
        raise BundleError("Relation metric denominator differs from pair-level matches.")
    return source_paths, metadata


def prepare_output(output_dir: Path, *, overwrite: bool) -> None:
    managed = [*(output_dir / name for name in COPIED_FILENAMES), output_dir / SNAPSHOT_FILENAME]
    existing = [path for path in managed if path.exists()]
    if existing and not overwrite:
        raise BundleError(
            "Evaluation bundle already exists; use a new directory or --overwrite."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / SNAPSHOT_FILENAME
    if marker.exists():
        marker.unlink()
    if overwrite:
        for path in existing:
            if path.exists():
                path.unlink()


def finalize_bundle(
    *,
    condition: str,
    base_evaluation_dir: Path,
    predictions_path: Path,
    run_metadata_path: Path,
    output_dir: Path,
    overwrite: bool,
) -> dict[str, Any]:
    source_paths, source_metadata = validate_source_bundle(
        condition=condition,
        base_evaluation_dir=base_evaluation_dir,
        predictions_path=predictions_path,
        run_metadata_path=run_metadata_path,
    )
    prepare_output(output_dir, overwrite=overwrite)
    for source_name, destination_name in [
        ("metrics", "metrics.json"),
        ("matches", "matches.json"),
        ("errors", "errors.json"),
        ("predictions", "predictions.json"),
    ]:
        shutil.copy2(source_paths[source_name], output_dir / destination_name)

    prediction_hash = sha256_file(output_dir / "predictions.json")
    packaged_metadata = {
        **source_metadata,
        "prediction_sha256": prediction_hash,
        "source_run_metadata": display_path(run_metadata_path),
        "source_run_metadata_sha256": sha256_file(run_metadata_path),
    }
    write_json(output_dir / "run_metadata.json", packaged_metadata)
    snapshot = {
        "artifact_type": "relation_evaluation_snapshot",
        "version": "v0.1",
        "condition": condition,
        "evaluation_status": "final",
        "base_evaluation_dir": display_path(base_evaluation_dir),
        "prediction_sha256": prediction_hash,
        "run_metadata_sha256": sha256_file(output_dir / "run_metadata.json"),
        "metrics_sha256": sha256_file(output_dir / "metrics.json"),
        "matches_sha256": sha256_file(output_dir / "matches.json"),
        "errors_sha256": sha256_file(output_dir / "errors.json"),
        "source": {
            "base_metrics_sha256": sha256_file(source_paths["metrics"]),
            "base_matches_sha256": sha256_file(source_paths["matches"]),
            "base_errors_sha256": sha256_file(source_paths["errors"]),
            "base_pending_sha256": sha256_file(source_paths["pending"]),
            "predictions_path": display_path(predictions_path),
            "run_metadata_path": display_path(run_metadata_path),
        },
    }
    # The snapshot is the validity boundary and is always written last.
    write_json(output_dir / SNAPSHOT_FILENAME, snapshot)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        finalize_bundle(
            condition=args.condition,
            base_evaluation_dir=resolve_path(args.base_evaluation_dir),
            predictions_path=resolve_path(args.predictions),
            run_metadata_path=resolve_path(args.run_metadata),
            output_dir=resolve_path(args.output_dir),
            overwrite=args.overwrite,
        )
    except BundleError as exc:
        print(f"Relation evaluation finalization failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote final Relation evaluation bundle to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
