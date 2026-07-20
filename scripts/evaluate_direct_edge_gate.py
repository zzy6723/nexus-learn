#!/usr/bin/env python3
"""Evaluate Stage-A direct-edge gate predictions for Experiment 003-2b."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import evaluate_connection_discovery as connection_eval
from scripts import run_connection_discovery as base


ROOT = base.ROOT
BENCHMARK_ROOT = ROOT / "benchmark" / "connection_discovery" / "development_v0_1"
DEFAULT_GROUND_TRUTH = BENCHMARK_ROOT / "ground_truth.json"
EVALUATOR_VERSION = "direct_edge_gate_evaluator_v0.1"
RESULT_KEYS = {
    "canonical_pair_id",
    "ko_a_id",
    "ko_b_id",
    "decision",
    "evidence_ids",
    "rationale",
}
DECISIONS = {"DIRECT_CONNECTION", "NO_RELATION"}
ADJUDICATION_DECISIONS = {"supported", "not_supported"}
OUTPUT_NAMES = {
    "metrics.json",
    "matches.json",
    "errors.json",
    "adjudication_pending.json",
    "evaluation_complete.json",
}


class DirectGateEvaluationError(ValueError):
    """Raised when Stage-A artifacts cannot be evaluated safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--candidate-selection", default=str(base.DEFAULT_SELECTION))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument("--evidence-catalogs", default=str(base.DEFAULT_CATALOGS))
    parser.add_argument("--evaluation-dir", required=True)
    parser.add_argument("--adjudication")
    return parser.parse_args(argv)


def validate_predictions(
    predictions: dict[str, Any],
    selected_pairs: list[dict[str, Any]],
    catalog_map: dict[str, dict[str, Any]],
) -> None:
    if set(predictions) != {"artifact_type", "version", "results"}:
        raise DirectGateEvaluationError("prediction bundle field set is invalid")
    if predictions["artifact_type"] != "canonical_direct_edge_gate_predictions" or predictions["version"] != "v0.1":
        raise DirectGateEvaluationError("prediction bundle identity is invalid")
    results = predictions["results"]
    if not isinstance(results, list):
        raise DirectGateEvaluationError("prediction results must be a list")
    selected_map = {item["canonical_pair_id"]: item for item in selected_pairs}
    ids: list[str] = []
    for index, result in enumerate(results):
        if not isinstance(result, dict) or set(result) != RESULT_KEYS:
            raise DirectGateEvaluationError(f"result {index} field set is invalid")
        pair_id = result["canonical_pair_id"]
        if pair_id not in selected_map:
            raise DirectGateEvaluationError(f"result {index} has unknown pair ID")
        expected = [
            selected_map[pair_id]["ko_a"]["canonical_ko_id"],
            selected_map[pair_id]["ko_b"]["canonical_ko_id"],
        ]
        if [result["ko_a_id"], result["ko_b_id"]] != expected:
            raise DirectGateEvaluationError(f"{pair_id}: endpoints changed or reordered")
        if result["decision"] not in DECISIONS:
            raise DirectGateEvaluationError(f"{pair_id}: invalid gate decision")
        evidence_ids = result["evidence_ids"]
        if not isinstance(evidence_ids, list) or any(not isinstance(value, str) for value in evidence_ids):
            raise DirectGateEvaluationError(f"{pair_id}: invalid Evidence-ID list")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise DirectGateEvaluationError(f"{pair_id}: duplicate Evidence IDs")
        allowed = {item["evidence_id"] for item in catalog_map[pair_id]["evidence_items"]}
        if set(evidence_ids) - allowed:
            raise DirectGateEvaluationError(f"{pair_id}: unknown Evidence ID")
        if result["decision"] == "DIRECT_CONNECTION" and not evidence_ids:
            raise DirectGateEvaluationError(f"{pair_id}: positive gate has no Evidence")
        if result["decision"] == "NO_RELATION" and evidence_ids:
            raise DirectGateEvaluationError(f"{pair_id}: negative gate includes Evidence")
        if not isinstance(result["rationale"], str) or not result["rationale"].strip():
            raise DirectGateEvaluationError(f"{pair_id}: rationale is empty")
        ids.append(pair_id)
    if len(ids) != len(set(ids)) or set(ids) != set(selected_map):
        raise DirectGateEvaluationError("prediction pair set differs from selection")


