#!/usr/bin/env python3
"""Evaluate Experiment 003-1 canonical Connection candidate generation."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_connection_candidates import (
    COMPLETION_FILENAME,
    DEFAULT_FREEZE_MANIFEST,
    DEFAULT_PAIR_UNIVERSE,
    METADATA_FILENAME,
    ROOT,
    SELECTION_FILENAME,
    CandidateGenerationError,
    binding,
    display_path,
    load_json,
    resolve_path,
    serialize_json,
    sha256_file,
    validate_selection,
)


DEFAULT_GROUND_TRUTH = (
    ROOT / "benchmark" / "connection_discovery" / "development_v0_1" / "ground_truth.json"
)
DEFAULT_SUCCESS_CRITERIA = (
    ROOT / "benchmark" / "connection_discovery_success_criteria_v0_1.json"
)
EVALUATOR_VERSION = "connection_candidate_evaluator_v0.1"
OUTPUT_FILENAMES = (
    "metrics.json",
    "matches.json",
    "errors.json",
    "per_relation_metrics.json",
    "stratum_metrics.json",
    "evaluation_complete.json",
)


class CandidateEvaluationError(ValueError):
    """Raised when an evaluation bundle is structurally invalid."""


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(serialize_json(value))
        temporary = Path(handle.name)
    os.replace(temporary, path)


def validate_generation_bundle(
    *,
    selection: dict[str, Any],
    metadata: dict[str, Any],
    completion: dict[str, Any],
    selection_path: Path,
    metadata_path: Path,
    completion_path: Path,
    pair_universe: dict[str, Any],
    pair_universe_path: Path,
    freeze_manifest_path: Path,
) -> list[str]:
    errors = validate_selection(selection, pair_universe)
    if metadata.get("artifact_type") != "connection_candidate_generation_metadata":
        errors.append("metadata.artifact_type is invalid")
    if metadata.get("status") != "final":
        errors.append("metadata.status is not final")
    integrity = metadata.get("integrity")
    expected_integrity = {
        "gold_artifacts_read": False,
        "duplicate_pair_count": 0,
        "unknown_pair_count": 0,
        "endpoint_mismatch_count": 0,
        "self_pair_count": 0,
    }
    if integrity != expected_integrity:
        errors.append("metadata.integrity declaration mismatch")
    if metadata.get("output") != binding(selection_path):
        errors.append("metadata.output binding is stale")
    if metadata.get("freeze_manifest") != binding(freeze_manifest_path):
        errors.append("metadata.freeze_manifest binding is stale")
    if metadata.get("method") != selection.get("method"):
        errors.append("metadata.method differs from selection")
    if metadata.get("inputs") != selection.get("inputs"):
        errors.append("metadata.inputs differs from selection")
    elif metadata.get("inputs", {}).get("pair_universe") != binding(
        pair_universe_path
    ):
        errors.append("metadata pair-universe binding is stale")
    execution_commit = metadata.get("execution_commit_declared")
    if not isinstance(execution_commit, str) or re.fullmatch(
        r"[0-9a-f]{40}", execution_commit
    ) is None:
        errors.append("metadata.execution_commit_declared is invalid")
    generator = metadata.get("generator")
    if not isinstance(generator, dict):
        errors.append("metadata.generator is invalid")
    else:
        generator_path = resolve_path(generator.get("path", ""))
        if not generator_path.is_file():
            errors.append("metadata.generator path is missing")
        elif generator.get("sha256") != sha256_file(generator_path):
            errors.append("metadata.generator binding is stale")
    if completion.get("artifact_type") != "connection_candidate_generation_complete":
        errors.append("completion.artifact_type is invalid")
    if completion.get("status") != "final":
        errors.append("completion.status is not final")
    expected_artifacts = {
        "selection": binding(selection_path),
        "metadata": binding(metadata_path),
    }
    if completion.get("artifacts") != expected_artifacts:
        errors.append("completion artifact bindings are stale")
    if not completion_path.is_file():
        errors.append("completion marker is missing")
    if completion.get("execution_commit_declared") != metadata.get(
        "execution_commit_declared"
    ):
        errors.append("execution commit mismatch")
    if completion.get("method") != selection.get("method"):
        errors.append("completion.method differs from selection")
    expected_counts = {
        "universe_pairs": selection.get("universe_pair_count"),
        "selected_pairs": selection.get("selected_pair_count"),
    }
    if completion.get("counts") != expected_counts:
        errors.append("completion.counts mismatch")
    return errors


def validate_frozen_evaluation_inputs(
    *,
    freeze_manifest: dict[str, Any],
    pair_universe_path: Path,
    ground_truth_path: Path,
    success_criteria_path: Path,
) -> list[str]:
    errors: list[str] = []
    if freeze_manifest.get("artifact_type") != (
        "connection_discovery_benchmark_freeze_manifest"
    ):
        errors.append("freeze manifest artifact_type is invalid")
    if freeze_manifest.get("status") != "frozen_content_binding":
        errors.append("freeze manifest status is invalid")
    frozen = freeze_manifest.get("frozen_artifacts")
    if not isinstance(frozen, dict):
        return errors + ["freeze manifest frozen_artifacts is invalid"]
    expected = {
        "pair_universe": pair_universe_path,
        "ground_truth": ground_truth_path,
        "success_criteria": success_criteria_path,
    }
    for name, path in expected.items():
        if frozen.get(name) != binding(path):
            errors.append(f"frozen {name} binding mismatch")
    return errors


def score_selection(
    *,
    pair_universe: dict[str, Any],
    ground_truth: dict[str, Any],
    selection: dict[str, Any],
    success_criteria: dict[str, Any],
) -> dict[str, Any]:
    universe_pairs = pair_universe["pairs"]
    ground_truth_pairs = ground_truth["pairs"]
    universe_by_id = {item["canonical_pair_id"]: item for item in universe_pairs}
    truth_by_id = {item["canonical_pair_id"]: item for item in ground_truth_pairs}
    if len(universe_by_id) != len(universe_pairs):
        raise CandidateEvaluationError("Pair universe contains duplicate IDs")
    if set(universe_by_id) != set(truth_by_id):
        raise CandidateEvaluationError("Ground Truth pair set differs from universe")
    selected_ids = {
        item["canonical_pair_id"] for item in selection["selected_pairs"]
    }

    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    primary_positive_ids: set[str] = set()
    primary_negative_ids: set[str] = set()
    diagnostic_ids: set[str] = set()
    relation_support: Counter[str] = Counter()
    relation_selected: Counter[str] = Counter()
    strata: dict[str, dict[str, int]] = defaultdict(lambda: Counter())

    for pair in universe_pairs:
        pair_id = pair["canonical_pair_id"]
        truth = truth_by_id[pair_id]
        selected = pair_id in selected_ids
        category = truth["category"]
        primary = truth["primary_scoring_eligible"]
        positive = primary and category == "IN_SCHEMA_CONNECTION"
        negative = primary and category == "NO_IN_SCHEMA_CONNECTION"
        diagnostic = not primary
        if positive:
            primary_positive_ids.add(pair_id)
        elif negative:
            primary_negative_ids.add(pair_id)
        elif diagnostic:
            diagnostic_ids.add(pair_id)
        else:
            raise CandidateEvaluationError(f"Unsupported scoring state for {pair_id}")

        relation_type = truth["gold_edge"]["relation_type"] if truth["gold_edge"] else None
        if positive and relation_type:
            relation_support[relation_type] += 1
            if selected:
                relation_selected[relation_type] += 1

        scope_labels = [truth["provenance_stratum"]]
        for name, flag in truth["scope_flags"].items():
            if flag:
                scope_labels.append(name)
        if diagnostic and category == "IN_SCHEMA_CONNECTION":
            scope_labels.append("diagnostic_compositional_positive")
        for label in scope_labels:
            strata[label]["all_pairs"] += 1
            if selected:
                strata[label]["selected_pairs"] += 1
            if positive:
                strata[label]["primary_positive_pairs"] += 1
                if selected:
                    strata[label]["selected_primary_positive_pairs"] += 1
            if diagnostic and category == "IN_SCHEMA_CONNECTION":
                strata[label]["diagnostic_positive_pairs"] += 1
                if selected:
                    strata[label]["selected_diagnostic_positive_pairs"] += 1

        if positive:
            outcome = "retrieved_primary_positive" if selected else "missed_primary_positive"
        elif negative:
            outcome = "retained_primary_negative" if selected else "filtered_primary_negative"
        else:
            outcome = "selected_diagnostic" if selected else "omitted_diagnostic"
        record = {
            "canonical_pair_id": pair_id,
            "ko_a": pair["ko_a"],
            "ko_b": pair["ko_b"],
            "provenance_stratum": pair["provenance_stratum"],
            "scope_flags": pair["scope_flags"],
            "gold_category": category,
            "primary_scoring_eligible": primary,
            "gold_relation_type": relation_type,
            "selected": selected,
            "outcome": outcome,
        }
        matches.append(record)
        if outcome in {"missed_primary_positive", "retained_primary_negative"}:
            errors.append({
                "error_type": outcome,
                "canonical_pair_id": pair_id,
                "gold_relation_type": relation_type,
                "provenance_stratum": pair["provenance_stratum"],
            })

    retrieved_positive = len(primary_positive_ids & selected_ids)
    retrieved_negative = len(primary_negative_ids & selected_ids)
    selected_diagnostic = len(diagnostic_ids & selected_ids)
    selected_primary = retrieved_positive + retrieved_negative
    primary_count = len(primary_positive_ids) + len(primary_negative_ids)
    total_count = len(universe_pairs)
    selected_count = len(selected_ids)
    counts = {
        "eligible_pairs": total_count,
        "primary_scored_pairs": primary_count,
        "primary_positive_pairs": len(primary_positive_ids),
        "primary_negative_pairs": len(primary_negative_ids),
        "diagnostic_pairs": len(diagnostic_ids),
        "selected_pairs": selected_count,
        "selected_primary_pairs": selected_primary,
        "retrieved_primary_positive_pairs": retrieved_positive,
        "missed_primary_positive_pairs": len(primary_positive_ids) - retrieved_positive,
        "retained_primary_negative_pairs": retrieved_negative,
        "filtered_primary_negative_pairs": len(primary_negative_ids) - retrieved_negative,
        "selected_diagnostic_pairs": selected_diagnostic,
        "duplicate_pairs": 0,
        "self_pairs": 0,
    }
    metrics = {
        "primary_positive_candidate_recall": safe_ratio(
            retrieved_positive, len(primary_positive_ids)
        ),
        "candidate_precision_primary": safe_ratio(retrieved_positive, selected_primary),
        "workload_retention_total": safe_ratio(selected_count, total_count),
        "workload_reduction_total": (
            1 - selected_count / total_count if total_count else None
        ),
        "actionable_yield_total": safe_ratio(retrieved_positive, selected_count),
    }

    relation_rows = []
    for relation_type in ground_truth["allowed_relation_types"]:
        support = relation_support[relation_type]
        retrieved = relation_selected[relation_type]
        relation_rows.append({
            "relation_type": relation_type,
            "primary_positive_support": support,
            "retrieved_primary_positives": retrieved,
            "candidate_recall": safe_ratio(retrieved, support),
        })

    stratum_rows = []
    for label in sorted(strata):
        row = dict(strata[label])
        row.update({
            "stratum": label,
            "primary_positive_candidate_recall": safe_ratio(
                row.get("selected_primary_positive_pairs", 0),
                row.get("primary_positive_pairs", 0),
            ),
            "diagnostic_positive_candidate_recall": safe_ratio(
                row.get("selected_diagnostic_positive_pairs", 0),
                row.get("diagnostic_positive_pairs", 0),
            ),
            "selection_rate": safe_ratio(
                row.get("selected_pairs", 0), row.get("all_pairs", 0)
            ),
        })
        stratum_rows.append(row)

    criteria = success_criteria["stage_003_1_candidate_generation"]
    row_by_stratum = {row["stratum"]: row for row in stratum_rows}
    relation_gate_rows = [
        row for row in relation_rows if row["primary_positive_support"] >= 4
    ]
    gate_checks = {
        "primary_positive_candidate_recall": {
            "value": metrics["primary_positive_candidate_recall"],
            "operator": ">=",
            "threshold": criteria["primary_positive_candidate_recall_minimum"],
        },
        "missed_primary_positives": {
            "value": counts["missed_primary_positive_pairs"],
            "operator": "<=",
            "threshold": criteria["maximum_missed_primary_positives"],
        },
        "same_course_primary_positive_recall": {
            "value": row_by_stratum["same_course_cross_lecture"][
                "primary_positive_candidate_recall"
            ],
            "operator": ">=",
            "threshold": criteria["same_course_primary_positive_recall_minimum"],
        },
        "cross_course_primary_positive_recall": {
            "value": row_by_stratum["cross_course"][
                "primary_positive_candidate_recall"
            ],
            "operator": ">=",
            "threshold": criteria["cross_course_primary_positive_recall_minimum"],
        },
        "per_relation_recall": {
            "value": min(row["candidate_recall"] for row in relation_gate_rows),
            "operator": ">=",
            "threshold": criteria[
                "per_relation_recall_minimum_for_labels_with_support_at_least_4"
            ],
            "included_relations": [row["relation_type"] for row in relation_gate_rows],
        },
        "workload_reduction": {
            "value": metrics["workload_reduction_total"],
            "operator": ">=",
            "threshold": criteria["workload_reduction_minimum"],
        },
        "duplicate_pairs": {
            "value": counts["duplicate_pairs"],
            "operator": "<=",
            "threshold": criteria["maximum_duplicate_pairs"],
        },
        "self_pairs": {
            "value": counts["self_pairs"],
            "operator": "<=",
            "threshold": criteria["maximum_self_pairs"],
        },
    }
    for check in gate_checks.values():
        value = check["value"]
        threshold = check["threshold"]
        check["passed"] = (
            value is not None
            and (value >= threshold if check["operator"] == ">=" else value <= threshold)
        )
    method_name = selection["method"]["name"]
    control = method_name == "all_pairs"
    gate = {
        "applicable": not control,
        "outcome": (
            "not_applicable_control"
            if control
            else "passed"
            if all(check["passed"] for check in gate_checks.values())
            else "failed"
        ),
        "checks": gate_checks,
        "selection_rule": criteria["selection_rule"],
    }
    return {
        "metrics": {
            "artifact_type": "connection_candidate_generation_metrics",
            "version": "v0.1",
            "evaluation_status": "final",
            "method": selection["method"],
            "counts": counts,
            "metrics": metrics,
            "gate_assessment": gate,
            "claim_limit": (
                "All primary positives are overlap_bridge; passing does not validate "
                "disjoint-provenance implicit discovery."
            ),
        },
        "matches": matches,
        "errors": errors,
        "per_relation_metrics": {
            "artifact_type": "connection_candidate_per_relation_metrics",
            "version": "v0.1",
            "relations": relation_rows,
        },
        "stratum_metrics": {
            "artifact_type": "connection_candidate_stratum_metrics",
            "version": "v0.1",
            "strata": stratum_rows,
        },
    }


def prepare_output_dir(path: Path) -> None:
    existing = [path / name for name in OUTPUT_FILENAMES if (path / name).exists()]
    if existing:
        raise CandidateEvaluationError(
            "Refusing to overwrite existing evaluation artifacts: "
            + ", ".join(display_path(item) for item in existing)
        )
    path.mkdir(parents=True, exist_ok=True)


def write_evaluation(
    output_dir: Path,
    artifacts: dict[str, Any],
    *,
    inputs: dict[str, Path],
) -> None:
    outputs: dict[str, dict[str, str]] = {}
    for key in ("metrics", "matches", "errors", "per_relation_metrics", "stratum_metrics"):
        path = output_dir / f"{key}.json"
        atomic_write(path, artifacts[key])
        outputs[key] = binding(path)
    completion = {
        "artifact_type": "connection_candidate_evaluation_complete",
        "version": "v0.1",
        "evaluation_status": "final",
        "inputs": {name: binding(path) for name, path in inputs.items()},
        "evaluator": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": EVALUATOR_VERSION,
        },
        "outputs": outputs,
        "counts": artifacts["metrics"]["counts"],
        "gate_outcome": artifacts["metrics"]["gate_assessment"]["outcome"],
    }
    atomic_write(output_dir / "evaluation_complete.json", completion)


def write_invalid_evaluation(
    output_dir: Path,
    *,
    messages: list[str],
    inputs: dict[str, Path],
) -> None:
    errors = [
        {"error_type": "fatal_integrity_error", "message": message}
        for message in messages
    ]
    errors_path = output_dir / "errors.json"
    atomic_write(errors_path, errors)
    available_inputs = {
        name: binding(path) for name, path in inputs.items() if path.is_file()
    }
    completion = {
        "artifact_type": "connection_candidate_evaluation_complete",
        "version": "v0.1",
        "evaluation_status": "invalid",
        "inputs": available_inputs,
        "evaluator": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": EVALUATOR_VERSION,
        },
        "outputs": {"errors": binding(errors_path)},
        "fatal_error_count": len(errors),
    }
    atomic_write(output_dir / "evaluation_complete.json", completion)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-universe", default=str(DEFAULT_PAIR_UNIVERSE))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument("--success-criteria", default=str(DEFAULT_SUCCESS_CRITERIA))
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE_MANIFEST))
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--evaluation-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_dir = resolve_path(args.candidate_dir)
    evaluation_dir = resolve_path(args.evaluation_dir)
    input_paths = {
        "pair_universe": resolve_path(args.pair_universe),
        "ground_truth": resolve_path(args.ground_truth),
        "success_criteria": resolve_path(args.success_criteria),
        "freeze_manifest": resolve_path(args.freeze_manifest),
        "candidate_selection": candidate_dir / SELECTION_FILENAME,
        "candidate_metadata": candidate_dir / METADATA_FILENAME,
        "candidate_completion": candidate_dir / COMPLETION_FILENAME,
    }
    output_prepared = False
    try:
        prepare_output_dir(evaluation_dir)
        output_prepared = True
        pair_universe = load_json(input_paths["pair_universe"])
        ground_truth = load_json(input_paths["ground_truth"])
        success_criteria = load_json(input_paths["success_criteria"])
        freeze_manifest = load_json(input_paths["freeze_manifest"])
        selection = load_json(input_paths["candidate_selection"])
        metadata = load_json(input_paths["candidate_metadata"])
        completion = load_json(input_paths["candidate_completion"])
        errors = validate_generation_bundle(
            selection=selection,
            metadata=metadata,
            completion=completion,
            selection_path=input_paths["candidate_selection"],
            metadata_path=input_paths["candidate_metadata"],
            completion_path=input_paths["candidate_completion"],
            pair_universe=pair_universe,
            pair_universe_path=input_paths["pair_universe"],
            freeze_manifest_path=input_paths["freeze_manifest"],
        )
        errors.extend(
            validate_frozen_evaluation_inputs(
                freeze_manifest=freeze_manifest,
                pair_universe_path=input_paths["pair_universe"],
                ground_truth_path=input_paths["ground_truth"],
                success_criteria_path=input_paths["success_criteria"],
            )
        )
        if errors:
            raise CandidateEvaluationError("; ".join(errors))
        artifacts = score_selection(
            pair_universe=pair_universe,
            ground_truth=ground_truth,
            selection=selection,
            success_criteria=success_criteria,
        )
        write_evaluation(evaluation_dir, artifacts, inputs=input_paths)
    except (CandidateGenerationError, CandidateEvaluationError) as exc:
        if output_prepared:
            write_invalid_evaluation(
                evaluation_dir,
                messages=[str(exc)],
                inputs=input_paths,
            )
        print(f"Candidate evaluation failed: {exc}")
        return 1
    print(
        f"Evaluated {selection['method']['name']}: "
        f"{artifacts['metrics']['gate_assessment']['outcome']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
