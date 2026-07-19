#!/usr/bin/env python3
"""Finalize context identity decisions into provenance-complete KO clusters."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_deterministic_ko_canonicalization import (
    normalize_name,
    stable_cluster_id,
    validate_normalization_config,
)


FINALIZER_VERSION = "context_ko_cluster_finalizer_v0.1"
DEFAULT_METHOD_ID = "candidate_scoped_context_resolution_v0_1"


class ClusterFinalizationError(ValueError):
    """Raised when identity decisions cannot be safely finalized."""


class UnionFind:
    def __init__(self, members: list[str]) -> None:
        self.parent = {item: item for item in members}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", required=True)
    parser.add_argument("--normalization-config", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--resolution-run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--adjudication")
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
        raise ClusterFinalizationError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClusterFinalizationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ClusterFinalizationError(f"{label} must be a JSON object.")
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


def validate_sources(
    candidate_dir: Path, resolution_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidate_marker = load_json(
        candidate_dir / "candidate_generation_complete.json", label="candidate marker"
    )
    if candidate_marker.get("status") != "final":
        raise ClusterFinalizationError("Candidate bundle is not final.")
    candidates = load_json(candidate_dir / "candidate_pairs.json", label="candidates")
    resolution_marker = load_json(
        resolution_dir / "resolution_complete.json", label="resolution marker"
    )
    decisions_path = resolution_dir / "output" / "identity_decisions.json"
    metadata_path = resolution_dir / "metadata" / "run_metadata.json"
    if resolution_marker.get("status") != "final" or resolution_marker.get("artifacts") != {
        "identity_decisions": binding(decisions_path),
        "metadata": binding(metadata_path),
    }:
        raise ClusterFinalizationError("Resolution completion marker is stale.")
    decisions = load_json(decisions_path, label="identity decisions")
    metadata = load_json(metadata_path, label="resolution metadata")
    if metadata.get("run_status") != "completed":
        raise ClusterFinalizationError("Resolution run is not completed.")
    expected = {item["candidate_id"] for item in candidates["candidates"]}
    results = decisions.get("results")
    if not isinstance(results, list) or {item.get("candidate_id") for item in results} != expected:
        raise ClusterFinalizationError("Resolution decisions do not align with candidates.")
    return candidates, decisions, metadata


def apply_adjudication(
    results: list[dict[str, Any]], adjudication_path: Path | None
) -> tuple[list[dict[str, Any]], int]:
    by_id = {item["candidate_id"]: dict(item) for item in results}
    unresolved = {item["candidate_id"] for item in results if item["decision"] == "UNRESOLVED"}
    if adjudication_path is None:
        return list(by_id.values()), 0
    adjudication = load_json(adjudication_path, label="adjudication")
    if adjudication.get("prediction_sha256") is None:
        raise ClusterFinalizationError("Adjudication is not snapshot-bound.")
    decisions = adjudication.get("decisions")
    if not isinstance(decisions, list):
        raise ClusterFinalizationError("Adjudication decisions must be a list.")
    used: set[str] = set()
    for item in decisions:
        candidate_id = item.get("candidate_id")
        if candidate_id not in by_id or candidate_id in used:
            raise ClusterFinalizationError("Adjudication contains stale or duplicate IDs.")
        if item.get("decision") not in {"SAME_OBJECT", "DISTINCT_OBJECT"}:
            raise ClusterFinalizationError("Adjudication decision must be resolved.")
        if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
            raise ClusterFinalizationError("Adjudication rationale is required.")
        by_id[candidate_id]["decision"] = item["decision"]
        by_id[candidate_id]["adjudicated"] = True
        used.add(candidate_id)
    if unresolved - used:
        raise ClusterFinalizationError("Adjudication does not resolve every UNRESOLVED pair.")
    return list(by_id.values()), len(used)


def provisional_components(
    mention_ids: list[str], candidates: dict[str, Any], decisions: list[dict[str, Any]]
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    candidate_by_id = {item["candidate_id"]: item for item in candidates["candidates"]}
    union = UnionFind(mention_ids)
    for result in decisions:
        if result["decision"] == "SAME_OBJECT":
            candidate = candidate_by_id[result["candidate_id"]]
            union.union(candidate["mention_a"]["mention_id"], candidate["mention_b"]["mention_id"])
    groups: dict[str, list[str]] = defaultdict(list)
    for mention_id in mention_ids:
        groups[union.find(mention_id)].append(mention_id)
    contradictions = []
    for result in decisions:
        if result["decision"] != "DISTINCT_OBJECT":
            continue
        candidate = candidate_by_id[result["candidate_id"]]
        left = candidate["mention_a"]["mention_id"]
        right = candidate["mention_b"]["mention_id"]
        if union.find(left) == union.find(right):
            contradictions.append(
                {"candidate_id": result["candidate_id"], "mention_ids": [left, right]}
            )
    return groups, contradictions


def build_cluster_artifacts(
    inventory: dict[str, Any], groups: dict[str, list[str]], normalization: dict[str, Any],
    *, method_id: str = DEFAULT_METHOD_ID, method_version: str = "v0.1",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    mentions = inventory["mentions"]
    mention_by_id = {item["mention_id"]: item for item in mentions}
    order = {item["mention_id"]: index for index, item in enumerate(mentions)}
    wrappers = validate_normalization_config(normalization)
    ordered_groups = sorted(groups.values(), key=lambda group: min(order[item] for item in group))
    clusters = []
    assignments = []
    audit_records = []
    cluster_by_mention: dict[str, str] = {}
    for member_ids in ordered_groups:
        member_ids = sorted(member_ids, key=order.get)
        first = mention_by_id[member_ids[0]]
        cluster_id = stable_cluster_id(
            ko_type=first["type"], identity_key="context_identity_component",
            mention_ids=member_ids,
        )
        clusters.append(
            {
                "canonical_id": cluster_id,
                "canonical_name": first["name"],
                "canonical_type": first["type"],
                "normalized_identity_key": "context_identity_component",
                "mention_ids": member_ids,
                "mention_provenance": [mention_by_id[item] for item in member_ids],
            }
        )
        for mention_id in member_ids:
            cluster_by_mention[mention_id] = cluster_id
            assignments.append({"mention_id": mention_id, "canonical_id": cluster_id})
    assignments.sort(key=lambda item: order[item["mention_id"]])
    for mention in mentions:
        normalized, operations = normalize_name(mention["name"], wrappers=wrappers)
        audit_records.append(
            {
                "mention_id": mention["mention_id"], "original_name": mention["name"],
                "normalized_name": normalized, "identity_key": "context_identity_component",
                "type": mention["type"], "normalization_operations": operations,
                "assigned_cluster_id": cluster_by_mention[mention["mention_id"]],
            }
        )
    counts = {
        "mentions": len(mentions), "clusters": len(clusters),
        "singleton_clusters": sum(len(item["mention_ids"]) == 1 for item in clusters),
        "multi_mention_clusters": sum(len(item["mention_ids"]) > 1 for item in clusters),
    }
    prediction = {
        "artifact_type": "ko_canonicalization_prediction", "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"],
        "cluster_order": "ascending_first_mention_inventory_index",
        "method": {"method_id": method_id, "version": method_version, "merge_rule": "same_object_connected_components", "uses_alias_resource": False},
        "counts": counts, "clusters": clusters,
    }
    assignment_artifact = {
        "artifact_type": "ko_canonicalization_assignments", "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"], "method_id": method_id,
        "assignments": assignments,
    }
    audit = {
        "artifact_type": "ko_name_normalization_audit", "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"], "method_id": method_id,
        "records": audit_records,
    }
    return prediction, assignment_artifact, audit


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    normalization_path = Path(args.normalization_config).resolve()
    candidate_dir = Path(args.candidate_dir).resolve()
    resolution_dir = Path(args.resolution_run_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    adjudication_path = Path(args.adjudication).resolve() if args.adjudication else None
    paths = {
        "prediction": output_dir / "canonical_clusters.json",
        "assignments": output_dir / "mention_assignments.json",
        "audit": output_dir / "normalization_audit.json",
        "decision_audit": output_dir / "decision_audit.json",
        "pending": output_dir / "adjudication_pending.json",
        "metadata": output_dir / "metadata.json",
        "completion": output_dir / "generation_complete.json",
    }
    try:
        existing = [path for path in paths.values() if path.exists()]
        if existing and not args.overwrite:
            raise ClusterFinalizationError("Refusing to overwrite cluster artifacts.")
        if args.overwrite:
            for path in existing:
                path.unlink()
        inventory = load_json(inventory_path, label="mention inventory")
        normalization = load_json(normalization_path, label="normalization")
        candidates, raw_decisions, resolution_metadata = validate_sources(candidate_dir, resolution_dir)
        decisions_path = resolution_dir / "output" / "identity_decisions.json"
        if adjudication_path:
            adjudication = load_json(adjudication_path, label="adjudication")
            if adjudication.get("prediction_sha256") != sha256_file(decisions_path):
                raise ClusterFinalizationError("Adjudication targets a stale prediction snapshot.")
        decisions, adjudicated_count = apply_adjudication(
            raw_decisions["results"], adjudication_path
        )
        mention_ids = [item["mention_id"] for item in inventory["mentions"]]
        groups, contradictions = provisional_components(mention_ids, candidates, decisions)
        unresolved = [item["candidate_id"] for item in decisions if item["decision"] == "UNRESOLVED"]
        if unresolved or contradictions:
            pending = {
                "artifact_type": "ko_context_resolution_adjudication_pending", "version": "v0.1",
                "prediction_sha256": sha256_file(decisions_path),
                "unresolved_candidate_ids": unresolved,
                "inconsistent_components": contradictions,
            }
            atomic_write(paths["pending"], pending)
            print("Cluster finalization pending adjudication.")
            return 2
        method_id = resolution_metadata.get("method_id", DEFAULT_METHOD_ID)
        if not isinstance(method_id, str) or not method_id.strip():
            raise ClusterFinalizationError("Resolution metadata has no valid method_id.")
        method_version = resolution_metadata.get("version", "v0.1")
        if not isinstance(method_version, str) or not method_version.strip():
            raise ClusterFinalizationError("Resolution metadata has no valid version.")
        prediction, assignments, audit = build_cluster_artifacts(
            inventory, groups, normalization,
            method_id=method_id, method_version=method_version,
        )
        atomic_write(paths["prediction"], prediction)
        atomic_write(paths["assignments"], assignments)
        atomic_write(paths["audit"], audit)
        atomic_write(
            paths["decision_audit"],
            {
                "artifact_type": "ko_context_decision_audit", "version": "v0.1",
                "prediction_sha256": sha256_file(decisions_path),
                "adjudicated_decision_count": adjudicated_count,
                "unresolved_count": 0, "inconsistent_component_count": 0,
                "decisions": decisions,
            },
        )
        metadata = {
            "artifact_type": "ko_canonicalization_run_metadata", "version": "v0.1",
            "run_status": "completed", "method_id": method_id,
            "method_commit": resolution_metadata["method_commit"],
            "git_commit_at_start": resolution_metadata["git_commit_at_start"],
            "git_dirty_at_start": resolution_metadata["git_dirty_at_start"],
            "mention_inventory": binding(inventory_path),
            "normalization_config": binding(normalization_path), "alias_resource": None,
            "runner": {**binding(Path(__file__).resolve()), "version": FINALIZER_VERSION},
            "source_resolution": binding(decisions_path),
            "candidate_bundle": binding(candidate_dir / "candidate_pairs.json"),
            "decision_audit": binding(paths["decision_audit"]),
            "counts": prediction["counts"],
        }
        atomic_write(paths["metadata"], metadata)
        marker = {
            "artifact_type": "ko_canonicalization_generation_complete", "version": "v0.1",
            "status": "final", "method_id": method_id,
            "method_commit": resolution_metadata["method_commit"],
            "artifacts": {
                "canonical_clusters": binding(paths["prediction"]),
                "mention_assignments": binding(paths["assignments"]),
                "normalization_audit": binding(paths["audit"]),
                "metadata": binding(paths["metadata"]),
            },
        }
        atomic_write(paths["completion"], marker)
    except ClusterFinalizationError as exc:
        print(f"Cluster finalization failed: {exc}")
        return 1
    print(f"Finalized {prediction['counts']['clusters']} canonical KO clusters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
