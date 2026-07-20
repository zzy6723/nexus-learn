#!/usr/bin/env python3
"""Finalize the four-method Experiment 003-1 development comparison."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_connection_candidates import (  # noqa: E402
    DEFAULT_FREEZE_MANIFEST,
    ROOT,
    binding,
    display_path,
    load_json,
    resolve_path,
    serialize_json,
    sha256_file,
)


METHODS = (
    "all_pairs",
    "overlap_bridge",
    "lexical_only",
    "hybrid_provenance_lexical",
)
DEFAULT_RUNS_ROOT = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_1_candidate_generation"
    / "runs"
    / "development_v0_1"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_1_candidate_generation"
)
COMPARISON_FILENAME = "comparison.json"
COMPLETION_FILENAME = "development_validation_complete.json"
FINALIZER_VERSION = "connection_candidate_validation_finalizer_v0.1"


class FinalizationError(ValueError):
    """Raised when formal candidate evaluations cannot be finalized."""


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(serialize_json(value))
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _bound_output_is_current(binding_value: Any) -> bool:
    if not isinstance(binding_value, dict) or set(binding_value) != {"path", "sha256"}:
        return False
    path = resolve_path(binding_value["path"])
    return path.is_file() and sha256_file(path) == binding_value["sha256"]


def load_method_result(
    runs_root: Path, method: str, method_commit: str
) -> dict[str, Any]:
    run_dir = runs_root / method / "run_01"
    generation_dir = run_dir / "generation"
    evaluation_dir = run_dir / "evaluation"
    metadata_path = generation_dir / "metadata.json"
    generation_complete_path = generation_dir / "generation_complete.json"
    metrics_path = evaluation_dir / "metrics.json"
    relation_path = evaluation_dir / "per_relation_metrics.json"
    stratum_path = evaluation_dir / "stratum_metrics.json"
    evaluation_complete_path = evaluation_dir / "evaluation_complete.json"
    metadata = load_json(metadata_path)
    generation_complete = load_json(generation_complete_path)
    metrics = load_json(metrics_path)
    relations = load_json(relation_path)
    strata = load_json(stratum_path)
    evaluation_complete = load_json(evaluation_complete_path)

    errors: list[str] = []
    if metadata.get("execution_commit_declared") != method_commit:
        errors.append("method commit mismatch")
    if metadata.get("status") != "final":
        errors.append("generation metadata is not final")
    if generation_complete.get("status") != "final":
        errors.append("generation completion is not final")
    if evaluation_complete.get("evaluation_status") != "final":
        errors.append("evaluation completion is not final")
    if metrics.get("evaluation_status") != "final":
        errors.append("metrics are not final")
    if metrics.get("method", {}).get("name") != method:
        errors.append("method identity mismatch")
    for name, item in evaluation_complete.get("outputs", {}).items():
        if not _bound_output_is_current(item):
            errors.append(f"stale evaluation output binding: {name}")
    if errors:
        raise FinalizationError(f"{method}: " + "; ".join(errors))

    stratum_map = {item["stratum"]: item for item in strata["strata"]}
    relation_map = {
        item["relation_type"]: item
        for item in relations["relations"]
        if item["primary_positive_support"]
    }
    values = metrics["metrics"]
    counts = metrics["counts"]
    return {
        "method": method,
        "method_id": metrics["method"]["id"],
        "gate_outcome": metrics["gate_assessment"]["outcome"],
        "selected_pairs": counts["selected_pairs"],
        "retrieved_primary_positive_pairs": counts[
            "retrieved_primary_positive_pairs"
        ],
        "missed_primary_positive_pairs": counts["missed_primary_positive_pairs"],
        "primary_positive_candidate_recall": values[
            "primary_positive_candidate_recall"
        ],
        "candidate_precision_primary": values["candidate_precision_primary"],
        "workload_reduction_total": values["workload_reduction_total"],
        "same_course_primary_positive_recall": stratum_map[
            "same_course_cross_lecture"
        ]["primary_positive_candidate_recall"],
        "cross_course_primary_positive_recall": stratum_map["cross_course"][
            "primary_positive_candidate_recall"
        ],
        "diagnostic_compositional_positive_recall": stratum_map[
            "diagnostic_compositional_positive"
        ]["diagnostic_positive_candidate_recall"],
        "per_relation_primary_recall": {
            name: item["candidate_recall"] for name, item in relation_map.items()
        },
        "duplicate_pairs": counts["duplicate_pairs"],
        "self_pairs": counts["self_pairs"],
        "artifacts": {
            "generation_complete": binding(generation_complete_path),
            "evaluation_complete": binding(evaluation_complete_path),
            "metrics": binding(metrics_path),
        },
    }


def build_comparison(
    *,
    rows: list[dict[str, Any]],
    method_commit: str,
    freeze_manifest_path: Path,
) -> dict[str, Any]:
    by_method = {row["method"]: row for row in rows}
    overlap = by_method["overlap_bridge"]
    if overlap["gate_outcome"] != "passed":
        raise FinalizationError("Selected primary-route method did not pass")
    if overlap["primary_positive_candidate_recall"] != 1.0:
        raise FinalizationError("Selected primary-route method lost a primary positive")
    return {
        "artifact_type": "connection_candidate_development_comparison",
        "version": "v0.1",
        "evaluation_status": "final",
        "method_commit": method_commit,
        "freeze_manifest": binding(freeze_manifest_path),
        "methods": rows,
        "decision": {
            "selected_method": "overlap_bridge_v0.1",
            "selected_role": "experiment_003_2_v0_1_primary_route",
            "selection_basis": [
                "Retained all 41 primary positives.",
                "Reduced the eligible classification workload by 67.70%.",
                "Had the highest primary candidate precision among passing non-control methods.",
                "Introduced no duplicate, self-pair, unknown-endpoint, or alignment errors.",
            ],
            "scope_limit": (
                "The policy is selected only for explicit overlap-bridge v0.1 "
                "classification. It is a provenance shortcut, not a validated "
                "implicit cross-document candidate method."
            ),
            "diagnostic_method": "lexical_only_v0.1",
            "diagnostic_basis": (
                "Lexical-only retrieval retained four of five disjoint-provenance "
                "compositional positives but missed one primary REQUIRES pair."
            ),
        },
        "next_stage": "003_2_oracle_canonical_connection_discovery",
    }


def write_finalization(
    *,
    output_dir: Path,
    comparison: dict[str, Any],
    method_commit: str,
    freeze_manifest_path: Path,
) -> tuple[Path, Path]:
    comparison_path = output_dir / COMPARISON_FILENAME
    completion_path = output_dir / COMPLETION_FILENAME
    existing = [path for path in (comparison_path, completion_path) if path.exists()]
    if existing:
        raise FinalizationError(
            "Refusing to overwrite existing finalization artifacts: "
            + ", ".join(display_path(path) for path in existing)
        )
    atomic_write(comparison_path, comparison)
    completion = {
        "artifact_type": "connection_candidate_development_validation_complete",
        "version": "v0.1",
        "status": "complete_with_scope_limitation",
        "method_commit": method_commit,
        "freeze_manifest": binding(freeze_manifest_path),
        "comparison": binding(comparison_path),
        "method_evaluations": {
            row["method"]: row["artifacts"] for row in comparison["methods"]
        },
        "selected_method": comparison["decision"]["selected_method"],
        "selected_role": comparison["decision"]["selected_role"],
        "claim_limit": comparison["decision"]["scope_limit"],
        "next_stage": comparison["next_stage"],
        "finalizer": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": FINALIZER_VERSION,
        },
    }
    atomic_write(completion_path, completion)
    return comparison_path, completion_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if re.fullmatch(r"[0-9a-f]{40}", args.method_commit) is None:
            raise FinalizationError("method_commit must be a 40-character SHA-1")
        runs_root = resolve_path(args.runs_root)
        output_dir = resolve_path(args.output_dir)
        freeze_manifest_path = resolve_path(args.freeze_manifest)
        rows = [
            load_method_result(runs_root, method, args.method_commit)
            for method in METHODS
        ]
        comparison = build_comparison(
            rows=rows,
            method_commit=args.method_commit,
            freeze_manifest_path=freeze_manifest_path,
        )
        paths = write_finalization(
            output_dir=output_dir,
            comparison=comparison,
            method_commit=args.method_commit,
            freeze_manifest_path=freeze_manifest_path,
        )
    except (FinalizationError, ValueError) as exc:
        print(f"Candidate validation finalization failed: {exc}")
        return 1
    print("Wrote " + " and ".join(display_path(path) for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
