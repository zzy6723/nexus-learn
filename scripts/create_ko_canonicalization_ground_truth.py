#!/usr/bin/env python3
"""Create a deterministic cluster-annotation scaffold from a KO mention inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_candidate_pair_universe import display_path, sha256_file  # noqa: E402


DEFAULT_MENTION_INVENTORY = (
    ROOT / "benchmark" / "ko_mentions" / "development_v0_1" / "mention_inventory.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "ko_canonicalization_development_v0_1.json"
)
ANNOTATION_GUIDELINES = ROOT / "benchmark" / "ko_canonicalization_annotation_guidelines.md"
EVALUATION_PROTOCOL = ROOT / "benchmark" / "ko_canonicalization_protocol.md"
MENTION_SCHEMA = ROOT / "benchmark" / "schema" / "ko_mention_inventory.schema.json"
GROUND_TRUTH_SCHEMA = (
    ROOT / "benchmark" / "schema" / "ko_canonicalization_ground_truth.schema.json"
)
ALLOWED_TYPES = ["Concept", "Method", "Formula"]
DOCUMENT_VERSIONS = {
    ANNOTATION_GUIDELINES: "ko_canonicalization_annotation_v0.1",
    EVALUATION_PROTOCOL: "ko_canonicalization_protocol_v0.1",
    MENTION_SCHEMA: "v0.1",
    GROUND_TRUTH_SCHEMA: "v0.1",
}


class CanonicalizationScaffoldError(ValueError):
    """Raised when the scaffold cannot be created without ambiguity."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", default=str(DEFAULT_MENTION_INVENTORY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--merge",
        action="append",
        default=[],
        metavar="MENTION_ID,MENTION_ID",
        help="Comma-separated mention IDs that form one reviewed identity cluster.",
    )
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="Mark every generated cluster final after a completed human review.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalizationScaffoldError(
            f"Unable to read {label} {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise CanonicalizationScaffoldError(f"{label} must be a JSON object.")
    return value


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
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def parse_merge_groups(
    raw_groups: list[str],
    *,
    known_mentions: set[str],
) -> list[list[str]]:
    groups: list[list[str]] = []
    claimed: set[str] = set()
    for index, raw_group in enumerate(raw_groups):
        group = [item.strip() for item in raw_group.split(",") if item.strip()]
        if len(group) < 2:
            raise CanonicalizationScaffoldError(
                f"--merge entry {index + 1} requires at least two mention IDs."
            )
        if len(group) != len(set(group)):
            raise CanonicalizationScaffoldError(
                f"--merge entry {index + 1} contains a duplicate mention ID."
            )
        unknown = sorted(set(group) - known_mentions)
        if unknown:
            raise CanonicalizationScaffoldError(
                f"--merge entry {index + 1} contains unknown mentions: {unknown}."
            )
        overlap = sorted(set(group) & claimed)
        if overlap:
            raise CanonicalizationScaffoldError(
                f"Mention IDs occur in multiple merge groups: {overlap}."
            )
        claimed.update(group)
        groups.append(group)
    return groups


