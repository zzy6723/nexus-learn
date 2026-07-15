"""Helpers for executable Predicted-KO Relation fixture tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "predicted_ko_relation"
TEMPLATE_BUNDLE = FIXTURES / "valid_bundle"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def update_json(path: Path, update: Any) -> Any:
    value = read_json(path)
    update(value)
    write_json(path, value)
    return value


def materialize_runtime_bundle(destination: Path) -> tuple[Path, dict[str, str]]:
    """Copy the golden template and replace symbolic references with real hashes."""

    bundle = destination / "valid_bundle"
    shutil.copytree(TEMPLATE_BUNDLE, bundle)

    shared = FIXTURES / "shared"
    oracle_inventory_hash = sha256_file(shared / "synthetic_oracle_inventory.json")
    predicted_inventory_hash = sha256_file(
        shared / "synthetic_predicted_inventory.json"
    )
    original_ground_truth_hash = sha256_file(
        shared / "synthetic_original_ground_truth.json"
    )
    lecture_inventory = read_json(shared / "synthetic_lectures.json")
    lecture_hashes = {
        lecture["lecture_id"]: sha256_bytes(lecture["text"].encode("utf-8"))
        for lecture in lecture_inventory["lectures"]
    }

    alignment_path = bundle / "alignment.json"

    def update_alignment(value: dict[str, Any]) -> None:
        value["oracle_inventory_sha256"] = oracle_inventory_hash
        value["predicted_inventory_sha256"] = predicted_inventory_hash
        value["lecture_sha256"] = lecture_hashes

    update_json(alignment_path, update_alignment)
    alignment_hash = sha256_file(alignment_path)

    update_json(
        bundle / "alignment_pending.json",
        lambda value: value.__setitem__("alignment_snapshot_sha256", alignment_hash),
    )

    def update_alignment_resolved(value: dict[str, Any]) -> None:
        value["alignment_snapshot_sha256"] = alignment_hash
        value["oracle_inventory_sha256"] = oracle_inventory_hash
        value["predicted_inventory_sha256"] = predicted_inventory_hash
        value["lecture_sha256"] = lecture_hashes

    update_json(bundle / "alignment_resolved.json", update_alignment_resolved)
    update_json(
        bundle / "alignment_bundle_complete.json",
        lambda value: value.__setitem__(
            "artifacts",
            {
                filename: sha256_file(bundle / filename)
                for filename in [
                    "alignment.json",
                    "alignment_pending.json",
                    "alignment_resolved.json",
                ]
            },
        ),
    )

    pair_manifest_path = bundle / "recoverable_pair_manifest.json"

    def update_pair_manifest(value: dict[str, Any]) -> None:
        value["original_ground_truth_sha256"] = original_ground_truth_hash
        value["alignment_sha256"] = alignment_hash

    update_json(pair_manifest_path, update_pair_manifest)
    pair_manifest_hash = sha256_file(pair_manifest_path)

    ko_manifest_path = bundle / "recoverable_ko_manifest.json"

    def update_ko_manifest(value: dict[str, Any]) -> None:
        value["alignment_sha256"] = alignment_hash
        value["pair_manifest_sha256"] = pair_manifest_hash

    update_json(ko_manifest_path, update_ko_manifest)
    ko_manifest_hash = sha256_file(ko_manifest_path)

    matched_kos_path = bundle / "matched_knowledge_objects.json"

    def update_matched_kos(value: dict[str, Any]) -> None:
        derivation = value["derivation"]
        derivation["original_ko_ground_truth_sha256"] = oracle_inventory_hash
        derivation["alignment_sha256"] = alignment_hash
        derivation["pair_manifest_sha256"] = pair_manifest_hash
        derivation["ko_manifest_sha256"] = ko_manifest_hash

    update_json(matched_kos_path, update_matched_kos)
    matched_kos_hash = sha256_file(matched_kos_path)

    matched_ground_truth_path = bundle / "matched_relation_ground_truth.json"

    def update_matched_ground_truth(value: dict[str, Any]) -> None:
        value["knowledge_object_ground_truths"] = [str(matched_kos_path)]
        derivation = value["derivation"]
        derivation["original_ground_truth_sha256"] = original_ground_truth_hash
        derivation["alignment_sha256"] = alignment_hash
        derivation["pair_manifest_sha256"] = pair_manifest_hash
        derivation["ko_manifest_sha256"] = ko_manifest_hash
        derivation["matched_knowledge_objects_sha256"] = matched_kos_hash

    update_json(matched_ground_truth_path, update_matched_ground_truth)
    matched_ground_truth_hash = sha256_file(matched_ground_truth_path)

    batch_plan_path = bundle / "batch_plan.json"

    def update_batch_plan(value: dict[str, Any]) -> None:
        value["pair_manifest_sha256"] = pair_manifest_hash
        value["ko_manifest_sha256"] = ko_manifest_hash

    update_json(batch_plan_path, update_batch_plan)
    batch_plan_hash = sha256_file(batch_plan_path)

    relation_prompt_hash = sha256_file(
        ROOT / "experiments" / "relation_extraction" / "002_prompt_refinement" / "prompt.md"
    )
    relation_schema_hash = sha256_file(
        ROOT / "docs" / "decisions" / "004-relation-schema.md"
    )

    input_hashes: dict[str, str] = {}
    for condition, filename in [
        ("A_prime", "oracle_normalized_input.json"),
        ("B_prime", "predicted_normalized_input.json"),
    ]:
        input_path = bundle / filename

        def update_input(value: dict[str, Any]) -> None:
            value["pair_manifest_sha256"] = pair_manifest_hash
            value["ko_manifest_sha256"] = ko_manifest_hash
            value["matched_ground_truth_sha256"] = matched_ground_truth_hash
            value["relation_prompt_sha256"] = relation_prompt_hash
            value["relation_schema_sha256"] = relation_schema_hash
            value["batch_plan_sha256"] = batch_plan_hash
            value["lecture_sha256"] = lecture_hashes
            value["ko_content_sha256"] = sha256_json(
                value["model_input"]["knowledge_objects"]
            )
            value["model_input_sha256"] = sha256_json(value["model_input"])

        update_json(input_path, update_input)
        input_hashes[condition] = sha256_file(input_path)

    update_json(
        bundle / "projection_bundle_complete.json",
        lambda value: value.update({
            "upstream": {
                "alignment_bundle_complete_sha256": sha256_file(
                    bundle / "alignment_bundle_complete.json"
                )
            },
            "artifacts": {
                filename: sha256_file(bundle / filename)
                for filename in [
                    "recoverable_pair_manifest.json",
                    "recoverable_ko_manifest.json",
                    "matched_knowledge_objects.json",
                    "matched_relation_ground_truth.json",
                    "oracle_normalized_input.json",
                    "predicted_normalized_input.json",
                    "batch_plan.json",
                    "projection_errors.json",
                ]
            },
        }),
    )

    evaluation_hashes: dict[str, str] = {}
    metadata_hashes: dict[str, str] = {}
    prediction_hashes: dict[str, str] = {}
    for condition in ["A0", "A_prime", "B_prime"]:
        evaluation_dir = bundle / f"{condition}_evaluation"
        prediction_path = evaluation_dir / "predictions.json"
        metadata_path = evaluation_dir / "run_metadata.json"
        prediction_hash = sha256_file(prediction_path)
        prediction_hashes[condition] = prediction_hash

        def update_metadata(value: dict[str, Any]) -> None:
            value["prediction_sha256"] = prediction_hash
            if condition in input_hashes:
                value["input_artifact_sha256"] = input_hashes[condition]
                value["batch_plan_sha256"] = batch_plan_hash
            else:
                value["input_artifact_sha256"] = original_ground_truth_hash
                value["batch_plan_sha256"] = original_ground_truth_hash

        update_json(metadata_path, update_metadata)
        metadata_hash = sha256_file(metadata_path)
        metadata_hashes[condition] = metadata_hash

        snapshot_path = evaluation_dir / "evaluation_snapshot.json"

        def update_snapshot(value: dict[str, Any]) -> None:
            value["prediction_sha256"] = prediction_hash
            value["run_metadata_sha256"] = metadata_hash
            value["metrics_sha256"] = sha256_file(evaluation_dir / "metrics.json")
            value["matches_sha256"] = sha256_file(evaluation_dir / "matches.json")
            value["errors_sha256"] = sha256_file(evaluation_dir / "errors.json")

        update_json(snapshot_path, update_snapshot)
        evaluation_hashes[condition] = sha256_file(snapshot_path)

    provenance = {
        "original_ground_truth_sha256": original_ground_truth_hash,
        "alignment_sha256": alignment_hash,
        "pair_manifest_sha256": pair_manifest_hash,
        "ko_manifest_sha256": ko_manifest_hash,
        "matched_ground_truth_sha256": matched_ground_truth_hash,
        "A0_evaluation_sha256": evaluation_hashes["A0"],
        "A_prime_evaluation_sha256": evaluation_hashes["A_prime"],
        "B_prime_evaluation_sha256": evaluation_hashes["B_prime"],
        "A_prime_input_sha256": input_hashes["A_prime"],
        "B_prime_input_sha256": input_hashes["B_prime"],
        "A_prime_run_metadata_sha256": metadata_hashes["A_prime"],
        "B_prime_run_metadata_sha256": metadata_hashes["B_prime"],
        "A_prime_prediction_sha256": prediction_hashes["A_prime"],
        "B_prime_prediction_sha256": prediction_hashes["B_prime"],
        "batch_plan_sha256": batch_plan_hash,
    }
    for filename in [
        "pipeline_metrics.json",
        "pipeline_errors.json",
        "pair_transitions.json",
    ]:
        update_json(
            bundle / filename,
            lambda value, current=provenance: value.__setitem__(
                "provenance", current
            ),
        )

    update_json(
        bundle / "pipeline_evaluation_complete.json",
        lambda value: value.update({
            "upstream": {
                **provenance,
                "alignment_bundle_complete_sha256": sha256_file(
                    bundle / "alignment_bundle_complete.json"
                ),
                "projection_bundle_complete_sha256": sha256_file(
                    bundle / "projection_bundle_complete.json"
                ),
            },
            "artifacts": {
                filename: sha256_file(bundle / filename)
                for filename in [
                    "pipeline_metrics.json",
                    "pipeline_errors.json",
                    "pair_transitions.json",
                ]
            },
        }),
    )

    return bundle, provenance
