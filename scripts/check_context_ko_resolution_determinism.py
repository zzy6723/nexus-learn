#!/usr/bin/env python3
"""Check run-specific canonical assignment and ID order invariance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "context_ko_resolution_determinism_checker_v0.1"


class DeterminismCheckError(ValueError):
    """Raised when run artifacts are stale or order invariance fails."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", required=True)
    parser.add_argument("--normalization-config", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--resolution-run-dir", required=True)
    parser.add_argument("--cluster-dir", required=True)
    parser.add_argument("--output", required=True)
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
        raise DeterminismCheckError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeterminismCheckError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DeterminismCheckError(f"{label} must be a JSON object.")
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


def semantic_maps(
    *, inventory: dict[str, Any], candidates: dict[str, Any],
    decisions: list[dict[str, Any]], normalization: dict[str, Any]
) -> tuple[dict[str, str], dict[frozenset[str], str]]:
    from scripts.finalize_context_ko_clusters import (
        build_cluster_artifacts,
        provisional_components,
    )

    mention_ids = [item["mention_id"] for item in inventory["mentions"]]
    groups, contradictions = provisional_components(mention_ids, candidates, decisions)
    if contradictions:
        raise DeterminismCheckError("Identity decisions contain a contradiction.")
    prediction, assignments, _ = build_cluster_artifacts(
        inventory, groups, normalization
    )
    assignment_map = {
        item["mention_id"]: item["canonical_id"]
        for item in assignments["assignments"]
    }
    cluster_map = {
        frozenset(item["mention_ids"]): item["canonical_id"]
        for item in prediction["clusters"]
    }
    return assignment_map, cluster_map


def build_report(
    *, inventory_path: Path, normalization_path: Path, candidate_dir: Path,
    resolution_dir: Path, cluster_dir: Path
) -> dict[str, Any]:
    inventory = load_json(inventory_path, label="mention inventory")
    normalization = load_json(normalization_path, label="normalization config")
    candidates_path = candidate_dir / "candidate_pairs.json"
    decisions_path = resolution_dir / "output/identity_decisions.json"
    cluster_path = cluster_dir / "canonical_clusters.json"
    assignments_path = cluster_dir / "mention_assignments.json"
    cluster_completion_path = cluster_dir / "generation_complete.json"
    candidates = load_json(candidates_path, label="candidate pairs")
    decisions_artifact = load_json(decisions_path, label="identity decisions")
    stored_clusters = load_json(cluster_path, label="canonical clusters")
    stored_assignments = load_json(assignments_path, label="mention assignments")
    cluster_completion = load_json(cluster_completion_path, label="cluster completion")
    if cluster_completion.get("status") != "final":
        raise DeterminismCheckError("Cluster artifact is not final.")
    if cluster_completion.get("artifacts", {}).get("canonical_clusters") != binding(cluster_path):
        raise DeterminismCheckError("Cluster completion binds stale clusters.")
    if cluster_completion.get("artifacts", {}).get("mention_assignments") != binding(assignments_path):
        raise DeterminismCheckError("Cluster completion binds stale assignments.")
    decisions = decisions_artifact.get("results")
    if not isinstance(decisions, list):
        raise DeterminismCheckError("Identity decisions must contain results.")

    baseline = semantic_maps(
        inventory=inventory,
        candidates=candidates,
        decisions=decisions,
        normalization=normalization,
    )
    reversed_inventory = {
        **inventory,
        "mentions": list(reversed(inventory["mentions"])),
    }
    mention_reversed = semantic_maps(
        inventory=reversed_inventory,
        candidates=candidates,
        decisions=decisions,
        normalization=normalization,
    )
    decision_reversed = semantic_maps(
        inventory=inventory,
        candidates=candidates,
        decisions=list(reversed(decisions)),
        normalization=normalization,
    )
    reversed_candidates = {
        **candidates,
        "candidates": list(reversed(candidates["candidates"])),
    }
    candidate_reversed = semantic_maps(
        inventory=inventory,
        candidates=reversed_candidates,
        decisions=decisions,
        normalization=normalization,
    )
    stored_assignment_map = {
        item["mention_id"]: item["canonical_id"]
        for item in stored_assignments["assignments"]
    }
    stored_cluster_map = {
        frozenset(item["mention_ids"]): item["canonical_id"]
        for item in stored_clusters["clusters"]
    }
    stored = (stored_assignment_map, stored_cluster_map)
    checks = {
        "stored_output_matches_recomputed_semantics": stored == baseline,
        "canonical_assignment_invariant_to_mention_order": mention_reversed[0] == baseline[0],
        "canonical_id_invariant_to_mention_order": mention_reversed[1] == baseline[1],
        "cluster_identity_invariant_to_candidate_decision_order": decision_reversed == baseline,
        "cluster_identity_invariant_to_candidate_manifest_order": candidate_reversed == baseline,
    }
    return {
        "artifact_type": "ko_context_resolution_determinism_report",
        "version": "v0.1",
        "status": "final" if all(checks.values()) else "failed",
        "checks": checks,
        "counts": {
            "mentions": len(inventory["mentions"]),
            "candidates": len(candidates["candidates"]),
            "canonical_clusters": len(stored_clusters["clusters"]),
        },
        "inputs": {
            "mention_inventory": binding(inventory_path),
            "normalization_config": binding(normalization_path),
            "candidate_pairs": binding(candidates_path),
            "identity_decisions": binding(decisions_path),
            "cluster_completion": binding(cluster_completion_path),
        },
        "checker": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output).resolve()
    try:
        if output.exists() and not args.overwrite:
            raise DeterminismCheckError(f"Refusing to overwrite: {display_path(output)}")
        report = build_report(
            inventory_path=Path(args.mention_inventory).resolve(),
            normalization_path=Path(args.normalization_config).resolve(),
            candidate_dir=Path(args.candidate_dir).resolve(),
            resolution_dir=Path(args.resolution_run_dir).resolve(),
            cluster_dir=Path(args.cluster_dir).resolve(),
        )
        atomic_write(output, report)
    except DeterminismCheckError as exc:
        print(f"Determinism check failed: {exc}")
        return 1
    print(f"Wrote determinism report with status: {report['status']}")
    return 0 if report["status"] == "final" else 2


if __name__ == "__main__":
    raise SystemExit(main())
