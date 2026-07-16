#!/usr/bin/env python3
"""Evaluate Candidate Pair selection and Relation classification end to end."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import finalize_candidate_relation_evaluation as finalizer  # noqa: E402
from scripts import prepare_candidate_relation_diagnostic as preparer  # noqa: E402
from scripts import project_candidate_pairs_to_relations as projector  # noqa: E402
from scripts import run_candidate_relation_diagnostic as diagnostic_runner  # noqa: E402


DEFAULT_CONTRACT = ROOT / "benchmark" / "candidate_relation_downstream_diagnostic_v0_1.json"
DEFAULT_PROJECTION_MARKER = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "candidate_relation_projection_development_v0_1_complete.json"
)
DEFAULT_RUN_ROOT = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "downstream_diagnostic_v0_1"
)
CONDITIONS = ["all_pairs", "rule_filtered_v0_1"]
GRAPH_RELATIONS = set(projector.GRAPH_RELATIONS)
SUPPORTED_EVIDENCE_STATUSES = {
    "auto_supported_by_gold_evidence",
    "supported",
}
UNSUPPORTED_EVIDENCE_STATUSES = {"not_supported"}
OUTPUT_FILENAMES = [
    "pipeline_metrics.json",
    "pipeline_errors.json",
    "pair_transitions.json",
    "summary.md",
]
COMPLETION_FILENAME = "pipeline_evaluation_complete.json"


class PipelineEvaluationError(RuntimeError):
    """A fatal downstream pipeline evaluation integrity error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ConditionBundle:
    condition: str
    directory: Path
    snapshot_path: Path
    snapshot: dict[str, Any]
    preparation: dict[str, Any]
    metrics: dict[str, Any]
    matches: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    predictions: dict[str, Any]
    metadata: dict[str, Any]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen 002B-2 downstream typed-edge diagnostic."
    )
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT.relative_to(ROOT)))
    parser.add_argument(
        "--projection-marker",
        default=str(DEFAULT_PROJECTION_MARKER.relative_to(ROOT)),
    )
    parser.add_argument("--all-pairs-bundle")
    parser.add_argument("--rule-filtered-bundle")
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
        raise PipelineEvaluationError(
            "invalid_pipeline_input",
            f"Unable to read {label} {display_path(path)}: {exc}",
        ) from exc


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def f1_score(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def prepare_output(output_dir: Path) -> None:
    managed = [
        *(output_dir / name for name in OUTPUT_FILENAMES),
        output_dir / COMPLETION_FILENAME,
    ]
    existing = [display_path(path) for path in managed if path.exists()]
    if existing:
        raise PipelineEvaluationError(
            "output_exists",
            f"Pipeline outputs already exist; use a new directory: {existing}",
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def validate_projection(
    *, contract_path: Path, marker_path: Path
) -> tuple[dict[str, Any], dict[str, Path], list[dict[str, Any]], list[dict[str, Any]]]:
    marker, paths = preparer.validate_projection_marker(
        marker_path=marker_path,
        contract_path=contract_path,
    )
    canonical = read_json(paths["relation_ground_truth"], label="Relation projection")
    mapping = read_json(paths["pair_mapping"], label="pair mapping")
    pairs = canonical.get("pairs") if isinstance(canonical, dict) else None
    mappings = mapping.get("mappings") if isinstance(mapping, dict) else None
    if not isinstance(pairs, list) or not isinstance(mappings, list):
        raise PipelineEvaluationError(
            "invalid_projection", "Projection pairs or mappings have invalid shape."
        )
    pair_ids = [item.get("pair_id") for item in pairs if isinstance(item, dict)]
    relation_mapping_ids = [
        item.get("relation_pair_id") for item in mappings if isinstance(item, dict)
    ]
    candidate_mapping_ids = [
        item.get("candidate_pair_id") for item in mappings if isinstance(item, dict)
    ]
    if (
        len(pair_ids) != len(pairs)
        or len(pair_ids) != len(set(pair_ids))
        or pair_ids != relation_mapping_ids
        or len(candidate_mapping_ids) != len(set(candidate_mapping_ids))
    ):
        raise PipelineEvaluationError(
            "invalid_projection", "Projection and mapping pair order differ."
        )
    counts = Counter(item.get("category") for item in pairs)
    if counts != Counter({"positive": 80, "hard_negative": 91, "schema_gap": 5}):
        raise PipelineEvaluationError(
            "denominator_mismatch", "Projected Relation category counts are stale."
        )
    return marker, paths, pairs, mappings


def condition_record(contract: dict[str, Any], condition: str) -> dict[str, Any]:
    for item in contract.get("candidate_conditions", []):
        if isinstance(item, dict) and item.get("condition") == condition:
            return item
    raise PipelineEvaluationError(
        "condition_missing", f"Contract has no Candidate condition {condition}."
    )


def selected_ids_from_contract(
    contract: dict[str, Any],
    *,
    condition: str,
    mapping_by_candidate: dict[str, dict[str, Any]],
) -> list[str]:
    record = condition_record(contract, condition)
    selection_path = projector.validate_binding(
        record.get("selection"), label=f"{condition} selection"
    )
    selection = read_json(selection_path, label=f"{condition} selection")
    selected = selection.get("selected_pairs") if isinstance(selection, dict) else None
    if not isinstance(selected, list):
        raise PipelineEvaluationError(
            "invalid_selection", f"{condition} selected_pairs must be a list."
        )
    candidate_ids = [item.get("pair_id") for item in selected if isinstance(item, dict)]
    if len(candidate_ids) != len(selected) or len(candidate_ids) != len(set(candidate_ids)):
        raise PipelineEvaluationError(
            "invalid_selection", f"{condition} has invalid or duplicate pair IDs."
        )
    relation_ids: list[str] = []
    for candidate_id in candidate_ids:
        mapping = mapping_by_candidate.get(candidate_id)
        if mapping is None:
            raise PipelineEvaluationError(
                "unknown_candidate_pair",
                f"{condition} selected unknown pair {candidate_id}.",
            )
        relation_ids.append(mapping["relation_pair_id"])
    if len(relation_ids) != record.get("expected_selected_pairs"):
        raise PipelineEvaluationError(
            "selected_count_mismatch", f"{condition} selected count differs from contract."
        )
    return relation_ids


def validate_snapshot_artifacts(
    directory: Path, snapshot: dict[str, Any]
) -> dict[str, Path]:
    artifacts = snapshot.get("artifacts")
    required = set(finalizer.COPIED_FILENAMES)
    allowed = required | {finalizer.OPTIONAL_ADJUDICATION_FILENAME}
    if not isinstance(artifacts, dict) or not required <= set(artifacts) <= allowed:
        raise PipelineEvaluationError(
            "invalid_evaluation_snapshot", "Evaluation snapshot artifact set is invalid."
        )
    paths: dict[str, Path] = {}
    for name, expected_hash in artifacts.items():
        path = directory / name
        if not path.is_file() or expected_hash != projector.sha256_file(path):
            raise PipelineEvaluationError(
                "stale_evaluation_snapshot", f"Snapshot has stale artifact {name}."
            )
        paths[name] = path
    return paths


def load_condition_bundle(
    *,
    condition: str,
    directory: Path,
    contract_path: Path,
    contract: dict[str, Any],
    expected_relation_ids: list[str],
) -> ConditionBundle:
    snapshot_path = directory / finalizer.SNAPSHOT_FILENAME
    snapshot = read_json(snapshot_path, label=f"{condition} evaluation snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("artifact_type") != "candidate_relation_evaluation_snapshot"
        or snapshot.get("version") != "v0.1"
        or snapshot.get("evaluation_status") != "final"
        or snapshot.get("condition") != condition
    ):
        raise PipelineEvaluationError(
            "invalid_evaluation_snapshot", f"{condition} snapshot is not final."
        )
    if snapshot.get("contract") != projector.binding(contract_path):
        raise PipelineEvaluationError(
            "stale_evaluation_snapshot", f"{condition} snapshot contract is stale."
        )
    if snapshot.get("implementation") != projector.binding(
        Path(finalizer.__file__).resolve()
    ):
        raise PipelineEvaluationError(
            "stale_evaluation_snapshot", f"{condition} finalizer binding is stale."
        )
    preparation_path = projector.validate_binding(
        snapshot.get("preparation"), label=f"{condition} preparation"
    )
    preparation = diagnostic_runner.validate_preparation(
        prepared_dir=preparation_path.parent,
        contract_path=contract_path,
        condition=condition,
    )
    if preparation_path != preparation["marker_path"]:
        raise PipelineEvaluationError(
            "stale_evaluation_snapshot", f"{condition} preparation path differs."
        )
    prepared_ids = [
        item.get("pair_id")
        for item in preparation["selected_gt"].get("pairs", [])
        if isinstance(item, dict)
    ]
    if prepared_ids != expected_relation_ids:
        raise PipelineEvaluationError(
            "selected_pair_mismatch", f"{condition} preparation differs from selection."
        )

    run_marker_path = projector.validate_binding(
        snapshot.get("run_completion"), label=f"{condition} run completion"
    )
    run_marker = read_json(run_marker_path, label=f"{condition} run completion")
    if (
        run_marker.get("condition") != condition
        or run_marker.get("status") != "completed"
        or run_marker.get("method_commit") != snapshot.get("method_commit")
    ):
        raise PipelineEvaluationError(
            "invalid_run_snapshot", f"{condition} run completion is invalid."
        )
    paths = validate_snapshot_artifacts(directory, snapshot)
    metrics = read_json(paths["metrics.json"], label=f"{condition} metrics")
    matches = read_json(paths["matches.json"], label=f"{condition} matches")
    errors = read_json(paths["errors.json"], label=f"{condition} errors")
    pending = read_json(
        paths["adjudication_pending.json"], label=f"{condition} pending adjudication"
    )
    predictions = read_json(paths["predictions.json"], label=f"{condition} predictions")
    metadata = read_json(paths["run_metadata.json"], label=f"{condition} metadata")
    if not isinstance(metrics, dict) or metrics.get("evaluation_status") != "final":
        raise PipelineEvaluationError(
            "base_evaluation_not_final", f"{condition} base evaluation is not final."
        )
    if not isinstance(matches, list) or not isinstance(errors, list):
        raise PipelineEvaluationError(
            "invalid_base_evaluation", f"{condition} matches/errors are invalid."
        )
    if not isinstance(pending, list) or pending:
        raise PipelineEvaluationError(
            "base_evaluation_not_final", f"{condition} still has pending cases."
        )
    match_ids = [item.get("pair_id") for item in matches if isinstance(item, dict)]
    prediction_ids = [
        item.get("pair_id")
        for item in predictions.get("results", [])
        if isinstance(item, dict)
    ]
    if match_ids != expected_relation_ids or prediction_ids != expected_relation_ids:
        raise PipelineEvaluationError(
            "evaluation_pair_mismatch",
            f"{condition} predictions/matches differ from selected pair order.",
        )
    if metrics.get("total_pairs") != len(expected_relation_ids):
        raise PipelineEvaluationError(
            "denominator_mismatch", f"{condition} total-pair denominator is stale."
        )
    if not isinstance(metadata, dict) or (
        metadata.get("condition") != condition
        or metadata.get("run_status") != "completed"
        or metadata.get("request_success") is not True
        or metadata.get("json_parse_success") is not True
        or metadata.get("prediction_schema_valid") is not True
        or metadata.get("finish_reason") != "stop"
        or metadata.get("git_dirty_at_start") is not False
        or metadata.get("git_commit_at_start") != snapshot.get("method_commit")
    ):
        raise PipelineEvaluationError(
            "invalid_run_snapshot", f"{condition} run metadata is invalid."
        )
    record = condition_record(contract, condition)
    if len(expected_relation_ids) != record["expected_selected_pairs"]:
        raise PipelineEvaluationError(
            "selected_count_mismatch", f"{condition} selected count is stale."
        )
    return ConditionBundle(
        condition=condition,
        directory=directory,
        snapshot_path=snapshot_path,
        snapshot=snapshot,
        preparation=preparation,
        metrics=metrics,
        matches=matches,
        errors=errors,
        predictions=predictions,
        metadata=metadata,
    )


def validate_matched_execution(
    all_pairs: ConditionBundle, rule_filtered: ConditionBundle, contract: dict[str, Any]
) -> None:
    fields = [
        "provider",
        "model_requested",
        "request_parameters",
        "request_partitioning",
        "git_commit_at_start",
    ]
    for field in fields:
        if all_pairs.metadata.get(field) != rule_filtered.metadata.get(field):
            raise PipelineEvaluationError(
                "condition_execution_mismatch", f"Condition metadata differs at {field}."
            )
    hash_fields = [
        "prompt_sha256",
        "relation_schema_sha256",
        "knowledge_object_ground_truth_sha256",
        "lecture_sha256",
    ]
    for field in hash_fields:
        if all_pairs.metadata.get("hashes", {}).get(field) != rule_filtered.metadata.get(
            "hashes", {}
        ).get(field):
            raise PipelineEvaluationError(
                "condition_execution_mismatch", f"Condition hashes differ at {field}."
            )
    execution = contract["execution"]
    if (
        all_pairs.metadata.get("provider") != execution["provider"]
        or all_pairs.metadata.get("model_requested") != execution["model"]
        or all_pairs.metadata.get("request_partitioning")
        != execution["request_partitioning"]
    ):
        raise PipelineEvaluationError(
            "condition_execution_mismatch", "Formal runs differ from frozen execution."
        )
    expected_parameters = {
        "temperature": float(execution["temperature"]),
        "top_p": float(execution["top_p"]),
        "max_tokens": execution["max_tokens"],
        "stream": execution["stream"],
        "response_format": execution["response_format"],
        "thinking": execution["thinking"],
    }
    if all_pairs.metadata.get("request_parameters") != expected_parameters:
        raise PipelineEvaluationError(
            "condition_execution_mismatch", "Formal request parameters are stale."
        )
    preceding = rule_filtered.metadata.get("preceding_all_pairs_metadata")
    # The runner already validates condition order. Here we require a hash-bound
    # preceding metadata artifact and compare it with the frozen All-Pairs copy.
    if not isinstance(preceding, dict) or set(preceding) != {"path", "sha256"}:
        raise PipelineEvaluationError(
            "condition_order_unbound",
            "Rule-Filtered metadata lacks preceding All-Pairs provenance.",
        )
    preceding_path = resolve_path(preceding["path"])
    if (
        not preceding_path.is_file()
        or preceding["sha256"] != projector.sha256_file(preceding_path)
        or preceding["sha256"]
        != all_pairs.snapshot["source"]["run_metadata"]["sha256"]
    ):
        raise PipelineEvaluationError(
            "condition_order_unbound",
            "Rule-Filtered preceding metadata differs from All-Pairs.",
        )


def error_types_by_pair(errors: list[dict[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for item in errors:
        if not isinstance(item, dict):
            continue
        pair_id = item.get("pair_id")
        error_type = item.get("error_type")
        if isinstance(pair_id, str) and isinstance(error_type, str):
            result[pair_id].append(error_type)
    return result


def conditional_relation_metrics(bundle: ConditionBundle) -> dict[str, Any]:
    metrics = bundle.metrics
    matches = [item for item in bundle.matches if item.get("primary_scored") is True]
    evidence_statuses = [
        item.get("evidence_support_status")
        for item in bundle.matches
        if item.get("primary_scored") is True
        and item.get("evidence_support_status")
        in SUPPORTED_EVIDENCE_STATUSES | UNSUPPORTED_EVIDENCE_STATUSES
    ]
    evidence_supported = sum(
        status in SUPPORTED_EVIDENCE_STATUSES for status in evidence_statuses
    )
    return {
        "strict_edge_accuracy": rate(
            int(metrics["strict_edge_correct_count"]),
            int(metrics["primary_scored_pairs"]),
        ),
        "relation_type_accuracy_ignoring_direction": rate(
            int(metrics["relation_type_correct_count"]),
            int(metrics["primary_scored_pairs"]),
        ),
        "positive_relation_accuracy": rate(
            int(metrics["positive_relation_correct_count"]),
            int(metrics["positive_pairs"]),
        ),
        "no_relation_accuracy": rate(
            int(metrics["no_relation_correct_count"]),
            int(metrics["hard_negative_pairs"]),
        ),
        "endpoint_direction_accuracy": rate(
            int(metrics["endpoint_direction_correct_count"]),
            int(metrics["endpoint_direction_scored_count"]),
        ),
        "direction_accuracy_when_type_correct": rate(
            int(metrics["direction_when_type_correct_count"]),
            int(metrics["direction_when_type_correct_scored_count"]),
        ),
        "exact_evidence_span_rate": rate(
            int(metrics["exact_evidence_span_count"]),
            int(metrics["evidence_span_count"]),
        ),
        "semantic_evidence_support_on_accepted_primary_graph_edges": rate(
            evidence_supported, len(evidence_statuses)
        ),
        "evidence_support_breakdown": dict(sorted(Counter(evidence_statuses).items())),
        "manual_adjudication_count": metrics["manual_adjudication_count"],
        "pending_adjudication_count": metrics["pending_adjudication_count"],
        "related_to_prediction_rate": rate(
            sum(
                item.get("predicted_edge", {}).get("relation_type") == "RELATED_TO"
                for item in matches
            ),
            len(matches),
        ),
        "related_to_overuse_count": metrics["related_to_overuse_count"],
    }


def classify_selected_primary(match: dict[str, Any], category: str) -> str:
    if match.get("strict_edge_correct") is True:
        return "strict_success"
    predicted_type = match.get("predicted_edge", {}).get("relation_type")
    if category == "hard_negative":
        if predicted_type in GRAPH_RELATIONS:
            return "false_positive_relation"
        raise PipelineEvaluationError(
            "unclassified_primary_error",
            f"Hard negative {match.get('pair_id')} has an unclassified strict failure.",
        )
    if predicted_type == "NO_RELATION":
        return "classifier_no_relation_false_negative"
    if match.get("relation_type_correct") is False:
        return "wrong_relation_type"
    if match.get("direction_correct") is False:
        return "wrong_direction"
    raise PipelineEvaluationError(
        "unclassified_primary_error",
        f"Positive {match.get('pair_id')} has an unclassified strict failure.",
    )


def score_condition(
    *,
    condition: str,
    canonical_pairs: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    selected_relation_ids: list[str],
    matches: list[dict[str, Any]],
    base_errors: list[dict[str, Any]],
    base_metrics: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    mapping_by_relation = {item["relation_pair_id"]: item for item in mappings}
    selected = set(selected_relation_ids)
    match_by_id = {item["pair_id"]: item for item in matches}
    if len(match_by_id) != len(matches) or set(match_by_id) != selected:
        raise PipelineEvaluationError(
            "evaluation_pair_mismatch", f"{condition} matches differ from selection."
        )
    base_error_types = error_types_by_pair(base_errors)
    counters: Counter[str] = Counter()
    outcomes: list[dict[str, Any]] = []
    pipeline_errors: list[dict[str, Any]] = []

    for pair in canonical_pairs:
        relation_id = pair["pair_id"]
        mapping = mapping_by_relation.get(relation_id)
        if mapping is None:
            raise PipelineEvaluationError(
                "invalid_projection", f"Missing mapping for {relation_id}."
            )
        category = pair["category"]
        is_selected = relation_id in selected
        match = match_by_id.get(relation_id)
        predicted_edge = match.get("predicted_edge") if match else None
        evidence_status = match.get("evidence_support_status") if match else None
        pipeline_correct: bool | None
        failure_locus: str
        outcome: str

        counters["total_pairs"] += 1
        counters[f"category_{category}"] += 1
        counters["selected_pairs"] += int(is_selected)
        counters[f"selected_{category}"] += int(is_selected)
        if category == "schema_gap":
            pipeline_correct = None
            failure_locus = "not_primary_scored"
            outcome = "diagnostic_processed" if is_selected else "diagnostic_not_processed"
            if is_selected and predicted_edge is not None:
                counters[
                    "schema_gap_graph_predictions"
                ] += predicted_edge.get("relation_type") in GRAPH_RELATIONS
        else:
            counters["primary_pairs"] += 1
            if not is_selected:
                if category == "positive":
                    pipeline_correct = False
                    failure_locus = "candidate_induced_false_negative"
                    outcome = "candidate_missed_positive"
                else:
                    pipeline_correct = True
                    failure_locus = "strict_success"
                    outcome = "candidate_rejected_negative"
            else:
                if match is None:
                    raise PipelineEvaluationError(
                        "evaluation_pair_mismatch", f"Selected pair {relation_id} is unevaluated."
                    )
                failure_locus = classify_selected_primary(match, category)
                pipeline_correct = failure_locus == "strict_success"
                outcome = (
                    "correct_relation"
                    if pipeline_correct and category == "positive"
                    else "classifier_rejected_negative"
                    if pipeline_correct
                    else failure_locus
                )
                predicted_type = predicted_edge.get("relation_type")
                counters["graph_predictions_primary"] += int(
                    predicted_type in GRAPH_RELATIONS
                )

            counters["pipeline_strict_correct"] += int(bool(pipeline_correct))
            counters[failure_locus] += 1
            if category == "positive":
                counters["positive_pairs"] += 1
                counters["typed_edge_true_positive"] += int(bool(pipeline_correct))
            else:
                counters["hard_negative_pairs"] += 1

        record = {
            "condition": condition,
            "candidate_pair_id": mapping["candidate_pair_id"],
            "relation_pair_id": relation_id,
            "lecture_id": mapping["lecture_id"],
            "category": category,
            "candidate_label": mapping["candidate_label"],
            "selected": is_selected,
            "candidate_outcome": outcome,
            "pipeline_correct": pipeline_correct,
            "failure_locus": failure_locus,
            "gold_edge": {
                "source": pair["source"],
                "target": pair["target"],
                "relation_type": pair["relation_type"],
            },
            "predicted_edge": predicted_edge,
            "evidence_support_status": evidence_status,
            "base_error_types": base_error_types.get(relation_id, []),
        }
        outcomes.append(record)
        if failure_locus not in {"strict_success", "not_primary_scored"}:
            pipeline_errors.append(record)
        if evidence_status == "not_supported":
            pipeline_errors.append({
                **record,
                "failure_locus": "evidence_not_supported",
                "pipeline_correct": pipeline_correct,
            })

    expected_counts = Counter(item["category"] for item in canonical_pairs)
    if (
        counters["primary_pairs"] != 171
        or counters["positive_pairs"] != 80
        or counters["hard_negative_pairs"] != 91
        or expected_counts["schema_gap"] != 5
    ):
        raise PipelineEvaluationError(
            "denominator_mismatch", f"{condition} pipeline denominators are stale."
        )
    precision_metric = rate(
        counters["typed_edge_true_positive"], counters["graph_predictions_primary"]
    )
    recall_metric = rate(counters["typed_edge_true_positive"], 80)
    usage = metadata.get("usage")
    if not isinstance(usage, dict) or usage.get("request_count") != len(selected):
        raise PipelineEvaluationError(
            "workload_mismatch", f"{condition} API usage does not match selected pairs."
        )
    selected_primary = counters["selected_positive"] + counters["selected_hard_negative"]
    metrics = {
        "candidate": {
            "selected_pair_count": counters["selected_pairs"],
            "selected_primary_pairs": selected_primary,
            "selected_positive_pairs": counters["selected_positive"],
            "selected_hard_negative_pairs": counters["selected_hard_negative"],
            "selected_schema_gap_pairs": counters["selected_schema_gap"],
            "positive_recall": rate(counters["selected_positive"], 80),
            "primary_precision": rate(counters["selected_positive"], selected_primary),
            "total_workload_retention": rate(counters["selected_pairs"], 176),
            "total_workload_reduction": rate(176 - counters["selected_pairs"], 176),
        },
        "conditional_relation": {
            "strict_edge_accuracy": rate(
                int(base_metrics["strict_edge_correct_count"]),
                int(base_metrics["primary_scored_pairs"]),
            ),
            "relation_type_accuracy_ignoring_direction": rate(
                int(base_metrics["relation_type_correct_count"]),
                int(base_metrics["primary_scored_pairs"]),
            ),
            "positive_relation_accuracy": rate(
                int(base_metrics["positive_relation_correct_count"]),
                int(base_metrics["positive_pairs"]),
            ),
            "no_relation_accuracy": rate(
                int(base_metrics["no_relation_correct_count"]),
                int(base_metrics["hard_negative_pairs"]),
            ),
            "endpoint_direction_accuracy": rate(
                int(base_metrics["endpoint_direction_correct_count"]),
                int(base_metrics["endpoint_direction_scored_count"]),
            ),
            "direction_accuracy_when_type_correct": rate(
                int(base_metrics["direction_when_type_correct_count"]),
                int(base_metrics["direction_when_type_correct_scored_count"]),
            ),
        },
        "pipeline": {
            "strict_accuracy": rate(counters["pipeline_strict_correct"], 171),
            "positive_typed_edge_precision": precision_metric,
            "positive_typed_edge_recall": recall_metric,
            "positive_typed_edge_f1": f1_score(
                precision_metric["value"], recall_metric["value"]
            ),
            "candidate_induced_false_negatives": counters[
                "candidate_induced_false_negative"
            ],
            "classifier_no_relation_false_negatives": counters[
                "classifier_no_relation_false_negative"
            ],
            "wrong_relation_type": counters["wrong_relation_type"],
            "wrong_direction_when_type_correct": counters["wrong_direction"],
            "false_positive_relations": counters["false_positive_relation"],
            "hard_negative_strict_success": rate(
                sum(
                    item["pipeline_correct"] is True
                    for item in outcomes
                    if item["category"] == "hard_negative"
                ),
                91,
            ),
            "positive_strict_success": rate(
                counters["typed_edge_true_positive"], 80
            ),
        },
        "workload": {
            "pair_workload": counters["selected_pairs"],
            "api_request_count": usage["request_count"],
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
            "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
            "latency_ms": metadata.get("latency_ms"),
        },
        "evidence": {
            "exact_span_rate": rate(
                int(base_metrics["exact_evidence_span_count"]),
                int(base_metrics["evidence_span_count"]),
            ),
            "semantic_support_on_accepted_primary_graph_edges": (
                conditional_relation_metrics_from(matches)
            ),
            "manual_adjudication_count": base_metrics["manual_adjudication_count"],
            "pending_adjudication_count": base_metrics["pending_adjudication_count"],
        },
        "diagnostics": {
            "schema_gap_pairs": 5,
            "selected_schema_gap_pairs": counters["selected_schema_gap"],
            "schema_gap_graph_predictions": counters["schema_gap_graph_predictions"],
        },
    }
    return metrics, outcomes, pipeline_errors


def conditional_relation_metrics_from(matches: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [
        item.get("evidence_support_status")
        for item in matches
        if item.get("primary_scored", True) is True
        and item.get("evidence_support_status")
        in SUPPORTED_EVIDENCE_STATUSES | UNSUPPORTED_EVIDENCE_STATUSES
    ]
    supported = sum(status in SUPPORTED_EVIDENCE_STATUSES for status in statuses)
    return {
        **rate(supported, len(statuses)),
        "breakdown": dict(sorted(Counter(statuses).items())),
    }


def build_transitions(
    *,
    canonical_pairs: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    outcomes: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    pair_by_relation = {item["pair_id"]: item for item in canonical_pairs}
    mapping_by_relation = {item["relation_pair_id"]: item for item in mappings}
    outcome_maps = {
        condition: {item["relation_pair_id"]: item for item in items}
        for condition, items in outcomes.items()
    }
    transitions: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    shared_prediction_disagreements = 0
    for relation_id in [item["pair_id"] for item in canonical_pairs]:
        pair = pair_by_relation[relation_id]
        mapping = mapping_by_relation[relation_id]
        all_item = outcome_maps["all_pairs"][relation_id]
        filtered_item = outcome_maps["rule_filtered_v0_1"][relation_id]
        if pair["category"] == "schema_gap":
            transition = "diagnostic_excluded_from_primary"
        elif not filtered_item["selected"]:
            if pair["category"] == "positive":
                transition = (
                    "filtered_missed_positive_all_pairs_correct"
                    if all_item["pipeline_correct"] is True
                    else "filtered_missed_positive_all_pairs_incorrect"
                )
            else:
                transition = "filtered_rejected_negative"
        else:
            left = "correct" if all_item["pipeline_correct"] else "incorrect"
            right = "correct" if filtered_item["pipeline_correct"] else "incorrect"
            transition = f"shared_{left}_to_{right}"
            shared_prediction_disagreements += int(
                all_item["predicted_edge"] != filtered_item["predicted_edge"]
            )
        counts[transition] += 1
        transitions.append({
            "candidate_pair_id": mapping["candidate_pair_id"],
            "relation_pair_id": relation_id,
            "lecture_id": mapping["lecture_id"],
            "category": pair["category"],
            "transition": transition,
            "all_pairs": {
                "selected": all_item["selected"],
                "pipeline_correct": all_item["pipeline_correct"],
                "failure_locus": all_item["failure_locus"],
                "predicted_edge": all_item["predicted_edge"],
            },
            "rule_filtered_v0_1": {
                "selected": filtered_item["selected"],
                "pipeline_correct": filtered_item["pipeline_correct"],
                "failure_locus": filtered_item["failure_locus"],
                "predicted_edge": filtered_item["predicted_edge"],
            },
        })
    summary = {
        "transition_counts": dict(sorted(counts.items())),
        "filtered_missed_positive_count": (
            counts["filtered_missed_positive_all_pairs_correct"]
            + counts["filtered_missed_positive_all_pairs_incorrect"]
        ),
        "filtered_missed_positive_all_pairs_strict_correct": counts[
            "filtered_missed_positive_all_pairs_correct"
        ],
        "filtered_missed_positive_all_pairs_strict_incorrect": counts[
            "filtered_missed_positive_all_pairs_incorrect"
        ],
        "shared_selected_prediction_disagreement_count": shared_prediction_disagreements,
    }
    return {
        "artifact_type": "candidate_relation_pair_transitions",
        "version": "v0.1",
        "pair_count": len(transitions),
        "summary": summary,
        "transitions": transitions,
    }, summary


def metric_delta(right: dict[str, Any], left: dict[str, Any]) -> float | None:
    right_value = right.get("value")
    left_value = left.get("value")
    if right_value is None or left_value is None:
        return None
    return right_value - left_value


def summary_markdown(metrics: dict[str, Any]) -> str:
    all_metrics = metrics["conditions"]["all_pairs"]
    filtered = metrics["conditions"]["rule_filtered_v0_1"]

    def show(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.4f}"

    rows = [
        ("Candidate selected", all_metrics["candidate"]["selected_pair_count"], filtered["candidate"]["selected_pair_count"]),
        ("Candidate positive recall", show(all_metrics["candidate"]["positive_recall"]["value"]), show(filtered["candidate"]["positive_recall"]["value"])),
        ("Conditional Relation strict", show(all_metrics["conditional_relation"]["strict_edge_accuracy"]["value"]), show(filtered["conditional_relation"]["strict_edge_accuracy"]["value"])),
        ("End-to-end strict /171", show(all_metrics["pipeline"]["strict_accuracy"]["value"]), show(filtered["pipeline"]["strict_accuracy"]["value"])),
        ("Positive typed-edge recall /80", show(all_metrics["pipeline"]["positive_typed_edge_recall"]["value"]), show(filtered["pipeline"]["positive_typed_edge_recall"]["value"])),
        ("Positive typed-edge precision", show(all_metrics["pipeline"]["positive_typed_edge_precision"]["value"]), show(filtered["pipeline"]["positive_typed_edge_precision"]["value"])),
        ("Candidate-induced FN", all_metrics["pipeline"]["candidate_induced_false_negatives"], filtered["pipeline"]["candidate_induced_false_negatives"]),
        ("Classifier NO_RELATION FN", all_metrics["pipeline"]["classifier_no_relation_false_negatives"], filtered["pipeline"]["classifier_no_relation_false_negatives"]),
        ("Wrong Relation type", all_metrics["pipeline"]["wrong_relation_type"], filtered["pipeline"]["wrong_relation_type"]),
        ("Wrong direction", all_metrics["pipeline"]["wrong_direction_when_type_correct"], filtered["pipeline"]["wrong_direction_when_type_correct"]),
        ("False-positive Relations", all_metrics["pipeline"]["false_positive_relations"], filtered["pipeline"]["false_positive_relations"]),
        ("Exact Evidence span", show(all_metrics["evidence"]["exact_span_rate"]["value"]), show(filtered["evidence"]["exact_span_rate"]["value"])),
        ("API requests", all_metrics["workload"]["api_request_count"], filtered["workload"]["api_request_count"]),
    ]
    table = "\n".join(
        f"| {label} | {left} | {right} |" for label, left, right in rows
    )
    comparison = metrics["comparison"]
    return f"""# 002B-2 Downstream Typed-Edge Diagnostic

**Status:** Final
**Scope:** Inspected development diagnostic, not unseen holdout evidence

| Metric | All-Pairs v0.1 | Rule-Filtered v0.1 |
| --- | ---: | ---: |
{table}

## Interpretation

- Rule-Filtered v0.1 remains failed at the frozen Candidate recall gate.
- It omitted 10 primary positive pairs; the frozen All-Pairs classifier was strictly
  correct on {comparison['missed_positives_all_pairs_strict_correct']} of those omitted pairs.
- Downstream results diagnose the observed loss under the frozen classifier; they do
  not make omitted candidates recoverable and cannot reverse the Candidate gate.
- All-Pairs v0.1 remains the current lecture-local safety fallback, while its quadratic
  workload and false-positive exposure remain material limitations.
"""


def evaluate_pipeline(
    *,
    contract_path: Path,
    projection_marker_path: Path,
    bundle_dirs: dict[str, Path],
    output_dir: Path,
) -> dict[str, Any]:
    prepare_output(output_dir)
    contract = projector.read_json(contract_path, label="diagnostic contract")
    projector.validate_contract(contract)
    _, _, canonical_pairs, mappings = validate_projection(
        contract_path=contract_path, marker_path=projection_marker_path
    )
    mapping_by_candidate = {item["candidate_pair_id"]: item for item in mappings}
    selected_ids = {
        condition: selected_ids_from_contract(
            contract,
            condition=condition,
            mapping_by_candidate=mapping_by_candidate,
        )
        for condition in CONDITIONS
    }
    if selected_ids["all_pairs"] != [item["pair_id"] for item in canonical_pairs]:
        raise PipelineEvaluationError(
            "all_pairs_not_exhaustive", "All-Pairs does not preserve the full universe."
        )
    bundles = {
        condition: load_condition_bundle(
            condition=condition,
            directory=bundle_dirs[condition],
            contract_path=contract_path,
            contract=contract,
            expected_relation_ids=selected_ids[condition],
        )
        for condition in CONDITIONS
    }
    validate_matched_execution(
        bundles["all_pairs"], bundles["rule_filtered_v0_1"], contract
    )
    condition_metrics: dict[str, Any] = {}
    condition_outcomes: dict[str, list[dict[str, Any]]] = {}
    all_errors: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        bundle = bundles[condition]
        metrics, outcomes, errors = score_condition(
            condition=condition,
            canonical_pairs=canonical_pairs,
            mappings=mappings,
            selected_relation_ids=selected_ids[condition],
            matches=bundle.matches,
            base_errors=bundle.errors,
            base_metrics=bundle.metrics,
            metadata=bundle.metadata,
        )
        evidence = conditional_relation_metrics(bundle)
        metrics["conditional_relation"].update({
            "exact_evidence_span_rate": evidence["exact_evidence_span_rate"],
            "semantic_evidence_support_on_accepted_primary_graph_edges": evidence[
                "semantic_evidence_support_on_accepted_primary_graph_edges"
            ],
            "evidence_support_breakdown": evidence["evidence_support_breakdown"],
            "manual_adjudication_count": evidence["manual_adjudication_count"],
            "pending_adjudication_count": evidence["pending_adjudication_count"],
            "related_to_prediction_rate": evidence["related_to_prediction_rate"],
            "related_to_overuse_count": evidence["related_to_overuse_count"],
        })
        condition_metrics[condition] = metrics
        condition_outcomes[condition] = outcomes
        all_errors.extend(errors)

    transitions, transition_summary = build_transitions(
        canonical_pairs=canonical_pairs,
        mappings=mappings,
        outcomes=condition_outcomes,
    )
    all_pipeline = condition_metrics["all_pairs"]["pipeline"]
    filtered_pipeline = condition_metrics["rule_filtered_v0_1"]["pipeline"]
    all_workload = condition_metrics["all_pairs"]["workload"]
    filtered_workload = condition_metrics["rule_filtered_v0_1"]["workload"]
    comparison = {
        "candidate_gate_outcome": "failed_frozen_recall_gate",
        "candidate_gate_overridden": False,
        "selected_safe_fallback": "all_pairs_v0_1",
        "pair_workload_reduction": rate(
            all_workload["pair_workload"] - filtered_workload["pair_workload"],
            all_workload["pair_workload"],
        ),
        "api_request_reduction": rate(
            all_workload["api_request_count"] - filtered_workload["api_request_count"],
            all_workload["api_request_count"],
        ),
        "pipeline_strict_accuracy_delta_filtered_minus_all_pairs": metric_delta(
            filtered_pipeline["strict_accuracy"], all_pipeline["strict_accuracy"]
        ),
        "positive_typed_edge_precision_delta_filtered_minus_all_pairs": metric_delta(
            filtered_pipeline["positive_typed_edge_precision"],
            all_pipeline["positive_typed_edge_precision"],
        ),
        "positive_typed_edge_recall_delta_filtered_minus_all_pairs": metric_delta(
            filtered_pipeline["positive_typed_edge_recall"],
            all_pipeline["positive_typed_edge_recall"],
        ),
        "missed_positive_pairs": transition_summary["filtered_missed_positive_count"],
        "missed_positives_all_pairs_strict_correct": transition_summary[
            "filtered_missed_positive_all_pairs_strict_correct"
        ],
        "missed_positives_all_pairs_strict_incorrect": transition_summary[
            "filtered_missed_positive_all_pairs_strict_incorrect"
        ],
        "shared_selected_prediction_disagreement_count": transition_summary[
            "shared_selected_prediction_disagreement_count"
        ],
    }
    pipeline_metrics = {
        "artifact_type": "candidate_relation_pipeline_metrics",
        "version": "v0.1",
        "evaluation_status": "final",
        "experiment": "002B-2_downstream_typed_edge_diagnostic",
        "split_role": "development_diagnostic",
        "denominators": contract["denominators"],
        "method_commit": bundles["all_pairs"].metadata["git_commit_at_start"],
        "conditions": condition_metrics,
        "comparison": comparison,
        "interpretation_boundary": {
            "downstream_results_may_override_candidate_gate": False,
            "fresh_holdout_claim": False,
            "production_readiness_established": False,
        },
    }
    error_artifact = {
        "artifact_type": "candidate_relation_pipeline_errors",
        "version": "v0.1",
        "error_count": len(all_errors),
        "errors": all_errors,
    }
    metrics_path = output_dir / "pipeline_metrics.json"
    errors_path = output_dir / "pipeline_errors.json"
    transitions_path = output_dir / "pair_transitions.json"
    summary_path = output_dir / "summary.md"
    projector.atomic_write(metrics_path, pipeline_metrics)
    projector.atomic_write(errors_path, error_artifact)
    projector.atomic_write(transitions_path, transitions)
    atomic_write_text(summary_path, summary_markdown(pipeline_metrics))
    completion = {
        "artifact_type": "candidate_relation_pipeline_evaluation_complete",
        "version": "v0.1",
        "evaluation_status": "final",
        "method_commit": pipeline_metrics["method_commit"],
        "contract": projector.binding(contract_path),
        "projection_completion": projector.binding(projection_marker_path),
        "implementation": projector.binding(Path(__file__).resolve()),
        "evaluation_snapshots": {
            condition: projector.binding(bundles[condition].snapshot_path)
            for condition in CONDITIONS
        },
        "artifacts": {
            name: projector.binding(output_dir / name)
            for name in OUTPUT_FILENAMES
        },
        "integrity": {
            "primary_denominator": 171,
            "diagnostic_denominator": 5,
            "all_pairs_selected": 176,
            "rule_filtered_selected": 127,
            "rule_filtered_candidate_misses": 10,
            "pending_adjudications": 0,
            "candidate_gate_overridden": False,
        },
    }
    projector.atomic_write(output_dir / COMPLETION_FILENAME, completion)
    return completion


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bundle_dirs = {
        "all_pairs": resolve_path(args.all_pairs_bundle)
        if args.all_pairs_bundle
        else DEFAULT_RUN_ROOT / "formal" / "all_pairs" / "run_01" / "relation_evaluation",
        "rule_filtered_v0_1": resolve_path(args.rule_filtered_bundle)
        if args.rule_filtered_bundle
        else DEFAULT_RUN_ROOT
        / "formal"
        / "rule_filtered_v0_1"
        / "run_01"
        / "relation_evaluation",
    }
    output_dir = (
        resolve_path(args.output_dir)
        if args.output_dir
        else DEFAULT_RUN_ROOT / "pipeline_evaluation" / "run_01"
    )
    try:
        completion = evaluate_pipeline(
            contract_path=resolve_path(args.contract),
            projection_marker_path=resolve_path(args.projection_marker),
            bundle_dirs=bundle_dirs,
            output_dir=output_dir,
        )
    except (
        PipelineEvaluationError,
        finalizer.EvaluationFinalizationError,
        diagnostic_runner.DiagnosticRunError,
        preparer.PreparationError,
        projector.ProjectionError,
        RuntimeError,
    ) as exc:
        code = getattr(exc, "code", "pipeline_evaluation_failed")
        print(f"Candidate Relation pipeline evaluation failed [{code}]: {exc}", file=sys.stderr)
        return 1
    print(
        "Completed Candidate-to-Relation pipeline evaluation: "
        f"{completion['integrity']['primary_denominator']} primary pairs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
