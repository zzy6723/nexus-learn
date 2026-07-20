#!/usr/bin/env python3
"""Validate a Connection source bundle and generate its exhaustive pair universe."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any


ALLOWED_TYPES = {"Concept", "Method", "Formula"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_pair_id(left_id: str, right_id: str) -> str:
    left_id, right_id = sorted((left_id, right_id))
    digest = hashlib.sha256(f"connection_pair_v0.1|{left_id}|{right_id}".encode()).hexdigest()
    return f"conn_dev_pair_{digest[:16]}"


def build_pair_universe(
    source_manifest: dict[str, Any],
    canonical_inventory: dict[str, Any],
    *,
    repository_root: Path,
    source_manifest_path: Path,
    canonical_inventory_path: Path,
) -> dict[str, Any]:
    lecture_records = source_manifest.get("lectures")
    if not isinstance(lecture_records, list) or not lecture_records:
        raise ValueError("Source manifest must contain a non-empty lectures list.")

    lectures: dict[str, dict[str, Any]] = {}
    lecture_text: dict[str, str] = {}
    lecture_hashes: dict[str, str] = {}
    for record in lecture_records:
        if not isinstance(record, dict):
            raise ValueError("Every lecture record must be an object.")
        required = ("lecture_id", "course_id", "topic_id", "sequence", "path")
        missing = [key for key in required if record.get(key) in (None, "")]
        if missing:
            raise ValueError(f"Lecture record is missing fields: {', '.join(missing)}")
        lecture_id = record["lecture_id"]
        if lecture_id in lectures:
            raise ValueError(f"Duplicate lecture_id: {lecture_id}")
        path = repository_root / record["path"]
        if not path.is_file():
            raise ValueError(f"Missing lecture file: {path}")
        lectures[lecture_id] = record
        lecture_text[lecture_id] = path.read_text(encoding="utf-8")
        lecture_hashes[lecture_id] = sha256_path(path)

    objects = canonical_inventory.get("canonical_objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("Canonical inventory must contain canonical_objects.")

    canonical: dict[str, dict[str, Any]] = {}
    mention_ids: set[str] = set()
    mention_count = 0
    source_span_count = 0
    for obj in objects:
        canonical_id = obj.get("canonical_ko_id")
        name = obj.get("canonical_name")
        ko_type = obj.get("canonical_type")
        mentions = obj.get("mentions")
        if not canonical_id or not name or ko_type not in ALLOWED_TYPES:
            raise ValueError(f"Invalid canonical object: {canonical_id!r}")
        if canonical_id in canonical:
            raise ValueError(f"Duplicate canonical_ko_id: {canonical_id}")
        if not isinstance(mentions, list) or not mentions:
            raise ValueError(f"Canonical object {canonical_id} has no mentions.")

        lecture_ids: set[str] = set()
        for mention in mentions:
            mention_id = mention.get("mention_id")
            lecture_id = mention.get("lecture_id")
            spans = mention.get("source_spans")
            if not mention_id or mention_id in mention_ids:
                raise ValueError(f"Invalid or duplicate mention_id: {mention_id!r}")
            if lecture_id not in lectures:
                raise ValueError(
                    f"Mention {mention_id} references unknown lecture {lecture_id!r}."
                )
            if not isinstance(spans, list) or not spans:
                raise ValueError(f"Mention {mention_id} has no source spans.")
            for span in spans:
                if not isinstance(span, str) or not span.strip():
                    raise ValueError(f"Mention {mention_id} has an empty source span.")
                if span not in lecture_text[lecture_id]:
                    raise ValueError(
                        f"Mention {mention_id} source span is not exact in {lecture_id}."
                    )
            mention_ids.add(mention_id)
            lecture_ids.add(lecture_id)
            mention_count += 1
            source_span_count += len(spans)

        canonical[canonical_id] = {
            "canonical_ko_id": canonical_id,
            "canonical_name": name,
            "canonical_type": ko_type,
            "lecture_ids": sorted(lecture_ids),
        }

    pairs: list[dict[str, Any]] = []
    excluded_same_lecture_only = 0
    disjoint_count = 0
    overlap_bridge_count = 0
    same_course_count = 0
    cross_course_count = 0
    same_topic_count = 0
    cross_topic_count = 0

    for left_id, right_id in combinations(sorted(canonical), 2):
        left = canonical[left_id]
        right = canonical[right_id]
        left_lectures = set(left["lecture_ids"])
        right_lectures = set(right["lecture_ids"])
        cross_lecture_combinations = [
            (a, b) for a in left_lectures for b in right_lectures if a != b
        ]
        if not cross_lecture_combinations:
            excluded_same_lecture_only += 1
            continue

        provenance_stratum = (
            "disjoint_provenance"
            if left_lectures.isdisjoint(right_lectures)
            else "overlap_bridge"
        )
        if provenance_stratum == "disjoint_provenance":
            disjoint_count += 1
        else:
            overlap_bridge_count += 1

        same_course = any(
            lectures[a]["course_id"] == lectures[b]["course_id"]
            for a, b in cross_lecture_combinations
        )
        cross_course = any(
            lectures[a]["course_id"] != lectures[b]["course_id"]
            for a, b in cross_lecture_combinations
        )
        same_topic = any(
            lectures[a]["topic_id"] == lectures[b]["topic_id"]
            for a, b in cross_lecture_combinations
        )
        cross_topic = any(
            lectures[a]["topic_id"] != lectures[b]["topic_id"]
            for a, b in cross_lecture_combinations
        )
        same_course_count += same_course
        cross_course_count += cross_course
        same_topic_count += same_topic
        cross_topic_count += cross_topic

        pairs.append(
            {
                "canonical_pair_id": stable_pair_id(left_id, right_id),
                "ko_a": left,
                "ko_b": right,
                "provenance_stratum": provenance_stratum,
                "scope_flags": {
                    "same_course_cross_lecture": same_course,
                    "cross_course": cross_course,
                    "same_topic_cross_lecture": same_topic,
                    "cross_topic": cross_topic,
                },
            }
        )

    pair_ids = [pair["canonical_pair_id"] for pair in pairs]
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("Stable canonical pair IDs collided.")

    object_count = len(canonical)
    all_pair_count = object_count * (object_count - 1) // 2
    if len(pairs) + excluded_same_lecture_only != all_pair_count:
        raise AssertionError("Pair universe denominator is inconsistent.")

    return {
        "artifact_type": "canonical_connection_pair_universe",
        "version": "v0.1",
        "status": "draft_pre_annotation",
        "split": source_manifest.get("split", "development"),
        "pair_identity": "sha256_of_sorted_canonical_ids_v0.1",
        "inputs": {
            "source_manifest": {
                "path": str(source_manifest_path),
                "sha256": sha256_path(source_manifest_path),
            },
            "oracle_canonical_inventory": {
                "path": str(canonical_inventory_path),
                "sha256": sha256_path(canonical_inventory_path),
            },
            "lectures": [
                {
                    "lecture_id": lecture_id,
                    "path": lectures[lecture_id]["path"],
                    "sha256": lecture_hashes[lecture_id],
                }
                for lecture_id in sorted(lectures)
            ],
        },
        "counts": {
            "lectures": len(lectures),
            "courses": len({record["course_id"] for record in lectures.values()}),
            "topics": len({record["topic_id"] for record in lectures.values()}),
            "canonical_knowledge_objects": object_count,
            "mentions": mention_count,
            "source_spans": source_span_count,
            "all_unique_unordered_pairs": all_pair_count,
            "eligible_cross_lecture_pairs": len(pairs),
            "excluded_same_lecture_only_pairs": excluded_same_lecture_only,
            "disjoint_provenance_pairs": disjoint_count,
            "overlap_bridge_pairs": overlap_bridge_count,
            "same_course_cross_lecture_pairs": same_course_count,
            "cross_course_pairs": cross_course_count,
            "same_topic_cross_lecture_pairs": same_topic_count,
            "cross_topic_pairs": cross_topic_count,
        },
        "gold_fields_present": False,
        "pairs": pairs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--canonical-inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = build_pair_universe(
        load_json(args.source_manifest),
        load_json(args.canonical_inventory),
        repository_root=args.repository_root.resolve(),
        source_manifest_path=args.source_manifest,
        canonical_inventory_path=args.canonical_inventory,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(universe, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        "Wrote "
        f"{universe['counts']['eligible_cross_lecture_pairs']} eligible pairs to "
        f"{args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
