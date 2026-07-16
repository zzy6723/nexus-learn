#!/usr/bin/env python3
"""Prepare one Candidate Generator condition for downstream Relation diagnosis."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import project_candidate_pairs_to_relations as projector  # noqa: E402
from scripts import run_relation_extraction as relation_runner  # noqa: E402


DEFAULT_CONTRACT = ROOT / "benchmark" / "candidate_relation_downstream_diagnostic_v0_1.json"
DEFAULT_PROJECTION_MARKER = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "candidate_relation_projection_development_v0_1_complete.json"
)
DEFAULT_PREPARATION_ROOT = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "downstream_diagnostic_v0_1"
    / "preparation"
)
MANAGED_FILENAMES = [
    "selected_relation_ground_truth.json",
    "model_input.json",
    "batch_plan.json",
    "source_manifest.json",
    "preparation_complete.json",
]
CONDITIONS = {"all_pairs", "rule_filtered_v0_1"}


class PreparationError(RuntimeError):
    """Raised when one diagnostic condition cannot be prepared safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a frozen Candidate-to-Relation diagnostic condition."
    )
    parser.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT.relative_to(ROOT)))
    parser.add_argument(
        "--projection-marker",
        default=str(DEFAULT_PROJECTION_MARKER.relative_to(ROOT)),
    )
    parser.add_argument(
        "--output-dir",
        help="Default: experiments/.../downstream_diagnostic_v0_1/preparation/<condition>",
    )
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    return projector.display_path(path)


def read_json(path: Path, *, label: str) -> dict[str, Any]:
    return projector.read_json(path, label=label)


def binding(path: Path) -> dict[str, str]:
    return projector.binding(path)


def validate_bound_file(value: Any, *, label: str) -> Path:
    return projector.validate_binding(value, label=label)


