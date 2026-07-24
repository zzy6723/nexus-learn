#!/usr/bin/env python3
"""Create the deterministic Experiment 004 development benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


GENERATED_FILENAMES = (
    "source_manifest.json",
    "connection_instances.json",
    "annotation_scaffold.json",
    "benchmark_complete.json",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def create_benchmark(
    *,
    project_root: Path,
    selection_path: Path,
    annotation_path: Path,
    ground_truth_path: Path,
    inventory_path: Path,
    lecture_dir: Path,
    output_dir: Path,
    overwrite: bool,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_paths = [output_dir / name for name in GENERATED_FILENAMES]
    existing = [path for path in generated_paths if path.exists()]
    if existing and not overwrite:
        rendered = ", ".join(path.as_posix() for path in existing)
        raise ValueError(f"Generated benchmark artifacts already exist: {rendered}")

    selection = read_json(selection_path)
    annotation_spec = read_json(annotation_path)
    ground_truth = read_json(ground_truth_path)
    inventory = read_json(inventory_path)

    if selection.get("split") != "development":
        raise ValueError("Selection split must be development.")
    selected = selection.get("selected_connections")
    if not isinstance(selected, list) or not selected:
        raise ValueError("Selection must contain selected_connections.")
    annotations = annotation_spec.get("annotations")
    if not isinstance(annotations, list) or not annotations:
        raise ValueError("Annotation spec must contain annotations.")
    annotations_by_pair = {
        item["canonical_pair_id"]: item for item in annotations
    }
    if len(annotations_by_pair) != len(annotations):
        raise ValueError("Annotation spec contains duplicate Connection IDs.")
    selected_ids = [item["canonical_pair_id"] for item in selected]
    if set(annotations_by_pair) != set(selected_ids):
        raise ValueError(
            "Annotation spec Connection IDs must exactly match the selection."
        )

    pairs = {
        pair["canonical_pair_id"]: pair for pair in ground_truth.get("pairs", [])
    }
    objects = {
        item["canonical_ko_id"]: item
        for item in inventory.get("canonical_objects", [])
    }

    instances: list[dict[str, Any]] = []
    annotation_items: list[dict[str, Any]] = []
    relation_counts: Counter[str] = Counter()
    lecture_ids: set[str] = set()

    for index, selection_item in enumerate(selected, start=1):
        pair_id = selection_item["canonical_pair_id"]
        if pair_id not in pairs:
            raise ValueError(f"Unknown selected pair: {pair_id}")
        pair = pairs[pair_id]
        if pair.get("category") != "IN_SCHEMA_CONNECTION":
            raise ValueError(f"{pair_id} is not an in-schema Connection.")
        if pair.get("primary_scoring_eligible") is not True:
            raise ValueError(f"{pair_id} is not a primary-scored Connection.")

        edge = pair.get("gold_edge")
        if not isinstance(edge, dict):
            raise ValueError(f"{pair_id} is missing a gold edge.")
        relation_type = edge["relation_type"]
        if relation_type != selection_item["expected_relation_type"]:
            raise ValueError(f"{pair_id} Relation does not match the selection spec.")
        if relation_type == "RELATED_TO":
            raise ValueError("RELATED_TO is not supported by the development source.")

        source_id = edge["source_canonical_ko_id"]
        target_id = edge["target_canonical_ko_id"]
        if source_id not in objects or target_id not in objects:
            raise ValueError(f"{pair_id} references an unknown canonical object.")
        evidence = pair.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{pair_id} must have human-validated Evidence.")

        for item in evidence:
            lecture_ids.add(item["lecture_id"])

        explanation_instance_id = f"le_dev_{index:03d}"
        instances.append(
            {
                "explanation_instance_id": explanation_instance_id,
                "source_connection_pair_id": pair_id,
                "source_ko": {
                    "canonical_ko_id": source_id,
                    "canonical_name": objects[source_id]["canonical_name"],
                    "canonical_type": objects[source_id]["canonical_type"],
                },
                "relation_type": relation_type,
                "symmetric": bool(edge.get("symmetric", False)),
                "target_ko": {
                    "canonical_ko_id": target_id,
                    "canonical_name": objects[target_id]["canonical_name"],
                    "canonical_type": objects[target_id]["canonical_type"],
                },
                "evidence": evidence,
                "evidence_support_scope": pair["evidence_support_scope"],
                "source_annotation_rationale": pair["rationale"],
                "provenance_stratum": pair["provenance_stratum"],
                "scope_flags": pair["scope_flags"],
                "data_role": "development_only",
            }
        )
        annotation = annotations_by_pair[pair_id]
        required_points = annotation.get("required_points")
        forbidden_points = annotation.get("forbidden_or_unsupported_points")
        risk_tags = annotation.get("risk_tags")
        if not isinstance(required_points, list) or not required_points:
            raise ValueError(f"{pair_id} must define required semantic points.")
        if not isinstance(forbidden_points, list) or not forbidden_points:
            raise ValueError(f"{pair_id} must define forbidden points.")
        if not isinstance(risk_tags, list) or not risk_tags:
            raise ValueError(f"{pair_id} must define risk tags.")
        annotation_items.append(
            {
                "explanation_instance_id": explanation_instance_id,
                "source_connection_pair_id": pair_id,
                "required_points": required_points,
                "forbidden_or_unsupported_points": forbidden_points,
                "risk_tags": risk_tags,
                "model_input_allowed": False,
            }
        )
        relation_counts[relation_type] += 1

    expected = selection.get("expected_counts", {})
    if len(instances) != expected.get("instances"):
        raise ValueError("Generated instance count does not match selection spec.")
    if dict(relation_counts) != expected.get("relation_support"):
        raise ValueError("Generated Relation counts do not match selection spec.")

    lecture_sources = []
    for lecture_id in sorted(lecture_ids):
        lecture_path = lecture_dir / f"{lecture_id}.md"
        if not lecture_path.is_file():
            raise ValueError(f"Missing lecture source: {lecture_path}")
        lecture_sources.append(
            {
                "lecture_id": lecture_id,
                "path": relative_path(lecture_path, project_root),
                "sha256": sha256(lecture_path),
            }
        )

    manifest = {
        "artifact_type": "learning_explanation_source_manifest",
        "artifact_schema_version": "v0.1",
        "status": "prepared_not_frozen",
        "split": "development",
        "sources": {
            "selection_spec": {
                "path": relative_path(selection_path, project_root),
                "sha256": sha256(selection_path),
            },
            "annotation_scaffold_spec": {
                "path": relative_path(annotation_path, project_root),
                "sha256": sha256(annotation_path),
            },
            "connection_ground_truth": {
                "path": relative_path(ground_truth_path, project_root),
                "sha256": sha256(ground_truth_path),
            },
            "oracle_canonical_inventory": {
                "path": relative_path(inventory_path, project_root),
                "sha256": sha256(inventory_path),
            },
            "lectures": lecture_sources,
        },
        "source_boundary": {
            "uses_human_validated_connections_only": True,
            "uses_connection_model_predictions": False,
            "independent_validation_source": False,
        },
    }

    bundle = {
        "artifact_type": "oracle_conditioned_learning_explanation_instances",
        "artifact_schema_version": "v0.1",
        "status": "prepared_not_frozen",
        "split": "development",
        "counts": {
            "instances": len(instances),
            "relation_support": dict(relation_counts),
            "evidence_items": sum(len(item["evidence"]) for item in instances),
        },
        "instances": instances,
    }

    manifest_path = output_dir / "source_manifest.json"
    bundle_path = output_dir / "connection_instances.json"
    annotation_scaffold_path = output_dir / "annotation_scaffold.json"
    write_json(manifest_path, manifest)
    write_json(bundle_path, bundle)
    write_json(
        annotation_scaffold_path,
        {
            "artifact_type": "learning_explanation_annotation_scaffold",
            "artifact_schema_version": "v0.1",
            "status": "prepared_not_frozen",
            "split": "development",
            "reference_prose": False,
            "model_input_allowed": False,
            "annotations": annotation_items,
        },
    )

    complete = {
        "artifact_type": "learning_explanation_benchmark_complete",
        "artifact_schema_version": "v0.1",
        "status": "prepared_for_review_not_frozen",
        "split": "development",
        "artifacts": {
            "source_manifest": {
                "path": relative_path(manifest_path, project_root),
                "sha256": sha256(manifest_path),
            },
            "connection_instances": {
                "path": relative_path(bundle_path, project_root),
                "sha256": sha256(bundle_path),
            },
            "annotation_scaffold": {
                "path": relative_path(annotation_scaffold_path, project_root),
                "sha256": sha256(annotation_scaffold_path),
            },
        },
        "counts": bundle["counts"],
        "model_execution_authorized": False,
        "next_gate": "Human review, protocol review, repository freeze, and clean-state preflight are required before any explanation model run.",
    }
    write_json(output_dir / "benchmark_complete.json", complete)
    return complete


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selection-spec",
        default="benchmark/learning_explanation/development_v0_1/selection_spec.json",
    )
    parser.add_argument(
        "--annotation-spec",
        default=(
            "benchmark/learning_explanation/development_v0_1/"
            "annotation_scaffold_spec.json"
        ),
    )
    parser.add_argument(
        "--ground-truth",
        default="benchmark/connection_discovery/development_v0_1/ground_truth.json",
    )
    parser.add_argument(
        "--canonical-inventory",
        default=(
            "benchmark/connection_discovery/development_v0_1/"
            "oracle_canonical_inventory.json"
        ),
    )
    parser.add_argument(
        "--lecture-dir",
        default="benchmark/connection_discovery/development_v0_1/lectures",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark/learning_explanation/development_v0_1",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path.cwd()
    try:
        complete = create_benchmark(
            project_root=project_root,
            selection_path=Path(args.selection_spec),
            annotation_path=Path(args.annotation_spec),
            ground_truth_path=Path(args.ground_truth),
            inventory_path=Path(args.canonical_inventory),
            lecture_dir=Path(args.lecture_dir),
            output_dir=Path(args.output_dir),
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Learning Explanation benchmark creation failed: {exc}")
        return 1

    print(
        "Prepared "
        f"{complete['counts']['instances']} Oracle Connection instances at "
        f"{args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
