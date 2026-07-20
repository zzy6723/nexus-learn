#!/usr/bin/env python3
"""Finalize all structural, Evidence, and determinism gates for 002C-5."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments/knowledge_object_resolution/002c_5_independent_validation"
BENCHMARK = ROOT / "benchmark/ko_canonicalization/independent_v0_1"
RUN_ROOT = BASE / "runs/independent_v0_1"
DEFAULT_RESOLUTION = RUN_ROOT / "context/run_01"
DEFAULT_CLUSTERS = RUN_ROOT / "clusters/run_01"
DEFAULT_EVALUATION = RUN_ROOT / "evaluation/run_01"
DEFAULT_REVIEW = RUN_ROOT / "evidence_review/run_01"
DEFAULT_DETERMINISM = RUN_ROOT / "determinism/run_01/determinism_report.json"
DEFAULT_OUTPUT = RUN_ROOT / "independent_validation_complete.json"
VERSION = "ko_independent_validation_finalizer_v0.1"


class IndependentValidationError(ValueError):
    """Raised when an independent validation artifact is missing or stale."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution-run-dir", default=str(DEFAULT_RESOLUTION))
    parser.add_argument("--cluster-dir", default=str(DEFAULT_CLUSTERS))
    parser.add_argument("--evaluation-dir", default=str(DEFAULT_EVALUATION))
    parser.add_argument("--evidence-review-dir", default=str(DEFAULT_REVIEW))
    parser.add_argument("--determinism-report", default=str(DEFAULT_DETERMINISM))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise IndependentValidationError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentValidationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise IndependentValidationError(f"{label} must be a JSON object.")
    return value


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


def compare_min(
    failures: list[str], name: str, actual: float | int | None, expected: float | int
) -> None:
    if actual is None or actual < expected:
        failures.append(name)


def compare_max(
    failures: list[str], name: str, actual: float | int | None, expected: float | int
) -> None:
    if actual is None or actual > expected:
        failures.append(name)


def exact_evidence_counts(
    decisions: dict[str, Any], lecture_inventory: dict[str, Any]
) -> tuple[int, int]:
    lecture_text = {
        item["lecture_id"]: item["text"] for item in lecture_inventory["lectures"]
    }
    exact = total = 0
    for result in decisions.get("results", []):
        ids = result.get("evidence_ids")
        spans = result.get("evidence_spans")
        if not isinstance(ids, list) or not isinstance(spans, list) or len(ids) != len(spans):
            raise IndependentValidationError("Evidence IDs and materialized spans do not align.")
        if result.get("decision") != "UNRESOLVED" and not spans:
            raise IndependentValidationError("Resolved identity decision has no Evidence.")
        for span in spans:
            lecture_id = span.get("lecture_id")
            text = span.get("span")
            if lecture_id not in lecture_text or not isinstance(text, str) or not text:
                raise IndependentValidationError("Materialized Evidence span is malformed.")
            total += 1
            exact += int(text in lecture_text[lecture_id])
    return exact, total