def prepare_output_dir(output_dir: Path) -> None:
    existing = [output_dir / name for name in MANAGED_FILENAMES if (output_dir / name).exists()]
    if existing:
        raise PreparationError(
            "Preparation artifacts already exist; use a new directory: "
            + str([display_path(path) for path in existing])
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def validate_projection_marker(
    *,
    marker_path: Path,
    contract_path: Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    marker = read_json(marker_path, label="Candidate-to-Relation projection marker")
    if (
        marker.get("artifact_type") != "candidate_relation_projection_complete"
        or marker.get("version") != "v0.1"
        or marker.get("status") != "final"
    ):
        raise PreparationError("Candidate-to-Relation projection is not final.")
    if marker.get("contract") != binding(contract_path):
        raise PreparationError("Projection marker points to a different contract.")
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "knowledge_objects",
        "relation_ground_truth",
        "pair_mapping",
    }:
        raise PreparationError("Projection marker artifact set is invalid.")
    paths = {
        name: validate_bound_file(value, label=f"projection {name}")
        for name, value in artifacts.items()
    }
    if marker.get("counts") != {
        "knowledge_objects": 39,
        "lectures": 4,
        "pairs": 176,
        "primary_pairs": 171,
        "positive_pairs": 80,
        "hard_negative_pairs": 91,
        "schema_gap_pairs": 5,
        "ambiguous_pairs": 0,
    }:
        raise PreparationError("Projection marker counts differ from v0.1.")
    return marker, paths


def condition_record(contract: dict[str, Any], condition: str) -> dict[str, Any]:
    records = [
        item
        for item in contract.get("candidate_conditions", [])
        if isinstance(item, dict) and item.get("condition") == condition
    ]
    if len(records) != 1:
        raise PreparationError(f"Contract has no unique condition {condition}.")
    return records[0]


def validate_candidate_selection(
    *,
    record: dict[str, Any],
) -> tuple[dict[str, Any], Path, Path]:
    selection_path = validate_bound_file(record.get("selection"), label="candidate selection")
    completion_path = validate_bound_file(record.get("completion"), label="candidate completion")
    selection = read_json(selection_path, label="candidate selection")
    completion = read_json(completion_path, label="candidate completion")
    if selection.get("artifact_type") != "candidate_pair_selection":
        raise PreparationError("Candidate selection has an invalid artifact_type.")
    if selection.get("generator", {}).get("id") != record.get("method_id"):
        raise PreparationError("Candidate selection method differs from the contract.")
    selected = selection.get("selected_pairs")
    if not isinstance(selected, list) or selection.get("selected_pair_count") != len(selected):
        raise PreparationError("Candidate selection count is invalid.")
    if len(selected) != record.get("expected_selected_pairs"):
        raise PreparationError("Candidate selection count differs from the contract.")
    if completion.get("status") != "final":
        raise PreparationError("Candidate Generator completion marker is not final.")
    bound_selection = completion.get("artifacts", {}).get("candidate_selection")
    if bound_selection != binding(selection_path):
        raise PreparationError("Candidate completion marker has a stale selection binding.")
    return selection, selection_path, completion_path


def validate_mapping(
    mapping: dict[str, Any],
    canonical_gt: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    mappings = mapping.get("mappings")
    relation_pairs = canonical_gt.get("pairs")
    if not isinstance(mappings, list) or not isinstance(relation_pairs, list):
        raise PreparationError("Projection mapping or Relation Ground Truth is invalid.")
    if mapping.get("mapping_count") != 176 or len(mappings) != 176:
        raise PreparationError("Projection mapping must contain all 176 pairs.")
    mapping_by_candidate: dict[str, dict[str, Any]] = {}
    pair_by_relation: dict[str, dict[str, Any]] = {}
    for item in mappings:
        candidate_id = item.get("candidate_pair_id")
        relation_id = item.get("relation_pair_id")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(relation_id, str)
            or candidate_id in mapping_by_candidate
        ):
            raise PreparationError("Projection mapping contains invalid or duplicate IDs.")
        if projector.candidate_to_relation_id(candidate_id) != relation_id:
            raise PreparationError(f"Projection mapping changed ID suffix for {candidate_id}.")
        mapping_by_candidate[candidate_id] = item
    for pair in relation_pairs:
        relation_id = pair.get("pair_id")
        if not isinstance(relation_id, str) or relation_id in pair_by_relation:
            raise PreparationError("Canonical Relation projection has duplicate IDs.")
        pair_by_relation[relation_id] = pair
    if {item["relation_pair_id"] for item in mappings} != set(pair_by_relation):
        raise PreparationError("Projection mapping and Relation Ground Truth differ.")
    return mapping_by_candidate, pair_by_relation


def build_selected_ground_truth(
    *,
    condition: str,
    selection: dict[str, Any],
    canonical_gt: dict[str, Any],
    mapping_by_candidate: dict[str, dict[str, Any]],
    pair_by_relation: dict[str, dict[str, Any]],
    canonical_gt_path: Path,
    selection_path: Path,
    mapping_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    selected_relation_ids: list[str] = []
    selected_pairs: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for index, selected in enumerate(selection["selected_pairs"]):
        candidate_id = selected.get("pair_id")
        if not isinstance(candidate_id, str) or candidate_id in seen_candidates:
            raise PreparationError(f"Selected candidate {index} has invalid or duplicate ID.")
        seen_candidates.add(candidate_id)
        mapping = mapping_by_candidate.get(candidate_id)
        if mapping is None:
            raise PreparationError(f"Selected candidate {candidate_id} has no projection mapping.")
        for field in ("lecture_id", "ko_a", "ko_b"):
            if selected.get(field) != mapping.get(field):
                raise PreparationError(f"Selected candidate {candidate_id} changed {field}.")
        relation_id = mapping["relation_pair_id"]
        selected_relation_ids.append(relation_id)
        selected_pairs.append(dict(pair_by_relation[relation_id]))

    derived = {
        **{key: value for key, value in canonical_gt.items() if key != "pairs"},
        "artifact_type": "candidate_relation_selected_ground_truth",
        "status": "derived_not_run",
        "description": (
            f"Relation Ground Truth subset selected by Candidate condition {condition}."
        ),
        "notes": [
            *canonical_gt.get("notes", []),
            f"Selected by frozen Candidate condition {condition}.",
            "This gold artifact is evaluator-facing and is never included in model input.",
        ],
        "derivation": {
            "condition": condition,
            "canonical_relation_ground_truth": binding(canonical_gt_path),
            "candidate_selection": binding(selection_path),
            "pair_mapping": binding(mapping_path),
        },
        "pairs": selected_pairs,
    }
    return derived, selected_relation_ids


def prepare_condition(
    *,
    condition: str,
    contract_path: Path,
    projection_marker_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    prepare_output_dir(output_dir)
    contract = read_json(contract_path, label="diagnostic contract")
    projector.validate_contract(contract)
    projection_marker, projection_paths = validate_projection_marker(
        marker_path=projection_marker_path,
        contract_path=contract_path,
    )
    record = condition_record(contract, condition)
    selection, selection_path, selection_completion_path = validate_candidate_selection(
        record=record
    )
    canonical_gt_path = projection_paths["relation_ground_truth"]
    ko_path = projection_paths["knowledge_objects"]
    mapping_path = projection_paths["pair_mapping"]
    canonical_gt = read_json(canonical_gt_path, label="canonical Relation projection")
    mapping = read_json(mapping_path, label="candidate-to-Relation mapping")
    mapping_by_candidate, pair_by_relation = validate_mapping(mapping, canonical_gt)
    selected_gt, selected_relation_ids = build_selected_ground_truth(
        condition=condition,
        selection=selection,
        canonical_gt=canonical_gt,
        mapping_by_candidate=mapping_by_candidate,
        pair_by_relation=pair_by_relation,
        canonical_gt_path=canonical_gt_path,
        selection_path=selection_path,
        mapping_path=mapping_path,
    )

    selected_gt_path = output_dir / "selected_relation_ground_truth.json"
    model_input_path = output_dir / "model_input.json"
    batch_plan_path = output_dir / "batch_plan.json"
    source_manifest_path = output_dir / "source_manifest.json"
    marker_path = output_dir / "preparation_complete.json"
    atomic_write(selected_gt_path, selected_gt)

    ko_registry, lecture_paths, ko_hashes = relation_runner.load_knowledge_object_registry(
        [display_path(ko_path)]
    )
    model_input, candidate_members, lecture_hashes = relation_runner.build_model_input(
        selected_gt, ko_registry, lecture_paths
    )
    leakage_audit = relation_runner.validate_model_input(model_input, candidate_members)
    execution_plan, _ = relation_runner.build_candidate_scoped_batches(
        model_input, candidate_members
    )
    if execution_plan["pair_ids"] != selected_relation_ids:
        raise PreparationError("Candidate-scoped batch plan changed selected pair order.")

    model_input_artifact = {
        "artifact_type": "candidate_relation_model_input",
        "version": "v0.1",
        "condition": condition,
        "request_partitioning": relation_runner.CANDIDATE_SCOPED_PARTITIONING,
        "selected_ground_truth_sha256": projector.sha256_file(selected_gt_path),
        "candidate_selection_sha256": projector.sha256_file(selection_path),
        "pair_mapping_sha256": projector.sha256_file(mapping_path),
        "knowledge_objects_sha256": projector.sha256_file(ko_path),
        "pair_manifest_sha256": projector.sha256_file(selection_path),
        "ko_manifest_sha256": projector.sha256_file(ko_path),
        "matched_ground_truth_sha256": projector.sha256_file(selected_gt_path),
        "relation_prompt_sha256": contract["relation_method"]["prompt"]["sha256"],
        "relation_schema_sha256": contract["relation_method"]["schema"]["sha256"],
        "model_input_sha256": projector.sha256_json(model_input),
        "lecture_sha256": lecture_hashes,
        "model_input": model_input,
    }
    atomic_write(model_input_path, model_input_artifact)
    execution_plan.update({
        "condition": condition,
        "selected_ground_truth_sha256": projector.sha256_file(selected_gt_path),
        "candidate_selection_sha256": projector.sha256_file(selection_path),
        "pair_mapping_sha256": projector.sha256_file(mapping_path),
        "model_input_sha256": projector.sha256_json(model_input),
    })
    atomic_write(batch_plan_path, execution_plan)

    source_manifest = {
        "artifact_type": "candidate_relation_diagnostic_source_manifest",
        "version": "v0.1",
        "condition": condition,
        "contract": binding(contract_path),
        "projection_completion": binding(projection_marker_path),
        "canonical_relation_ground_truth": binding(canonical_gt_path),
        "knowledge_objects": binding(ko_path),
        "pair_mapping": binding(mapping_path),
        "candidate_selection": binding(selection_path),
        "candidate_completion": binding(selection_completion_path),
        "selected_relation_ground_truth": binding(selected_gt_path),
        "relation_prompt": contract["relation_method"]["prompt"],
        "relation_schema": contract["relation_method"]["schema"],
        "base_runner_dependency": contract["relation_method"]["base_runner_dependency"],
        "base_evaluator": contract["relation_method"]["base_evaluator"],
        "preparer": binding(Path(__file__).resolve()),
        "knowledge_object_ground_truth_hashes": ko_hashes,
        "counts": {
            "selected_pairs": len(selected_relation_ids),
            "knowledge_objects": len(model_input["knowledge_objects"]),
            "lectures": len(model_input["lectures"]),
            "request_batches": len(execution_plan["batches"]),
        },
        "gold_leakage_audit": leakage_audit,
    }
    atomic_write(source_manifest_path, source_manifest)
    marker = {
        "artifact_type": "candidate_relation_diagnostic_preparation_complete",
        "version": "v0.1",
        "status": "final",
        "condition": condition,
        "contract": binding(contract_path),
        "projection_completion": binding(projection_marker_path),
        "implementation": binding(Path(__file__).resolve()),
        "artifacts": {
            "selected_relation_ground_truth": binding(selected_gt_path),
            "model_input": binding(model_input_path),
            "batch_plan": binding(batch_plan_path),
            "source_manifest": binding(source_manifest_path),
        },
        "counts": source_manifest["counts"],
        "gold_leakage_audit": leakage_audit,
        "integrity": {
            "pair_ids_unique": len(selected_relation_ids) == len(set(selected_relation_ids)),
            "pair_order_matches_candidate_selection": True,
            "endpoint_mismatch_count": 0,
            "gold_fields_model_facing": 0,
        },
    }
    atomic_write(marker_path, marker)
    return marker


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = (
        resolve_path(args.output_dir)
        if args.output_dir
        else DEFAULT_PREPARATION_ROOT / args.condition
    )
    try:
        marker = prepare_condition(
            condition=args.condition,
            contract_path=resolve_path(args.contract),
            projection_marker_path=resolve_path(args.projection_marker),
            output_dir=output_dir,
        )
    except (PreparationError, projector.ProjectionError, RuntimeError) as exc:
        print(f"Candidate Relation preparation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Prepared {args.condition}: {marker['counts']['selected_pairs']} pairs, "
        f"{marker['counts']['request_batches']} candidate-scoped requests"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
