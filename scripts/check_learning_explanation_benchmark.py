#!/usr/bin/env python3
"""Strictly validate the Experiment 004 development benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_path_hash(project_root: Path, record: dict[str, Any]) -> Path:
    path = project_root / record["path"]
    if not path.is_file():
        raise ValueError(f"Missing bound artifact: {path}")
    actual = sha256(path)
    if actual != record["sha256"]:
        raise ValueError(f"Hash mismatch for {path}")
    return path


def validate_benchmark(project_root: Path, benchmark_dir: Path) -> dict[str, Any]:
    manifest_path = benchmark_dir / "source_manifest.json"
    bundle_path = benchmark_dir / "connection_instances.json"
    annotation_scaffold_path = benchmark_dir / "annotation_scaffold.json"
    complete_path = benchmark_dir / "benchmark_complete.json"
    for path in (
        manifest_path,
        bundle_path,
        annotation_scaffold_path,
        complete_path,
    ):
        if not path.is_file():
            raise ValueError(f"Missing required benchmark artifact: {path}")

    manifest = read_json(manifest_path)
    bundle = read_json(bundle_path)
    annotation_scaffold = read_json(annotation_scaffold_path)
    complete = read_json(complete_path)

    validate_path_hash(project_root, complete["artifacts"]["source_manifest"])
    validate_path_hash(project_root, complete["artifacts"]["connection_instances"])
    validate_path_hash(project_root, complete["artifacts"]["annotation_scaffold"])

    sources = manifest["sources"]
    selection_path = validate_path_hash(project_root, sources["selection_spec"])
    annotation_spec_path = validate_path_hash(
        project_root, sources["annotation_scaffold_spec"]
    )
    ground_truth_path = validate_path_hash(
        project_root, sources["connection_ground_truth"]
    )
    inventory_path = validate_path_hash(
        project_root, sources["oracle_canonical_inventory"]
    )
    lecture_paths = {
        item["lecture_id"]: validate_path_hash(project_root, item)
        for item in sources["lectures"]
    }

    selection = read_json(selection_path)
    annotation_spec = read_json(annotation_spec_path)
    ground_truth = read_json(ground_truth_path)
    inventory = read_json(inventory_path)
    selected = selection["selected_connections"]
    selected_ids = [item["canonical_pair_id"] for item in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Selection contains duplicate canonical pair IDs.")
    spec_annotations = annotation_spec.get("annotations")
    if not isinstance(spec_annotations, list):
        raise ValueError("Annotation spec must contain an annotations list.")
    spec_ids = [item["canonical_pair_id"] for item in spec_annotations]
    if len(spec_ids) != len(set(spec_ids)):
        raise ValueError("Annotation spec contains duplicate Connection IDs.")
    if set(spec_ids) != set(selected_ids):
        raise ValueError("Annotation spec does not align with the selection.")

    pairs = {
        pair["canonical_pair_id"]: pair for pair in ground_truth.get("pairs", [])
    }
    objects = {
        item["canonical_ko_id"]: item
        for item in inventory.get("canonical_objects", [])
    }
    instances = bundle.get("instances")
    if not isinstance(instances, list):
        raise ValueError("Connection instance bundle must contain an instances list.")
    if len(instances) != len(selected_ids):
        raise ValueError("Connection instance count does not match selection.")
    generated_annotations = annotation_scaffold.get("annotations")
    if not isinstance(generated_annotations, list):
        raise ValueError("Generated annotation scaffold must contain annotations.")
    if len(generated_annotations) != len(instances):
        raise ValueError("Annotation scaffold count does not match instances.")
    if annotation_scaffold.get("model_input_allowed") is not False:
        raise ValueError("Annotation scaffold must be forbidden from model input.")
    annotation_by_instance = {
        item["explanation_instance_id"]: item for item in generated_annotations
    }
    if len(annotation_by_instance) != len(generated_annotations):
        raise ValueError("Annotation scaffold contains duplicate instance IDs.")

    relation_counts: Counter[str] = Counter()
    evidence_count = 0
    seen_instance_ids = set()
    seen_pair_ids = set()

    for index, instance in enumerate(instances, start=1):
        expected_instance_id = f"le_dev_{index:03d}"
        if instance["explanation_instance_id"] != expected_instance_id:
            raise ValueError("Explanation instance IDs are not sequential.")
        if expected_instance_id in seen_instance_ids:
            raise ValueError("Duplicate explanation instance ID.")
        seen_instance_ids.add(expected_instance_id)
        annotation = annotation_by_instance.get(expected_instance_id)
        if annotation is None:
            raise ValueError("Annotation scaffold is missing an instance.")

        pair_id = instance["source_connection_pair_id"]
        if pair_id != selected_ids[index - 1]:
            raise ValueError("Instance order differs from the selection spec.")
        if pair_id in seen_pair_ids:
            raise ValueError("Duplicate source Connection pair.")
        seen_pair_ids.add(pair_id)
        if annotation["source_connection_pair_id"] != pair_id:
            raise ValueError("Annotation scaffold pair alignment changed.")
        for field in (
            "required_points",
            "forbidden_or_unsupported_points",
            "risk_tags",
        ):
            values = annotation.get(field)
            if not isinstance(values, list) or not values:
                raise ValueError(f"{pair_id} annotation field {field} is empty.")
        if annotation.get("model_input_allowed") is not False:
            raise ValueError(f"{pair_id} annotation is not model-input isolated.")

        pair = pairs[pair_id]
        if pair["category"] != "IN_SCHEMA_CONNECTION":
            raise ValueError(f"{pair_id} is not an in-schema Connection.")
        if pair["primary_scoring_eligible"] is not True:
            raise ValueError(f"{pair_id} is not primary-scoring eligible.")
        edge = pair["gold_edge"]
        source = instance["source_ko"]
        target = instance["target_ko"]
        if source["canonical_ko_id"] != edge["source_canonical_ko_id"]:
            raise ValueError(f"{pair_id} source endpoint changed.")
        if target["canonical_ko_id"] != edge["target_canonical_ko_id"]:
            raise ValueError(f"{pair_id} target endpoint changed.")
        if instance["relation_type"] != edge["relation_type"]:
            raise ValueError(f"{pair_id} Relation changed.")
        if instance["relation_type"] == "RELATED_TO":
            raise ValueError("RELATED_TO lacks source-benchmark positive support.")
        if source["canonical_name"] != objects[source["canonical_ko_id"]][
            "canonical_name"
        ]:
            raise ValueError(f"{pair_id} source name changed.")
        if target["canonical_name"] != objects[target["canonical_ko_id"]][
            "canonical_name"
        ]:
            raise ValueError(f"{pair_id} target name changed.")

        evidence = instance["evidence"]
        if evidence != pair["evidence"]:
            raise ValueError(f"{pair_id} Evidence differs from Ground Truth.")
        for evidence_item in evidence:
            lecture_id = evidence_item["lecture_id"]
            if lecture_id not in lecture_paths:
                raise ValueError(f"{pair_id} references an undeclared lecture.")
            lecture_text = lecture_paths[lecture_id].read_text()
            if evidence_item["span"] not in lecture_text:
                raise ValueError(f"{pair_id} Evidence span is not exact.")
        evidence_count += len(evidence)
        relation_counts[instance["relation_type"]] += 1

    expected = selection["expected_counts"]
    if len(instances) != expected["instances"]:
        raise ValueError("Instance count differs from the frozen expectation.")
    if dict(relation_counts) != expected["relation_support"]:
        raise ValueError("Relation support differs from the selection spec.")
    if bundle["counts"]["instances"] != len(instances):
        raise ValueError("Bundle instance count is stale.")
    if bundle["counts"]["relation_support"] != dict(relation_counts):
        raise ValueError("Bundle Relation counts are stale.")
    if bundle["counts"]["evidence_items"] != evidence_count:
        raise ValueError("Bundle Evidence count is stale.")
    if complete["counts"] != bundle["counts"]:
        raise ValueError("Completion counts differ from the bundle.")
    if complete["model_execution_authorized"] is not False:
        raise ValueError("Preparation artifact must not authorize model execution.")

    return {
        "instances": len(instances),
        "relation_support": dict(relation_counts),
        "evidence_items": evidence_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark-dir",
        default="benchmark/learning_explanation/development_v0_1",
    )
    parser.add_argument("--project-root", default=".")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        counts = validate_benchmark(
            Path(args.project_root).resolve(),
            Path(args.benchmark_dir).resolve(),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Learning Explanation benchmark invalid: {exc}")
        return 1
    print(
        "Learning Explanation benchmark PASSED: "
        f"{counts['instances']} instances, "
        f"{counts['evidence_items']} Evidence items"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
