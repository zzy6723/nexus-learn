#!/usr/bin/env python3
"""Evaluate deterministic KO identity clusters against frozen cluster Ground Truth."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ko_canonicalization_ground_truth import (  # noqa: E402
    DEFAULT_COMPLETION_MARKER as DEFAULT_GROUND_TRUTH_MARKER,
    DEFAULT_GROUND_TRUTH,
    DEFAULT_MENTION_INVENTORY,
    validate_bundle as validate_ground_truth_bundle,
)
from scripts.generate_candidate_pair_universe import display_path, sha256_file  # noqa: E402
from scripts.knowledge_object_matching import name_matching_key  # noqa: E402


DEFAULT_SUCCESS_CRITERIA = (
    ROOT / "benchmark" / "ko_canonicalization_success_criteria_v0_1.json"
)
EVALUATOR_VERSION = "ko_canonicalization_evaluator_v0.1"
RUN_FILENAMES = {
    "prediction": "canonical_clusters.json",
    "assignments": "mention_assignments.json",
    "audit": "normalization_audit.json",
    "metadata": "metadata.json",
    "completion": "generation_complete.json",
}
EVALUATION_FILENAMES = {
    "metrics": "metrics.json",
    "assignments": "mention_assignments.json",
    "pairs": "pairwise_matches.json",
    "clusters": "cluster_matches.json",
    "errors": "errors.json",
    "completion": "evaluation_complete.json",
}


class CanonicalizationEvaluationError(ValueError):
    """Raised when formal evaluation cannot produce trustworthy metrics."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", default=str(DEFAULT_MENTION_INVENTORY))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument(
        "--ground-truth-marker",
        default=str(DEFAULT_GROUND_TRUTH_MARKER),
    )
    parser.add_argument("--success-criteria", default=str(DEFAULT_SUCCESS_CRITERIA))
    parser.add_argument("--prediction-dir", required=True)
    parser.add_argument("--evaluation-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalizationEvaluationError(
            f"Unable to read {label} {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise CanonicalizationEvaluationError(f"{label} must be a JSON object.")
    return value


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(serialize_json(value))
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None if precision is None or recall is None else 0.0
    return 2 * precision * recall / (precision + recall)


def binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def validate_binding(
    value: Any,
    *,
    expected_path: Path,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        errors.append(f"{label}: invalid artifact binding")
        return
    path = Path(value["path"])
    if not path.is_absolute():
        path = ROOT / path
    if path.resolve() != expected_path.resolve():
        errors.append(f"{label}: path mismatch")
    if not path.is_file():
        errors.append(f"{label}: bound file is missing")
    elif value.get("sha256") != sha256_file(path):
        errors.append(f"{label}: stale SHA-256 binding")


def load_and_validate_run(
    prediction_dir: Path,
    *,
    inventory: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []
    paths = {name: prediction_dir / filename for name, filename in RUN_FILENAMES.items()}
    artifacts: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"run.{name}: missing file {display_path(path)}")
            artifacts[name] = {}
            continue
        artifacts[name] = load_json_object(path, label=f"run {name}")

    marker = artifacts["completion"]
    if marker.get("artifact_type") != "ko_canonicalization_generation_complete":
        errors.append("generation marker: invalid artifact_type")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        errors.append("generation marker: status must be final v0.1")
    marker_artifacts = marker.get("artifacts")
    expected_marker_names = {
        "canonical_clusters": paths["prediction"],
        "mention_assignments": paths["assignments"],
        "normalization_audit": paths["audit"],
        "metadata": paths["metadata"],
    }
    if not isinstance(marker_artifacts, dict) or set(marker_artifacts) != set(
        expected_marker_names
    ):
        errors.append("generation marker: artifact set mismatch")
    else:
        for name, expected_path in expected_marker_names.items():
            validate_binding(
                marker_artifacts[name],
                expected_path=expected_path,
                label=f"generation marker.{name}",
                errors=errors,
            )

    prediction = artifacts["prediction"]
    assignments = artifacts["assignments"]
    audit = artifacts["audit"]
    metadata = artifacts["metadata"]
    if prediction.get("artifact_type") != "ko_canonicalization_prediction":
        errors.append("prediction: invalid artifact_type")
    if assignments.get("artifact_type") != "ko_canonicalization_assignments":
        errors.append("assignments: invalid artifact_type")
    if audit.get("artifact_type") != "ko_name_normalization_audit":
        errors.append("normalization audit: invalid artifact_type")
    if metadata.get("artifact_type") != "ko_canonicalization_run_metadata":
        errors.append("metadata: invalid artifact_type")
    method_ids = {
        prediction.get("method", {}).get("method_id")
        if isinstance(prediction.get("method"), dict)
        else None,
        assignments.get("method_id"),
        audit.get("method_id"),
        metadata.get("method_id"),
        marker.get("method_id"),
    }
    if len(method_ids) != 1 or None in method_ids:
        errors.append("run artifacts: method identity mismatch")
    if metadata.get("run_status") != "completed":
        errors.append("metadata: run_status must be completed")
    if metadata.get("git_dirty_at_start") is not False:
        errors.append("metadata: formal run started from a dirty worktree")
    if metadata.get("git_commit_at_start") != metadata.get("method_commit"):
        errors.append("metadata: launch commit differs from method commit")
    if marker.get("method_commit") != metadata.get("method_commit"):
        errors.append("generation marker: method commit mismatch")
    inventory_binding = metadata.get("mention_inventory")
    inventory_path = Path(inventory_binding.get("path", "")) if isinstance(inventory_binding, dict) else Path()
    if not inventory_path.is_absolute():
        inventory_path = ROOT / inventory_path
    if not isinstance(inventory_binding, dict) or inventory_binding.get("sha256") != (
        sha256_file(inventory_path) if inventory_path.is_file() else None
    ):
        errors.append("metadata: mention inventory binding is stale")

    mentions = inventory["mentions"]
    mention_by_id = {item["mention_id"]: item for item in mentions}
    clusters = prediction.get("clusters")
    if not isinstance(clusters, list):
        errors.append("prediction.clusters: must be a list")
        clusters = []
    seen_ids: set[str] = set()
    assigned: list[str] = []
    for index, cluster in enumerate(clusters):
        label = f"prediction.clusters[{index}]"
        expected_keys = {
            "canonical_id",
            "canonical_name",
            "canonical_type",
            "normalized_identity_key",
            "mention_ids",
            "mention_provenance",
        }
        if not isinstance(cluster, dict) or set(cluster) != expected_keys:
            errors.append(f"{label}: invalid fields")
            continue
        canonical_id = cluster.get("canonical_id")
        if canonical_id in seen_ids:
            errors.append(f"{label}: duplicate canonical ID")
        seen_ids.add(canonical_id)
        member_ids = cluster.get("mention_ids")
        snapshots = cluster.get("mention_provenance")
        if not isinstance(member_ids, list) or not member_ids:
            errors.append(f"{label}: empty mention membership")
            continue
        if len(member_ids) != len(set(member_ids)):
            errors.append(f"{label}: duplicate mention within cluster")
        if not isinstance(snapshots, list) or len(snapshots) != len(member_ids):
            errors.append(f"{label}: provenance count mismatch")
            snapshots = []
        for member_index, mention_id in enumerate(member_ids):
            if mention_id not in mention_by_id:
                errors.append(f"{label}: unknown mention {mention_id}")
                continue
            assigned.append(mention_id)
            if cluster.get("canonical_type") != mention_by_id[mention_id]["type"]:
                errors.append(f"{label}: cross-type cluster")
            if member_index >= len(snapshots) or snapshots[member_index] != mention_by_id[mention_id]:
                errors.append(f"{label}: lost provenance for {mention_id}")
    duplicate_assignments = sorted(
        mention_id for mention_id, count in Counter(assigned).items() if count > 1
    )
    orphan_mentions = sorted(set(mention_by_id) - set(assigned))
    if duplicate_assignments:
        errors.append(f"prediction: duplicate assignments {duplicate_assignments}")
    if orphan_mentions:
        errors.append(f"prediction: orphan mentions {orphan_mentions}")

    assignment_rows = assignments.get("assignments")
    expected_assignment_map = {
        mention_id: cluster["canonical_id"]
        for cluster in clusters
        if isinstance(cluster, dict)
        for mention_id in cluster.get("mention_ids", [])
    }
    if not isinstance(assignment_rows, list):
        errors.append("assignments.assignments: must be a list")
    else:
        actual_assignment_map: dict[str, str] = {}
        for row in assignment_rows:
            if not isinstance(row, dict) or set(row) != {"mention_id", "canonical_id"}:
                errors.append("assignments: invalid row")
                continue
            if row["mention_id"] in actual_assignment_map:
                errors.append("assignments: duplicate mention row")
            actual_assignment_map[row["mention_id"]] = row["canonical_id"]
        if actual_assignment_map != expected_assignment_map:
            errors.append("assignments: rows do not match predicted clusters")

    audit_rows = audit.get("records")
    if not isinstance(audit_rows, list) or len(audit_rows) != len(mentions):
        errors.append("normalization audit: mention coverage mismatch")
    else:
        audit_ids = [row.get("mention_id") for row in audit_rows if isinstance(row, dict)]
        if audit_ids != [item["mention_id"] for item in mentions]:
            errors.append("normalization audit: order or mention IDs mismatch")
        for row in audit_rows:
            if isinstance(row, dict) and expected_assignment_map.get(row.get("mention_id")) != row.get(
                "assigned_cluster_id"
            ):
                errors.append("normalization audit: assigned cluster mismatch")
                break
    return prediction, assignments, audit, metadata, errors


def partition_map(clusters: list[dict[str, Any]]) -> dict[str, str]:
    return {
        mention_id: cluster["canonical_id"]
        for cluster in clusters
        for mention_id in cluster["mention_ids"]
    }


def cluster_memberships(clusters: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        cluster["canonical_id"]: set(cluster["mention_ids"])
        for cluster in clusters
    }


def evaluate_partitions(
    inventory: dict[str, Any],
    ground_truth: dict[str, Any],
    prediction: dict[str, Any],
    audit: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    mentions = inventory["mentions"]
    mention_by_id = {item["mention_id"]: item for item in mentions}
    gold_clusters = ground_truth["clusters"]
    predicted_clusters = prediction["clusters"]
    gold_map = partition_map(gold_clusters)
    predicted_map = partition_map(predicted_clusters)
    gold_members = cluster_memberships(gold_clusters)
    predicted_members = cluster_memberships(predicted_clusters)
    audit_by_id = {item["mention_id"]: item for item in audit["records"]}

    true_positive = false_positive = false_negative = 0
    pair_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for left_index, left in enumerate(mentions):
        for right in mentions[left_index + 1 :]:
            left_id = left["mention_id"]
            right_id = right["mention_id"]
            gold_same = gold_map[left_id] == gold_map[right_id]
            predicted_same = predicted_map[left_id] == predicted_map[right_id]
            if gold_same and predicted_same:
                outcome = "true_positive"
                true_positive += 1
            elif not gold_same and predicted_same:
                outcome = "false_merge"
                false_positive += 1
                same_normalized_name = (
                    audit_by_id[left_id]["normalized_name"]
                    == audit_by_id[right_id]["normalized_name"]
                )
                errors.append(
                    {
                        "error_type": "same_name_false_merge"
                        if same_normalized_name
                        else "false_merge",
                        "mention_ids": [left_id, right_id],
                        "predicted_canonical_id": predicted_map[left_id],
                        "gold_canonical_ids": [gold_map[left_id], gold_map[right_id]],
                    }
                )
            elif gold_same and not predicted_same:
                outcome = "false_split"
                false_negative += 1
                alias_like = (
                    audit_by_id[left_id]["normalized_name"]
                    != audit_by_id[right_id]["normalized_name"]
                )
                errors.append(
                    {
                        "error_type": "alias_false_split" if alias_like else "false_split",
                        "mention_ids": [left_id, right_id],
                        "predicted_canonical_ids": [
                            predicted_map[left_id],
                            predicted_map[right_id],
                        ],
                        "gold_canonical_id": gold_map[left_id],
                    }
                )
            else:
                outcome = "true_negative"
            pair_rows.append(
                {
                    "mention_a": left_id,
                    "mention_b": right_id,
                    "gold_identity": "SAME_OBJECT" if gold_same else "DISTINCT_OBJECT",
                    "predicted_identity": "SAME_OBJECT"
                    if predicted_same
                    else "DISTINCT_OBJECT",
                    "outcome": outcome,
                }
            )

    precision = safe_ratio(true_positive, true_positive + false_positive)
    recall = safe_ratio(true_positive, true_positive + false_negative)
    pairwise_f1 = f1(precision, recall)

    b3_precision_parts: list[float] = []
    b3_recall_parts: list[float] = []
    assignment_rows: list[dict[str, Any]] = []
    for mention in mentions:
        mention_id = mention["mention_id"]
        gold_set = gold_members[gold_map[mention_id]]
        predicted_set = predicted_members[predicted_map[mention_id]]
        intersection = len(gold_set & predicted_set)
        b3_precision_parts.append(intersection / len(predicted_set))
        b3_recall_parts.append(intersection / len(gold_set))
        assignment_rows.append(
            {
                "mention_id": mention_id,
                "gold_canonical_id": gold_map[mention_id],
                "predicted_canonical_id": predicted_map[mention_id],
                "gold_cluster_size": len(gold_set),
                "predicted_cluster_size": len(predicted_set),
            }
        )
    b3_precision = sum(b3_precision_parts) / len(mentions)
    b3_recall = sum(b3_recall_parts) / len(mentions)
    b3_f1 = f1(b3_precision, b3_recall)

    predicted_sets = set(map(frozenset, predicted_members.values()))
    gold_sets = set(map(frozenset, gold_members.values()))
    exact_gold_matches = len(gold_sets & predicted_sets)
    gold_singletons = {members for members in gold_sets if len(members) == 1}
    predicted_singletons = {members for members in predicted_sets if len(members) == 1}
    singleton_matches = len(gold_singletons & predicted_singletons)
    cluster_rows = [
        {
            "gold_canonical_id": cluster["canonical_id"],
            "gold_mention_ids": cluster["mention_ids"],
            "exact_predicted_cluster_match": frozenset(cluster["mention_ids"])
            in predicted_sets,
        }
        for cluster in gold_clusters
    ]
    for gold_singleton in sorted(gold_singletons, key=lambda item: sorted(item)):
        mention_id = next(iter(gold_singleton))
        if len(predicted_members[predicted_map[mention_id]]) > 1:
            errors.append(
                {
                    "error_type": "singleton_absorbed",
                    "mention_ids": [mention_id],
                    "predicted_canonical_id": predicted_map[mention_id],
                }
            )

    metrics = {
        "evaluation_status": "final",
        "benchmark_counts": {
            "mentions": len(mentions),
            "gold_clusters": len(gold_clusters),
            "gold_same_object_pairs": true_positive + false_negative,
            "gold_distinct_object_pairs": len(pair_rows) - true_positive - false_negative,
        },
        "prediction_counts": {
            "clusters": len(predicted_clusters),
            "singleton_clusters": sum(
                len(item["mention_ids"]) == 1 for item in predicted_clusters
            ),
            "multi_mention_clusters": sum(
                len(item["mention_ids"]) > 1 for item in predicted_clusters
            ),
        },
        "integrity": {
            "mention_coverage": 1.0,
            "duplicate_assignments": 0,
            "orphan_mentions": 0,
            "cross_type_clusters": 0,
            "lost_provenance_mentions": 0,
        },
        "pairwise_identity": {
            "true_positive_same_object": true_positive,
            "false_positive_same_object": false_positive,
            "false_negative_same_object": false_negative,
            "same_object_precision": precision,
            "same_object_recall": recall,
            "same_object_f1": pairwise_f1,
        },
        "cluster_quality": {
            "b_cubed_precision": b3_precision,
            "b_cubed_recall": b3_recall,
            "b_cubed_f1": b3_f1,
            "exact_gold_cluster_matches": exact_gold_matches,
            "exact_gold_cluster_match_rate": exact_gold_matches / len(gold_clusters),
            "singleton_precision": safe_ratio(
                singleton_matches,
                len(predicted_singletons),
            ),
            "singleton_recall": safe_ratio(singleton_matches, len(gold_singletons)),
        },
        "error_counts": dict(sorted(Counter(item["error_type"] for item in errors).items())),
        "interpretation_warning": (
            "Pairwise accuracy is intentionally omitted from primary metrics because "
            "DISTINCT_OBJECT pairs dominate this benchmark."
        ),
    }
    return metrics, assignment_rows, pair_rows, cluster_rows, errors


def criteria_pass(metrics: dict[str, Any], criteria: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    integrity = metrics["integrity"]
    for key, expected in criteria["integrity_gates"].items():
        actual = metrics["evaluation_status"] if key == "evaluation_status" else integrity[key]
        if actual != expected:
            failures.append(f"integrity:{key} expected {expected}, got {actual}")
    quality = metrics["pairwise_identity"] | metrics["cluster_quality"]
    mappings = {
        "same_object_pairwise_precision_min": "same_object_precision",
        "same_object_pairwise_recall_min": "same_object_recall",
        "b_cubed_f1_min": "b_cubed_f1",
        "exact_gold_cluster_match_rate_min": "exact_gold_cluster_match_rate",
    }
    for criterion, metric_name in mappings.items():
        threshold = criteria["quality_gates"][criterion]
        actual = quality[metric_name]
        if actual is None or actual < threshold:
            failures.append(f"quality:{metric_name} expected >= {threshold}, got {actual}")
    return not failures, failures


def write_invalid(
    evaluation_dir: Path,
    *,
    errors: list[str],
    overwrite: bool,
) -> None:
    paths = {name: evaluation_dir / filename for name, filename in EVALUATION_FILENAMES.items()}
    if overwrite:
        for path in paths.values():
            if path.exists():
                path.unlink()
    elif any(path.exists() for path in paths.values()):
        raise CanonicalizationEvaluationError("Evaluation artifacts already exist.")
    atomic_write(
        paths["errors"],
        {
            "evaluation_status": "invalid",
            "fatal_errors": errors,
            "quality_errors": [],
        },
    )
    atomic_write(
        paths["completion"],
        {
            "artifact_type": "ko_canonicalization_evaluation_complete",
            "version": "v0.1",
            "status": "invalid",
            "evaluator_version": EVALUATOR_VERSION,
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    ground_truth_path = Path(args.ground_truth).resolve()
    ground_truth_marker_path = Path(args.ground_truth_marker).resolve()
    criteria_path = Path(args.success_criteria).resolve()
    prediction_dir = Path(args.prediction_dir).resolve()
    evaluation_dir = Path(args.evaluation_dir).resolve()
    try:
        gt_errors, _ = validate_ground_truth_bundle(
            inventory_path=inventory_path,
            ground_truth_path=ground_truth_path,
            completion_marker_path=ground_truth_marker_path,
            allow_draft=False,
            require_completion_marker=True,
        )
        if gt_errors:
            raise CanonicalizationEvaluationError(
                "Ground Truth bundle invalid: " + "; ".join(gt_errors)
            )
        inventory = load_json_object(inventory_path, label="mention inventory")
        ground_truth = load_json_object(ground_truth_path, label="Ground Truth")
        criteria = load_json_object(criteria_path, label="success criteria")
        prediction, _, audit, metadata, run_errors = load_and_validate_run(
            prediction_dir,
            inventory=inventory,
        )
        if run_errors:
            write_invalid(evaluation_dir, errors=run_errors, overwrite=args.overwrite)
            print(f"Evaluation invalid: {len(run_errors)} fatal integrity errors.")
            return 1
        metrics, assignments, pairs, clusters, quality_errors = evaluate_partitions(
            inventory,
            ground_truth,
            prediction,
            audit,
        )
        passed, gate_failures = criteria_pass(metrics, criteria)
        metrics["success_criteria"] = {
            "passed": passed,
            "failures": gate_failures,
        }
        paths = {
            name: evaluation_dir / filename
            for name, filename in EVALUATION_FILENAMES.items()
        }
        existing = [path for path in paths.values() if path.exists()]
        if existing and not args.overwrite:
            raise CanonicalizationEvaluationError(
                "Refusing to overwrite: " + ", ".join(display_path(path) for path in existing)
            )
        if args.overwrite:
            for path in paths.values():
                if path.exists():
                    path.unlink()
        atomic_write(paths["metrics"], metrics)
        atomic_write(
            paths["assignments"],
            {"evaluation_status": "final", "assignments": assignments},
        )
        atomic_write(
            paths["pairs"],
            {"evaluation_status": "final", "pairs": pairs},
        )
        atomic_write(
            paths["clusters"],
            {"evaluation_status": "final", "clusters": clusters},
        )
        atomic_write(
            paths["errors"],
            {
                "evaluation_status": "final",
                "fatal_errors": [],
                "quality_errors": quality_errors,
            },
        )
        marker = {
            "artifact_type": "ko_canonicalization_evaluation_complete",
            "version": "v0.1",
            "status": "final",
            "method_id": metadata["method_id"],
            "method_commit": metadata["method_commit"],
            "evaluator": {
                **binding(Path(__file__).resolve()),
                "version": EVALUATOR_VERSION,
            },
            "inputs": {
                "mention_inventory": binding(inventory_path),
                "ground_truth": binding(ground_truth_path),
                "ground_truth_completion_marker": binding(ground_truth_marker_path),
                "success_criteria": binding(criteria_path),
                "generation_completion_marker": binding(
                    prediction_dir / RUN_FILENAMES["completion"]
                ),
            },
            "outputs": {
                name: binding(path)
                for name, path in paths.items()
                if name != "completion"
            },
            "success_criteria_passed": passed,
        }
        atomic_write(paths["completion"], marker)
    except CanonicalizationEvaluationError as exc:
        print(f"Canonicalization evaluation failed: {exc}")
        return 1
    print(f"Wrote final canonicalization evaluation to {display_path(evaluation_dir)}")
    print(f"Success criteria passed: {passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