def pending_artifact(predictions: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_type": "direct_edge_evidence_adjudication_pending",
        "version": "v0.1",
        "prediction_content_sha256": base.sha256_json(predictions),
        "pending_snapshot_sha256": base.sha256_json(items),
        "pending_count": len(items),
        "items": items,
    }


def load_adjudication(
    adjudication: dict[str, Any] | None,
    pending: dict[str, Any],
) -> dict[str, str]:
    if not pending["items"]:
        if adjudication is not None:
            raise DirectGateEvaluationError("adjudication supplied with no pending items")
        return {}
    if adjudication is None:
        return {}
    expected = {
        "artifact_type",
        "version",
        "prediction_content_sha256",
        "pending_snapshot_sha256",
        "decisions",
    }
    if set(adjudication) != expected:
        raise DirectGateEvaluationError("adjudication field set is invalid")
    if adjudication["artifact_type"] != "direct_edge_evidence_adjudication" or adjudication["version"] != "v0.1":
        raise DirectGateEvaluationError("adjudication identity is invalid")
    for key in ("prediction_content_sha256", "pending_snapshot_sha256"):
        if adjudication[key] != pending[key]:
            raise DirectGateEvaluationError(f"stale adjudication {key}")
    pending_ids = {item["canonical_pair_id"] for item in pending["items"]}
    decisions: dict[str, str] = {}
    for item in adjudication["decisions"]:
        if set(item) != {"canonical_pair_id", "decision", "rationale"}:
            raise DirectGateEvaluationError("adjudication decision field set is invalid")
        pair_id = item["canonical_pair_id"]
        if pair_id not in pending_ids or pair_id in decisions:
            raise DirectGateEvaluationError("adjudication pair set is invalid")
        if item["decision"] not in ADJUDICATION_DECISIONS:
            raise DirectGateEvaluationError("adjudication decision is invalid")
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise DirectGateEvaluationError("adjudication rationale is empty")
        decisions[pair_id] = item["decision"]
    if set(decisions) != pending_ids:
        raise DirectGateEvaluationError("adjudication does not cover pending items")
    return decisions


