#!/usr/bin/env python3
"""Evaluate Experiment 003-2 canonical Connection predictions."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_connection_discovery import (
    ALLOWED_RELATIONS,
    DEFAULT_CATALOGS,
    DEFAULT_FREEZE_MANIFEST,
    DEFAULT_SELECTION,
    ROOT,
    RESULT_KEYS,
    binding,
    display_path,
    load_json,
    resolve_path,
    serialize_json,
    sha256_file,
    sha256_json,
)


BENCHMARK_ROOT = ROOT / "benchmark" / "connection_discovery" / "development_v0_1"
DEFAULT_GROUND_TRUTH = BENCHMARK_ROOT / "ground_truth.json"
DEFAULT_SUCCESS_CRITERIA = ROOT / "benchmark" / "connection_discovery_success_criteria_v0_1.json"
EVALUATOR_VERSION = "canonical_connection_evaluator_v0.1"
SYMMETRIC_RELATIONS = {"CONTRASTS_WITH", "RELATED_TO"}
ADJUDICATION_DECISIONS = {"supported", "not_supported"}
OUTPUT_NAMES = (
    "metrics.json", "matches.json", "errors.json", "materialized_predictions.json",
    "per_relation_metrics.json", "stratum_metrics.json", "adjudication_pending.json",
    "evaluation_complete.json",
)


class EvaluationError(ValueError):
    """Raised when evaluation cannot safely produce scored metrics."""


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(serialize_json(value))
        temporary = Path(handle.name)
    os.replace(temporary, path)


def edge_from_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_canonical_ko_id": prediction["source_canonical_ko_id"],
        "target_canonical_ko_id": prediction["target_canonical_ko_id"],
        "relation_type": prediction["relation_type"],
        "symmetric": prediction["relation_type"] in SYMMETRIC_RELATIONS,
    }


def edge_matches(prediction: dict[str, Any], edge: dict[str, Any]) -> bool:
    if prediction["relation_type"] != edge["relation_type"]:
        return False
    direct = (
        prediction["source_canonical_ko_id"] == edge["source_canonical_ko_id"]
        and prediction["target_canonical_ko_id"] == edge["target_canonical_ko_id"]
    )
    reverse = (
        prediction["source_canonical_ko_id"] == edge["target_canonical_ko_id"]
        and prediction["target_canonical_ko_id"] == edge["source_canonical_ko_id"]
    )
    symmetric = bool(edge.get("symmetric")) or edge["relation_type"] in SYMMETRIC_RELATIONS
    return direct or (symmetric and reverse)


def accepted_edges(truth: dict[str, Any]) -> list[dict[str, Any]]:
    edge = truth.get("gold_edge")
    return ([] if edge is None else [edge]) + list(truth.get("acceptable_alternatives", []))


def validate_prediction_bundle(
    predictions: dict[str, Any],
    *,
    selected_pairs: list[dict[str, Any]],
    catalog_map: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if set(predictions) != {"artifact_type", "version", "results"}:
        return ["prediction bundle field set is invalid"]
    if predictions.get("artifact_type") != "canonical_connection_predictions" or predictions.get("version") != "v0.1":
        errors.append("prediction bundle identity is invalid")
    results = predictions.get("results")
    if not isinstance(results, list):
        return errors + ["prediction results must be a list"]
    selected_map = {item["canonical_pair_id"]: item for item in selected_pairs}
    ids: list[str] = []
    for index, result in enumerate(results):
        if not isinstance(result, dict) or set(result) != RESULT_KEYS:
            errors.append(f"result {index} field set is invalid")
            continue
        pair_id = result.get("canonical_pair_id")
        if pair_id not in selected_map:
            errors.append(f"result {index} has unknown canonical_pair_id")
            continue
        endpoints = {
            result.get("source_canonical_ko_id"), result.get("target_canonical_ko_id")
        }
        expected = {
            selected_map[pair_id]["ko_a"]["canonical_ko_id"],
            selected_map[pair_id]["ko_b"]["canonical_ko_id"],
        }
        if endpoints != expected:
            errors.append(f"{pair_id}: candidate endpoints changed")
        if result.get("relation_type") not in ALLOWED_RELATIONS:
            errors.append(f"{pair_id}: Relation type is invalid")
        evidence_ids = result.get("evidence_ids")
        if not isinstance(evidence_ids, list) or any(not isinstance(item, str) for item in evidence_ids):
            errors.append(f"{pair_id}: evidence_ids must be a string list")
        elif len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"{pair_id}: duplicate Evidence IDs")
        else:
            allowed = {item["evidence_id"] for item in catalog_map[pair_id]["evidence_items"]}
            if set(evidence_ids) - allowed:
                errors.append(f"{pair_id}: unknown Evidence ID")
        if not isinstance(result.get("rationale"), str):
            errors.append(f"{pair_id}: rationale must be a string")
        ids.append(pair_id)
    if len(ids) != len(set(ids)):
        errors.append("prediction bundle contains duplicate pair IDs")
    if set(ids) != set(selected_map):
        errors.append("prediction pair set differs from selected candidates")
    return errors


def materialize_prediction(
    prediction: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    evidence_map = {item["evidence_id"]: item for item in catalog["evidence_items"]}
    return {
        **prediction,
        "materialized_evidence": [evidence_map[item] for item in prediction["evidence_ids"]],
    }


def build_pending_artifact(
    predictions: dict[str, Any], items: list[dict[str, Any]]
) -> dict[str, Any]:
    snapshot = sha256_json(items)
    return {
        "artifact_type": "canonical_connection_evidence_adjudication_pending",
        "version": "v0.1",
        "prediction_content_sha256": sha256_json(predictions),
        "pending_snapshot_sha256": snapshot,
        "pending_count": len(items),
        "items": items,
    }


def load_adjudication(
    adjudication: dict[str, Any] | None,
    *,
    pending: dict[str, Any],
) -> dict[str, str]:
    if not pending["items"]:
        if adjudication is not None:
            raise EvaluationError("adjudication supplied when no items are pending")
        return {}
    if adjudication is None:
        return {}
    expected_keys = {
        "artifact_type", "version", "prediction_content_sha256",
        "pending_snapshot_sha256", "decisions",
    }
    if set(adjudication) != expected_keys:
        raise EvaluationError("adjudication field set is invalid")
    if adjudication["artifact_type"] != "canonical_connection_evidence_adjudication" or adjudication["version"] != "v0.1":
        raise EvaluationError("adjudication identity is invalid")
    for field in ("prediction_content_sha256", "pending_snapshot_sha256"):
        if adjudication[field] != pending[field]:
            raise EvaluationError(f"stale adjudication {field}")
    pending_ids = {item["canonical_pair_id"] for item in pending["items"]}
    decisions: dict[str, str] = {}
    for item in adjudication["decisions"]:
        if set(item) != {"canonical_pair_id", "decision", "rationale"}:
            raise EvaluationError("adjudication decision field set is invalid")
        pair_id = item["canonical_pair_id"]
        if pair_id not in pending_ids or pair_id in decisions:
            raise EvaluationError("adjudication pair set is invalid")
        if item["decision"] not in ADJUDICATION_DECISIONS:
            raise EvaluationError("adjudication decision is invalid")
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise EvaluationError("adjudication rationale is empty")
        decisions[pair_id] = item["decision"]
    if set(decisions) != pending_ids:
        raise EvaluationError("adjudication decisions do not cover the pending set")
    return decisions


def evaluate(
    *,
    predictions: dict[str, Any],
    selected_pairs: list[dict[str, Any]],
    ground_truth: dict[str, Any],
    catalogs: dict[str, Any],
    success_criteria: dict[str, Any],
    adjudication: dict[str, Any] | None = None,
) -> dict[str, Any]:
    truth_map = {item["canonical_pair_id"]: item for item in ground_truth["pairs"]}
    selected_ids = {item["canonical_pair_id"] for item in selected_pairs}
    catalog_map = {item["canonical_pair_id"]: item for item in catalogs["catalogs"]}
    prediction_map = {item["canonical_pair_id"]: item for item in predictions["results"]}
    materialized = [
        materialize_prediction(item, catalog_map[item["canonical_pair_id"]])
        for item in predictions["results"]
    ]
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    pending_items: list[dict[str, Any]] = []
    auto_supported: set[str] = set()
    automatic_not_supported: set[str] = set()
    relation_counts: dict[str, Counter[str]] = defaultdict(Counter)
    stratum_counts: dict[str, Counter[str]] = defaultdict(Counter)

    primary_positive = [item for item in ground_truth["pairs"] if item["primary_scoring_eligible"] and item["category"] == "IN_SCHEMA_CONNECTION"]
    primary_negative = [item for item in ground_truth["pairs"] if item["primary_scoring_eligible"] and item["category"] == "NO_IN_SCHEMA_CONNECTION"]
    selected_primary_positive = [item for item in primary_positive if item["canonical_pair_id"] in selected_ids]
    selected_primary_negative = [item for item in primary_negative if item["canonical_pair_id"] in selected_ids]
    for truth in primary_positive:
        if truth["canonical_pair_id"] not in selected_ids:
            errors.append({
                "error_type": "candidate_miss",
                "canonical_pair_id": truth["canonical_pair_id"],
                "gold_relation_type": truth["gold_edge"]["relation_type"],
            })

    correct_positive = 0
    correct_negative = 0
    predicted_positive_primary = 0
    type_correct_positive = 0
    direction_correct_when_type = 0
    related_to_primary = 0
    positive_prediction_count = 0
    exact_materialized_cases = 0

    for pair_id in [item["canonical_pair_id"] for item in selected_pairs]:
        truth = truth_map[pair_id]
        prediction = prediction_map[pair_id]
        relation_type = prediction["relation_type"]
        is_positive_prediction = relation_type != "NO_RELATION"
        is_primary_positive = truth["primary_scoring_eligible"] and truth["category"] == "IN_SCHEMA_CONNECTION"
        is_primary_negative = truth["primary_scoring_eligible"] and truth["category"] == "NO_IN_SCHEMA_CONNECTION"
        accepted = accepted_edges(truth)
        strict_correct = is_primary_positive and any(edge_matches(prediction, edge) for edge in accepted)
        no_relation_correct = is_primary_negative and relation_type == "NO_RELATION"
        type_correct = is_primary_positive and any(relation_type == edge["relation_type"] for edge in accepted)
        direction_correct = is_primary_positive and any(edge_matches(prediction, edge) for edge in accepted if relation_type == edge["relation_type"])
        if is_primary_positive:
            gold_type = truth["gold_edge"]["relation_type"]
            relation_counts[gold_type]["support"] += 1
            relation_counts[gold_type]["strict_correct"] += int(strict_correct)
            type_correct_positive += int(type_correct)
            if type_correct:
                direction_correct_when_type += int(direction_correct)
        if is_primary_negative:
            correct_negative += int(no_relation_correct)
        if strict_correct:
            correct_positive += 1
        if (is_primary_positive or is_primary_negative) and is_positive_prediction:
            predicted_positive_primary += 1
        if (is_primary_positive or is_primary_negative) and relation_type == "RELATED_TO":
            related_to_primary += 1

        quality_errors: list[str] = []
        semantic_status: str | None = None
        if is_positive_prediction:
            positive_prediction_count += 1
            if prediction["evidence_ids"]:
                exact_materialized_cases += 1
            else:
                quality_errors.append("missing_evidence")
                automatic_not_supported.add(pair_id)
                semantic_status = "not_supported"
            if not prediction["rationale"].strip():
                quality_errors.append("missing_rationale")
            if prediction["evidence_ids"]:
                gold_ids = {item["evidence_id"] for item in truth.get("evidence", [])}
                if strict_correct and set(prediction["evidence_ids"]) == gold_ids:
                    auto_supported.add(pair_id)
                    semantic_status = "auto_supported_exact_gold"
                else:
                    materialized_item = next(item for item in materialized if item["canonical_pair_id"] == pair_id)
                    pending_items.append({
                        "canonical_pair_id": pair_id,
                        "predicted_edge": edge_from_prediction(prediction),
                        "evidence_ids": prediction["evidence_ids"],
                        "materialized_evidence": materialized_item["materialized_evidence"],
                        "rationale": prediction["rationale"],
                        "prediction_snapshot_sha256": sha256_json(prediction),
                    })
                    semantic_status = "pending"
        else:
            if prediction["evidence_ids"]:
                quality_errors.append("no_relation_with_evidence")
            if not prediction["rationale"].strip():
                quality_errors.append("missing_rationale")

        if is_primary_positive:
            if relation_type == "NO_RELATION": error_type = "false_negative_relation"
            elif not type_correct: error_type = "wrong_relation_type"
            elif not direction_correct: error_type = "wrong_direction"
            elif quality_errors: error_type = "evidence_failure"
            else: error_type = None
        elif is_primary_negative and is_positive_prediction:
            error_type = "false_positive_relation"
        else:
            error_type = None
        if error_type:
            errors.append({"error_type": error_type, "canonical_pair_id": pair_id, "gold_relation_type": truth["gold_edge"]["relation_type"] if truth["gold_edge"] else "NO_RELATION", "predicted_relation_type": relation_type})
        for quality_error in quality_errors:
            errors.append({"error_type": quality_error, "canonical_pair_id": pair_id})

        for label in [truth["provenance_stratum"], *[name for name, flag in truth["scope_flags"].items() if flag]]:
            if is_primary_positive:
                stratum_counts[label]["positive_support"] += 1
                stratum_counts[label]["strict_correct"] += int(strict_correct)
        matches.append({
            "canonical_pair_id": pair_id, "gold_category": truth["category"],
            "primary_scoring_eligible": truth["primary_scoring_eligible"],
            "gold_edge": truth["gold_edge"], "prediction": prediction,
            "strict_edge_correct": strict_correct, "no_relation_correct": no_relation_correct,
            "type_correct": type_correct, "direction_correct": direction_correct,
            "evidence_semantic_status": semantic_status, "quality_errors": quality_errors,
        })

    pending_artifact = build_pending_artifact(predictions, pending_items)
    decisions = load_adjudication(adjudication, pending=pending_artifact)
    supported = len(auto_supported) + sum(value == "supported" for value in decisions.values())
    not_supported = len(automatic_not_supported) + sum(value == "not_supported" for value in decisions.values())
    pending_count = len(pending_items) - len(decisions)
    for match in matches:
        pair_id = match["canonical_pair_id"]
        if pair_id in decisions:
            match["evidence_semantic_status"] = decisions[pair_id]
            if decisions[pair_id] == "not_supported":
                errors.append({"error_type": "evidence_semantic_not_supported", "canonical_pair_id": pair_id})

    selected_primary_count = len(selected_primary_positive) + len(selected_primary_negative)
    conditional = {
        "positive_typed_edge_recall": safe_ratio(correct_positive, len(selected_primary_positive)),
        "positive_edge_precision": safe_ratio(correct_positive, predicted_positive_primary),
        "no_relation_accuracy": safe_ratio(correct_negative, len(selected_primary_negative)),
        "strict_edge_accuracy": safe_ratio(correct_positive + correct_negative, selected_primary_count),
        "relation_type_accuracy_on_positives": safe_ratio(type_correct_positive, len(selected_primary_positive)),
        "direction_accuracy_when_type_correct": safe_ratio(direction_correct_when_type, type_correct_positive),
        "exact_evidence_materialization_rate": safe_ratio(exact_materialized_cases, positive_prediction_count),
        "semantic_evidence_support_rate": safe_ratio(supported, positive_prediction_count) if pending_count == 0 else None,
        "related_to_prediction_rate": safe_ratio(related_to_primary, selected_primary_count),
    }
    candidate_misses = len(primary_positive) - len(selected_primary_positive)
    full_correct_positive = correct_positive
    full_correct_negative = correct_negative + (len(primary_negative) - len(selected_primary_negative))
    full = {
        "primary_connection_precision": safe_ratio(full_correct_positive, predicted_positive_primary),
        "primary_connection_recall": safe_ratio(full_correct_positive, len(primary_positive)),
        "primary_connection_f1": None,
        "pipeline_strict_accuracy": safe_ratio(full_correct_positive + full_correct_negative, len(primary_positive) + len(primary_negative)),
        "cross_course_connection_recall": safe_ratio(
            sum(1 for item in selected_primary_positive if item["scope_flags"]["cross_course"] and any(edge_matches(prediction_map[item["canonical_pair_id"]], edge) for edge in accepted_edges(item))),
            sum(1 for item in primary_positive if item["scope_flags"]["cross_course"]),
        ),
    }
    p, r = full["primary_connection_precision"], full["primary_connection_recall"]
    full["primary_connection_f1"] = 2 * p * r / (p + r) if p is not None and r is not None and p + r else None

    status = "final" if pending_count == 0 else "draft_pending_adjudication"
    criteria = success_criteria["stage_003_2_conditional_classification"]
    checks = {
        "positive_typed_edge_recall": (conditional["positive_typed_edge_recall"], ">=", criteria["positive_typed_edge_recall_minimum"]),
        "positive_edge_precision": (conditional["positive_edge_precision"], ">=", criteria["positive_edge_precision_minimum"]),
        "no_relation_accuracy": (conditional["no_relation_accuracy"], ">=", criteria["no_relation_accuracy_minimum"]),
        "exact_evidence_materialization_rate": (conditional["exact_evidence_materialization_rate"], "==", criteria["exact_evidence_materialization_rate"]),
        "semantic_evidence_support_rate": (conditional["semantic_evidence_support_rate"], ">=", criteria["semantic_evidence_support_rate_minimum"]),
        "related_to_prediction_rate": (conditional["related_to_prediction_rate"], "<=", criteria["related_to_prediction_rate_maximum"]),
        "fatal_alignment_errors": (0, "<=", criteria["maximum_fatal_alignment_errors"]),
    }
    gate_checks = {}
    for name, (value, operator, threshold) in checks.items():
        passed = value is not None and (value >= threshold if operator == ">=" else value <= threshold if operator == "<=" else value == threshold)
        gate_checks[name] = {"value": value, "operator": operator, "threshold": threshold, "passed": passed}
    gate = {"outcome": "pending_adjudication" if status != "final" else "passed" if all(item["passed"] for item in gate_checks.values()) else "failed", "checks": gate_checks, "anti_majority_rule": criteria["anti_majority_rule"]}
    full_criteria = success_criteria["full_universe_discovery"]
    full_checks_raw = {
        "primary_connection_precision": (full["primary_connection_precision"], ">=", full_criteria["primary_connection_precision_minimum"]),
        "primary_connection_recall": (full["primary_connection_recall"], ">=", full_criteria["primary_connection_recall_minimum"]),
        "primary_connection_f1": (full["primary_connection_f1"], ">=", full_criteria["primary_connection_f1_minimum"]),
        "cross_course_connection_recall": (full["cross_course_connection_recall"], ">=", full_criteria["cross_course_connection_recall_minimum"]),
        "duplicate_connections": (0, "<=", full_criteria["maximum_duplicate_connections"]),
    }
    full_gate_checks = {}
    for name, (value, operator, threshold) in full_checks_raw.items():
        passed = value is not None and (value >= threshold if operator == ">=" else value <= threshold)
        full_gate_checks[name] = {"value": value, "operator": operator, "threshold": threshold, "passed": passed}
    full_gate = {
        "outcome": "passed" if all(item["passed"] for item in full_gate_checks.values()) else "failed",
        "checks": full_gate_checks,
    }

    relation_rows = [{"relation_type": relation, "support": values["support"], "strict_correct": values["strict_correct"], "recall": safe_ratio(values["strict_correct"], values["support"])} for relation, values in sorted(relation_counts.items())]
    stratum_rows = [{"stratum": label, "positive_support": values["positive_support"], "strict_correct": values["strict_correct"], "recall": safe_ratio(values["strict_correct"], values["positive_support"])} for label, values in sorted(stratum_counts.items())]
    counts = {
        "universe_primary_positive_pairs": len(primary_positive), "universe_primary_negative_pairs": len(primary_negative),
        "selected_primary_positive_pairs": len(selected_primary_positive), "selected_primary_negative_pairs": len(selected_primary_negative),
        "candidate_misses": candidate_misses, "correct_positive_edges": correct_positive,
        "correct_no_relation": correct_negative, "predicted_positive_primary": predicted_positive_primary,
        "false_positive_relations": sum(item["error_type"] == "false_positive_relation" for item in errors),
        "false_negative_relations": sum(item["error_type"] == "false_negative_relation" for item in errors),
        "wrong_relation_type": sum(item["error_type"] == "wrong_relation_type" for item in errors),
        "wrong_direction": sum(item["error_type"] == "wrong_direction" for item in errors),
        "positive_evidence_cases": positive_prediction_count, "evidence_auto_supported": len(auto_supported),
        "evidence_supported_by_adjudication": sum(value == "supported" for value in decisions.values()),
        "evidence_not_supported": not_supported, "evidence_pending": pending_count,
    }
    return {
        "metrics": {"artifact_type": "canonical_connection_metrics", "version": "v0.1", "evaluation_status": status, "counts": counts, "conditional_metrics": conditional, "full_universe_metrics": full, "gate_assessment": gate, "full_universe_gate_assessment": full_gate},
        "matches": matches, "errors": errors,
        "materialized_predictions": {"artifact_type": "materialized_canonical_connection_predictions", "version": "v0.1", "results": materialized},
        "per_relation_metrics": {"artifact_type": "canonical_connection_per_relation_metrics", "version": "v0.1", "relations": relation_rows},
        "stratum_metrics": {"artifact_type": "canonical_connection_stratum_metrics", "version": "v0.1", "strata": stratum_rows},
        "adjudication_pending": pending_artifact,
    }


def prepare_evaluation_dir(path: Path, *, adjudication_supplied: bool, prediction_path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True)
        return
    marker_path = path / "evaluation_complete.json"
    if not adjudication_supplied or not marker_path.is_file():
        raise EvaluationError("evaluation directory already exists")
    marker = load_json(marker_path)
    if marker.get("evaluation_status") != "draft_pending_adjudication":
        raise EvaluationError("only a draft evaluation may be finalized")
    if marker.get("inputs", {}).get("predictions") != binding(prediction_path):
        raise EvaluationError("draft evaluation prediction binding is stale")
    for name in OUTPUT_NAMES:
        artifact = path / name
        if artifact.exists():
            artifact.unlink()


def write_outputs(output_dir: Path, artifacts: dict[str, Any], inputs: dict[str, Path]) -> None:
    outputs = {}
    for name, value in artifacts.items():
        path = output_dir / f"{name}.json"
        atomic_write(path, value)
        outputs[name] = binding(path)
    marker = {
        "artifact_type": "canonical_connection_evaluation_complete", "version": "v0.1",
        "evaluation_status": artifacts["metrics"]["evaluation_status"],
        "inputs": {name: binding(path) for name, path in inputs.items()},
        "outputs": outputs,
        "evaluator": {"path": display_path(Path(__file__)), "sha256": sha256_file(Path(__file__)), "version": EVALUATOR_VERSION},
        "gate_outcome": artifacts["metrics"]["gate_assessment"]["outcome"],
    }
    atomic_write(output_dir / "evaluation_complete.json", marker)


def write_invalid(output_dir: Path, *, message: str, inputs: dict[str, Path]) -> None:
    errors_path = output_dir / "errors.json"
    atomic_write(errors_path, [{"error_type": "fatal_integrity_error", "message": message}])
    marker = {
        "artifact_type": "canonical_connection_evaluation_complete",
        "version": "v0.1",
        "evaluation_status": "invalid",
        "inputs": {name: binding(path) for name, path in inputs.items() if path.is_file()},
        "outputs": {"errors": binding(errors_path)},
        "fatal_error_count": 1,
        "evaluator": {"path": display_path(Path(__file__)), "sha256": sha256_file(Path(__file__)), "version": EVALUATOR_VERSION},
    }
    atomic_write(output_dir / "evaluation_complete.json", marker)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--candidate-selection", default=str(DEFAULT_SELECTION))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument("--evidence-catalogs", default=str(DEFAULT_CATALOGS))
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE_MANIFEST))
    parser.add_argument("--success-criteria", default=str(DEFAULT_SUCCESS_CRITERIA))
    parser.add_argument("--evaluation-dir", required=True)
    parser.add_argument("--adjudication")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = resolve_path(args.run_dir)
    prediction_path = run_dir / "output" / "canonical_connection_predictions.json"
    run_metadata_path = run_dir / "metadata" / "run_metadata.json"
    paths = {
        "predictions": prediction_path, "run_metadata": run_metadata_path,
        "candidate_selection": resolve_path(args.candidate_selection),
        "ground_truth": resolve_path(args.ground_truth),
        "evidence_catalogs": resolve_path(args.evidence_catalogs),
        "freeze_manifest": resolve_path(args.freeze_manifest),
        "success_criteria": resolve_path(args.success_criteria),
    }
    evaluation_dir = resolve_path(args.evaluation_dir)
    adjudication_path = resolve_path(args.adjudication) if args.adjudication else None
    output_prepared = False
    try:
        prepare_evaluation_dir(evaluation_dir, adjudication_supplied=adjudication_path is not None, prediction_path=prediction_path)
        output_prepared = True
        predictions = load_json(prediction_path)
        metadata = load_json(run_metadata_path)
        selection = load_json(paths["candidate_selection"])
        ground_truth = load_json(paths["ground_truth"])
        catalogs = load_json(paths["evidence_catalogs"])
        freeze_manifest = load_json(paths["freeze_manifest"])
        success_criteria = load_json(paths["success_criteria"])
        if metadata.get("run_status") != "completed" or metadata.get("execution_scope") != "full_selected_candidate_set":
            raise EvaluationError("run metadata is not a completed full execution")
        if metadata.get("git_dirty_at_start") is not False or metadata.get("git_commit_at_start") != metadata.get("method_commit"):
            raise EvaluationError("run repository state is not a clean method commit")
        if metadata.get("prediction") != binding(prediction_path):
            raise EvaluationError("run metadata prediction binding is stale")
        expected_metadata_inputs = {
            "candidate_selection": binding(paths["candidate_selection"]),
            "evidence_catalogs": binding(paths["evidence_catalogs"]),
            "freeze_manifest": binding(paths["freeze_manifest"]),
        }
        for name, expected in expected_metadata_inputs.items():
            if metadata.get("inputs", {}).get(name) != expected:
                raise EvaluationError(f"run metadata {name} binding is stale")
        if metadata.get("candidate_count") != selection.get("selected_pair_count") or metadata.get("completed_candidate_count") != selection.get("selected_pair_count"):
            raise EvaluationError("run candidate counts are incomplete")
        frozen = freeze_manifest.get("frozen_artifacts", {})
        for name, path in {"ground_truth": paths["ground_truth"], "evidence_catalogs": paths["evidence_catalogs"], "success_criteria": paths["success_criteria"]}.items():
            if frozen.get(name) != binding(path):
                raise EvaluationError(f"frozen {name} binding mismatch")
        catalog_map = {item["canonical_pair_id"]: item for item in catalogs["catalogs"]}
        fatal = validate_prediction_bundle(predictions, selected_pairs=selection["selected_pairs"], catalog_map=catalog_map)
        if fatal:
            raise EvaluationError("; ".join(fatal))
        adjudication = load_json(adjudication_path) if adjudication_path else None
        artifacts = evaluate(
            predictions=predictions, selected_pairs=selection["selected_pairs"],
            ground_truth=ground_truth, catalogs=catalogs,
            success_criteria=success_criteria, adjudication=adjudication,
        )
        if adjudication_path:
            paths["adjudication"] = adjudication_path
        write_outputs(evaluation_dir, artifacts, paths)
    except EvaluationError as exc:
        if output_prepared:
            write_invalid(evaluation_dir, message=str(exc), inputs=paths)
        print(f"Connection evaluation failed: {exc}")
        return 1
    print(f"Connection evaluation status: {artifacts['metrics']['evaluation_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
