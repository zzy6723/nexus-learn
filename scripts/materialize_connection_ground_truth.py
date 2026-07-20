#!/usr/bin/env python3
"""Materialize exhaustive Connection Ground Truth from reviewed decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


GRAPH_RELATIONS = {
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
}
CATEGORIES = {
    "IN_SCHEMA_CONNECTION",
    "NO_IN_SCHEMA_CONNECTION",
    "OUT_OF_SCHEMA_CONNECTION",
    "AMBIGUOUS",
}
SUPPORT_SCOPES = {
    "single_lecture_explicit",
    "cross_lecture_explicit",
    "multi_lecture_compositional",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def endpoint_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def materialize_ground_truth(
    pair_universe: dict[str, Any],
    evidence_catalogs: dict[str, Any],
    annotation_spec: dict[str, Any],
    *,
    pair_universe_path: Path,
    evidence_catalogs_path: Path,
    annotation_spec_path: Path,
) -> dict[str, Any]:
    pairs = pair_universe.get("pairs")
    catalogs = evidence_catalogs.get("catalogs")
    decisions = annotation_spec.get("decisions")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Pair universe is empty.")
    if not isinstance(catalogs, list) or len(catalogs) != len(pairs):
        raise ValueError("Evidence catalog count must match pair count.")
    if not isinstance(decisions, list):
        raise ValueError("Annotation spec must contain decisions.")
    review = annotation_spec.get("default_negative_review", {})
    if review.get("status") != "complete":
        raise ValueError("Default-negative review is not complete.")

    pair_by_endpoints: dict[tuple[str, str], dict[str, Any]] = {}
    pair_by_id: dict[str, dict[str, Any]] = {}
    object_types: dict[str, str] = {}
    for pair in pairs:
        left = pair["ko_a"]["canonical_ko_id"]
        right = pair["ko_b"]["canonical_ko_id"]
        key = endpoint_key(left, right)
        if key in pair_by_endpoints:
            raise ValueError(f"Duplicate endpoint pair: {key}")
        pair_by_endpoints[key] = pair
        pair_by_id[pair["canonical_pair_id"]] = pair
        object_types[left] = pair["ko_a"]["canonical_type"]
        object_types[right] = pair["ko_b"]["canonical_type"]

    catalog_by_pair: dict[str, dict[str, Any]] = {}
    for catalog in catalogs:
        pair_id = catalog.get("canonical_pair_id")
        if pair_id in catalog_by_pair or pair_id not in pair_by_id:
            raise ValueError(f"Invalid Evidence catalog pair: {pair_id!r}")
        catalog_by_pair[pair_id] = catalog
    if set(catalog_by_pair) != set(pair_by_id):
        raise ValueError("Evidence catalogs do not align with the pair universe.")

    decision_by_pair: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        endpoints = decision.get("endpoint_ids")
        if not isinstance(endpoints, list) or len(endpoints) != 2:
            raise ValueError("Every decision must declare two endpoint_ids.")
        key = endpoint_key(endpoints[0], endpoints[1])
        pair = pair_by_endpoints.get(key)
        if pair is None:
            raise ValueError(f"Decision references an ineligible pair: {key}")
        pair_id = pair["canonical_pair_id"]
        if pair_id in decision_by_pair:
            raise ValueError(f"Duplicate annotation decision for {pair_id}.")
        category = decision.get("category")
        if category not in CATEGORIES:
            raise ValueError(f"Override decision has invalid category: {category!r}")
        decision_by_pair[pair_id] = decision

    expected_negative_count = len(pairs) - len(decision_by_pair)
    if review.get("reviewed_pair_count") != expected_negative_count:
        raise ValueError(
            "Reviewed default-negative count does not match the materialized denominator: "
            f"{review.get('reviewed_pair_count')} != {expected_negative_count}."
        )

    output_pairs: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    primary_pairs = 0
    primary_positive = 0
    primary_negative = 0

    for pair in pairs:
        pair_id = pair["canonical_pair_id"]
        decision = decision_by_pair.get(pair_id)
        if decision is None:
            record = {
                "canonical_pair_id": pair_id,
                "ko_a": pair["ko_a"],
                "ko_b": pair["ko_b"],
                "provenance_stratum": pair["provenance_stratum"],
                "scope_flags": pair["scope_flags"],
                "category": "NO_IN_SCHEMA_CONNECTION",
                "primary_scoring_eligible": True,
                "gold_edge": None,
                "acceptable_alternatives": [],
                "evidence": [],
                "evidence_support_scope": None,
                "rationale": (
                    "The reviewed frozen material does not directly support an "
                    "ADR-004 graph Relation for this canonical pair."
                ),
                "annotation_origin": "reviewed_default_negative",
            }
            category_counts[record["category"]] += 1
            primary_pairs += 1
            primary_negative += 1
            output_pairs.append(record)
            continue

        category = decision["category"]
        primary = bool(decision.get("primary_scoring_eligible", False))
        rationale = decision.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"Decision for {pair_id} lacks a rationale.")

        catalog = catalog_by_pair[pair_id]
        catalog_lookup = {
            (item["lecture_id"], item["block_index"]): item
            for item in catalog["evidence_items"]
        }
        evidence = []
        seen_evidence: set[tuple[str, int]] = set()
        for ref in decision.get("evidence_refs", []):
            ref_key = (ref.get("lecture_id"), ref.get("block_index"))
            if ref_key in seen_evidence or ref_key not in catalog_lookup:
                raise ValueError(f"Invalid or duplicate Evidence ref {ref_key} for {pair_id}.")
            seen_evidence.add(ref_key)
            evidence.append(catalog_lookup[ref_key])
        if category != "NO_IN_SCHEMA_CONNECTION" and not evidence:
            raise ValueError(f"Non-negative decision for {pair_id} lacks Evidence.")

        gold_edge = None
        alternatives = decision.get("acceptable_alternatives", [])
        support_scope = decision.get("evidence_support_scope")
        if category == "IN_SCHEMA_CONNECTION":
            relation_type = decision.get("relation_type")
            source = decision.get("source_canonical_ko_id")
            target = decision.get("target_canonical_ko_id")
            if relation_type not in GRAPH_RELATIONS:
                raise ValueError(f"Invalid Relation for {pair_id}: {relation_type!r}")
            if endpoint_key(source, target) != endpoint_key(
                pair["ko_a"]["canonical_ko_id"], pair["ko_b"]["canonical_ko_id"]
            ):
                raise ValueError(f"Gold edge changes endpoints for {pair_id}.")
            if relation_type == "FORMALIZES" and object_types[source] != "Formula":
                raise ValueError(f"FORMALIZES source is not a Formula for {pair_id}.")
            if support_scope not in SUPPORT_SCOPES:
                raise ValueError(f"Invalid Evidence support scope for {pair_id}.")
            if support_scope == "multi_lecture_compositional" and primary:
                raise ValueError("Compositional Evidence cannot enter v0.1 primary scoring.")
            gold_edge = {
                "source_canonical_ko_id": source,
                "target_canonical_ko_id": target,
                "relation_type": relation_type,
                "symmetric": relation_type == "CONTRASTS_WITH",
            }
            relation_counts[relation_type] += 1
            support_counts[support_scope] += 1
        elif category == "OUT_OF_SCHEMA_CONNECTION":
            if primary:
                raise ValueError("Schema-gap pairs cannot enter primary scoring.")
            if not decision.get("schema_gap_relation"):
                raise ValueError(f"Schema gap {pair_id} lacks a proposed relation family.")
            support_scope = decision.get("evidence_support_scope")
            if support_scope not in SUPPORT_SCOPES:
                raise ValueError(f"Schema gap {pair_id} lacks a valid support scope.")
        elif category == "AMBIGUOUS":
            if primary or not alternatives:
                raise ValueError("Ambiguous decisions require alternatives and are diagnostic.")
        elif category == "NO_IN_SCHEMA_CONNECTION":
            if not primary:
                raise ValueError("Explicit NO_IN_SCHEMA_CONNECTION decisions are primary.")
            support_scope = None

        record = {
            "canonical_pair_id": pair_id,
            "ko_a": pair["ko_a"],
            "ko_b": pair["ko_b"],
            "provenance_stratum": pair["provenance_stratum"],
            "scope_flags": pair["scope_flags"],
            "category": category,
            "primary_scoring_eligible": primary,
            "gold_edge": gold_edge,
            "acceptable_alternatives": alternatives,
            "evidence": evidence,
            "evidence_support_scope": support_scope,
            "rationale": rationale,
            "annotation_origin": "explicit_reviewed_decision",
        }
        if category == "OUT_OF_SCHEMA_CONNECTION":
            record["schema_gap_relation"] = decision["schema_gap_relation"]
        category_counts[category] += 1
        if primary:
            primary_pairs += 1
            if category == "IN_SCHEMA_CONNECTION":
                primary_positive += 1
            elif category == "NO_IN_SCHEMA_CONNECTION":
                primary_negative += 1
        output_pairs.append(record)

    if primary_pairs != primary_positive + primary_negative:
        raise AssertionError("Primary denominator is inconsistent.")

    return {
        "artifact_type": "canonical_connection_ground_truth",
        "version": "v0.1",
        "status": "ready_to_freeze",
        "split": pair_universe.get("split", "development"),
        "annotation_protocol": "benchmark/connection_discovery_annotation_guidelines.md",
        "evaluation_protocol": "benchmark/connection_discovery_protocol.md",
        "allowed_relation_types": sorted(GRAPH_RELATIONS),
        "inputs": {
            "pair_universe": {
                "path": str(pair_universe_path),
                "sha256": sha256_path(pair_universe_path),
            },
            "evidence_catalogs": {
                "path": str(evidence_catalogs_path),
                "sha256": sha256_path(evidence_catalogs_path),
            },
            "annotation_spec": {
                "path": str(annotation_spec_path),
                "sha256": sha256_path(annotation_spec_path),
            },
        },
        "counts": {
            "all_eligible_pairs": len(output_pairs),
            "primary_scored_pairs": primary_pairs,
            "primary_positive_pairs": primary_positive,
            "primary_negative_pairs": primary_negative,
            "diagnostic_pairs": len(output_pairs) - primary_pairs,
            "categories": dict(sorted(category_counts.items())),
            "relations": dict(sorted(relation_counts.items())),
            "evidence_support_scopes": dict(sorted(support_counts.items())),
        },
        "default_negative_review": review,
        "pairs": output_pairs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-universe", required=True, type=Path)
    parser.add_argument("--evidence-catalogs", required=True, type=Path)
    parser.add_argument("--annotation-spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ground_truth = materialize_ground_truth(
        load_json(args.pair_universe),
        load_json(args.evidence_catalogs),
        load_json(args.annotation_spec),
        pair_universe_path=args.pair_universe,
        evidence_catalogs_path=args.evidence_catalogs,
        annotation_spec_path=args.annotation_spec,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ground_truth, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {ground_truth['counts']['all_eligible_pairs']} Connection annotations "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
