#!/usr/bin/env python3
"""Materialize explicit locked-reuse KO clusters from a reviewed annotation plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_GUIDELINES = ROOT / "benchmark" / "ko_canonicalization_annotation_guidelines.md"
EVALUATION_PROTOCOL = ROOT / "benchmark" / "ko_canonicalization_protocol.md"
MENTION_SCHEMA = ROOT / "benchmark" / "schema" / "ko_mention_inventory.schema.json"
GROUND_TRUTH_SCHEMA = ROOT / "benchmark" / "schema" / "ko_canonicalization_ground_truth.schema.json"
GENERATOR_VERSION = "ko_locked_reuse_ground_truth_generator_v0.1"


class GroundTruthCreationError(ValueError):
    """Raised when the reviewed annotation plan is incomplete or inconsistent."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", required=True)
    parser.add_argument("--annotation-plan", required=True)
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


def binding(path: Path, *, version: str | None = None) -> dict[str, str]:
    value = {"path": display_path(path), "sha256": sha256_file(path)}
    if version is not None:
        value["version"] = version
    return value


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GroundTruthCreationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise GroundTruthCreationError(f"{label} must be a JSON object.")
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


def build_ground_truth(
    inventory: dict[str, Any], plan: dict[str, Any], inventory_path: Path
) -> dict[str, Any]:
    if plan.get("status") != "final_pre_method_execution" or plan.get("data_role") != "locked_reuse":
        raise GroundTruthCreationError("Annotation plan is not final locked reuse.")
    if plan.get("annotation_policy", {}).get("all_mentions_reviewed") is not True:
        raise GroundTruthCreationError("Annotation plan does not declare complete review.")
    mentions = inventory.get("mentions")
    if not isinstance(mentions, list) or not mentions:
        raise GroundTruthCreationError("Mention inventory is empty.")
    mention_by_id = {item["mention_id"]: item for item in mentions}
    order = {item["mention_id"]: index for index, item in enumerate(mentions)}
    merged: dict[str, dict[str, Any]] = {}
    assigned: set[str] = set()
    for cluster in plan.get("multi_mention_clusters", []):
        member_ids = cluster.get("mention_ids")
        if not isinstance(member_ids, list) or len(member_ids) < 2:
            raise GroundTruthCreationError("Every planned merge needs at least two mentions.")
        if any(item not in mention_by_id for item in member_ids) or assigned & set(member_ids):
            raise GroundTruthCreationError("Planned merge has unknown or duplicate mentions.")
        types = {mention_by_id[item]["type"] for item in member_ids}
        if types != {cluster.get("canonical_type")}:
            raise GroundTruthCreationError("Planned merge violates type identity.")
        first = min(member_ids, key=order.get)
        merged[first] = cluster
        assigned.update(member_ids)
    raw_clusters = []
    for mention in mentions:
        mention_id = mention["mention_id"]
        if mention_id in merged:
            planned = merged[mention_id]
            raw_clusters.append(
                {
                    "canonical_name": planned["canonical_name"],
                    "canonical_type": planned["canonical_type"],
                    "mention_ids": sorted(planned["mention_ids"], key=order.get),
                    "aliases": planned["aliases"],
                    "annotation_status": "final",
                    "identity_rationale": planned["identity_rationale"],
                    "notes": planned["notes"],
                }
            )
        elif mention_id not in assigned:
            raw_clusters.append(
                {
                    "canonical_name": mention["name"],
                    "canonical_type": mention["type"],
                    "mention_ids": [mention_id],
                    "aliases": [],
                    "annotation_status": "final",
                    "identity_rationale": (
                        "No other mention in the reviewed locked-reuse inventory denotes "
                        "the same Knowledge Object at the same educational granularity."
                    ),
                    "notes": "",
                }
            )
    clusters = [
        {"canonical_id": f"canonical_ko_dev_{index:03d}", **cluster}
        for index, cluster in enumerate(raw_clusters, start=1)
    ]
    return {
        "artifact_type": "ko_canonicalization_ground_truth",
        "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"],
        "status": "frozen",
        "mention_inventory": binding(inventory_path),
        "annotation_guidelines": binding(
            ANNOTATION_GUIDELINES, version="ko_canonicalization_annotation_v0.1"
        ),
        "evaluation_protocol": binding(
            EVALUATION_PROTOCOL, version="ko_canonicalization_protocol_v0.1"
        ),
        "schema_bindings": {
            "mention_inventory": binding(MENTION_SCHEMA, version="v0.1"),
            "ground_truth": binding(GROUND_TRUTH_SCHEMA, version="v0.1"),
        },
        "identity_policy": {
            "cluster_annotation": "authoritative",
            "canonical_id_scheme": "opaque_sequential_in_first_mention_order",
            "cross_type_merge": "forbidden",
            "singleton_records": "required",
            "provenance_retention": "through_complete_mention_membership",
        },
        "allowed_types": ["Concept", "Method", "Formula"],
        "clusters": clusters,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    plan_path = Path(args.annotation_plan).resolve()
    output_path = Path(args.output).resolve()
    try:
        if output_path.exists() and not args.overwrite:
            raise GroundTruthCreationError(f"Refusing to overwrite: {display_path(output_path)}")
        ground_truth = build_ground_truth(
            load_json(inventory_path, label="mention inventory"),
            load_json(plan_path, label="annotation plan"),
            inventory_path,
        )
        atomic_write(output_path, ground_truth)
    except GroundTruthCreationError as exc:
        print(f"Ground Truth creation failed: {exc}")
        return 1
    print(f"Wrote {len(ground_truth['clusters'])} locked-reuse canonical clusters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