def evaluate_gates(
    *, metrics: dict[str, Any], criteria: dict[str, Any],
    evidence_audit: dict[str, Any], determinism: dict[str, Any],
    exact_evidence: int, total_evidence: int,
) -> list[str]:
    failures: list[str] = []
    candidate = metrics["candidate_generation"]
    resolver = metrics["resolver"]
    cluster = metrics["cluster_quality"]
    integrity = metrics["integrity"]
    errors = metrics["cluster_error_counts"]
    candidate_gates = criteria["candidate_gates"]
    resolver_gates = criteria["resolver_gates"]
    cluster_gates = criteria["cluster_gates"]
    evidence_gates = criteria["evidence_gates"]

    compare_min(
        failures,
        "candidate_same_object_recall",
        candidate.get("gold_same_object_pair_recall"),
        candidate_gates["gold_same_object_pair_recall_min"],
    )
    compare_max(
        failures,
        "selected_candidate_count",
        candidate.get("selected_candidates"),
        candidate_gates["selected_candidate_count_max"],
    )
    compare_min(
        failures,
        "selected_hard_negative_count",
        candidate.get("selected_hard_negatives"),
        candidate_gates["selected_hard_negative_count_min"],
    )
    if any(not item.get("passed") for item in candidate.get("required_candidate_decisions", [])):
        failures.append("required_candidate_decision")
    compare_min(failures, "same_object_precision", resolver.get("same_object_precision"), resolver_gates["same_object_precision_min"])
    compare_min(failures, "same_object_recall", resolver.get("same_object_recall_end_to_end"), resolver_gates["same_object_recall_min"])
    compare_min(failures, "distinct_object_accuracy", resolver.get("distinct_object_accuracy_on_candidates"), resolver_gates["distinct_object_accuracy_min"])
    compare_max(failures, "unresolved_rate", resolver.get("unresolved_rate"), resolver_gates["unresolved_rate_max"])
    compare_max(failures, "inconsistent_components", resolver.get("inconsistent_component_count"), resolver_gates["inconsistent_component_count_max"])
    compare_max(failures, "schema_failure_rate", resolver.get("schema_failure_rate"), resolver_gates["schema_failure_rate_max"])

    for metric_name, gate_name in (
        ("b_cubed_precision", "b_cubed_precision_min"),
        ("b_cubed_recall", "b_cubed_recall_min"),
        ("b_cubed_f1", "b_cubed_f1_min"),
        ("exact_gold_cluster_match_rate", "exact_gold_cluster_match_rate_min"),
        ("singleton_precision", "singleton_precision_min"),
        ("singleton_recall", "singleton_recall_min"),
    ):
        compare_min(failures, metric_name, cluster.get(metric_name), cluster_gates[gate_name])
    compare_max(failures, "false_merge", errors.get("false_merge", 0), cluster_gates["false_merge_count_max"])
    compare_max(failures, "false_split", errors.get("false_split", 0), cluster_gates["false_split_count_max"])
    for key in (
        "mention_coverage",
        "duplicate_assignments",
        "orphan_mentions",
        "lost_provenance_mentions",
        "cross_type_clusters",
    ):
        if integrity.get(key) != cluster_gates[key]:
            failures.append(key)

    exact_rate = exact_evidence / total_evidence if total_evidence else None
    compare_min(failures, "exact_evidence_materialization", exact_rate, evidence_gates["exact_materialization_rate_min"])
    audit_counts = evidence_audit.get("counts", {})
    reviewed = audit_counts.get("reviewed_candidates", 0)
    supported = audit_counts.get("supported", 0)
    support_rate = supported / reviewed if reviewed else None
    compare_min(failures, "semantic_evidence_support", support_rate, evidence_gates["semantic_support_rate_min"])
    compare_max(failures, "evidence_pending", audit_counts.get("pending"), evidence_gates["pending_count_max"])
    stale_unused = audit_counts.get("stale_decisions", 0) + audit_counts.get("unused_decisions", 0)
    compare_max(failures, "stale_or_unused_evidence_decisions", stale_unused, evidence_gates["stale_or_unused_decisions_max"])
    if evidence_audit.get("status") != "final" or evidence_audit.get("reviewed_blind") is not True:
        failures.append("blind_evidence_audit")

    for gate_name, required in criteria["determinism_gates"].items():
        if required and determinism.get("checks", {}).get(gate_name) is not True:
            failures.append(gate_name)
    if determinism.get("status") != "final":
        failures.append("determinism_report")
    return sorted(set(failures))


