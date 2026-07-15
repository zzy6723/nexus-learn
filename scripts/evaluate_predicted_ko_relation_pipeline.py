#!/usr/bin/env python3
"""Compose final Entity-to-Relation pipeline diagnostics for Experiment 002B-1."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from . import project_recoverable_relation_pairs as projector
    from .check_relation_ground_truth import validate_ground_truth
except ImportError:  # Direct execution.
    import project_recoverable_relation_pairs as projector
    from check_relation_ground_truth import validate_ground_truth


ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.1"
FINAL_FILENAMES = [
    "pipeline_metrics.json",
    "pipeline_errors.json",
    "pair_transitions.json",
]
NOOP_FILENAMES = [
    "A_prime_noop_evaluation.json",
    "B_prime_noop_evaluation.json",
]
COMPLETION_FILENAME = "pipeline_evaluation_complete.json"
MANAGED_FILENAMES = [*FINAL_FILENAMES, *NOOP_FILENAMES, COMPLETION_FILENAME]
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SUPPORTED_EVIDENCE_STATUSES = {
    "auto_supported_by_gold_evidence",
    "supported",
}
GROUNDING_NONEXACT_ERRORS = {
    "missing_evidence",
    "invalid_evidence_span",
    "evidence_lecture_outside_candidate",
}
SECONDARY_FLAG_ORDER = [
    "ko_name_changed",
    "ko_type_mismatch",
    "predicted_source_span_invalid",
    "predicted_source_span_insufficient",
    "manual_identity_alignment",
    "relation_grounding_nonexact",
    "relation_grounding_unsupported",
]


class PipelineError(RuntimeError):
    """A fatal pipeline-integrity failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class EvaluationBundle:
    condition: str
    metrics: dict[str, Any] | None
    matches: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    predictions: dict[str, Any] | None
    metadata: dict[str, Any] | None
    snapshot: dict[str, Any] | None
    evaluation_sha256: str
    prediction_sha256: str | None
    metadata_sha256: str | None
    execution_status: str


def serialize_json(value: Any) -> str:
    return projector.serialize_json(value)


def sha256_bytes(value: bytes) -> str:
    return projector.sha256_bytes(value)


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise PipelineError("missing_pipeline_input", f"Unable to read {path}: {exc}") from exc


def artifact_sha256(value: Any) -> str:
    return projector.artifact_sha256(value)


def read_json(path: Path, *, code: str = "invalid_pipeline_input") -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PipelineError(code, f"Unable to read {path}: {exc}") from exc


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def ref_key(value: dict[str, Any]) -> tuple[str, str]:
    try:
        return projector.ref_key(value, field="pipeline_ref")
    except projector.ProjectionError as exc:
        raise PipelineError(exc.code, str(exc)) from exc


def validate_marker(
    marker_path: Path,
    *,
    artifact_type: str,
    base_dir: Path,
    expected_artifacts: set[str] | None = None,
) -> tuple[dict[str, Any], str]:
    marker = read_json(marker_path, code="stale_completion_marker")
    if marker.get("artifact_type") != artifact_type:
        raise PipelineError("stale_completion_marker", f"Unexpected marker type at {marker_path}.")
    if marker.get("evaluation_status") != "final":
        raise PipelineError("stale_completion_marker", f"Marker is not final: {marker_path}.")
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise PipelineError("stale_completion_marker", f"Marker has no artifact hashes: {marker_path}.")
    if expected_artifacts is not None and set(artifacts) != expected_artifacts:
        raise PipelineError(
            "stale_completion_marker",
            f"Marker artifact set differs from the required bundle at {marker_path}.",
        )
    for filename, expected_hash in artifacts.items():
        if (
            not isinstance(filename, str)
            or not isinstance(expected_hash, str)
            or not SHA256_PATTERN.fullmatch(expected_hash)
        ):
            raise PipelineError("stale_completion_marker", f"Marker entry is invalid: {marker_path}.")
        if sha256_file(base_dir / filename) != expected_hash:
            raise PipelineError(
                "stale_completion_marker",
                f"Completion marker has a stale hash for {filename}.",
            )
    return marker, sha256_file(marker_path)


def load_projection_artifacts(projection_dir: Path) -> dict[str, Any]:
    return {
        filename: read_json(projection_dir / filename)
        for filename in projector.MANAGED_FILENAMES
    }


