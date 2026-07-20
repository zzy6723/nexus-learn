#!/usr/bin/env python3
"""Evaluate 002C-2 candidate generation, identity decisions, and final clusters."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_ko_canonicalization import (
    evaluate_partitions,
    load_and_validate_run,
)
from scripts.check_ko_canonicalization_ground_truth import validate_bundle
from scripts.generate_candidate_pair_universe import display_path, sha256_file


EVALUATOR_VERSION = "context_ko_resolution_evaluator_v0.1"


class ContextEvaluationError(ValueError):
    """Raised when formal context-resolution evaluation is invalid."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--ground-truth-marker", required=True)
    parser.add_argument("--success-criteria", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--resolution-run-dir", required=True)
    parser.add_argument("--cluster-dir", required=True)
    parser.add_argument("--evaluation-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextEvaluationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextEvaluationError(f"{label} must be a JSON object.")
    return value


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ContextEvaluationError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def gold_same_pairs(ground_truth: dict[str, Any]) -> set[frozenset[str]]:
    return {
        frozenset((left, right))
        for cluster in ground_truth["clusters"]
        for left, right in combinations(cluster["mention_ids"], 2)
    }


def evaluate(
    *, inventory: dict[str, Any], ground_truth: dict[str, Any],
    candidates: dict[str, Any], decisions: dict[str, Any], decision_audit: dict[str, Any],
    prediction: dict[str, Any], audit: dict[str, Any], criteria: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    mentions = inventory["mentions"]
    all_pairs = {frozenset((a["mention_id"], b["mention_id"])) for a, b in combinations(mentions, 2)}
    same_pairs = gold_same_pairs(ground_truth)
    selected_by_id = {item["candidate_id"]: item for item in candidates["candidates"]}
    selected_pairs = {
        frozenset((item["mention_a"]["mention_id"], item["mention_b"]["mention_id"]))
        for item in selected_by_id.values()
    }
    result_by_id = {item["candidate_id"]: item for item in decisions["results"]}
    if set(result_by_id) != set(selected_by_id):
        raise ContextEvaluationError("Decision and candidate IDs do not align.")
    rows = []
    tp = fp = fn = tn = unresolved = 0
    decision_counts: Counter[str] = Counter()
    for candidate_id, candidate in selected_by_id.items():
        pair = frozenset((candidate["mention_a"]["mention_id"], candidate["mention_b"]["mention_id"]))
        gold = "SAME_OBJECT" if pair in same_pairs else "DISTINCT_OBJECT"
        result = result_by_id[candidate_id]
        predicted = result["decision"]
        decision_counts[predicted] += 1
        if predicted == "UNRESOLVED":
            unresolved += 1
            if gold == "SAME_OBJECT":
                fn += 1
            outcome = "unresolved"
        elif predicted == "SAME_OBJECT" and gold == "SAME_OBJECT":
            tp += 1
            outcome = "true_positive"
        elif predicted == "SAME_OBJECT":
            fp += 1
            outcome = "false_merge"
        elif gold == "SAME_OBJECT":
            fn += 1
            outcome = "false_split"
        else:
            tn += 1
            outcome = "true_negative"
        rows.append(
            {"candidate_id": candidate_id, "mention_ids": sorted(pair), "gold_identity": gold,
             "predicted_identity": predicted, "outcome": outcome}
        )
    precision = safe_ratio(tp, tp + fp)
    conditional_recall = safe_ratio(tp, len(same_pairs & selected_pairs))
    end_to_end_recall = safe_ratio(tp, len(same_pairs))
    partition_metrics, assignments, pair_rows, cluster_rows, partition_errors = evaluate_partitions(
        inventory, ground_truth, prediction, audit
    )
    candidate_gates = criteria["candidate_gates"]
    resolver_gates = criteria["resolver_gates"]
    required_specs = candidate_gates.get("required_candidate_decisions")
    legacy_homonym = candidate_gates.get("required_homonym_candidate")
    if required_specs is None:
        required_specs = [
            {
                "case": "homonym",
                "mention_ids": legacy_homonym,
                "decision": resolver_gates["homonym_decision"],
            }
        ]
    required_rows = []
    for spec in required_specs:
        required_pair = frozenset(spec["mention_ids"])
        candidate_id = next(
            (item_id for item_id, candidate in selected_by_id.items()
             if frozenset((candidate["mention_a"]["mention_id"], candidate["mention_b"]["mention_id"])) == required_pair),
            None,
        )
        actual_decision = result_by_id[candidate_id]["decision"] if candidate_id else None
        required_rows.append(
            {
                "case": spec["case"], "mention_ids": sorted(required_pair),
                "candidate_id": candidate_id, "selected": candidate_id is not None,
                "expected_decision": spec["decision"], "actual_decision": actual_decision,
                "passed": candidate_id is not None and actual_decision == spec["decision"],
            }
        )
    homonym_row = next((item for item in required_rows if item["case"] == "homonym"), None)
    metrics = {
        "evaluation_status": "final",
        "benchmark_counts": {
            "mentions": len(mentions), "all_unordered_pairs": len(all_pairs),
            "gold_same_object_pairs": len(same_pairs),
            "gold_distinct_object_pairs": len(all_pairs - same_pairs),
        },
        "candidate_generation": {
            "selected_candidates": len(selected_pairs),
            "candidate_reduction_rate": 1 - len(selected_pairs) / len(all_pairs),
            "gold_same_object_pairs_selected": len(same_pairs & selected_pairs),
            "gold_same_object_pair_recall": safe_ratio(len(same_pairs & selected_pairs), len(same_pairs)),
            "selected_hard_negatives": len(selected_pairs - same_pairs),
            "required_candidate_decisions": required_rows,
            "required_homonym_selected": homonym_row["selected"] if homonym_row else None,
        },
        "resolver": {
            "true_positive_same_object": tp, "false_positive_same_object": fp,
            "false_negative_same_object": fn, "same_object_precision": precision,
            "same_object_recall_on_candidates": conditional_recall,
            "same_object_recall_end_to_end": end_to_end_recall,
            "same_object_f1_end_to_end": f1(precision, end_to_end_recall),
            "true_negative_distinct_object": tn,
            "distinct_object_accuracy_on_candidates": safe_ratio(
                tn, len(selected_pairs - same_pairs)
            ),
            "unresolved_count": unresolved,
            "unresolved_rate": safe_ratio(unresolved, len(selected_pairs)),
            "decision_counts": dict(sorted(decision_counts.items())),
            "homonym_decision": homonym_row["actual_decision"] if homonym_row else None,
            "inconsistent_component_count": decision_audit["inconsistent_component_count"],
            "manual_adjudication_count": decision_audit["adjudicated_decision_count"],
            "schema_failure_rate": 0.0,
        },
        "cluster_quality": partition_metrics["cluster_quality"],
        "integrity": partition_metrics["integrity"],
        "cluster_error_counts": partition_metrics["error_counts"],
    }
    failures = []
    if metrics["candidate_generation"]["gold_same_object_pair_recall"] < candidate_gates["gold_same_object_pair_recall_min"]:
        failures.append("candidate_same_object_recall")
    selected_count_max = candidate_gates.get("selected_candidate_count_max")
    if selected_count_max is not None and len(selected_pairs) > selected_count_max:
        failures.append("selected_candidate_count")
    hard_negative_min = candidate_gates.get("selected_hard_negative_count_min")
    if hard_negative_min is not None and len(selected_pairs - same_pairs) < hard_negative_min:
        failures.append("selected_hard_negative_count")
    if any(not item["selected"] for item in required_rows):
        failures.append("required_candidate_selection")
    checks = {
        "same_object_precision": (precision, resolver_gates["same_object_precision_min"], ">="),
        "same_object_recall": (end_to_end_recall, resolver_gates["same_object_recall_min"], ">="),
        "unresolved_rate": (metrics["resolver"]["unresolved_rate"], resolver_gates["unresolved_rate_max"], "<="),
        "inconsistent_components": (metrics["resolver"]["inconsistent_component_count"], resolver_gates["inconsistent_component_count_max"], "<="),
    }
    if "distinct_object_accuracy_min" in resolver_gates:
        checks["distinct_object_accuracy"] = (
            metrics["resolver"]["distinct_object_accuracy_on_candidates"],
            resolver_gates["distinct_object_accuracy_min"],
            ">=",
        )
    if "schema_failure_rate_max" in resolver_gates:
        checks["schema_failure_rate"] = (
            metrics["resolver"]["schema_failure_rate"],
            resolver_gates["schema_failure_rate_max"],
            "<=",
        )
    for name, (actual, threshold, operator) in checks.items():
        if actual is None or (operator == ">=" and actual < threshold) or (operator == "<=" and actual > threshold):
            failures.append(name)
    if any(not item["passed"] for item in required_rows):
        failures.append("required_candidate_decision")
    cluster_gates = criteria["cluster_gates"]
    if metrics["cluster_quality"]["b_cubed_f1"] < cluster_gates["b_cubed_f1_min"]:
        failures.append("b_cubed_f1")
    optional_cluster_minimums = {
        "b_cubed_precision": "b_cubed_precision_min",
        "b_cubed_recall": "b_cubed_recall_min",
        "exact_gold_cluster_match_rate": "exact_gold_cluster_match_rate_min",
        "singleton_precision": "singleton_precision_min",
        "singleton_recall": "singleton_recall_min",
    }
    for metric_name, gate_name in optional_cluster_minimums.items():
        if (
            gate_name in cluster_gates
            and metrics["cluster_quality"].get(metric_name) is not None
            and metrics["cluster_quality"][metric_name] < cluster_gates[gate_name]
        ):
            failures.append(metric_name)
    optional_error_maximums = {
        "false_merge": "false_merge_count_max",
        "false_split": "false_split_count_max",
    }
    for error_name, gate_name in optional_error_maximums.items():
        if (
            gate_name in cluster_gates
            and metrics["cluster_error_counts"].get(error_name, 0) > cluster_gates[gate_name]
        ):
            failures.append(error_name)
    for key in (
        "mention_coverage",
        "duplicate_assignments",
        "orphan_mentions",
        "lost_provenance_mentions",
        "cross_type_clusters",
    ):
        if key not in cluster_gates:
            continue
        if metrics["integrity"][key] != cluster_gates[key]:
            failures.append(key)
    metrics["success_criteria"] = {"passed": not failures, "failures": failures}
    return metrics, rows, partition_errors, failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {name: Path(value).resolve() for name, value in {
        "inventory": args.mention_inventory, "ground_truth": args.ground_truth,
        "ground_truth_marker": args.ground_truth_marker, "criteria": args.success_criteria,
        "candidate_dir": args.candidate_dir, "resolution_dir": args.resolution_run_dir,
        "cluster_dir": args.cluster_dir, "evaluation_dir": args.evaluation_dir,
    }.items()}
    output_paths = {
        "metrics": paths["evaluation_dir"] / "metrics.json",
        "candidate_matches": paths["evaluation_dir"] / "candidate_matches.json",
        "errors": paths["evaluation_dir"] / "errors.json",
        "completion": paths["evaluation_dir"] / "evaluation_complete.json",
    }
    try:
        existing = [path for path in output_paths.values() if path.exists()]
        if existing and not args.overwrite:
            raise ContextEvaluationError("Refusing to overwrite evaluation artifacts.")
        if args.overwrite:
            for path in existing:
                path.unlink()
        inventory = load_json(paths["inventory"], label="mention inventory")
        ground_truth = load_json(paths["ground_truth"], label="Ground Truth")
        criteria = load_json(paths["criteria"], label="success criteria")
        ground_truth_errors, _ = validate_bundle(
            inventory_path=paths["inventory"],
            ground_truth_path=paths["ground_truth"],
            completion_marker_path=paths["ground_truth_marker"],
            allow_draft=False,
            require_completion_marker=True,
        )
        if ground_truth_errors:
            raise ContextEvaluationError(
                "Ground Truth bundle invalid: " + "; ".join(ground_truth_errors)
            )
        candidates = load_json(paths["candidate_dir"] / "candidate_pairs.json", label="candidates")
        decisions = load_json(paths["resolution_dir"] / "output" / "identity_decisions.json", label="decisions")
        decision_audit = load_json(paths["cluster_dir"] / "decision_audit.json", label="decision audit")
        prediction, _, audit, metadata, run_errors = load_and_validate_run(
            paths["cluster_dir"], inventory=inventory
        )
        if run_errors:
            raise ContextEvaluationError("Invalid cluster run: " + "; ".join(run_errors))
        metrics, candidate_rows, quality_errors, failures = evaluate(
            inventory=inventory, ground_truth=ground_truth, candidates=candidates,
            decisions=decisions, decision_audit=decision_audit, prediction=prediction,
            audit=audit, criteria=criteria,
        )
        atomic_write(output_paths["metrics"], metrics)
        atomic_write(output_paths["candidate_matches"], {"evaluation_status": "final", "matches": candidate_rows})
        atomic_write(
            output_paths["errors"],
            {"evaluation_status": "final", "fatal_errors": [], "quality_errors": quality_errors, "gate_failures": failures},
        )
        marker = {
            "artifact_type": "ko_context_resolution_evaluation_complete", "version": "v0.1",
            "status": "final", "method_id": metadata["method_id"],
            "method_commit": metadata["method_commit"],
            "evaluator": {"path": display_path(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__).resolve()), "version": EVALUATOR_VERSION},
            "inputs": {
                "mention_inventory": binding(paths["inventory"]), "ground_truth": binding(paths["ground_truth"]),
                "ground_truth_marker": binding(paths["ground_truth_marker"]), "success_criteria": binding(paths["criteria"]),
                "candidate_completion": binding(paths["candidate_dir"] / "candidate_generation_complete.json"),
                "resolution_completion": binding(paths["resolution_dir"] / "resolution_complete.json"),
                "cluster_completion": binding(paths["cluster_dir"] / "generation_complete.json"),
            },
            "outputs": {name: binding(path) for name, path in output_paths.items() if name != "completion"},
            "success_criteria_passed": metrics["success_criteria"]["passed"],
        }
        atomic_write(output_paths["completion"], marker)
    except ContextEvaluationError as exc:
        print(f"Context evaluation failed: {exc}")
        return 1
    print(f"Wrote context evaluation. Success criteria passed: {metrics['success_criteria']['passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