def build_result(
    *, resolution_dir: Path, cluster_dir: Path, evaluation_dir: Path,
    review_dir: Path, determinism_path: Path,
) -> dict[str, Any]:
    paths = {
        "preflight": BASE / "preflight_complete.json",
        "benchmark_completion": BENCHMARK / "benchmark_complete.json",
        "success_criteria": BENCHMARK / "success_criteria.json",
        "pipeline_manifest": BASE / "full_pipeline_manifest_v0_1.json",
        "candidate_completion": RUN_ROOT / "candidates/candidate_generation_complete.json",
        "resolution_completion": resolution_dir / "resolution_complete.json",
        "identity_decisions": resolution_dir / "output/identity_decisions.json",
        "resolution_metadata": resolution_dir / "metadata/run_metadata.json",
        "cluster_completion": cluster_dir / "generation_complete.json",
        "canonical_clusters": cluster_dir / "canonical_clusters.json",
        "mention_assignments": cluster_dir / "mention_assignments.json",
        "metrics": evaluation_dir / "metrics.json",
        "evaluation_completion": evaluation_dir / "evaluation_complete.json",
        "evidence_review_set": review_dir / "blind_review_set.json",
        "evidence_adjudication": review_dir / "adjudication_resolved.json",
        "evidence_audit": review_dir / "evidence_semantic_audit.json",
        "determinism_report": determinism_path,
    }
    preflight = load_json(paths["preflight"], label="preflight")
    pipeline = load_json(paths["pipeline_manifest"], label="pipeline manifest")
    criteria = load_json(paths["success_criteria"], label="success criteria")
    resolution = load_json(paths["resolution_completion"], label="resolution completion")
    metadata = load_json(paths["resolution_metadata"], label="resolution metadata")
    cluster = load_json(paths["cluster_completion"], label="cluster completion")
    evaluation = load_json(paths["evaluation_completion"], label="evaluation completion")
    metrics = load_json(paths["metrics"], label="metrics")
    decisions = load_json(paths["identity_decisions"], label="identity decisions")
    review_set = load_json(paths["evidence_review_set"], label="blind Evidence review set")
    evidence_audit = load_json(paths["evidence_audit"], label="Evidence audit")
    determinism = load_json(paths["determinism_report"], label="determinism report")

    if preflight.get("status") != "frozen_pre_execution" or preflight.get("model_run_started") is not False:
        raise IndependentValidationError("Independent preflight is invalid.")
    if preflight.get("artifacts", {}).get("full_pipeline_manifest") != binding(paths["pipeline_manifest"]):
        raise IndependentValidationError("Preflight binds a stale pipeline manifest.")
    if resolution.get("status") != "final" or cluster.get("status") != "final" or evaluation.get("status") != "final":
        raise IndependentValidationError("A structural completion marker is not final.")
    if metadata.get("run_status") != "completed" or metadata.get("git_dirty_at_start") is not False:
        raise IndependentValidationError("Formal resolver run was not clean and completed.")
    if metadata.get("git_commit_at_start") != metadata.get("method_commit"):
        raise IndependentValidationError("Resolver execution commit is inconsistent.")
    selected = pipeline["selected_resolver"]
    if metadata.get("method_id") != selected["method_id"]:
        raise IndependentValidationError("Resolver method ID differs from the frozen pipeline.")
    if metadata.get("runner", {}).get("sha256") != selected["runner_sha256"]:
        raise IndependentValidationError("Resolver runner differs from the frozen pipeline.")
    if metadata.get("inputs", {}).get("prompt", {}).get("sha256") != selected["prompt_sha256"]:
        raise IndependentValidationError("Resolver prompt differs from the frozen pipeline.")
    if metadata.get("request_parameters") != {
        key: pipeline["model_request"][key]
        for key in ("model", "temperature", "top_p", "max_tokens", "response_format", "thinking")
    }:
        raise IndependentValidationError("Resolver request parameters differ from the freeze.")
    if metadata.get("candidate_count") != 7 or metadata.get("completed_candidate_count") != 7:
        raise IndependentValidationError("Resolver candidate denominator is invalid.")
    if not all(
        metadata.get(key) is True
        for key in ("request_success", "json_parse_success", "prediction_schema_valid")
    ) or metadata.get("finish_reason") != "stop":
        raise IndependentValidationError("Resolver request integrity gate failed.")
    if resolution.get("artifacts", {}).get("identity_decisions") != binding(paths["identity_decisions"]):
        raise IndependentValidationError("Resolution completion is stale.")
    if cluster.get("artifacts", {}).get("canonical_clusters") != binding(paths["canonical_clusters"]):
        raise IndependentValidationError("Cluster completion is stale.")
    if cluster.get("artifacts", {}).get("mention_assignments") != binding(paths["mention_assignments"]):
        raise IndependentValidationError("Cluster assignments are stale.")
    if evaluation.get("outputs", {}).get("metrics") != binding(paths["metrics"]):
        raise IndependentValidationError("Evaluation completion is stale.")
    if review_set.get("prediction_sha256") != sha256_file(paths["identity_decisions"]):
        raise IndependentValidationError("Blind review set is stale.")
    if evidence_audit.get("prediction_sha256") != sha256_file(paths["identity_decisions"]):
        raise IndependentValidationError("Evidence audit targets a stale prediction.")
    if evidence_audit.get("review_set_sha256") != sha256_file(paths["evidence_review_set"]):
        raise IndependentValidationError("Evidence audit targets a stale review set.")
    if evidence_audit.get("adjudication_sha256") != sha256_file(paths["evidence_adjudication"]):
        raise IndependentValidationError("Evidence audit targets a stale adjudication.")

    lecture_binding = load_json(paths["benchmark_completion"], label="benchmark completion")["lecture_inventory"]
    lecture_inventory_path = ROOT / lecture_binding["path"]
    if binding(lecture_inventory_path) != lecture_binding:
        raise IndependentValidationError("Frozen lecture inventory is stale.")
    exact, total = exact_evidence_counts(
        decisions,
        load_json(lecture_inventory_path, label="lecture inventory"),
    )
    failures = evaluate_gates(
        metrics=metrics,
        criteria=criteria,
        evidence_audit=evidence_audit,
        determinism=determinism,
        exact_evidence=exact,
        total_evidence=total,
    )
    return {
        "artifact_type": "ko_independent_canonicalization_validation_complete",
        "version": "v0.1",
        "status": "final",
        "validation_result": "passed" if not failures else "failed",
        "pipeline_id": pipeline["pipeline_id"],
        "execution_commit": metadata["method_commit"],
        "gate_failures": failures,
        "evidence_summary": {
            "exact_materialized_spans": exact,
            "total_materialized_spans": total,
            "exact_materialization_rate": exact / total if total else None,
            "semantic_review": evidence_audit["counts"],
        },
        "claim_boundary": (
            "Passing supports independent locked reuse on this pre-existing four-lecture "
            "source. Its one positive identity pair does not establish broad "
            "generalization, run-to-run stability, or production readiness."
        ),
        "artifacts": {name: binding(path) for name, path in paths.items()},
        "finalizer": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output).resolve()
    try:
        if output.exists() and not args.overwrite:
            raise IndependentValidationError(f"Refusing to overwrite: {display_path(output)}")
        result = build_result(
            resolution_dir=Path(args.resolution_run_dir).resolve(),
            cluster_dir=Path(args.cluster_dir).resolve(),
            evaluation_dir=Path(args.evaluation_dir).resolve(),
            review_dir=Path(args.evidence_review_dir).resolve(),
            determinism_path=Path(args.determinism_report).resolve(),
        )
        atomic_write(output, result)
    except IndependentValidationError as exc:
        print(f"002C-5 finalization failed: {exc}")
        return 1
    print(f"Wrote 002C-5 result: {result['validation_result']}")
    return 0 if result["validation_result"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
