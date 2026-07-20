#!/usr/bin/env python3
"""Finalize the non-Git preflight for Experiment 003-0 development benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": sha256_path(path)}


def finalize(
    *,
    audit_path: Path,
    success_criteria_path: Path,
    source_manifest_path: Path,
    canonical_inventory_path: Path,
    pair_universe_path: Path,
    evidence_catalogs_path: Path,
    ground_truth_path: Path,
    annotation_spec_path: Path,
    annotation_protocol_path: Path,
    evaluation_protocol_path: Path,
    schema_paths: list[Path],
) -> dict[str, Any]:
    audit = load_json(audit_path)
    success = load_json(success_criteria_path)
    ground_truth = load_json(ground_truth_path)
    if audit.get("freeze_ready") is not True or audit.get("errors"):
        raise ValueError("Annotation audit is not freeze-ready.")
    if success.get("status") != "ready_to_freeze":
        raise ValueError("Success criteria are not ready to freeze.")
    if success.get("benchmark_binding", {}).get("sha256") != sha256_path(
        ground_truth_path
    ):
        raise ValueError("Success criteria are stale relative to Ground Truth.")
    if success.get("frozen_denominators", {}).get("primary_scored_pairs") != ground_truth.get(
        "counts", {}
    ).get("primary_scored_pairs"):
        raise ValueError("Success-criteria denominator does not match Ground Truth.")

    ready_artifacts = [
        source_manifest_path,
        canonical_inventory_path,
        pair_universe_path,
        evidence_catalogs_path,
        ground_truth_path,
        annotation_spec_path,
    ]
    for path in ready_artifacts:
        if load_json(path).get("status") != "ready_to_freeze":
            raise ValueError(f"Artifact is not ready to freeze: {path}")
    for path in schema_paths:
        load_json(path)

    return {
        "artifact_type": "connection_discovery_benchmark_preflight",
        "version": "v0.1",
        "status": "ready_for_repository_freeze",
        "model_execution_allowed": False,
        "next_gate": (
            "Record the clean repository freeze commit, then bind a frozen execution "
            "manifest before any Experiment 003 model call."
        ),
        "counts": ground_truth["counts"],
        "scope_limitations": audit.get("scope_limitations", []),
        "artifacts": {
            "source_manifest": artifact(source_manifest_path),
            "oracle_canonical_inventory": artifact(canonical_inventory_path),
            "pair_universe": artifact(pair_universe_path),
            "evidence_catalogs": artifact(evidence_catalogs_path),
            "annotation_spec": artifact(annotation_spec_path),
            "ground_truth": artifact(ground_truth_path),
            "annotation_review_audit": artifact(audit_path),
            "success_criteria": artifact(success_criteria_path),
            "annotation_protocol": artifact(annotation_protocol_path),
            "evaluation_protocol": artifact(evaluation_protocol_path),
            "schemas": [artifact(path) for path in schema_paths],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--success-criteria", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--canonical-inventory", required=True, type=Path)
    parser.add_argument("--pair-universe", required=True, type=Path)
    parser.add_argument("--evidence-catalogs", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--annotation-spec", required=True, type=Path)
    parser.add_argument("--annotation-protocol", required=True, type=Path)
    parser.add_argument("--evaluation-protocol", required=True, type=Path)
    parser.add_argument("--schema", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = finalize(
        audit_path=args.audit,
        success_criteria_path=args.success_criteria,
        source_manifest_path=args.source_manifest,
        canonical_inventory_path=args.canonical_inventory,
        pair_universe_path=args.pair_universe,
        evidence_catalogs_path=args.evidence_catalogs,
        ground_truth_path=args.ground_truth,
        annotation_spec_path=args.annotation_spec,
        annotation_protocol_path=args.annotation_protocol,
        evaluation_protocol_path=args.evaluation_protocol,
        schema_paths=args.schema,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"003-0 preflight status: {result['status']}")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