def build_clusters(
    mentions: list[dict[str, Any]],
    *,
    raw_merge_groups: list[str],
    frozen: bool,
) -> list[dict[str, Any]]:
    mention_by_id = {item["mention_id"]: item for item in mentions}
    if len(mention_by_id) != len(mentions):
        raise CanonicalizationScaffoldError("Mention inventory has duplicate mention IDs.")
    order = {item["mention_id"]: index for index, item in enumerate(mentions)}
    groups = parse_merge_groups(
        raw_merge_groups,
        known_mentions=set(mention_by_id),
    )
    group_by_member: dict[str, list[str]] = {}
    for group in groups:
        ordered_group = sorted(group, key=order.__getitem__)
        types = {mention_by_id[mention_id]["type"] for mention_id in ordered_group}
        if len(types) != 1:
            raise CanonicalizationScaffoldError(
                f"Cross-type merge is forbidden: {ordered_group}."
            )
        for mention_id in ordered_group:
            group_by_member[mention_id] = ordered_group

    partition: list[list[str]] = []
    emitted: set[str] = set()
    for mention in mentions:
        mention_id = mention["mention_id"]
        if mention_id in emitted:
            continue
        cluster_members = group_by_member.get(mention_id, [mention_id])
        partition.append(cluster_members)
        emitted.update(cluster_members)

    split_token = "dev" if mentions[0]["mention_id"].startswith("ko_mention_dev_") else "holdout"
    clusters: list[dict[str, Any]] = []
    for cluster_number, member_ids in enumerate(partition, start=1):
        members = [mention_by_id[mention_id] for mention_id in member_ids]
        first = members[0]
        if len(members) == 1:
            rationale = (
                "No other mention in the reviewed inventory denotes the same "
                f"{first['type']} at the same educational granularity."
            )
        else:
            contexts = ", ".join(item["lecture_id"] for item in members)
            rationale = (
                f"The {len(members)} mentions denote the same {first['type']} "
                f"across these lecture contexts: {contexts}."
            )
        clusters.append(
            {
                "canonical_id": f"canonical_ko_{split_token}_{cluster_number:03d}",
                "canonical_name": first["name"],
                "canonical_type": first["type"],
                "mention_ids": member_ids,
                "aliases": [],
                "annotation_status": "final" if frozen else "draft",
                "identity_rationale": rationale if frozen else "Pending identity review.",
                "notes": "",
            }
        )
    return clusters


def document_binding(path: Path) -> dict[str, str]:
    return {
        "path": display_path(path),
        "version": DOCUMENT_VERSIONS[path],
        "sha256": sha256_file(path),
    }


def build_ground_truth(
    inventory: dict[str, Any],
    *,
    inventory_path: Path,
    raw_merge_groups: list[str],
    frozen: bool,
) -> dict[str, Any]:
    if inventory.get("artifact_type") != "ko_mention_inventory":
        raise CanonicalizationScaffoldError("Input is not a KO mention inventory.")
    mentions = inventory.get("mentions")
    if not isinstance(mentions, list) or not mentions:
        raise CanonicalizationScaffoldError("Mention inventory has no mentions.")
    return {
        "artifact_type": "ko_canonicalization_ground_truth",
        "version": "v0.1",
        "benchmark_split": inventory.get("benchmark_split"),
        "status": "frozen" if frozen else "draft_annotation_required",
        "mention_inventory": {
            "path": display_path(inventory_path),
            "sha256": sha256_file(inventory_path),
        },
        "annotation_guidelines": document_binding(ANNOTATION_GUIDELINES),
        "evaluation_protocol": document_binding(EVALUATION_PROTOCOL),
        "schema_bindings": {
            "mention_inventory": document_binding(MENTION_SCHEMA),
            "ground_truth": document_binding(GROUND_TRUTH_SCHEMA),
        },
        "identity_policy": {
            "cluster_annotation": "authoritative",
            "canonical_id_scheme": "opaque_sequential_in_first_mention_order",
            "cross_type_merge": "forbidden",
            "singleton_records": "required",
            "provenance_retention": "through_complete_mention_membership",
        },
        "allowed_types": ALLOWED_TYPES,
        "clusters": build_clusters(
            mentions,
            raw_merge_groups=raw_merge_groups,
            frozen=frozen,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    output_path = Path(args.output).resolve()
    try:
        if output_path.exists() and not args.overwrite:
            raise CanonicalizationScaffoldError(
                f"Refusing to overwrite: {display_path(output_path)}."
            )
        inventory = load_json_object(inventory_path, label="mention inventory")
        ground_truth = build_ground_truth(
            inventory,
            inventory_path=inventory_path,
            raw_merge_groups=args.merge,
            frozen=args.frozen,
        )
        atomic_write(output_path, ground_truth)
    except CanonicalizationScaffoldError as exc:
        print(f"Canonicalization scaffold generation failed: {exc}")
        return 1

    print(
        f"Wrote {len(ground_truth['clusters'])} canonical clusters to "
        f"{display_path(output_path)}"
    )
    print(f"Ground Truth status: {ground_truth['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
