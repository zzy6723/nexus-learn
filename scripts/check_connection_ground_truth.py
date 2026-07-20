#!/usr/bin/env python3
"""Check Connection Discovery benchmark alignment, Evidence, and review risks."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.generate_connection_evidence_catalogs import build_catalogs
    from scripts.generate_connection_pair_universe import build_pair_universe
except ModuleNotFoundError:  # Direct-file execution from the repository root.
    from generate_connection_evidence_catalogs import build_catalogs
    from generate_connection_pair_universe import build_pair_universe


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_ground_truth(
    source_manifest: dict[str, Any],
    canonical_inventory: dict[str, Any],
    pair_universe: dict[str, Any],
    evidence_catalogs: dict[str, Any],
    ground_truth: dict[str, Any],
    *,
    repository_root: Path,
    source_manifest_path: Path,
    canonical_inventory_path: Path,
    pair_universe_path: Path,
    evidence_catalogs_path: Path,
    ground_truth_path: Path,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []

    def record(code: str, detail: str) -> None:
        errors.append({"error_type": code, "detail": detail})

    regenerated_pairs = build_pair_universe(
        source_manifest,
        canonical_inventory,
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        canonical_inventory_path=canonical_inventory_path,
    )
    if regenerated_pairs != pair_universe:
        record("stale_pair_universe", "Stored pair universe differs from regeneration.")

    regenerated_catalogs = build_catalogs(
        source_manifest,
        pair_universe,
        repository_root=repository_root,
        source_manifest_path=source_manifest_path,
        pair_universe_path=pair_universe_path,
    )
    if regenerated_catalogs != evidence_catalogs:
        record("stale_evidence_catalogs", "Stored Evidence catalogs differ from regeneration.")

    expected_hashes = {
        "pair_universe": sha256_path(pair_universe_path),
        "evidence_catalogs": sha256_path(evidence_catalogs_path),
    }
    for key, expected in expected_hashes.items():
        actual = ground_truth.get("inputs", {}).get(key, {}).get("sha256")
        if actual != expected:
            record("stale_ground_truth_binding", f"{key} hash {actual!r} != {expected!r}")

    universe_pairs = pair_universe.get("pairs", [])
    gt_pairs = ground_truth.get("pairs", [])
    universe_ids = [item.get("canonical_pair_id") for item in universe_pairs]
    gt_ids = [item.get("canonical_pair_id") for item in gt_pairs]
    if universe_ids != gt_ids:
        record("pair_order_or_set_mismatch", "Ground Truth pair order/set differs.")
    if len(gt_ids) != len(set(gt_ids)):
        record("duplicate_ground_truth_pair", "Ground Truth contains duplicate pair IDs.")

    catalog_by_pair = {
        item["canonical_pair_id"]: item for item in evidence_catalogs.get("catalogs", [])
    }
    inventory_spans: dict[str, dict[str, list[str]]] = {}
    for obj in canonical_inventory.get("canonical_objects", []):
        per_lecture: dict[str, list[str]] = {}
        for mention in obj.get("mentions", []):
            per_lecture.setdefault(mention["lecture_id"], []).extend(
                mention.get("source_spans", [])
            )
        inventory_spans[obj["canonical_ko_id"]] = per_lecture

    category_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    primary_positive = 0
    primary_negative = 0
    primary_pairs = 0
    exact_evidence_items = 0
    selected_evidence_items = 0
    shared_block_negatives = []
    unresolved_shared_block_negatives = []
    primary_disjoint_positives = 0
    diagnostic_disjoint_positives = 0

    for record_item in gt_pairs:
        pair_id = record_item.get("canonical_pair_id")
        category = record_item.get("category")
        category_counts[category] += 1
        primary = record_item.get("primary_scoring_eligible") is True
        if primary:
            primary_pairs += 1
        if category == "IN_SCHEMA_CONNECTION":
            edge = record_item.get("gold_edge") or {}
            relation_counts[edge.get("relation_type")] += 1
            support_counts[record_item.get("evidence_support_scope")] += 1
            if primary:
                primary_positive += 1
                if record_item.get("provenance_stratum") == "disjoint_provenance":
                    primary_disjoint_positives += 1
            elif record_item.get("provenance_stratum") == "disjoint_provenance":
                diagnostic_disjoint_positives += 1
        elif category == "NO_IN_SCHEMA_CONNECTION" and primary:
            primary_negative += 1

        catalog = catalog_by_pair.get(pair_id)
        if catalog is None:
            record("missing_pair_catalog", f"No Evidence catalog for {pair_id}.")
            continue
        catalog_items = {
            (item["evidence_id"], item["lecture_id"], item["block_index"], item["span"])
            for item in catalog.get("evidence_items", [])
        }
        for evidence in record_item.get("evidence", []):
            selected_evidence_items += 1
            snapshot = (
                evidence.get("evidence_id"),
                evidence.get("lecture_id"),
                evidence.get("block_index"),
                evidence.get("span"),
            )
            if snapshot not in catalog_items:
                record("evidence_catalog_mismatch", f"Stale Evidence in {pair_id}.")
            else:
                exact_evidence_items += 1

        if category == "NO_IN_SCHEMA_CONNECTION":
            left_id = record_item["ko_a"]["canonical_ko_id"]
            right_id = record_item["ko_b"]["canonical_ko_id"]
            hits = []
            for item in catalog.get("evidence_items", []):
                lecture_id = item["lecture_id"]
                span = item["span"]
                left_hit = any(
                    value in span for value in inventory_spans[left_id].get(lecture_id, [])
                )
                right_hit = any(
                    value in span for value in inventory_spans[right_id].get(lecture_id, [])
                )
                if left_hit and right_hit:
                    hits.append(
                        {
                            "lecture_id": lecture_id,
                            "block_index": item["block_index"],
                            "evidence_id": item["evidence_id"],
                        }
                    )
            if hits:
                risk = {
                    "canonical_pair_id": pair_id,
                    "ko_a": record_item["ko_a"]["canonical_name"],
                    "ko_b": record_item["ko_b"]["canonical_name"],
                    "annotation_origin": record_item.get("annotation_origin"),
                    "rationale": record_item.get("rationale"),
                    "shared_blocks": hits,
                }
                shared_block_negatives.append(risk)
                if record_item.get("annotation_origin") != "explicit_reviewed_decision":
                    unresolved_shared_block_negatives.append(risk)

    stored_counts = ground_truth.get("counts", {})
    recomputed_counts = {
        "all_eligible_pairs": len(gt_pairs),
        "primary_scored_pairs": primary_pairs,
        "primary_positive_pairs": primary_positive,
        "primary_negative_pairs": primary_negative,
        "diagnostic_pairs": len(gt_pairs) - primary_pairs,
        "categories": dict(sorted(category_counts.items())),
        "relations": dict(sorted(relation_counts.items())),
        "evidence_support_scopes": dict(sorted(support_counts.items())),
    }
    if stored_counts != recomputed_counts:
        record("count_mismatch", "Stored Ground Truth counts are inconsistent.")
    if primary_pairs != primary_positive + primary_negative:
        record("primary_denominator_mismatch", "Primary counts do not sum.")
    if exact_evidence_items != selected_evidence_items:
        record("nonexact_or_stale_evidence", "Not all selected Evidence items are exact.")
    if unresolved_shared_block_negatives:
        record(
            "unreviewed_shared_block_negative",
            f"{len(unresolved_shared_block_negatives)} shared-block negatives lack explicit review.",
        )

    scope_limitations = []
    if primary_disjoint_positives == 0:
        scope_limitations.append(
            "No disjoint-provenance positive enters v0.1 primary scoring; the five "
            "compositional disjoint positives are diagnostic only."
        )
    if not relation_counts.get("RELATED_TO"):
        scope_limitations.append("RELATED_TO has no positive Ground Truth support.")

    status = "invalid" if errors else "passed_with_scope_limitations"
    return {
        "artifact_type": "connection_discovery_annotation_review_audit",
        "version": "v0.1",
        "status": status,
        "freeze_ready": not errors,
        "inputs": {
            "source_manifest": str(source_manifest_path),
            "oracle_canonical_inventory": str(canonical_inventory_path),
            "pair_universe": str(pair_universe_path),
            "evidence_catalogs": str(evidence_catalogs_path),
            "ground_truth": str(ground_truth_path),
        },
        "counts": recomputed_counts,
        "evidence": {
            "selected_items": selected_evidence_items,
            "exact_catalog_matches": exact_evidence_items,
        },
        "negative_review": {
            "shared_block_negative_count": len(shared_block_negatives),
            "explicitly_reviewed_shared_block_count": len(shared_block_negatives)
            - len(unresolved_shared_block_negatives),
            "unresolved_shared_block_count": len(unresolved_shared_block_negatives),
            "items": shared_block_negatives,
        },
        "positive_scope": {
            "primary_disjoint_provenance_positives": primary_disjoint_positives,
            "diagnostic_disjoint_provenance_positives": diagnostic_disjoint_positives,
        },
        "scope_limitations": scope_limitations,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--canonical-inventory", required=True, type=Path)
    parser.add_argument("--pair-universe", required=True, type=Path)
    parser.add_argument("--evidence-catalogs", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = audit_ground_truth(
        load_json(args.source_manifest),
        load_json(args.canonical_inventory),
        load_json(args.pair_universe),
        load_json(args.evidence_catalogs),
        load_json(args.ground_truth),
        repository_root=args.repository_root.resolve(),
        source_manifest_path=args.source_manifest,
        canonical_inventory_path=args.canonical_inventory,
        pair_universe_path=args.pair_universe,
        evidence_catalogs_path=args.evidence_catalogs,
        ground_truth_path=args.ground_truth,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"Connection Ground Truth audit status: {audit['status']}")
    print(f"Wrote audit to {args.output}")
    return 0 if audit["freeze_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
