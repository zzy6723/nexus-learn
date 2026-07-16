#!/usr/bin/env python3
"""Project exhaustive Candidate Ground Truth into Relation diagnostic artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "benchmark" / "candidate_relation_downstream_diagnostic_v0_1.json"
DEFAULT_KO_OUTPUT = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "candidate_relation_knowledge_objects_development_v0_1.json"
)
DEFAULT_RELATION_OUTPUT = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "candidate_relation_projection_development_v0_1.json"
)
DEFAULT_MAPPING_OUTPUT = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "candidate_relation_pair_mapping_development_v0_1.json"
)
DEFAULT_MARKER_OUTPUT = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "candidate_relation_projection_development_v0_1_complete.json"
)
ALLOWED_RELATION_TYPES = [
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
    "NO_RELATION",
]
GRAPH_RELATIONS = set(ALLOWED_RELATION_TYPES) - {"NO_RELATION"}
CANDIDATE_ID_RE = re.compile(r"cand_dev_(\d{3})")


class ProjectionError(RuntimeError):
    """Raised when the frozen projection contract cannot be satisfied."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project Candidate Pair Ground Truth into Relation artifacts."
    )
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT.relative_to(ROOT)))
    parser.add_argument("--knowledge-objects-output", default=str(DEFAULT_KO_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--relation-ground-truth-output", default=str(DEFAULT_RELATION_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--pair-mapping-output", default=str(DEFAULT_MAPPING_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--completion-marker-output", default=str(DEFAULT_MARKER_OUTPUT.relative_to(ROOT)))
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectionError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectionError(f"{label} must be a JSON object.")
    return value


def binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def validate_binding(value: Any, *, label: str) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ProjectionError(f"{label} must contain exactly path and sha256.")
    path = resolve_path(value.get("path", ""))
    if not path.is_file():
        raise ProjectionError(f"{label} is missing: {display_path(path)}")
    if value.get("sha256") != sha256_file(path):
        raise ProjectionError(f"{label} has a stale SHA-256 binding.")
    return path


def validate_contract(contract: dict[str, Any]) -> dict[str, Path]:
    if contract.get("artifact_type") != "candidate_relation_downstream_diagnostic_contract":
        raise ProjectionError("Unexpected diagnostic contract artifact_type.")
    if contract.get("version") != "v0.1":
        raise ProjectionError("Unexpected diagnostic contract version.")
    if contract.get("status") != "frozen_before_projection_and_api_execution":
        raise ProjectionError("Diagnostic contract is not frozen for projection.")
    if contract.get("split_role") != "development_diagnostic":
        raise ProjectionError("Diagnostic contract split role is invalid.")
    if contract.get("created") != "2026-07-17":
        raise ProjectionError("Diagnostic contract creation date is invalid.")

    paths: dict[str, Path] = {
        "protocol": validate_binding(contract.get("protocol"), label="protocol")
    }
    sources = contract.get("source_artifacts")
    if not isinstance(sources, dict):
        raise ProjectionError("Diagnostic contract is missing source_artifacts.")
    required_sources = {
        "candidate_ground_truth",
        "candidate_ground_truth_completion",
        "pair_universe",
        "pair_universe_completion",
        "predicted_ko_inventory",
        "lecture_inventory",
    }
    if set(sources) != required_sources:
        raise ProjectionError("Diagnostic contract source_artifacts differ from v0.1.")
    for name in sorted(required_sources):
        paths[name] = validate_binding(sources[name], label=name)

    relation_method = contract.get("relation_method")
    if not isinstance(relation_method, dict):
        raise ProjectionError("Diagnostic contract is missing relation_method.")
    for name in ("prompt", "schema", "base_runner_dependency", "base_evaluator"):
        paths[name] = validate_binding(relation_method.get(name), label=name)

    implementations = contract.get("diagnostic_implementations")
    required_implementations = {
        "projector",
        "preparer",
        "runner",
        "evaluation_finalizer",
        "pipeline_evaluator",
    }
    if not isinstance(implementations, dict) or set(implementations) != required_implementations:
        raise ProjectionError("Diagnostic implementation bindings differ from v0.1.")
    for name in sorted(required_implementations):
        paths[name] = validate_binding(
            implementations[name], label=f"diagnostic {name}"
        )

    conditions = contract.get("candidate_conditions")
    if not isinstance(conditions, list) or [
        item.get("condition") for item in conditions if isinstance(item, dict)
    ] != ["all_pairs", "rule_filtered_v0_1"]:
        raise ProjectionError("Diagnostic candidate conditions are invalid or reordered.")
    for item in conditions:
        condition = item["condition"]
        paths[f"{condition}_selection"] = validate_binding(
            item.get("selection"), label=f"{condition} selection"
        )
        paths[f"{condition}_completion"] = validate_binding(
            item.get("completion"), label=f"{condition} completion"
        )

    denominators = contract.get("denominators")
    if denominators != {
        "total_pairs": 176,
        "primary_pairs": 171,
        "positive_pairs": 80,
        "hard_negative_pairs": 91,
        "schema_gap_pairs": 5,
        "ambiguous_pairs": 0,
    }:
        raise ProjectionError("Diagnostic denominators differ from frozen v0.1.")
    projection_policy = contract.get("projection_policy")
    if not isinstance(projection_policy, dict) or projection_policy.get(
        "positive_relation_multiplicity"
    ) != "exactly_one_primary_relation_required":
        raise ProjectionError("Diagnostic projection policy is invalid.")
    return paths


def candidate_to_relation_id(candidate_pair_id: str) -> str:
    match = CANDIDATE_ID_RE.fullmatch(candidate_pair_id)
    if match is None:
        raise ProjectionError(f"Invalid candidate pair ID: {candidate_pair_id!r}")
    return f"rel_dev_{match.group(1)}"


def ref_tuple(value: Any, *, label: str) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"lecture_id", "ko_id"}:
        raise ProjectionError(f"{label} must contain lecture_id and ko_id.")
    lecture_id = value.get("lecture_id")
    ko_id = value.get("ko_id")
    if not isinstance(lecture_id, str) or not lecture_id:
        raise ProjectionError(f"{label}.lecture_id is invalid.")
    if not isinstance(ko_id, str) or not ko_id:
        raise ProjectionError(f"{label}.ko_id is invalid.")
    return lecture_id, ko_id


def ref_json(ref: tuple[str, str]) -> dict[str, str]:
    return {"lecture_id": ref[0], "ko_id": ref[1]}


def validate_source_snapshots(
    *,
    paths: dict[str, Path],
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidate_gt = read_json(paths["candidate_ground_truth"], label="Candidate Ground Truth")
    universe = read_json(paths["pair_universe"], label="pair universe")
    inventory = read_json(paths["predicted_ko_inventory"], label="predicted-KO inventory")
    lectures = read_json(paths["lecture_inventory"], label="lecture inventory")
    candidate_marker = read_json(
        paths["candidate_ground_truth_completion"], label="Candidate Ground Truth marker"
    )
    universe_marker = read_json(
        paths["pair_universe_completion"], label="pair-universe marker"
    )

    if candidate_gt.get("status") != "frozen":
        raise ProjectionError("Candidate Ground Truth is not frozen.")
    annotations = candidate_gt.get("annotations")
    pairs = universe.get("pairs")
    objects = inventory.get("knowledge_objects")
    lecture_items = lectures.get("lectures")
    if not all(isinstance(value, list) for value in (annotations, pairs, objects, lecture_items)):
        raise ProjectionError("One or more source snapshots have invalid list fields.")
    if any(item.get("annotation_status") != "final" for item in annotations):
        raise ProjectionError("Candidate Ground Truth contains non-final annotations.")
    if candidate_marker.get("completion_status") != "final":
        raise ProjectionError("Candidate Ground Truth completion marker is not final.")
    if universe_marker.get("status") != "final":
        raise ProjectionError("Pair-universe completion marker is not final.")
    if candidate_gt.get("pair_universe", {}).get("sha256") != sha256_file(
        paths["pair_universe"]
    ):
        raise ProjectionError("Candidate Ground Truth points to a different pair universe.")
    if universe.get("source_inventory", {}).get("sha256") != sha256_file(
        paths["predicted_ko_inventory"]
    ):
        raise ProjectionError("Pair universe points to a different predicted-KO inventory.")
    if universe.get("lecture_inventory", {}).get("sha256") != sha256_file(
        paths["lecture_inventory"]
    ):
        raise ProjectionError("Pair universe points to a different lecture inventory.")
    if inventory.get("normalized_content_sha256") != sha256_json(objects):
        raise ProjectionError("Predicted-KO normalized content hash is stale.")

    expected = contract["denominators"]
    label_counts = Counter(item.get("candidate_label") for item in annotations)
    if len(pairs) != expected["total_pairs"] or len(annotations) != len(pairs):
        raise ProjectionError("Source pair or annotation count differs from the contract.")
    if label_counts != Counter({
        "IN_SCHEMA_RELATION": expected["positive_pairs"],
        "NO_IN_SCHEMA_RELATION": expected["hard_negative_pairs"],
        "OUT_OF_SCHEMA_RELATION": expected["schema_gap_pairs"],
    }):
        raise ProjectionError("Candidate label counts differ from the contract.")
    if len(objects) != universe.get("total_ko_count"):
        raise ProjectionError("Predicted-KO inventory count differs from the pair universe.")
    return candidate_gt, universe, inventory, lectures


def build_knowledge_object_bridge(
    *,
    inventory: dict[str, Any],
    lecture_inventory: dict[str, Any],
    universe: dict[str, Any],
    inventory_path: Path,
    lecture_inventory_path: Path,
) -> dict[str, Any]:
    objects_by_lecture: dict[str, list[dict[str, Any]]] = {}
    seen_refs: set[tuple[str, str]] = set()
    for index, item in enumerate(inventory["knowledge_objects"]):
        if not isinstance(item, dict):
            raise ProjectionError(f"Predicted KO {index} is not an object.")
        required = {"lecture_id", "predicted_ko_id", "name", "type", "source_spans"}
        if not required.issubset(item):
            raise ProjectionError(f"Predicted KO {index} is missing model-facing fields.")
        ref = (item["lecture_id"], item["predicted_ko_id"])
        if ref in seen_refs:
            raise ProjectionError(f"Duplicate predicted KO reference: {ref}")
        seen_refs.add(ref)
        objects_by_lecture.setdefault(ref[0], []).append({
            "id": ref[1],
            "name": item["name"],
            "type": item["type"],
            "source_spans": list(item["source_spans"]),
        })

    source_paths = {
        item.get("lecture_id"): item.get("path")
        for item in lecture_inventory.get("sources", [])
        if isinstance(item, dict)
    }
    lecture_texts = {
        item.get("lecture_id"): item.get("text")
        for item in lecture_inventory.get("lectures", [])
        if isinstance(item, dict)
    }
    lecture_entries: list[dict[str, Any]] = []
    for declared in universe["lectures"]:
        lecture_id = declared["lecture_id"]
        path_text = source_paths.get(lecture_id)
        text = lecture_texts.get(lecture_id)
        if not isinstance(path_text, str) or not isinstance(text, str):
            raise ProjectionError(f"Lecture inventory is incomplete for {lecture_id}.")
        lecture_path = resolve_path(path_text)
        if not lecture_path.is_file():
            raise ProjectionError(f"Lecture source is missing for {lecture_id}.")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != declared[
            "lecture_text_sha256"
        ]:
            raise ProjectionError(f"Lecture model-text hash is stale for {lecture_id}.")
        lecture_objects = objects_by_lecture.get(lecture_id, [])
        if len(lecture_objects) != declared["ko_count"]:
            raise ProjectionError(f"Predicted-KO count differs for {lecture_id}.")
        lecture_entries.append({
            "lecture_id": lecture_id,
            "path": display_path(lecture_path),
            "objects": lecture_objects,
        })
    if set(objects_by_lecture) != {item["lecture_id"] for item in universe["lectures"]}:
        raise ProjectionError("Predicted-KO lecture IDs differ from the pair universe.")
    return {
        "artifact_type": "candidate_relation_knowledge_objects",
        "version": "v0.1",
        "split": "development",
        "source_inventory": binding(inventory_path),
        "lecture_inventory": binding(lecture_inventory_path),
        "lectures": lecture_entries,
    }


def build_relation_projection(
    *,
    candidate_gt: dict[str, Any],
    universe: dict[str, Any],
    ko_output_path: Path,
    created: str,
) -> tuple[dict[str, Any], dict[str, Any], Counter[str], Counter[str]]:
    annotations = {item["pair_id"]: item for item in candidate_gt["annotations"]}
    if len(annotations) != len(candidate_gt["annotations"]):
        raise ProjectionError("Candidate Ground Truth contains duplicate pair IDs.")
    relation_pairs: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    primary_relation_counts: Counter[str] = Counter()

    for pair in universe["pairs"]:
        candidate_id = pair["pair_id"]
        annotation = annotations.get(candidate_id)
        if annotation is None:
            raise ProjectionError(f"Missing Candidate annotation for {candidate_id}.")
        relation_id = candidate_to_relation_id(candidate_id)
        candidate_refs = {
            ref_tuple(pair["ko_a"], label=f"{candidate_id}.ko_a"),
            ref_tuple(pair["ko_b"], label=f"{candidate_id}.ko_b"),
        }
        label = annotation["candidate_label"]

        if label == "IN_SCHEMA_RELATION":
            gold_relations = annotation.get("gold_relations")
            if not isinstance(gold_relations, list) or len(gold_relations) != 1:
                raise ProjectionError(
                    f"{candidate_id} must have exactly one primary gold Relation."
                )
            gold = gold_relations[0]
            if gold.get("role") != "primary":
                raise ProjectionError(f"{candidate_id} gold Relation is not primary.")
            source = ref_tuple(gold.get("source"), label=f"{candidate_id}.source")
            target = ref_tuple(gold.get("target"), label=f"{candidate_id}.target")
            relation_type = gold.get("relation_type")
            if {source, target} != candidate_refs:
                raise ProjectionError(f"{candidate_id} gold Relation changed endpoints.")
            if relation_type not in GRAPH_RELATIONS:
                raise ProjectionError(f"{candidate_id} has invalid graph Relation.")
            projected = {
                "pair_id": relation_id,
                "category": "positive",
                "source": ref_json(source),
                "target": ref_json(target),
                "relation_type": relation_type,
                "symmetric": bool(gold.get("symmetric", False)),
                "evidence_spans": list(gold.get("evidence_spans", [])),
                "rationale": gold.get("rationale"),
            }
            primary_relation_counts[relation_type] += 1
            category = "positive"
        elif label == "NO_IN_SCHEMA_RELATION":
            if annotation.get("gold_relations"):
                raise ProjectionError(f"{candidate_id} negative contains gold Relations.")
            source, target = sorted(candidate_refs)
            projected = {
                "pair_id": relation_id,
                "category": "hard_negative",
                "source": ref_json(source),
                "target": ref_json(target),
                "relation_type": "NO_RELATION",
                "symmetric": False,
                "evidence_spans": [],
                "rationale": annotation.get("negative_rationale"),
            }
            primary_relation_counts["NO_RELATION"] += 1
            category = "hard_negative"
        elif label == "OUT_OF_SCHEMA_RELATION":
            gap = annotation.get("out_of_schema_relation")
            if not isinstance(gap, dict):
                raise ProjectionError(f"{candidate_id} schema gap lacks diagnostic detail.")
            source, target = sorted(candidate_refs)
            projected = {
                "pair_id": relation_id,
                "category": "schema_gap",
                "source": ref_json(source),
                "target": ref_json(target),
                "relation_type": "RELATED_TO",
                "symmetric": False,
                "evidence_spans": list(gap.get("evidence_spans", [])),
                "rationale": (
                    "Diagnostic placeholder only: "
                    + str(gap.get("schema_exclusion_rationale", ""))
                ),
            }
            category = "schema_gap"
        elif label == "AMBIGUOUS":
            raise ProjectionError(
                f"{candidate_id} is AMBIGUOUS; v0.1 projection fails closed."
            )
        else:
            raise ProjectionError(f"{candidate_id} has unknown Candidate label {label!r}.")

        if not isinstance(projected["rationale"], str) or not projected["rationale"].strip():
            raise ProjectionError(f"{candidate_id} projected rationale is empty.")
        relation_pairs.append(projected)
        category_counts[category] += 1
        mappings.append({
            "candidate_pair_id": candidate_id,
            "relation_pair_id": relation_id,
            "lecture_id": pair["lecture_id"],
            "ko_a": dict(pair["ko_a"]),
            "ko_b": dict(pair["ko_b"]),
            "candidate_label": label,
            "relation_category": category,
        })

    relation_coverage = {
        relation: (
            f"covered_with_{primary_relation_counts[relation]}_primary_instances"
            if primary_relation_counts[relation]
            else "no_primary_support"
        )
        for relation in ALLOWED_RELATION_TYPES
    }
    relation_projection = {
        "version": "v0.1",
        "split": "development",
        "status": "frozen_not_run",
        "created": created,
        "description": (
            "Deterministic Relation projection of the exhaustive 002B-2 "
            "predicted-KO Candidate Ground Truth for downstream diagnosis."
        ),
        "annotation_guidelines": "benchmark/candidate_pair_annotation_guidelines.md",
        "evaluation_protocol": "benchmark/candidate_to_relation_projection_protocol.md",
        "knowledge_object_ground_truths": [display_path(ko_output_path)],
        "notes": [
            "cand_dev_NNN maps deterministically to rel_dev_NNN.",
            "Every primary positive has exactly one predeclared gold Relation.",
            "Schema-gap RELATED_TO labels are diagnostic placeholders excluded from primary scoring.",
            "This is inspected development data and not a fresh holdout.",
        ],
        "allowed_relation_types": ALLOWED_RELATION_TYPES,
        "relation_coverage": relation_coverage,
        "primary_scoring_categories": ["positive", "hard_negative"],
        "lectures": [item["lecture_id"] for item in universe["lectures"]],
        "pairs": relation_pairs,
    }
    mapping = {
        "artifact_type": "candidate_to_relation_pair_mapping",
        "version": "v0.1",
        "benchmark_split": "development",
        "candidate_pair_id_pattern": "cand_dev_NNN",
        "relation_pair_id_pattern": "rel_dev_NNN",
        "mapping_policy": "preserve_three_digit_suffix_and_unordered_endpoints",
        "mapping_count": len(mappings),
        "mappings": mappings,
    }
    return relation_projection, mapping, category_counts, primary_relation_counts


def serialize_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(serialize_json(value), encoding="utf-8")
    os.replace(temporary, path)


def prepare_outputs(paths: list[Path]) -> None:
    existing = [display_path(path) for path in paths if path.exists()]
    if existing:
        raise ProjectionError(
            "Projection outputs already exist; use a new version instead of overwrite: "
            + str(existing)
        )


def build_projection_bundle(
    *,
    contract_path: Path,
    ko_output_path: Path,
    relation_output_path: Path,
    mapping_output_path: Path,
    marker_output_path: Path,
) -> dict[str, Any]:
    outputs = [ko_output_path, relation_output_path, mapping_output_path, marker_output_path]
    prepare_outputs(outputs)
    contract = read_json(contract_path, label="diagnostic contract")
    paths = validate_contract(contract)
    candidate_gt, universe, inventory, lectures = validate_source_snapshots(
        paths=paths, contract=contract
    )
    ko_bridge = build_knowledge_object_bridge(
        inventory=inventory,
        lecture_inventory=lectures,
        universe=universe,
        inventory_path=paths["predicted_ko_inventory"],
        lecture_inventory_path=paths["lecture_inventory"],
    )
    relation_projection, mapping, category_counts, relation_counts = build_relation_projection(
        candidate_gt=candidate_gt,
        universe=universe,
        ko_output_path=ko_output_path,
        created=contract["created"],
    )
    atomic_write(ko_output_path, ko_bridge)
    atomic_write(relation_output_path, relation_projection)
    atomic_write(mapping_output_path, mapping)

    marker = {
        "artifact_type": "candidate_relation_projection_complete",
        "version": "v0.1",
        "status": "final",
        "contract": binding(contract_path),
        "implementation": binding(Path(__file__).resolve()),
        "inputs": {
            name: binding(path)
            for name, path in sorted(paths.items())
            if name not in {"prompt", "schema", "base_runner_dependency", "base_evaluator"}
            and not name.endswith("_selection")
            and not name.endswith("_completion")
        },
        "artifacts": {
            "knowledge_objects": binding(ko_output_path),
            "relation_ground_truth": binding(relation_output_path),
            "pair_mapping": binding(mapping_output_path),
        },
        "counts": {
            "knowledge_objects": sum(len(item["objects"]) for item in ko_bridge["lectures"]),
            "lectures": len(ko_bridge["lectures"]),
            "pairs": len(relation_projection["pairs"]),
            "primary_pairs": category_counts["positive"] + category_counts["hard_negative"],
            "positive_pairs": category_counts["positive"],
            "hard_negative_pairs": category_counts["hard_negative"],
            "schema_gap_pairs": category_counts["schema_gap"],
            "ambiguous_pairs": category_counts["ambiguous"],
        },
        "primary_relation_counts": {
            relation: relation_counts[relation] for relation in ALLOWED_RELATION_TYPES
        },
        "integrity": {
            "pair_id_mapping_complete": True,
            "endpoint_mismatch_count": 0,
            "multi_relation_pair_count": 0,
            "gold_fields_model_facing": 0,
        },
    }
    atomic_write(marker_output_path, marker)
    return marker


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        marker = build_projection_bundle(
            contract_path=resolve_path(args.contract),
            ko_output_path=resolve_path(args.knowledge_objects_output),
            relation_output_path=resolve_path(args.relation_ground_truth_output),
            mapping_output_path=resolve_path(args.pair_mapping_output),
            marker_output_path=resolve_path(args.completion_marker_output),
        )
    except ProjectionError as exc:
        print(f"Candidate-to-Relation projection failed: {exc}", file=sys.stderr)
        return 1
    print(
        "Wrote Candidate-to-Relation projection: "
        f"{marker['counts']['pairs']} pairs, "
        f"{marker['counts']['primary_pairs']} primary, "
        f"{marker['counts']['schema_gap_pairs']} diagnostics"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