def primary_pair_maps(
    original_ground_truth: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    primary_categories = set(original_ground_truth["primary_scoring_categories"])
    primary: dict[str, dict[str, Any]] = {}
    diagnostic: dict[str, dict[str, Any]] = {}
    for pair in original_ground_truth["pairs"]:
        target = primary if pair["category"] in primary_categories else diagnostic
        if pair["pair_id"] in target:
            raise PipelineError("duplicate_pair_id", f"Duplicate pair {pair['pair_id']}.")
        target[pair["pair_id"]] = pair
    return primary, diagnostic


def validate_projection_chain(
    *,
    original_ground_truth: dict[str, Any],
    original_ground_truth_sha256: str,
    alignment_path: Path,
    alignment: dict[str, Any],
    projection_dir: Path,
    artifacts: dict[str, Any],
) -> tuple[str, str]:
    alignment_raw = alignment_path.read_bytes()
    alignment_marker, checked_alignment_marker_hash = validate_marker(
        alignment_path.parent / "alignment_bundle_complete.json",
        artifact_type="predicted_ko_alignment_bundle_complete",
        base_dir=alignment_path.parent,
    )
    alignment_artifact_names = set(alignment_marker["artifacts"])
    if not {"alignment.json", "alignment_pending.json"} <= alignment_artifact_names:
        raise PipelineError(
            "stale_completion_marker",
            "Alignment marker omits required alignment artifacts.",
        )
    if not alignment_artifact_names <= {
        "alignment.json",
        "alignment_pending.json",
        "alignment_resolved.json",
    }:
        raise PipelineError(
            "stale_completion_marker",
            "Alignment marker contains unknown managed artifacts.",
        )
    try:
        alignment_marker_hash = projector.validate_alignment_completion_marker(
            alignment_path, alignment_raw
        )
    except (OSError, projector.ProjectionError) as exc:
        code = getattr(exc, "code", "incomplete_alignment_bundle")
        raise PipelineError(code, str(exc)) from exc
    if alignment_marker_hash != checked_alignment_marker_hash:
        raise PipelineError(
            "stale_completion_marker", "Alignment marker hash changed during validation."
        )
    projection_marker, projection_marker_hash = validate_marker(
        projection_dir / projector.COMPLETION_FILENAME,
        artifact_type="predicted_ko_projection_bundle_complete",
        base_dir=projection_dir,
        expected_artifacts=set(projector.MANAGED_FILENAMES),
    )
    if projection_marker.get("upstream", {}).get(
        "alignment_bundle_complete_sha256"
    ) != alignment_marker_hash:
        raise PipelineError(
            "stale_completion_marker",
            "Projection marker does not bind the current alignment marker.",
        )

    primary, diagnostic = primary_pair_maps(original_ground_truth)
    alignment_hash = sha256_bytes(alignment_raw)
    try:
        projector.validate_projection_artifacts(
            artifacts,
            original_pair_ids=set(primary) | set(diagnostic),
            original_primary_pair_ids=set(primary),
            original_diagnostic_pair_ids=set(diagnostic),
            alignment_sha256=alignment_hash,
        )
    except projector.ProjectionError as exc:
        raise PipelineError(exc.code, str(exc)) from exc

    pair_manifest = artifacts["recoverable_pair_manifest.json"]
    if pair_manifest.get("original_ground_truth_sha256") != original_ground_truth_sha256:
        raise PipelineError(
            "stale_original_ground_truth",
            "Pair manifest does not bind the current original ground truth.",
        )
    matched_gt = artifacts["matched_relation_ground_truth.json"]
    derivation = matched_gt.get("derivation", {})
    if derivation.get("original_ground_truth_sha256") != original_ground_truth_sha256:
        raise PipelineError(
            "stale_matched_ground_truth",
            "Matched ground truth does not bind the current original ground truth.",
        )
    if derivation.get("alignment_sha256") != alignment_hash:
        raise PipelineError(
            "stale_matched_ground_truth",
            "Matched ground truth does not bind the current alignment.",
        )
    matched_errors, _ = validate_ground_truth(matched_gt)
    if matched_errors:
        raise PipelineError(
            "invalid_matched_ground_truth",
            "Matched ground truth failed its strict checker: " + "; ".join(matched_errors),
        )
    return alignment_marker_hash, projection_marker_hash


def load_evaluation_bundle(
    directory: Path,
    *,
    condition: str,
    expected_pair_ids: set[str],
    allowed_extra_pair_ids: set[str] | None = None,
    expected_pair_order: list[str] | None = None,
) -> EvaluationBundle:
    noop_candidates = [
        directory / "empty_matched_relation_evaluation.json",
        directory / f"{condition}_noop_evaluation.json",
    ]
    if expected_pair_ids and any(path.exists() for path in noop_candidates):
        raise PipelineError(
            "invalid_noop_evaluation",
            f"{condition} cannot use a no-op evaluation when pairs are recoverable.",
        )
    paths = {
        "metrics": directory / "metrics.json",
        "matches": directory / "matches.json",
        "errors": directory / "errors.json",
        "predictions": directory / "predictions.json",
        "metadata": directory / "run_metadata.json",
        "snapshot": directory / "evaluation_snapshot.json",
    }
    values = {name: read_json(path) for name, path in paths.items()}
    snapshot = values["snapshot"]
    metrics = values["metrics"]
    if snapshot.get("condition") != condition:
        raise PipelineError("evaluation_condition_mismatch", f"Expected {condition} evaluation.")
    status = snapshot.get("evaluation_status")
    if status != "final" or metrics.get("evaluation_status") != "final":
        code = (
            "base_relation_evaluation_invalid"
            if status == "invalid" or metrics.get("evaluation_status") == "invalid"
            else "base_relation_evaluation_not_final"
        )
        raise PipelineError(code, f"{condition} Relation evaluation is not final.")
    hash_fields = {
        "prediction_sha256": "predictions",
        "run_metadata_sha256": "metadata",
        "metrics_sha256": "metrics",
        "matches_sha256": "matches",
        "errors_sha256": "errors",
    }
    for field, name in hash_fields.items():
        actual = sha256_file(paths[name])
        if snapshot.get(field) != actual:
            code = (
                "evaluation_prediction_hash_mismatch"
                if field == "prediction_sha256"
                else "stale_evaluation_snapshot"
            )
            raise PipelineError(code, f"{condition} snapshot has stale {field}.")
    metadata = values["metadata"]
    prediction_hash = sha256_file(paths["predictions"])
    if metadata.get("prediction_sha256") != prediction_hash:
        raise PipelineError(
            "evaluation_prediction_hash_mismatch",
            f"{condition} metadata has stale prediction hash.",
        )

    matches = values["matches"]
    if not isinstance(matches, list):
        raise PipelineError("invalid_relation_matches", f"{condition} matches must be a list.")
    match_ids = [item.get("pair_id") for item in matches if isinstance(item, dict)]
    if len(match_ids) != len(matches) or len(match_ids) != len(set(match_ids)):
        raise PipelineError("duplicate_pair_outcome", f"{condition} has duplicate or invalid matches.")
    allowed_extra_pair_ids = allowed_extra_pair_ids or set()
    unknown = set(match_ids) - expected_pair_ids - allowed_extra_pair_ids
    missing = expected_pair_ids - set(match_ids)
    if unknown:
        raise PipelineError("unknown_pair_outcome", f"{condition} has unknown pairs: {sorted(unknown)}.")
    if missing:
        raise PipelineError("missing_pair_outcome", f"{condition} is missing pairs: {sorted(missing)}.")
    if condition != "A0" and set(match_ids) != expected_pair_ids:
        raise PipelineError("matched_pair_id_set_mismatch", f"{condition} pair set differs from manifest.")
    if expected_pair_order is not None:
        primary_order = [pair_id for pair_id in match_ids if pair_id in expected_pair_ids]
        if primary_order != expected_pair_order:
            raise PipelineError(
                "matched_pair_order_mismatch",
                f"{condition} pair order differs from the frozen manifest.",
            )
    primary_matches = [item for item in matches if item["pair_id"] in expected_pair_ids]
    if any(item.get("primary_scored") is not True for item in primary_matches):
        raise PipelineError("invalid_relation_matches", f"{condition} primary match is not primary-scored.")
    if metrics.get("primary_scored_pairs") != len(expected_pair_ids):
        raise PipelineError(
            "base_relation_metric_denominator_mismatch",
            f"{condition} aggregate primary denominator differs from pair-level matches.",
        )

    predictions = values["predictions"]
    prediction_ids = [item.get("pair_id") for item in predictions.get("results", [])]
    if len(prediction_ids) != len(set(prediction_ids)) or set(prediction_ids) != set(match_ids):
        raise PipelineError(
            "evaluation_prediction_pair_mismatch",
            f"{condition} predictions and matches cover different pairs.",
        )
    if not isinstance(values["errors"], list):
        raise PipelineError("invalid_relation_errors", f"{condition} errors must be a list.")
    return EvaluationBundle(
        condition=condition,
        metrics=metrics,
        matches=matches,
        errors=values["errors"],
        predictions=predictions,
        metadata=metadata,
        snapshot=snapshot,
        evaluation_sha256=sha256_file(paths["snapshot"]),
        prediction_sha256=prediction_hash,
        metadata_sha256=sha256_file(paths["metadata"]),
        execution_status="completed",
    )


def make_noop_evaluation(
    condition: str,
    *,
    pair_manifest_sha256: str,
    ko_manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "empty_matched_relation_evaluation",
        "version": VERSION,
        "condition": condition,
        "evaluation_status": "final",
        "execution_status": "not_run_no_recoverable_pairs",
        "pair_count": 0,
        "aggregate_metrics": None,
        "pair_manifest_sha256": pair_manifest_sha256,
        "ko_manifest_sha256": ko_manifest_sha256,
    }


def noop_bundle(condition: str, artifact: dict[str, Any]) -> EvaluationBundle:
    return EvaluationBundle(
        condition=condition,
        metrics=None,
        matches=[],
        errors=[],
        predictions=None,
        metadata=None,
        snapshot=None,
        evaluation_sha256=artifact_sha256(artifact),
        prediction_sha256=None,
        metadata_sha256=None,
        execution_status="not_run_no_recoverable_pairs",
    )


def validate_matched_execution(
    *,
    a_bundle: EvaluationBundle,
    b_bundle: EvaluationBundle,
    a_input_path: Path,
    b_input_path: Path,
    batch_plan_path: Path,
) -> None:
    if a_bundle.metadata is None or b_bundle.metadata is None:
        raise PipelineError("missing_matched_run", "Matched Relation run metadata is required.")
    a_metadata = a_bundle.metadata
    b_metadata = b_bundle.metadata
    if a_metadata.get("provider") != b_metadata.get("provider"):
        raise PipelineError("matched_provider_mismatch", "A-prime/B-prime providers differ.")
    if a_metadata.get("model_requested") != b_metadata.get("model_requested"):
        raise PipelineError("matched_model_mismatch", "A-prime/B-prime models differ.")
    if a_metadata.get("request_parameters") != b_metadata.get("request_parameters"):
        raise PipelineError(
            "matched_request_parameter_mismatch",
            "A-prime/B-prime request parameters differ.",
        )
    a_partitioning = a_metadata.get(
        "request_partitioning", "single_deterministic_batch_v0_1"
    )
    b_partitioning = b_metadata.get(
        "request_partitioning", "single_deterministic_batch_v0_1"
    )
    if a_partitioning != b_partitioning:
        raise PipelineError(
            "matched_request_partitioning_mismatch",
            "A-prime/B-prime request partitioning differs.",
        )
    if a_partitioning == "one_candidate_pair_per_request_v0_1":
        a_plan_hash = a_metadata.get("execution_batch_plan_sha256")
        b_plan_hash = b_metadata.get("execution_batch_plan_sha256")
        if (
            not isinstance(a_plan_hash, str)
            or len(a_plan_hash) != 64
            or a_plan_hash != b_plan_hash
        ):
            raise PipelineError(
                "matched_execution_batch_plan_mismatch",
                "Candidate-scoped A-prime/B-prime execution plans differ.",
            )
        if (
            a_metadata.get("execution_manifest_sha256")
            != b_metadata.get("execution_manifest_sha256")
        ):
            raise PipelineError(
                "matched_execution_manifest_mismatch",
                "Candidate-scoped A-prime/B-prime manifests differ.",
            )
        for condition, metadata in [
            ("A_prime", a_metadata),
            ("B_prime", b_metadata),
        ]:
            if (
                metadata.get("batch_count") != metadata.get("completed_batch_count")
                or metadata.get("batch_count") != len(
                    metadata.get("batch_results", [])
                )
            ):
                raise PipelineError(
                    "incomplete_candidate_scoped_execution",
                    f"{condition} candidate-scoped execution is incomplete.",
                )
    if a_metadata.get("git_commit_at_start") != b_metadata.get("git_commit_at_start"):
        raise PipelineError("matched_git_commit_mismatch", "Matched run commits differ.")
    if not a_metadata.get("git_commit_at_start"):
        raise PipelineError("matched_git_commit_mismatch", "Matched run commit is missing.")
    if a_metadata.get("git_dirty_at_start") is not False or b_metadata.get(
        "git_dirty_at_start"
    ) is not False:
        raise PipelineError("formal_run_started_dirty", "A matched formal run started dirty.")
    expected_inputs = {
        "A_prime": sha256_file(a_input_path),
        "B_prime": sha256_file(b_input_path),
    }
    batch_hash = sha256_file(batch_plan_path)
    for bundle, metadata in [(a_bundle, a_metadata), (b_bundle, b_metadata)]:
        if metadata.get("input_artifact_sha256") != expected_inputs[bundle.condition]:
            raise PipelineError(
                "run_metadata_input_hash_mismatch",
                f"{bundle.condition} metadata has stale input hash.",
            )
        if metadata.get("batch_plan_sha256") != batch_hash:
            raise PipelineError(
                "matched_batching_mismatch",
                f"{bundle.condition} metadata has stale batch-plan hash.",
            )


def evaluation_match_map(bundle: EvaluationBundle) -> dict[str, dict[str, Any]]:
    return {item["pair_id"]: item for item in bundle.matches}


def errors_by_pair(bundle: EvaluationBundle) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for item in bundle.errors:
        if not isinstance(item, dict):
            continue
        pair_id = item.get("pair_id")
        error_type = item.get("error_type")
        if isinstance(pair_id, str) and isinstance(error_type, str):
            result[pair_id].append(error_type)
    return result


def classify_outcome(
    match: dict[str, Any],
    *,
    gold_pair: dict[str, Any],
) -> dict[str, Any]:
    predicted_type = match.get("predicted_edge", {}).get("relation_type")
    strict = match.get("strict_edge_correct") is True
    error: str | None = None
    if not strict:
        if match.get("relation_type_correct") is False:
            if gold_pair["relation_type"] == "NO_RELATION" and predicted_type != "NO_RELATION":
                error = "false_positive_relation"
            elif gold_pair["relation_type"] != "NO_RELATION" and predicted_type == "NO_RELATION":
                error = "false_negative_relation"
            else:
                error = "wrong_relation_type"
        elif match.get("direction_correct") is False:
            error = "wrong_direction"
        else:
            error = "other_strict_error"
    return {
        "strict_correct": strict,
        "relation_type": predicted_type,
        "error": error,
    }


def conditional_metrics(
    bundle: EvaluationBundle,
    *,
    gold_pairs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not bundle.matches:
        return {
            "strict_edge_accuracy": rate(0, 0),
            "relation_type_accuracy": rate(0, 0),
            "positive_relation_accuracy": rate(0, 0),
            "no_relation_accuracy": rate(0, 0),
            "endpoint_direction_accuracy": rate(0, 0),
            "direction_accuracy_when_type_correct": rate(0, 0),
            "exact_evidence_span_rate": rate(0, 0),
            "semantic_evidence_support_rate": rate(0, 0),
            "per_type_confusion": {},
            "related_to_prediction_rate": rate(0, 0),
            "related_to_overuse_count": 0,
            "false_positive_relation_count": 0,
            "false_negative_relation_count": 0,
            "execution_status": bundle.execution_status,
        }
    matches = [item for item in bundle.matches if item["pair_id"] in gold_pairs]
    positive = [item for item in matches if gold_pairs[item["pair_id"]]["category"] == "positive"]
    hard_negative = [
        item for item in matches if gold_pairs[item["pair_id"]]["category"] == "hard_negative"
    ]
    direction = [item for item in matches if item.get("direction_correct") is not None]
    direction_type_correct = [
        item
        for item in matches
        if item.get("relation_type_correct") is True
        and item.get("direction_correct") is not None
    ]
    evidence = [
        item
        for item in matches
        if item.get("evidence_support_status") not in {None, "not_applicable"}
    ]
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for item in matches:
        gold_type = gold_pairs[item["pair_id"]]["relation_type"]
        predicted_type = item.get("predicted_edge", {}).get("relation_type")
        confusion[gold_type][str(predicted_type)] += 1
    metric_data = bundle.metrics or {}
    error_types = [
        item.get("error_type") for item in bundle.errors if isinstance(item, dict)
    ]
    related_to = sum(
        item.get("predicted_edge", {}).get("relation_type") == "RELATED_TO"
        for item in matches
    )
    return {
        "strict_edge_accuracy": rate(
            sum(item.get("strict_edge_correct") is True for item in matches), len(matches)
        ),
        "relation_type_accuracy": rate(
            sum(item.get("relation_type_correct") is True for item in matches), len(matches)
        ),
        "positive_relation_accuracy": rate(
            sum(item.get("strict_edge_correct") is True for item in positive), len(positive)
        ),
        "no_relation_accuracy": rate(
            sum(item.get("strict_edge_correct") is True for item in hard_negative),
            len(hard_negative),
        ),
        "endpoint_direction_accuracy": rate(
            sum(item.get("direction_correct") is True for item in direction), len(direction)
        ),
        "direction_accuracy_when_type_correct": rate(
            sum(item.get("direction_correct") is True for item in direction_type_correct),
            len(direction_type_correct),
        ),
        "exact_evidence_span_rate": rate(
            int(metric_data.get("exact_evidence_span_count", 0)),
            int(metric_data.get("evidence_span_count", 0)),
        ),
        "semantic_evidence_support_rate": rate(
            sum(item.get("evidence_support_status") in SUPPORTED_EVIDENCE_STATUSES for item in evidence),
            len(evidence),
        ),
        "per_type_confusion": {
            gold: dict(sorted(predicted.items()))
            for gold, predicted in sorted(confusion.items())
        },
        "related_to_prediction_rate": rate(related_to, len(matches)),
        "related_to_overuse_count": error_types.count("overused_related_to"),
        "false_positive_relation_count": error_types.count("false_positive_relation"),
        "false_negative_relation_count": error_types.count("false_negative_relation"),
        "execution_status": bundle.execution_status,
    }


def a0_transition(a0: dict[str, Any], b: dict[str, Any] | None) -> str:
    if b is None:
        return (
            "A0_correct_to_B_unrecoverable"
            if a0["strict_correct"]
            else "A0_wrong_to_B_unrecoverable"
        )
    if a0["strict_correct"]:
        if b["strict_correct"]:
            return "A0_correct_to_B_correct"
        if b["error"] == "wrong_direction":
            return "A0_correct_to_B_wrong_direction"
        return "A0_correct_to_B_wrong_type"
    if b["strict_correct"]:
        return "A0_wrong_to_B_correct"
    return (
        "A0_wrong_to_B_same_error"
        if a0["error"] == b["error"]
        else "A0_wrong_to_B_different_error"
    )


def matched_transition(a: dict[str, Any], b: dict[str, Any]) -> str:
    if a["strict_correct"] and b["strict_correct"]:
        return "A_prime_correct_to_B_prime_correct"
    if a["strict_correct"]:
        return "A_prime_correct_to_B_prime_wrong"
    if b["strict_correct"]:
        return "A_prime_wrong_to_B_prime_correct"
    return (
        "A_prime_wrong_to_B_prime_same_error"
        if a["error"] == b["error"]
        else "A_prime_wrong_to_B_prime_different_error"
    )


def failure_locus(
    *,
    recoverable: bool,
    a_outcome: dict[str, Any] | None,
    b_outcome: dict[str, Any] | None,
) -> str:
    if not recoverable:
        return "upstream_unrecoverable"
    assert a_outcome is not None and b_outcome is not None
    if not a_outcome["strict_correct"] and not b_outcome["strict_correct"]:
        return "pre_existing_A_prime_strict_error"
    if b_outcome["strict_correct"]:
        return "none"
    mapping = {
        "false_positive_relation": "B_prime_relation_false_positive",
        "false_negative_relation": "B_prime_relation_false_negative",
        "wrong_relation_type": "B_prime_relation_type_error",
        "wrong_direction": "B_prime_relation_direction_error",
        "other_strict_error": "B_prime_other_strict_error",
    }
    return mapping.get(b_outcome["error"], "B_prime_other_strict_error")


def secondary_flags_by_pair(
    *,
    ko_manifest: dict[str, Any],
    alignment: dict[str, Any],
    a_input: dict[str, Any],
    b_input: dict[str, Any],
    projection_errors: dict[str, Any],
    b_bundle: EvaluationBundle,
) -> dict[str, list[str]]:
    flags: dict[str, set[str]] = defaultdict(set)
    slots = {slot["slot_id"]: slot for slot in ko_manifest["slots"]}
    a_kos = {item["ko_id"]: item for item in a_input["model_input"]["knowledge_objects"]}
    b_kos = {item["ko_id"]: item for item in b_input["model_input"]["knowledge_objects"]}
    oracle_records = {
        ref_key(item["oracle_ref"]): item for item in alignment["oracle_records"]
    }
    for slot_id, slot in slots.items():
        pair_ids = slot["referenced_by_pair_ids"]
        if a_kos[slot_id]["name"] != b_kos[slot_id]["name"]:
            for pair_id in pair_ids:
                flags[pair_id].add("ko_name_changed")
        if a_kos[slot_id]["type"] != b_kos[slot_id]["type"]:
            for pair_id in pair_ids:
                flags[pair_id].add("ko_type_mismatch")
        if oracle_records[ref_key(slot["oracle_ref"])].get("alignment_level") == "manual":
            for pair_id in pair_ids:
                flags[pair_id].add("manual_identity_alignment")
    projection_flag_map = {
        "ko_type_mismatch": "ko_type_mismatch",
        "predicted_source_span_invalid": "predicted_source_span_invalid",
        "predicted_source_span_not_supporting_identity": (
            "predicted_source_span_insufficient"
        ),
    }
    for item in projection_errors.get("recoverable_slot_quality_flags", []):
        slot = slots[item["slot_id"]]
        for raw_flag in item["flags"]:
            normalized = projection_flag_map.get(raw_flag)
            if normalized:
                for pair_id in slot["referenced_by_pair_ids"]:
                    flags[pair_id].add(normalized)
    b_errors = errors_by_pair(b_bundle)
    b_matches = evaluation_match_map(b_bundle)
    for pair_id, error_types in b_errors.items():
        if any(error in GROUNDING_NONEXACT_ERRORS for error in error_types):
            flags[pair_id].add("relation_grounding_nonexact")
    for pair_id, match in b_matches.items():
        if match.get("evidence_support_status") == "not_supported":
            flags[pair_id].add("relation_grounding_unsupported")
    return {
        pair_id: [flag for flag in SECONDARY_FLAG_ORDER if flag in values]
        for pair_id, values in flags.items()
    }


def build_pipeline_outputs(
    *,
    original_ground_truth: dict[str, Any],
    alignment: dict[str, Any],
    pair_manifest: dict[str, Any],
    ko_manifest: dict[str, Any],
    projection_errors: dict[str, Any],
    a_input: dict[str, Any],
    b_input: dict[str, Any],
    a0_bundle: EvaluationBundle,
    a_bundle: EvaluationBundle,
    b_bundle: EvaluationBundle,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    primary_pairs, diagnostic_pairs = primary_pair_maps(original_ground_truth)
    recoverable_ids = [item["pair_id"] for item in pair_manifest["primary_pairs"]]
    unrecoverable = {
        item["pair_id"]: item["unrecoverable_reasons"]
        for item in pair_manifest["unrecoverable_primary_pairs"]
    }
    if set(recoverable_ids) | set(unrecoverable) != set(primary_pairs):
        raise PipelineError("primary_denominator_mismatch", "Pair manifest changed the primary universe.")
    if set(recoverable_ids) & set(unrecoverable):
        raise PipelineError("duplicate_pair_id", "A primary pair has two recoverability states.")
    if pair_manifest.get("original_primary_pair_count") != len(primary_pairs):
        raise PipelineError("primary_denominator_mismatch", "Frozen primary count changed.")
    if {item["pair_id"] for item in pair_manifest["diagnostic_pairs"]} != set(diagnostic_pairs):
        raise PipelineError("diagnostic_denominator_mismatch", "Frozen diagnostic count changed.")

    a0_matches = evaluation_match_map(a0_bundle)
    a_matches = evaluation_match_map(a_bundle)
    b_matches = evaluation_match_map(b_bundle)
    if set(primary_pairs) - set(a0_matches):
        raise PipelineError("missing_pair_outcome", "A0 does not cover the primary universe.")
    if set(a_matches) != set(recoverable_ids) or set(b_matches) != set(recoverable_ids):
        raise PipelineError("matched_pair_id_set_mismatch", "Matched outcomes differ from recoverable pairs.")

    alignment_records = {
        ref_key(item["oracle_ref"]): item for item in alignment["oracle_records"]
    }
    unique_endpoints = {
        ref_key(endpoint)
        for pair in primary_pairs.values()
        for endpoint in [pair["source"], pair["target"]]
    }
    recovered_endpoints = {
        ref
        for ref in unique_endpoints
        if ref in alignment_records and projector.endpoint_reasons(alignment_records[ref]) == []
    }
    weighted_recovered = sum(
        ref_key(endpoint) in recovered_endpoints
        for pair in primary_pairs.values()
        for endpoint in [pair["source"], pair["target"]]
    )
    type_matches = sum(
        alignment_records[ref].get("type_match") is True for ref in recovered_endpoints
    )

    positive_ids = {
        pair_id for pair_id, pair in primary_pairs.items() if pair["category"] == "positive"
    }
    negative_ids = set(primary_pairs) - positive_ids
    within_ids = {
        pair_id
        for pair_id, pair in primary_pairs.items()
        if pair["source"]["lecture_id"] == pair["target"]["lecture_id"]
    }
    cross_ids = set(primary_pairs) - within_ids
    recoverable_set = set(recoverable_ids)
    per_gold_type = {
        relation_type: rate(
            len(
                recoverable_set
                & {
                    pair_id
                    for pair_id, pair in primary_pairs.items()
                    if pair["relation_type"] == relation_type
                }
            ),
            sum(pair["relation_type"] == relation_type for pair in primary_pairs.values()),
        )
        for relation_type in original_ground_truth["allowed_relation_types"]
        if any(pair["relation_type"] == relation_type for pair in primary_pairs.values())
    }

    a_conditional = conditional_metrics(
        a_bundle, gold_pairs={pair_id: primary_pairs[pair_id] for pair_id in recoverable_ids}
    )
    b_conditional = conditional_metrics(
        b_bundle, gold_pairs={pair_id: primary_pairs[pair_id] for pair_id in recoverable_ids}
    )
    b_strict_ids = {
        pair_id
        for pair_id, match in b_matches.items()
        if match.get("strict_edge_correct") is True
    }
    secondary = secondary_flags_by_pair(
        ko_manifest=ko_manifest,
        alignment=alignment,
        a_input=a_input,
        b_input=b_input,
        projection_errors=projection_errors,
        b_bundle=b_bundle,
    )
    transitions: list[dict[str, Any]] = []
    for pair_id in sorted(primary_pairs):
        gold_pair = primary_pairs[pair_id]
        a0_outcome = classify_outcome(a0_matches[pair_id], gold_pair=gold_pair)
        recoverable = pair_id in recoverable_set
        a_outcome = (
            classify_outcome(a_matches[pair_id], gold_pair=gold_pair) if recoverable else None
        )
        b_outcome = (
            classify_outcome(b_matches[pair_id], gold_pair=gold_pair) if recoverable else None
        )
        transitions.append({
            "pair_id": pair_id,
            "category": gold_pair["category"],
            "gold_relation_type": gold_pair["relation_type"],
            "recoverability_status": "recoverable" if recoverable else "unrecoverable",
            "unrecoverable_reasons": [] if recoverable else unrecoverable[pair_id],
            "A0_outcome": a0_outcome,
            "A_prime_outcome": a_outcome,
            "B_prime_outcome": b_outcome,
            "A0_to_B_prime_transition": a0_transition(a0_outcome, b_outcome),
            "A_prime_to_B_prime_transition": (
                matched_transition(a_outcome, b_outcome) if recoverable else None
            ),
            "primary_failure_locus": failure_locus(
                recoverable=recoverable,
                a_outcome=a_outcome,
                b_outcome=b_outcome,
            ),
            "secondary_quality_flags": secondary.get(pair_id, []),
        })

    pair_weighted_type_exposure = sum(
        "ko_type_mismatch" in secondary.get(pair_id, []) for pair_id in primary_pairs
    )
    metrics = {
        "artifact_type": "predicted_ko_pipeline_metrics",
        "version": VERSION,
        "evaluation_status": "final",
        "aggregate_metrics_valid": True,
        "provenance": provenance,
        "denominators": {
            "all_pairs": len(original_ground_truth["pairs"]),
            "all_primary_pairs": len(primary_pairs),
            "positive_primary_pairs": len(positive_ids),
            "hard_negative_primary_pairs": len(negative_ids),
            "unique_primary_endpoint_kos": len(unique_endpoints),
            "primary_pair_endpoint_positions": len(primary_pairs) * 2,
            "diagnostic_pairs": len(diagnostic_pairs),
        },
        "alignment_metrics": {
            "unique_endpoint_recovery": rate(len(recovered_endpoints), len(unique_endpoints)),
            "pair_weighted_endpoint_recovery": rate(
                weighted_recovered, len(primary_pairs) * 2
            ),
            "unique_endpoint_type_match": rate(type_matches, len(recovered_endpoints)),
        },
        "pair_recoverability": {
            "overall": rate(len(recoverable_set), len(primary_pairs)),
            "positive": rate(len(recoverable_set & positive_ids), len(positive_ids)),
            "hard_negative": rate(len(recoverable_set & negative_ids), len(negative_ids)),
            "within_lecture": rate(len(recoverable_set & within_ids), len(within_ids)),
            "cross_lecture": rate(len(recoverable_set & cross_ids), len(cross_ids)),
            "per_gold_relation_type": per_gold_type,
        },
        "conditional_A_prime": a_conditional,
        "conditional_B_prime": b_conditional,
        "pipeline_metrics": {
            "strict_success": rate(len(b_strict_ids), len(primary_pairs)),
            "positive_strict_success": rate(
                len(b_strict_ids & positive_ids), len(positive_ids)
            ),
            "hard_negative_strict_success": rate(
                len(b_strict_ids & negative_ids), len(negative_ids)
            ),
            "recoverability_times_conditional_strict": (
                len(b_strict_ids) / len(primary_pairs) if primary_pairs else None
            ),
        },
        "counts": {
            "unique_type_mismatches": len(recovered_endpoints) - type_matches,
            "pair_weighted_type_mismatch_exposure": pair_weighted_type_exposure,
            "unmatched_extra_predictions": len(
                projection_errors.get("unmatched_extra_predicted_kos", [])
            ),
            "unrecoverable_primary_pairs": len(unrecoverable),
            "diagnostic_pairs_excluded": len(diagnostic_pairs),
            "fatal_errors": 0,
            "pending_items": 0,
        },
    }
    if metrics["pipeline_metrics"]["strict_success"]["numerator"] != b_conditional[
        "strict_edge_accuracy"
    ]["numerator"]:
        raise PipelineError("pipeline_product_identity_mismatch", "Strict numerators differ.")
    if b_conditional["strict_edge_accuracy"]["denominator"] != len(recoverable_set):
        raise PipelineError(
            "pipeline_product_identity_mismatch",
            "Conditional strict denominator differs from recoverable-pair count.",
        )

    nonfatal_errors: list[dict[str, Any]] = []
    for pair_id, reasons in sorted(unrecoverable.items()):
        for reason in reasons:
            nonfatal_errors.append({
                "error_code": reason,
                "pair_id": pair_id,
                "affected_pair_ids": [pair_id],
                "message": "The primary pair is correctly recorded as upstream unrecoverable.",
            })
    for item in projection_errors.get("recoverable_slot_quality_flags", []):
        slot = next(slot for slot in ko_manifest["slots"] if slot["slot_id"] == item["slot_id"])
        for error_code in item["flags"]:
            nonfatal_errors.append({
                "error_code": error_code,
                "pair_id": None,
                "oracle_ref": item["oracle_ref"],
                "predicted_ref": item["predicted_ref"],
                "affected_pair_ids": slot["referenced_by_pair_ids"],
                "message": "A nonfatal predicted-KO quality observation is propagated descriptively.",
            })
    for predicted_ref in projection_errors.get("unmatched_extra_predicted_kos", []):
        nonfatal_errors.append({
            "error_code": "unmatched_extra_predicted_ko",
            "pair_id": None,
            "predicted_ref": predicted_ref,
            "affected_pair_ids": [],
            "message": "The unmatched prediction is excluded from matched Relation inputs.",
        })
    for item in b_bundle.errors:
        if not isinstance(item, dict) or not isinstance(item.get("error_type"), str):
            continue
        nonfatal_errors.append({
            "error_code": f"b_prime_{item['error_type']}",
            "pair_id": item.get("pair_id"),
            "affected_pair_ids": [item["pair_id"]] if item.get("pair_id") else [],
            "message": "This Relation-evaluator observation occurred under B-prime.",
        })
    errors = {
        "artifact_type": "predicted_ko_pipeline_errors",
        "version": VERSION,
        "evaluation_status": "final",
        "provenance": provenance,
        "fatal_errors": [],
        "nonfatal_errors": nonfatal_errors,
        "pending_items": [],
    }
    transition_artifact = {
        "artifact_type": "predicted_ko_pair_transitions",
        "version": VERSION,
        "evaluation_status": "final",
        "provenance": provenance,
        "transitions": transitions,
    }
    return {
        "pipeline_metrics.json": metrics,
        "pipeline_errors.json": errors,
        "pair_transitions.json": transition_artifact,
    }


def prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    existing = [output_dir / name for name in MANAGED_FILENAMES if (output_dir / name).exists()]
    if existing and not overwrite:
        raise PipelineError(
            "output_exists",
            "Pipeline output already exists: " + ", ".join(str(path) for path in existing),
        )


def write_output_bundle(
    output_dir: Path,
    artifacts: dict[str, Any],
    *,
    evaluation_status: str,
    upstream: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_paths: dict[str, Path] = {}
    marker_path = output_dir / COMPLETION_FILENAME
    if marker_path.exists():
        marker_path.unlink()
    try:
        for filename in MANAGED_FILENAMES:
            target = output_dir / filename
            if filename not in artifacts and target.exists():
                target.unlink()
        for filename, value in artifacts.items():
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output_dir,
                prefix=f".{filename}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(serialize_json(value))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_paths[filename] = Path(temporary_file.name)
        marker = {
            "artifact_type": "predicted_ko_pipeline_evaluation_complete",
            "version": VERSION,
            "evaluation_status": evaluation_status,
            "upstream": upstream,
            "artifacts": {
                filename: artifact_sha256(value)
                for filename, value in sorted(artifacts.items())
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{COMPLETION_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialize_json(marker))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_paths[COMPLETION_FILENAME] = Path(temporary_file.name)
        for filename in sorted(artifacts):
            temporary_paths[filename].replace(output_dir / filename)
        temporary_paths[COMPLETION_FILENAME].replace(marker_path)
    finally:
        for path in temporary_paths.values():
            if path.exists():
                path.unlink()


def invalid_artifacts(error: PipelineError) -> dict[str, Any]:
    return {
        "pipeline_errors.json": {
            "artifact_type": "predicted_ko_pipeline_errors",
            "version": VERSION,
            "evaluation_status": "invalid",
            "aggregate_metrics_valid": False,
            "provenance": {},
            "fatal_errors": [{
                "error_code": error.code,
                "pair_id": None,
                "message": str(error),
            }],
            "nonfatal_errors": [],
            "pending_items": [],
        }
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the predicted-KO Relation pipeline from frozen artifacts."
    )
    parser.add_argument("--original-ground-truth", required=True)
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--projection-dir", required=True)
    parser.add_argument("--a0-evaluation-dir", required=True)
    parser.add_argument("--a-prime-evaluation-dir")
    parser.add_argument("--b-prime-evaluation-dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = resolve_path(args.output_dir)
    upstream: dict[str, Any] = {}
    try:
        prepare_output_dir(output_dir, overwrite=args.overwrite)
        original_path = resolve_path(args.original_ground_truth)
        alignment_path = resolve_path(args.alignment)
        projection_dir = resolve_path(args.projection_dir)
        original = read_json(original_path)
        original_errors, _ = validate_ground_truth(original)
        if original_errors:
            raise PipelineError(
                "invalid_original_ground_truth", "; ".join(original_errors)
            )
        alignment = read_json(alignment_path)
        projection = load_projection_artifacts(projection_dir)
        original_hash = sha256_file(original_path)
        alignment_marker_hash, projection_marker_hash = validate_projection_chain(
            original_ground_truth=original,
            original_ground_truth_sha256=original_hash,
            alignment_path=alignment_path,
            alignment=alignment,
            projection_dir=projection_dir,
            artifacts=projection,
        )
        pair_manifest = projection["recoverable_pair_manifest.json"]
        ko_manifest = projection["recoverable_ko_manifest.json"]
        matched_gt = projection["matched_relation_ground_truth.json"]
        projection_errors = projection["projection_errors.json"]
        a_input_path = projection_dir / "oracle_normalized_input.json"
        b_input_path = projection_dir / "predicted_normalized_input.json"
        batch_plan_path = projection_dir / "batch_plan.json"
        a_input = projection["oracle_normalized_input.json"]
        b_input = projection["predicted_normalized_input.json"]
        recoverable_ids = {item["pair_id"] for item in pair_manifest["primary_pairs"]}
        primary, diagnostic = primary_pair_maps(original)
        a0_bundle = load_evaluation_bundle(
            resolve_path(args.a0_evaluation_dir),
            condition="A0",
            expected_pair_ids=set(primary),
            allowed_extra_pair_ids=set(diagnostic),
            expected_pair_order=list(primary),
        )

        noops: dict[str, Any] = {}
        if recoverable_ids:
            if not args.a_prime_evaluation_dir or not args.b_prime_evaluation_dir:
                raise PipelineError(
                    "missing_matched_run",
                    "A-prime and B-prime evaluations are required for recoverable pairs.",
                )
            a_bundle = load_evaluation_bundle(
                resolve_path(args.a_prime_evaluation_dir),
                condition="A_prime",
                expected_pair_ids=recoverable_ids,
                expected_pair_order=[
                    item["pair_id"] for item in pair_manifest["primary_pairs"]
                ],
            )
            b_bundle = load_evaluation_bundle(
                resolve_path(args.b_prime_evaluation_dir),
                condition="B_prime",
                expected_pair_ids=recoverable_ids,
                expected_pair_order=[
                    item["pair_id"] for item in pair_manifest["primary_pairs"]
                ],
            )
            validate_matched_execution(
                a_bundle=a_bundle,
                b_bundle=b_bundle,
                a_input_path=a_input_path,
                b_input_path=b_input_path,
                batch_plan_path=batch_plan_path,
            )
        else:
            pair_hash = sha256_file(projection_dir / "recoverable_pair_manifest.json")
            ko_hash = sha256_file(projection_dir / "recoverable_ko_manifest.json")
            for condition, filename in [
                ("A_prime", "A_prime_noop_evaluation.json"),
                ("B_prime", "B_prime_noop_evaluation.json"),
            ]:
                noops[filename] = make_noop_evaluation(
                    condition,
                    pair_manifest_sha256=pair_hash,
                    ko_manifest_sha256=ko_hash,
                )
            a_bundle = noop_bundle("A_prime", noops["A_prime_noop_evaluation.json"])
            b_bundle = noop_bundle("B_prime", noops["B_prime_noop_evaluation.json"])

        provenance = {
            "original_ground_truth_sha256": original_hash,
            "alignment_sha256": sha256_file(alignment_path),
            "pair_manifest_sha256": sha256_file(
                projection_dir / "recoverable_pair_manifest.json"
            ),
            "ko_manifest_sha256": sha256_file(
                projection_dir / "recoverable_ko_manifest.json"
            ),
            "matched_ground_truth_sha256": sha256_file(
                projection_dir / "matched_relation_ground_truth.json"
            ),
            "A0_evaluation_sha256": a0_bundle.evaluation_sha256,
            "A_prime_evaluation_sha256": a_bundle.evaluation_sha256,
            "B_prime_evaluation_sha256": b_bundle.evaluation_sha256,
            "A_prime_input_sha256": sha256_file(a_input_path),
            "B_prime_input_sha256": sha256_file(b_input_path),
            "A_prime_run_metadata_sha256": a_bundle.metadata_sha256,
            "B_prime_run_metadata_sha256": b_bundle.metadata_sha256,
            "A_prime_prediction_sha256": a_bundle.prediction_sha256,
            "B_prime_prediction_sha256": b_bundle.prediction_sha256,
            "batch_plan_sha256": sha256_file(batch_plan_path),
        }
        upstream = {
            **provenance,
            "alignment_bundle_complete_sha256": alignment_marker_hash,
            "projection_bundle_complete_sha256": projection_marker_hash,
        }
        outputs = build_pipeline_outputs(
            original_ground_truth=original,
            alignment=alignment,
            pair_manifest=pair_manifest,
            ko_manifest=ko_manifest,
            projection_errors=projection_errors,
            a_input=a_input,
            b_input=b_input,
            a0_bundle=a0_bundle,
            a_bundle=a_bundle,
            b_bundle=b_bundle,
            provenance=provenance,
        )
        outputs.update(noops)
        write_output_bundle(
            output_dir,
            outputs,
            evaluation_status="final",
            upstream=upstream,
        )
    except PipelineError as exc:
        if exc.code == "output_exists":
            print(f"Pipeline evaluation failed [{exc.code}]: {exc}", file=sys.stderr)
            return 2
        write_output_bundle(
            output_dir,
            invalid_artifacts(exc),
            evaluation_status="invalid",
            upstream=upstream,
        )
        print(f"Pipeline evaluation invalid [{exc.code}]: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote final Step 4.4 pipeline evaluation to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