def evaluate(
    predictions: dict[str, Any],
    selection: dict[str, Any],
    ground_truth: dict[str, Any],
    catalogs: dict[str, Any],
    adjudication: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = selection["selected_pairs"]
    catalog_map = {item["canonical_pair_id"]: item for item in catalogs["catalogs"]}
    validate_predictions(predictions, selected, catalog_map)
    truth_map = {item["canonical_pair_id"]: item for item in ground_truth["pairs"]}
    prediction_map = {item["canonical_pair_id"]: item for item in predictions["results"]}
    pending_items: list[dict[str, Any]] = []
    evidence_status: dict[str, str] = {}
    for pair in selected:
        pair_id = pair["canonical_pair_id"]
        prediction = prediction_map[pair_id]
        if prediction["decision"] != "DIRECT_CONNECTION":
            continue
        truth = truth_map[pair_id]
        gold_ids = {item["evidence_id"] for item in truth.get("evidence", [])}
        if (
            truth.get("primary_scoring_eligible") is True
            and truth.get("category") == "IN_SCHEMA_CONNECTION"
            and set(prediction["evidence_ids"]) == gold_ids
        ):
            evidence_status[pair_id] = "auto_supported_exact_gold"
            continue
        evidence_map = {
            item["evidence_id"]: item for item in catalog_map[pair_id]["evidence_items"]
        }
        pending_items.append({
            "canonical_pair_id": pair_id,
            "endpoints": {
                "ko_a": pair["ko_a"],
                "ko_b": pair["ko_b"],
            },
            "evidence_ids": prediction["evidence_ids"],
            "materialized_evidence": [evidence_map[value] for value in prediction["evidence_ids"]],
            "rationale": prediction["rationale"],
            "prediction_snapshot_sha256": base.sha256_json(prediction),
        })
    pending = pending_artifact(predictions, pending_items)
    decisions = load_adjudication(adjudication, pending)
    for pair_id, decision in decisions.items():
        evidence_status[pair_id] = decision

    tp = tn = fp = fn = 0
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for pair in selected:
        pair_id = pair["canonical_pair_id"]
        truth = truth_map[pair_id]
        prediction = prediction_map[pair_id]
        eligible = truth.get("primary_scoring_eligible") is True
        gold_positive = truth.get("category") == "IN_SCHEMA_CONNECTION"
        predicted_positive = prediction["decision"] == "DIRECT_CONNECTION"
        if eligible:
            if gold_positive and predicted_positive:
                tp += 1
            elif gold_positive:
                fn += 1
                errors.append({"error_type": "gate_false_negative", "canonical_pair_id": pair_id})
            elif predicted_positive:
                fp += 1
                errors.append({"error_type": "gate_false_positive", "canonical_pair_id": pair_id})
            else:
                tn += 1
        status = evidence_status.get(pair_id)
        if status == "not_supported":
            errors.append({"error_type": "gate_evidence_not_supported", "canonical_pair_id": pair_id})
        matches.append({
            "canonical_pair_id": pair_id,
            "primary_scoring_eligible": eligible,
            "gold_category": truth.get("category"),
            "prediction": prediction,
            "gate_correct": (gold_positive == predicted_positive) if eligible else None,
            "evidence_semantic_status": status,
        })
    evidence_positive_count = sum(
        item["decision"] == "DIRECT_CONNECTION" for item in predictions["results"]
    )
    supported_count = sum(
        value in {"supported", "auto_supported_exact_gold"}
        for value in evidence_status.values()
    )
    pending_count = len(pending_items) if adjudication is None else 0
    status = "draft_pending_adjudication" if pending_count else "final"
    precision = connection_eval.safe_ratio(tp, tp + fp)
    recall = connection_eval.safe_ratio(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    negative_accuracy = connection_eval.safe_ratio(tn, tn + fp)
    evidence_rate = (
        None if pending_count else connection_eval.safe_ratio(supported_count, evidence_positive_count)
    )
    checks = {
        "direct_edge_recall": {"value": recall, "operator": ">=", "threshold": 0.80, "passed": recall is not None and recall >= 0.80},
        "direct_edge_precision": {"value": precision, "operator": ">=", "threshold": 0.70, "passed": precision is not None and precision >= 0.70},
        "primary_negative_accuracy": {"value": negative_accuracy, "operator": ">=", "threshold": 0.80, "passed": negative_accuracy is not None and negative_accuracy >= 0.80},
        "semantic_evidence_support_rate": {"value": evidence_rate, "operator": ">=", "threshold": 0.90, "passed": evidence_rate is not None and evidence_rate >= 0.90},
        "fatal_alignment_errors": {"value": 0, "operator": "<=", "threshold": 0, "passed": True},
    }
    metrics = {
        "artifact_type": "direct_edge_gate_metrics",
        "version": "v0.1",
        "evaluation_status": status,
        "counts": {
            "primary_positive_pairs": tp + fn,
            "primary_negative_pairs": tn + fp,
            "true_positive_gates": tp,
            "true_negative_gates": tn,
            "false_positive_gates": fp,
            "false_negative_gates": fn,
            "predicted_positive_gates": evidence_positive_count,
            "evidence_auto_supported": sum(value == "auto_supported_exact_gold" for value in evidence_status.values()),
            "evidence_supported_by_adjudication": sum(value == "supported" for value in evidence_status.values()),
            "evidence_not_supported": sum(value == "not_supported" for value in evidence_status.values()),
            "evidence_pending": pending_count,
        },
        "metrics": {
            "direct_edge_precision": precision,
            "direct_edge_recall": recall,
            "direct_edge_f1": f1,
            "primary_negative_accuracy": negative_accuracy,
            "semantic_evidence_support_rate": evidence_rate,
        },
        "diagnostic_gate_assessment": {
            "outcome": "pending_adjudication" if pending_count else "passed" if all(item["passed"] for item in checks.values()) else "failed",
            "checks": checks,
            "authority": "Diagnostic only; combined output remains subject to the original frozen 003-2 gates.",
        },
    }
    complete = {
        "artifact_type": "direct_edge_gate_evaluation_complete",
        "version": "v0.1",
        "status": status,
        "evaluator": {"path": base.display_path(Path(__file__)), "sha256": base.sha256_file(Path(__file__)), "version": EVALUATOR_VERSION},
        "prediction_content_sha256": base.sha256_json(predictions),
        "pending_count": pending_count,
    }
    return {
        "metrics.json": metrics,
        "matches.json": matches,
        "errors.json": errors,
        "adjudication_pending.json": pending,
        "evaluation_complete.json": complete,
    }


def prepare_output_dir(path: Path, adjudication_supplied: bool, prediction_hash: str) -> None:
    if not path.exists():
        path.mkdir(parents=True)
        return
    if not adjudication_supplied:
        raise DirectGateEvaluationError("evaluation directory already exists")
    metrics_path = path / "metrics.json"
    complete_path = path / "evaluation_complete.json"
    if not metrics_path.exists() or not complete_path.exists():
        raise DirectGateEvaluationError("existing evaluation is incomplete")
    metrics = base.load_json(metrics_path)
    complete = base.load_json(complete_path)
    if metrics.get("evaluation_status") != "draft_pending_adjudication":
        raise DirectGateEvaluationError("only a draft evaluation may be finalized")
    if complete.get("prediction_content_sha256") != prediction_hash:
        raise DirectGateEvaluationError("existing evaluation is bound to another prediction")
    for name in OUTPUT_NAMES:
        target = path / name
        if target.exists():
            target.unlink()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = base.resolve_path(args.run_dir)
    evaluation_dir = base.resolve_path(args.evaluation_dir)
    prediction_path = run_dir / "stage_a" / "output" / "direct_gate_predictions.json"
    try:
        metadata = base.load_json(run_dir / "metadata" / "run_metadata.json")
        if metadata.get("run_status") not in {"completed", "completed_subset"}:
            raise DirectGateEvaluationError("two-stage run is not complete")
        predictions = base.load_json(prediction_path)
        selection = base.load_json(base.resolve_path(args.candidate_selection))
        ground_truth = base.load_json(base.resolve_path(args.ground_truth))
        catalogs = base.load_json(base.resolve_path(args.evidence_catalogs))
        adjudication = base.load_json(base.resolve_path(args.adjudication)) if args.adjudication else None
        prepare_output_dir(evaluation_dir, adjudication is not None, base.sha256_json(predictions))
        artifacts = evaluate(predictions, selection, ground_truth, catalogs, adjudication)
        for name, value in artifacts.items():
            connection_eval.atomic_write(evaluation_dir / name, value)
    except (DirectGateEvaluationError, base.ConnectionRunError, OSError, json.JSONDecodeError) as exc:
        if evaluation_dir.exists():
            for name in OUTPUT_NAMES:
                target = evaluation_dir / name
                if target.exists():
                    target.unlink()
            connection_eval.atomic_write(evaluation_dir / "errors.json", [{"error_type": "fatal_evaluation_error", "message": str(exc)}])
        print(f"Direct-edge gate evaluation failed: {exc}")
        return 1
    print(f"Direct-edge gate evaluation status: {artifacts['metrics.json']['evaluation_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
