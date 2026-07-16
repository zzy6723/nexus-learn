#!/usr/bin/env python3
"""Evaluate candidate-pair selection against frozen exhaustive annotations."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.check_candidate_pair_ground_truth import (
    CandidateGroundTruthError,
    validate_candidate_pair_ground_truth,
)
from scripts.generate_candidate_pairs import (
    COMPLETION_FILENAME,
    DEFAULT_OUTPUT_SCHEMA,
    DEFAULT_PAIR_UNIVERSE,
    DEFAULT_PAIR_UNIVERSE_MARKER,
    METADATA_FILENAME,
    ROOT,
    SELECTION_FILENAME,
    CandidatePairGenerationError,
    _atomic_write_text,
    display_path,
    load_json_object,
    resolve_path,
    serialize_json,
    sha256_file,
    sha256_json,
    validate_candidate_selection,
    validate_pair_universe,
    validate_pair_universe_marker,
)


DEFAULT_GROUND_TRUTH = (
    ROOT / "benchmark" / "ground_truth" / "candidate_pairs_development_v0_1.json"
)
DEFAULT_GROUND_TRUTH_MARKER = DEFAULT_GROUND_TRUTH.with_name(
    "candidate_pairs_development_v0_1_complete.json"
)
DEFAULT_SUCCESS_CRITERIA = (
    ROOT / "benchmark" / "candidate_pair_generation_success_criteria_v0_1.json"
)
DEFAULT_CANDIDATE_DIR = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "development_v0_1"
    / "all_pairs"
    / "run_01"
)
DEFAULT_EVALUATION_DIR = DEFAULT_CANDIDATE_DIR / "evaluation"
EVALUATOR_VERSION = "candidate_pair_generation_evaluator_v0.1"
FINAL_ARTIFACT_NAMES = (
    "metrics.json",
    "matches.json",
    "errors.json",
    "per_relation_metrics.json",
    "per_lecture_metrics.json",
    "evaluation_complete.json",
)
PRIMARY_POSITIVE = "IN_SCHEMA_RELATION"
PRIMARY_NEGATIVE = "NO_IN_SCHEMA_RELATION"
DIAGNOSTIC_LABELS = ("OUT_OF_SCHEMA_RELATION", "AMBIGUOUS")


class CandidatePairEvaluationError(ValueError):
    """Raised when candidate evaluation cannot produce final metrics."""


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _binding_path(binding: dict[str, Any]) -> Path:
    return resolve_path(binding["path"])


def _validate_bound_file(
    binding: Any,
    *,
    label: str,
    errors: list[str],
    expected_path: Path | None = None,
) -> None:
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        errors.append(f"{label}: invalid artifact binding")
        return
    path_text = binding.get("path")
    digest = binding.get("sha256")
    if not isinstance(path_text, str) or not path_text:
        errors.append(f"{label}.path: invalid")
        return
    path = resolve_path(path_text)
    if expected_path is not None and path.resolve() != expected_path.resolve():
        errors.append(f"{label}.path: expected {display_path(expected_path)}")
    if not path.is_file():
        errors.append(f"{label}: bound file does not exist: {display_path(path)}")
        return
    if not isinstance(digest, str) or digest != sha256_file(path):
        errors.append(f"{label}.sha256: stale binding")


def validate_ground_truth_completion_marker(
    marker: dict[str, Any],
    *,
    marker_path: Path,
    pair_universe_path: Path,
    ground_truth_path: Path,
    ground_truth_summary: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if marker.get("artifact_type") != "candidate_pair_ground_truth_complete":
        errors.append("ground_truth_marker.artifact_type: invalid")
    if marker.get("version") != "v0.1":
        errors.append("ground_truth_marker.version: invalid")
    if marker.get("completion_status") != "final":
        errors.append("ground_truth_marker.completion_status: must be final")
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("ground_truth_marker.artifacts: must be an object")
        artifacts = {}
    expected_artifact_names = {
        "pair_universe",
        "ground_truth",
        "pair_universe_completion_marker",
        "annotation_guidelines",
        "relation_annotation_guidelines",
        "evaluation_protocol",
        "success_criteria",
        "pair_universe_schema",
        "ground_truth_schema",
    }
    if set(artifacts) != expected_artifact_names:
        errors.append("ground_truth_marker.artifacts: frozen artifact set mismatch")
    for name in sorted(expected_artifact_names):
        binding = artifacts.get(name)
        if name in {
            "annotation_guidelines",
            "relation_annotation_guidelines",
            "evaluation_protocol",
            "success_criteria",
            "pair_universe_schema",
            "ground_truth_schema",
        }:
            if not isinstance(binding, dict):
                errors.append(f"ground_truth_marker.artifacts.{name}: invalid binding")
                continue
            comparable = {key: binding.get(key) for key in ("path", "sha256")}
        else:
            comparable = binding
        expected_path = None
        if name == "pair_universe":
            expected_path = pair_universe_path
        elif name == "ground_truth":
            expected_path = ground_truth_path
        elif name == "pair_universe_completion_marker":
            expected_path = pair_universe_path.with_name(
                "pair_universe_complete.json"
            )
        _validate_bound_file(
            comparable,
            label=f"ground_truth_marker.artifacts.{name}",
            errors=errors,
            expected_path=expected_path,
        )

    checker = marker.get("checker")
    if not isinstance(checker, dict):
        errors.append("ground_truth_marker.checker: invalid binding")
    else:
        comparable = {key: checker.get(key) for key in ("path", "sha256")}
        _validate_bound_file(
            comparable,
            label="ground_truth_marker.checker",
            errors=errors,
        )
        if checker.get("version") != "candidate_pair_ground_truth_checker_v0.1":
            errors.append("ground_truth_marker.checker.version: invalid")

    counts = marker.get("counts")
    if not isinstance(counts, dict):
        errors.append("ground_truth_marker.counts: invalid")
    else:
        expected_counts = {
            "total_pairs": ground_truth_summary["pair_count"],
            "labels": ground_truth_summary["label_counts"],
            "annotation_statuses": ground_truth_summary[
                "annotation_status_counts"
            ],
            "primary_denominator": ground_truth_summary["primary_denominator"],
            "diagnostic_denominator": ground_truth_summary[
                "diagnostic_denominator"
            ],
            "pending_workflow_items": ground_truth_summary[
                "pending_workflow_items"
            ],
        }
        if counts != expected_counts:
            errors.append("ground_truth_marker.counts: denominator reconciliation failure")
    if not marker_path.is_file():
        errors.append("ground_truth_marker: marker file is missing")
    return errors


def validate_generation_completion_marker(
    marker: dict[str, Any],
    *,
    marker_path: Path,
    selection_path: Path,
    metadata_path: Path,
    pair_universe_path: Path,
    pair_universe_marker_path: Path,
    output_schema_path: Path,
    selection: dict[str, Any],
    metadata: dict[str, Any],
    pair_universe: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if marker.get("artifact_type") != "candidate_pair_generation_complete":
        errors.append("candidate_marker.artifact_type: invalid")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        errors.append("candidate_marker: must be final v0.1")
    artifacts = marker.get("artifacts")
    expected_paths = {
        "candidate_selection": selection_path,
        "metadata": metadata_path,
        "pair_universe": pair_universe_path,
        "pair_universe_completion_marker": pair_universe_marker_path,
        "output_schema": output_schema_path,
    }
    if not isinstance(artifacts, dict) or set(artifacts) != set(expected_paths):
        errors.append("candidate_marker.artifacts: artifact set mismatch")
        artifacts = {}
    for name, expected_path in expected_paths.items():
        _validate_bound_file(
            artifacts.get(name),
            label=f"candidate_marker.artifacts.{name}",
            errors=errors,
            expected_path=expected_path,
        )

    if metadata.get("artifact_type") != "candidate_pair_generation_metadata":
        errors.append("candidate_metadata.artifact_type: invalid")
    if metadata.get("version") != "v0.1" or metadata.get("status") != "final":
        errors.append("candidate_metadata: must be final v0.1")
    output = metadata.get("output")
    if not isinstance(output, dict):
        errors.append("candidate_metadata.output: invalid")
    else:
        if output.get("path") != display_path(selection_path):
            errors.append("candidate_metadata.output.path: stale binding")
        if output.get("sha256") != sha256_file(selection_path):
            errors.append("candidate_metadata.output.sha256: stale binding")
        if output.get("selected_pair_count") != selection.get("selected_pair_count"):
            errors.append("candidate_metadata.output.selected_pair_count: mismatch")
    integrity = metadata.get("integrity")
    expected_integrity = {
        "duplicate_pair_count": 0,
        "unknown_pair_count": 0,
        "endpoint_mismatch_count": 0,
        "order_matches_universe": True,
        "gold_artifacts_read": False,
    }
    if integrity != expected_integrity:
        errors.append("candidate_metadata.integrity: integrity declaration mismatch")
    if metadata.get("generator") != selection.get("generator"):
        errors.append("candidate_metadata.generator: selection mismatch")

    counts = marker.get("counts")
    expected_counts = {
        "universe_pairs": pair_universe.get("total_pair_count"),
        "selected_pairs": selection.get("selected_pair_count"),
        "missing_universe_pairs": pair_universe.get("total_pair_count", 0)
        - selection.get("selected_pair_count", 0),
        "extra_pairs": 0,
        "duplicate_pairs": 0,
        "endpoint_mismatches": 0,
    }
    if counts != expected_counts:
        errors.append("candidate_marker.counts: count mismatch")
    generator = marker.get("generator")
    selection_generator = selection.get("generator", {})
    if not isinstance(generator, dict):
        errors.append("candidate_marker.generator: invalid")
    else:
        if generator.get("id") != selection_generator.get("id"):
            errors.append("candidate_marker.generator.id: selection mismatch")
        if generator.get("version") != selection_generator.get("version"):
            errors.append("candidate_marker.generator.version: selection mismatch")
        if generator.get("config_sha256") != selection_generator.get(
            "config_sha256"
        ):
            errors.append("candidate_marker.generator.config_sha256: mismatch")
        implementation = generator.get("implementation")
        if implementation != selection_generator.get("implementation"):
            errors.append("candidate_marker.generator.implementation: mismatch")
        _validate_bound_file(
            implementation,
            label="candidate_marker.generator.implementation",
            errors=errors,
        )
    if not marker_path.is_file():
        errors.append("candidate_marker: marker file is missing")
    return errors


def _outcome(candidate_label: str, selected: bool) -> tuple[str, str | None]:
    if candidate_label == PRIMARY_POSITIVE:
        return ("true_positive", None) if selected else (
            "missed_positive",
            "missed_positive",
        )
    if candidate_label == PRIMARY_NEGATIVE:
        return ("retained_negative", "retained_negative") if selected else (
            "filtered_negative",
            None,
        )
    if candidate_label == "OUT_OF_SCHEMA_RELATION":
        return ("diagnostic_selected", "retained_out_of_schema") if selected else (
            "diagnostic_omitted",
            None,
        )
    if candidate_label == "AMBIGUOUS":
        return ("diagnostic_selected", "retained_ambiguous") if selected else (
            "diagnostic_omitted",
            None,
        )
    raise CandidatePairEvaluationError(f"Unsupported candidate label {candidate_label!r}")


def _compute_counts_and_metrics(
    labels: list[str], selected_flags: list[bool]
) -> tuple[dict[str, int], dict[str, float | None], dict[str, dict[str, Any]]]:
    total_pairs = len(labels)
    positive_pairs = sum(label == PRIMARY_POSITIVE for label in labels)
    negative_pairs = sum(label == PRIMARY_NEGATIVE for label in labels)
    diagnostic_pairs = total_pairs - positive_pairs - negative_pairs
    retrieved_pairs = sum(selected_flags)
    retrieved_positive_pairs = sum(
        selected and label == PRIMARY_POSITIVE
        for label, selected in zip(labels, selected_flags)
    )
    retrieved_negative_pairs = sum(
        selected and label == PRIMARY_NEGATIVE
        for label, selected in zip(labels, selected_flags)
    )
    retrieved_diagnostic_pairs = sum(
        selected and label in DIAGNOSTIC_LABELS
        for label, selected in zip(labels, selected_flags)
    )
    primary_pairs = positive_pairs + negative_pairs
    retrieved_primary_pairs = retrieved_positive_pairs + retrieved_negative_pairs
    counts = {
        "total_pairs": total_pairs,
        "primary_pairs": primary_pairs,
        "positive_pairs": positive_pairs,
        "negative_pairs": negative_pairs,
        "diagnostic_pairs": diagnostic_pairs,
        "retrieved_pairs": retrieved_pairs,
        "retrieved_primary_pairs": retrieved_primary_pairs,
        "retrieved_positive_pairs": retrieved_positive_pairs,
        "missed_positive_pairs": positive_pairs - retrieved_positive_pairs,
        "retrieved_negative_pairs": retrieved_negative_pairs,
        "filtered_negative_pairs": negative_pairs - retrieved_negative_pairs,
        "retrieved_diagnostic_pairs": retrieved_diagnostic_pairs,
    }
    metrics = {
        "candidate_recall": safe_ratio(retrieved_positive_pairs, positive_pairs),
        "candidate_precision": safe_ratio(
            retrieved_positive_pairs, retrieved_primary_pairs
        ),
        "retention_rate_primary": safe_ratio(retrieved_primary_pairs, primary_pairs),
        "reduction_ratio_primary": (
            1 - retrieved_primary_pairs / primary_pairs if primary_pairs else None
        ),
        "workload_retained_total": safe_ratio(retrieved_pairs, total_pairs),
        "workload_reduction_total": (
            1 - retrieved_pairs / total_pairs if total_pairs else None
        ),
        "actionable_yield_total": safe_ratio(
            retrieved_positive_pairs, retrieved_pairs
        ),
    }
    diagnostics: dict[str, dict[str, Any]] = {}
    for diagnostic_label in DIAGNOSTIC_LABELS:
        support = sum(label == diagnostic_label for label in labels)
        selected = sum(
            flag and label == diagnostic_label
            for label, flag in zip(labels, selected_flags)
        )
        diagnostics[diagnostic_label] = {
            "support": support,
            "selected": selected,
            "omitted": support - selected,
            "selection_rate": safe_ratio(selected, support),
        }
    return counts, metrics, diagnostics


def score_candidate_selection(
    *,
    pair_universe: dict[str, Any],
    ground_truth: dict[str, Any],
    selection: dict[str, Any],
    success_criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pairs = pair_universe["pairs"]
    annotations = ground_truth["annotations"]
    if len(pairs) != len(annotations):
        raise CandidatePairEvaluationError("Pair and annotation counts differ.")
    annotation_by_id = {item["pair_id"]: item for item in annotations}
    if len(annotation_by_id) != len(annotations):
        raise CandidatePairEvaluationError("Ground truth contains duplicate pair IDs.")
    selected_ids = {item["pair_id"] for item in selection["selected_pairs"]}
    labels: list[str] = []
    selected_flags: list[bool] = []
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for pair in pairs:
        pair_id = pair["pair_id"]
        annotation = annotation_by_id[pair_id]
        candidate_label = annotation["candidate_label"]
        selected = pair_id in selected_ids
        outcome, error_type = _outcome(candidate_label, selected)
        labels.append(candidate_label)
        selected_flags.append(selected)
        match = {
            "pair_id": pair_id,
            "lecture_id": pair["lecture_id"],
            "ko_a": pair["ko_a"],
            "ko_b": pair["ko_b"],
            "gold_candidate_label": candidate_label,
            "selected": selected,
            "candidate_outcome": outcome,
            "primary_confusion_role": (
                "true_positive"
                if candidate_label == PRIMARY_POSITIVE and selected
                else "false_negative"
                if candidate_label == PRIMARY_POSITIVE
                else "false_positive"
                if candidate_label == PRIMARY_NEGATIVE and selected
                else "true_negative"
                if candidate_label == PRIMARY_NEGATIVE
                else None
            ),
        }
        matches.append(match)
        if error_type is not None:
            errors.append(
                {
                    "error_type": error_type,
                    "pair_id": pair_id,
                    "lecture_id": pair["lecture_id"],
                    "gold_candidate_label": candidate_label,
                    "selected": selected,
                }
            )

    counts, metrics, diagnostics = _compute_counts_and_metrics(labels, selected_flags)
    if counts["primary_pairs"] + counts["diagnostic_pairs"] != counts["total_pairs"]:
        raise CandidatePairEvaluationError("Primary and diagnostic denominators do not reconcile.")

    relation_types = ground_truth.get("allowed_relation_types", [])
    per_relation: list[dict[str, Any]] = []
    relation_pair_support: dict[str, set[str]] = defaultdict(set)
    selected_relation_pairs: dict[str, set[str]] = defaultdict(set)
    relation_instance_support: Counter[str] = Counter()
    selected_relation_instances: Counter[str] = Counter()
    for annotation in annotations:
        if annotation["candidate_label"] != PRIMARY_POSITIVE:
            continue
        pair_id = annotation["pair_id"]
        for relation in annotation.get("gold_relations", []):
            relation_type = relation["relation_type"]
            relation_pair_support[relation_type].add(pair_id)
            relation_instance_support[relation_type] += 1
            if pair_id in selected_ids:
                selected_relation_pairs[relation_type].add(pair_id)
                selected_relation_instances[relation_type] += 1
    for relation_type in relation_types:
        pair_support = len(relation_pair_support[relation_type])
        selected_pair_count = len(selected_relation_pairs[relation_type])
        instance_support = relation_instance_support[relation_type]
        selected_instance_count = selected_relation_instances[relation_type]
        per_relation.append(
            {
                "relation_type": relation_type,
                "positive_pair_support": pair_support,
                "selected_positive_pairs": selected_pair_count,
                "candidate_recall": safe_ratio(selected_pair_count, pair_support),
                "relation_instance_support": instance_support,
                "selected_relation_instances": selected_instance_count,
                "relation_instance_coverage": safe_ratio(
                    selected_instance_count, instance_support
                ),
            }
        )

    by_lecture_labels: dict[str, list[str]] = defaultdict(list)
    by_lecture_selected: dict[str, list[bool]] = defaultdict(list)
    for pair, label, selected in zip(pairs, labels, selected_flags):
        by_lecture_labels[pair["lecture_id"]].append(label)
        by_lecture_selected[pair["lecture_id"]].append(selected)
    per_lecture: list[dict[str, Any]] = []
    for lecture_id in sorted(by_lecture_labels):
        lecture_counts, lecture_metrics, lecture_diagnostics = _compute_counts_and_metrics(
            by_lecture_labels[lecture_id], by_lecture_selected[lecture_id]
        )
        per_lecture.append(
            {
                "lecture_id": lecture_id,
                "counts": lecture_counts,
                "metrics": lecture_metrics,
                "diagnostics": lecture_diagnostics,
            }
        )

    generator_name = selection["generator"]["name"]
    if generator_name == "all_pairs":
        gate_assessment = {
            "applicable": False,
            "outcome": "not_applicable_control",
            "reason": (
                "All Pairs is the control and is not required to satisfy the "
                "Rule-Filtered workload-reduction gate."
            ),
        }
    elif success_criteria is None:
        gate_assessment = {
            "applicable": True,
            "outcome": "not_evaluated",
            "reason": "No success criteria were supplied.",
        }
    else:
        split = pair_universe["benchmark_split"]
        criteria = success_criteria[split]
        recall = metrics["candidate_recall"]
        reduction = metrics["workload_reduction_total"]
        per_lecture_recalls = [
            item["metrics"]["candidate_recall"]
            for item in per_lecture
            if item["counts"]["positive_pairs"] > 0
        ]
        layer_one_pass = (
            recall is not None
            and recall >= criteria["candidate_recall_min"]
            and counts["missed_positive_pairs"]
            <= criteria["missed_positive_count_max"]
            and reduction is not None
            and reduction >= criteria["workload_reduction_total_min"]
        )
        if split == "development":
            layer_one_pass = layer_one_pass and all(
                item >= criteria["per_lecture_candidate_recall_min"]
                for item in per_lecture_recalls
            )
        gate_assessment = {
            "applicable": True,
            "outcome": (
                "pending_downstream_evaluation" if layer_one_pass else "failed"
            ),
            "candidate_layer_passed": layer_one_pass,
            "reason": (
                "Candidate-layer gates passed; downstream typed-edge recall remains pending."
                if layer_one_pass
                else "One or more frozen candidate-layer gates failed."
            ),
        }

    metrics_artifact = {
        "artifact_type": "candidate_pair_generation_metrics",
        "version": "v0.1",
        "evaluation_status": "final",
        "benchmark_split": pair_universe["benchmark_split"],
        "generator": selection["generator"],
        "counts": counts,
        "metrics": metrics,
        "diagnostics": diagnostics,
        "gate_assessment": gate_assessment,
    }
    return {
        "metrics": metrics_artifact,
        "matches": matches,
        "errors": errors,
        "per_relation_metrics": {
            "artifact_type": "candidate_pair_generation_per_relation_metrics",
            "version": "v0.1",
            "evaluation_status": "final",
            "scoring_unit": "positive_pair_with_secondary_relation_instance_coverage",
            "relations": per_relation,
        },
        "per_lecture_metrics": {
            "artifact_type": "candidate_pair_generation_per_lecture_metrics",
            "version": "v0.1",
            "evaluation_status": "final",
            "lectures": per_lecture,
        },
    }


def _prepare_evaluation_dir(evaluation_dir: Path, *, overwrite: bool) -> None:
    existing = [evaluation_dir / name for name in FINAL_ARTIFACT_NAMES]
    present = [path for path in existing if path.exists()]
    if present and not overwrite:
        raise CandidatePairEvaluationError(
            "Refusing to overwrite existing evaluation artifact(s): "
            + ", ".join(display_path(path) for path in present)
        )
    if overwrite:
        for path in present:
            path.unlink()
    evaluation_dir.mkdir(parents=True, exist_ok=True)


def _write_invalid_evaluation(
    *,
    evaluation_dir: Path,
    fatal_errors: list[str],
    input_bindings: dict[str, dict[str, str]],
) -> None:
    error_records = [
        {"error_type": "fatal_integrity_error", "message": message}
        for message in fatal_errors
    ]
    errors_path = evaluation_dir / "errors.json"
    _atomic_write_text(errors_path, serialize_json(error_records))
    marker = {
        "artifact_type": "candidate_pair_generation_evaluation_complete",
        "version": "v0.1",
        "evaluation_status": "invalid",
        "inputs": input_bindings,
        "evaluator": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": EVALUATOR_VERSION,
        },
        "outputs": {
            "errors": {
                "path": display_path(errors_path),
                "sha256": sha256_file(errors_path),
            }
        },
        "fatal_error_count": len(fatal_errors),
    }
    _atomic_write_text(
        evaluation_dir / "evaluation_complete.json",
        serialize_json(marker),
    )


def _write_final_evaluation(
    *,
    evaluation_dir: Path,
    artifacts: dict[str, Any],
    input_bindings: dict[str, dict[str, str]],
) -> None:
    values_by_filename = {
        "metrics.json": artifacts["metrics"],
        "matches.json": artifacts["matches"],
        "errors.json": artifacts["errors"],
        "per_relation_metrics.json": artifacts["per_relation_metrics"],
        "per_lecture_metrics.json": artifacts["per_lecture_metrics"],
    }
    output_bindings: dict[str, dict[str, str]] = {}
    for filename, value in values_by_filename.items():
        path = evaluation_dir / filename
        _atomic_write_text(path, serialize_json(value))
        output_bindings[filename.removesuffix(".json")] = {
            "path": display_path(path),
            "sha256": sha256_file(path),
        }
    completion_marker = {
        "artifact_type": "candidate_pair_generation_evaluation_complete",
        "version": "v0.1",
        "evaluation_status": "final",
        "inputs": input_bindings,
        "evaluator": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": EVALUATOR_VERSION,
        },
        "outputs": output_bindings,
        "counts": artifacts["metrics"]["counts"],
    }
    _atomic_write_text(
        evaluation_dir / "evaluation_complete.json",
        serialize_json(completion_marker),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a candidate-pair selection against frozen exhaustive ground truth."
    )
    parser.add_argument("--pair-universe", default=str(DEFAULT_PAIR_UNIVERSE))
    parser.add_argument(
        "--pair-universe-completion-marker",
        default=str(DEFAULT_PAIR_UNIVERSE_MARKER),
    )
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument(
        "--ground-truth-completion-marker",
        default=str(DEFAULT_GROUND_TRUTH_MARKER),
    )
    parser.add_argument("--success-criteria", default=str(DEFAULT_SUCCESS_CRITERIA))
    parser.add_argument(
        "--candidate-selection",
        default=str(DEFAULT_CANDIDATE_DIR / SELECTION_FILENAME),
    )
    parser.add_argument(
        "--candidate-metadata",
        default=str(DEFAULT_CANDIDATE_DIR / METADATA_FILENAME),
    )
    parser.add_argument(
        "--candidate-completion-marker",
        default=str(DEFAULT_CANDIDATE_DIR / COMPLETION_FILENAME),
    )
    parser.add_argument("--output-schema", default=str(DEFAULT_OUTPUT_SCHEMA))
    parser.add_argument("--evaluation-dir", default=str(DEFAULT_EVALUATION_DIR))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pair_universe_path = resolve_path(args.pair_universe)
    pair_universe_marker_path = resolve_path(args.pair_universe_completion_marker)
    ground_truth_path = resolve_path(args.ground_truth)
    ground_truth_marker_path = resolve_path(args.ground_truth_completion_marker)
    success_criteria_path = resolve_path(args.success_criteria)
    selection_path = resolve_path(args.candidate_selection)
    metadata_path = resolve_path(args.candidate_metadata)
    candidate_marker_path = resolve_path(args.candidate_completion_marker)
    output_schema_path = resolve_path(args.output_schema)
    evaluation_dir = resolve_path(args.evaluation_dir)
    input_paths = {
        "pair_universe": pair_universe_path,
        "pair_universe_completion_marker": pair_universe_marker_path,
        "ground_truth": ground_truth_path,
        "ground_truth_completion_marker": ground_truth_marker_path,
        "success_criteria": success_criteria_path,
        "candidate_selection": selection_path,
        "candidate_metadata": metadata_path,
        "candidate_completion_marker": candidate_marker_path,
        "output_schema": output_schema_path,
    }
    try:
        _prepare_evaluation_dir(evaluation_dir, overwrite=args.overwrite)
        for label, path in input_paths.items():
            if not path.is_file():
                raise CandidatePairEvaluationError(
                    f"Missing {label}: {display_path(path)}"
                )
        input_bindings = {
            label: {"path": display_path(path), "sha256": sha256_file(path)}
            for label, path in input_paths.items()
        }
        pair_universe = load_json_object(pair_universe_path, label="pair universe")
        pair_universe_marker = load_json_object(
            pair_universe_marker_path,
            label="pair-universe completion marker",
        )
        ground_truth = load_json_object(ground_truth_path, label="ground truth")
        ground_truth_marker = load_json_object(
            ground_truth_marker_path,
            label="ground-truth completion marker",
        )
        success_criteria = load_json_object(
            success_criteria_path,
            label="success criteria",
        )
        selection = load_json_object(selection_path, label="candidate selection")
        metadata = load_json_object(metadata_path, label="candidate metadata")
        candidate_marker = load_json_object(
            candidate_marker_path,
            label="candidate completion marker",
        )

        fatal_errors: list[str] = []
        _, universe_errors = validate_pair_universe(pair_universe)
        fatal_errors.extend(universe_errors)
        fatal_errors.extend(
            validate_pair_universe_marker(
                pair_universe_marker,
                marker_path=pair_universe_marker_path,
                pair_universe_path=pair_universe_path,
                pair_universe=pair_universe,
            )
        )
        ground_truth_errors, ground_truth_summary = (
            validate_candidate_pair_ground_truth(
                pair_universe_path,
                ground_truth_path,
                allow_draft=False,
            )
        )
        fatal_errors.extend(ground_truth_errors)
        fatal_errors.extend(
            validate_ground_truth_completion_marker(
                ground_truth_marker,
                marker_path=ground_truth_marker_path,
                pair_universe_path=pair_universe_path,
                ground_truth_path=ground_truth_path,
                ground_truth_summary=ground_truth_summary,
            )
        )
        fatal_errors.extend(
            validate_candidate_selection(
                selection,
                pair_universe=pair_universe,
                pair_universe_path=pair_universe_path,
            )
        )
        fatal_errors.extend(
            validate_generation_completion_marker(
                candidate_marker,
                marker_path=candidate_marker_path,
                selection_path=selection_path,
                metadata_path=metadata_path,
                pair_universe_path=pair_universe_path,
                pair_universe_marker_path=pair_universe_marker_path,
                output_schema_path=output_schema_path,
                selection=selection,
                metadata=metadata,
                pair_universe=pair_universe,
            )
        )
        if success_criteria.get("artifact_type") != (
            "candidate_pair_generation_success_criteria"
        ):
            fatal_errors.append("success_criteria.artifact_type: invalid")
        ground_truth_criteria = ground_truth.get("success_criteria", {})
        if ground_truth_criteria.get("path") != display_path(success_criteria_path):
            fatal_errors.append("success_criteria.path: ground-truth binding mismatch")
        if ground_truth_criteria.get("sha256") != sha256_file(success_criteria_path):
            fatal_errors.append("success_criteria.sha256: ground-truth binding mismatch")

        if fatal_errors:
            _write_invalid_evaluation(
                evaluation_dir=evaluation_dir,
                fatal_errors=fatal_errors,
                input_bindings=input_bindings,
            )
            print(
                f"Candidate evaluation invalid: {len(fatal_errors)} fatal error(s).",
                file=sys.stderr,
            )
            print(f"Artifacts {display_path(evaluation_dir)}", file=sys.stderr)
            return 1

        artifacts = score_candidate_selection(
            pair_universe=pair_universe,
            ground_truth=ground_truth,
            selection=selection,
            success_criteria=success_criteria,
        )
        _write_final_evaluation(
            evaluation_dir=evaluation_dir,
            artifacts=artifacts,
            input_bindings=input_bindings,
        )
    except (
        OSError,
        CandidateGroundTruthError,
        CandidatePairGenerationError,
        CandidatePairEvaluationError,
    ) as exc:
        print(f"Candidate pair evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote candidate evaluation to {display_path(evaluation_dir)}")
    print("Evaluation status: final")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
