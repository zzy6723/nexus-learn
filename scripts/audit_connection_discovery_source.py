#!/usr/bin/env python3
"""Audit whether a canonical KO bundle is suitable for Connection Discovery."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any


DEFAULT_SCALE_TARGETS = {
    "lectures": {"minimum": 4, "maximum": 8},
    "canonical_knowledge_objects": {"minimum": 20, "maximum": 35},
    "eligible_cross_lecture_pairs": {"minimum": 150, "maximum": 500},
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def in_range(value: int, target: dict[str, int]) -> bool:
    return target["minimum"] <= value <= target["maximum"]


def build_audit(
    canonical_bundle: dict[str, Any],
    source_manifest: dict[str, Any],
    *,
    canonical_path: str,
    source_manifest_path: str,
) -> dict[str, Any]:
    clusters = canonical_bundle.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        raise ValueError("Canonical bundle must contain a non-empty clusters list.")

    declared_lectures = source_manifest.get("lecture_ids")
    if not isinstance(declared_lectures, list) or not declared_lectures:
        raise ValueError("Source manifest must declare a non-empty lecture_ids list.")
    lecture_ids = sorted(set(declared_lectures))

    canonical_ids: set[str] = set()
    cluster_lecture_sets: dict[str, set[str]] = {}
    type_counts: Counter[str] = Counter()
    lecture_cluster_counts: Counter[str] = Counter()
    lecture_mention_counts: Counter[str] = Counter()
    exact_spans = 0
    nonexact_spans = 0
    mention_count = 0

    for cluster in clusters:
        canonical_id = cluster.get("canonical_id")
        canonical_type = cluster.get("canonical_type")
        provenance = cluster.get("mention_provenance")
        if not isinstance(canonical_id, str) or not canonical_id:
            raise ValueError("Every cluster must have a non-empty canonical_id.")
        if canonical_id in canonical_ids:
            raise ValueError(f"Duplicate canonical_id: {canonical_id}")
        if not isinstance(canonical_type, str) or not canonical_type:
            raise ValueError(f"Cluster {canonical_id} lacks canonical_type.")
        if not isinstance(provenance, list) or not provenance:
            raise ValueError(f"Cluster {canonical_id} lacks mention provenance.")

        canonical_ids.add(canonical_id)
        type_counts[canonical_type] += 1
        lectures: set[str] = set()
        for mention in provenance:
            lecture_id = mention.get("lecture_id")
            flags = mention.get("source_span_exact_flags", [])
            if lecture_id not in lecture_ids:
                raise ValueError(
                    f"Cluster {canonical_id} references undeclared lecture {lecture_id!r}."
                )
            if not isinstance(flags, list) or not all(
                isinstance(flag, bool) for flag in flags
            ):
                raise ValueError(
                    f"Mention in cluster {canonical_id} has invalid exact-span flags."
                )
            lectures.add(lecture_id)
            mention_count += 1
            lecture_mention_counts[lecture_id] += 1
            exact_spans += sum(flags)
            nonexact_spans += len(flags) - sum(flags)

        cluster_lecture_sets[canonical_id] = lectures
        for lecture_id in lectures:
            lecture_cluster_counts[lecture_id] += 1

    eligible = 0
    disjoint = 0
    overlap_bridge = 0
    ineligible_same_lecture_only = 0
    for left_id, right_id in combinations(sorted(canonical_ids), 2):
        left = cluster_lecture_sets[left_id]
        right = cluster_lecture_sets[right_id]
        is_cross_lecture = any(a != b for a in left for b in right)
        if not is_cross_lecture:
            ineligible_same_lecture_only += 1
            continue
        eligible += 1
        if left.isdisjoint(right):
            disjoint += 1
        else:
            overlap_bridge += 1

    canonical_count = len(canonical_ids)
    total_pairs = canonical_count * (canonical_count - 1) // 2
    multi_lecture_clusters = sum(
        len(lectures) > 1 for lectures in cluster_lecture_sets.values()
    )
    scale = {
        "targets": DEFAULT_SCALE_TARGETS,
        "checks": {
            "lectures_within_target": in_range(
                len(lecture_ids), DEFAULT_SCALE_TARGETS["lectures"]
            ),
            "canonical_knowledge_objects_within_target": in_range(
                canonical_count,
                DEFAULT_SCALE_TARGETS["canonical_knowledge_objects"],
            ),
            "eligible_cross_lecture_pairs_within_target": in_range(
                eligible,
                DEFAULT_SCALE_TARGETS["eligible_cross_lecture_pairs"],
            ),
        },
    }

    lecture_records = source_manifest.get("lectures")
    course_metadata_declared = (
        isinstance(lecture_records, list)
        and len(lecture_records) == len(lecture_ids)
        and all(isinstance(item, dict) and item.get("course_id") for item in lecture_records)
    )
    topic_metadata_declared = (
        isinstance(lecture_records, list)
        and len(lecture_records) == len(lecture_ids)
        and all(isinstance(item, dict) and item.get("topic_id") for item in lecture_records)
    )

    return {
        "artifact_type": "connection_discovery_source_adequacy_audit",
        "version": "v0.1",
        "status": "structural_audit_complete",
        "inputs": {
            "canonical_clusters": canonical_path,
            "source_manifest": source_manifest_path,
        },
        "counts": {
            "lectures": len(lecture_ids),
            "canonical_knowledge_objects": canonical_count,
            "knowledge_object_mentions": mention_count,
            "canonical_types": dict(sorted(type_counts.items())),
            "single_lecture_canonical_objects": canonical_count
            - multi_lecture_clusters,
            "multi_lecture_canonical_objects": multi_lecture_clusters,
            "source_spans": exact_spans + nonexact_spans,
            "exact_source_spans": exact_spans,
            "nonexact_source_spans": nonexact_spans,
        },
        "pair_universe": {
            "all_unique_unordered_canonical_pairs": total_pairs,
            "eligible_cross_lecture_pairs": eligible,
            "disjoint_provenance_pairs": disjoint,
            "overlap_bridge_pairs": overlap_bridge,
            "ineligible_same_lecture_only_pairs": ineligible_same_lecture_only,
            "duplicate_pairs": 0,
            "self_pairs": 0,
        },
        "per_lecture": [
            {
                "lecture_id": lecture_id,
                "canonical_objects_with_provenance": lecture_cluster_counts[lecture_id],
                "mentions": lecture_mention_counts[lecture_id],
            }
            for lecture_id in lecture_ids
        ],
        "metadata_coverage": {
            "lecture_ids_declared": True,
            "course_ids_declared": bool(course_metadata_declared),
            "topic_ids_declared": bool(topic_metadata_declared),
        },
        "scale_assessment": scale,
        "semantic_assessment": {
            "status": "manual_review_required",
            "note": (
                "Positive density, Relation-type coverage, hard-negative quality, "
                "and educational value cannot be inferred from provenance alone."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-clusters", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_audit(
        load_json(args.canonical_clusters),
        load_json(args.source_manifest),
        canonical_path=str(args.canonical_clusters),
        source_manifest_path=str(args.source_manifest),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote Connection Discovery source audit to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
