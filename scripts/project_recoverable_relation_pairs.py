#!/usr/bin/env python3
"""Project final KO alignment into matched Relation experiment artifacts."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from . import align_predicted_kos as alignment_lib
    from .knowledge_object_matching import NAME_MATCHING_NORMALIZATION_VERSION
    from .normalize_predicted_kos import STRUCTURAL_NORMALIZATION_VERSION
    from .run_relation_extraction import validate_model_input
except ImportError:  # Direct execution: python3 scripts/project_recoverable_relation_pairs.py
    import align_predicted_kos as alignment_lib
    from knowledge_object_matching import NAME_MATCHING_NORMALIZATION_VERSION
    from normalize_predicted_kos import STRUCTURAL_NORMALIZATION_VERSION
    from run_relation_extraction import validate_model_input


ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.1"
DERIVATION_VERSION = "predicted_ko_projection_v0_1"
SLOT_PATTERN = re.compile(r"ko_slot_[0-9]{3}")
UNRECOVERABLE_REASON_ORDER = [
    "missing_endpoint",
    "duplicate_endpoint",
    "split_endpoint",
    "merge_endpoint",
    "ambiguous_endpoint",
    "granularity_mismatch",
    "collapsed_endpoints",
]
STATUS_TO_REASON = {
    "missing": "missing_endpoint",
    "duplicate": "duplicate_endpoint",
    "split": "split_endpoint",
    "merge": "merge_endpoint",
    "ambiguous": "ambiguous_endpoint",
    "granularity_mismatch": "granularity_mismatch",
}
MANAGED_FILENAMES = [
    "recoverable_pair_manifest.json",
    "recoverable_ko_manifest.json",
    "matched_knowledge_objects.json",
    "matched_relation_ground_truth.json",
    "oracle_normalized_input.json",
    "predicted_normalized_input.json",
    "batch_plan.json",
    "projection_errors.json",
]
COMPLETION_FILENAME = "projection_bundle_complete.json"

KORef = tuple[str, str]


class ProjectionError(RuntimeError):
    """A fatal projection input or derived-artifact integrity error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> str:
    return alignment_lib.canonical_json(value)


def serialize_json(value: Any) -> str:
    return alignment_lib.serialize_json(value)


def sha256_bytes(value: bytes) -> str:
    return alignment_lib.sha256_bytes(value)


def sha256_text(value: str) -> str:
    return alignment_lib.sha256_text(value)


def sha256_json(value: Any) -> str:
    return alignment_lib.sha256_json(value)


def artifact_sha256(value: Any) -> str:
    return sha256_text(serialize_json(value))


def ref_dict(ref: KORef) -> dict[str, str]:
    return {"lecture_id": ref[0], "ko_id": ref[1]}


def ref_key(value: Any, *, field: str) -> KORef:
    try:
        return alignment_lib.ref_key(value, field=field)
    except alignment_lib.AlignmentError as exc:
        raise ProjectionError("unknown_ko_reference", str(exc)) from exc


def ref_label(ref: KORef) -> str:
    return f"{ref[0]}::{ref[1]}"


def require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectionError("invalid_projection_input", f"{field} must be non-empty.")
    return value


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def resolve_path(value: str, default: Path | None = None) -> Path:
    if not value and default is not None:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_json_bytes(path: Path, *, code: str) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8")), raw
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectionError(code, f"Unable to read {path}: {exc}") from exc


def parse_relation_ground_truth(
    data: Any,
    *,
    oracle_refs: set[KORef],
) -> tuple[str, list[str], list[dict[str, Any]]]:
    if not isinstance(data, dict):
        raise ProjectionError("invalid_relation_ground_truth", "Relation ground truth must be an object.")
    split = require_string(data.get("split"), field="relation_ground_truth.split")
    primary_categories = data.get("primary_scoring_categories")
    if not isinstance(primary_categories, list) or not all(
        isinstance(item, str) and item for item in primary_categories
    ):
        raise ProjectionError(
            "invalid_relation_ground_truth",
            "primary_scoring_categories must be a non-empty string list.",
        )
    pairs = data.get("pairs")
    if not isinstance(pairs, list):
        raise ProjectionError("invalid_relation_ground_truth", "pairs must be a list.")
    parsed: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ProjectionError(
                "invalid_relation_ground_truth", f"pairs[{index}] must be an object."
            )
        pair_id = require_string(pair.get("pair_id"), field=f"pairs[{index}].pair_id")
        if pair_id in seen_ids:
            raise ProjectionError("duplicate_pair_id", f"Duplicate pair ID {pair_id}.")
        seen_ids.add(pair_id)
        category = require_string(pair.get("category"), field=f"{pair_id}.category")
        source = ref_key(pair.get("source"), field=f"{pair_id}.source")
        target = ref_key(pair.get("target"), field=f"{pair_id}.target")
        if source == target:
            raise ProjectionError("collapsed_oracle_pair", f"{pair_id} repeats one Oracle endpoint.")
        unknown = [ref for ref in [source, target] if ref not in oracle_refs]
        if unknown:
            raise ProjectionError(
                "unknown_ko_reference",
                f"{pair_id} references unknown Oracle KOs: {unknown}.",
            )
        parsed.append({
            "pair_id": pair_id,
            "category": category,
            "source_ref": source,
            "target_ref": target,
            "raw": pair,
        })
    return split, list(primary_categories), parsed


def raw_oracle_index(data: dict[str, Any]) -> tuple[dict[KORef, dict[str, Any]], dict[str, dict[str, Any]]]:
    objects: dict[KORef, dict[str, Any]] = {}
    lectures: dict[str, dict[str, Any]] = {}
    for lecture in data["lectures"]:
        lecture_id = lecture["lecture_id"]
        if lecture_id in lectures:
            raise ProjectionError(
                "duplicate_oracle_ko_identity", f"Duplicate Oracle lecture {lecture_id}."
            )
        lectures[lecture_id] = lecture
        for obj in lecture["objects"]:
            ref = lecture_id, obj["id"]
            if ref in objects:
                raise ProjectionError(
                    "duplicate_oracle_ko_identity", f"Duplicate Oracle KO {ref_label(ref)}."
                )
            objects[ref] = obj
    return objects, lectures


def validate_final_alignment(
    alignment: Any,
    *,
    split: str,
    oracle_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
    lectures: dict[str, str],
    oracle_inventory_sha256: str,
    predicted_inventory_sha256: str,
) -> tuple[dict[KORef, dict[str, Any]], dict[KORef, dict[str, Any]]]:
    if not isinstance(alignment, dict):
        raise ProjectionError("invalid_alignment", "Alignment must be an object.")
    if alignment.get("evaluation_status") != "final":
        raise ProjectionError(
            "unresolved_alignment_projected", "Projection requires final alignment."
        )
    if alignment.get("split") != split:
        raise ProjectionError("split_mismatch", "Alignment and Relation split differ.")
    if alignment.get("structural_normalization_version") != STRUCTURAL_NORMALIZATION_VERSION:
        raise ProjectionError("normalization_version_mismatch", "Structural normalization version differs.")
    if alignment.get("name_matching_normalization_version") != NAME_MATCHING_NORMALIZATION_VERSION:
        raise ProjectionError("normalization_version_mismatch", "Name matching version differs.")
    if alignment.get("oracle_inventory_sha256") != oracle_inventory_sha256:
        raise ProjectionError("stale_alignment_reference", "Alignment Oracle inventory hash is stale.")
    if alignment.get("predicted_inventory_sha256") != predicted_inventory_sha256:
        raise ProjectionError("stale_alignment_reference", "Alignment predicted inventory hash is stale.")
    expected_lecture_hashes = {
        lecture_id: sha256_text(text) for lecture_id, text in sorted(lectures.items())
    }
    if alignment.get("lecture_sha256") != expected_lecture_hashes:
        raise ProjectionError("stale_alignment_reference", "Alignment lecture hashes are stale.")
    try:
        alignment_lib.validate_bidirectional_accounting(alignment)
    except alignment_lib.AlignmentError as exc:
        raise ProjectionError(exc.code, str(exc)) from exc
    oracle_records: dict[KORef, dict[str, Any]] = {}
    for record in alignment.get("oracle_records", []):
        ref = ref_key(record.get("oracle_ref"), field="alignment.oracle_ref")
        if ref in oracle_records:
            raise ProjectionError("duplicate_oracle_ko_identity", f"Duplicate alignment Oracle {ref_label(ref)}.")
        if record.get("adjudication_required"):
            raise ProjectionError("unresolved_alignment_projected", f"{ref_label(ref)} still requires adjudication.")
        oracle_records[ref] = record
    predicted_records: dict[KORef, dict[str, Any]] = {}
    for record in alignment.get("predicted_records", []):
        ref = ref_key(record.get("predicted_ref"), field="alignment.predicted_ref")
        if ref in predicted_records:
            raise ProjectionError(
                "duplicate_predicted_ko_identity", f"Duplicate alignment prediction {ref_label(ref)}."
            )
        predicted_records[ref] = record
    if set(oracle_records) != set(oracle_objects):
        raise ProjectionError("incomplete_oracle_accounting", "Alignment does not account for every Oracle KO.")
    if set(predicted_records) != set(predicted_objects):
        raise ProjectionError(
            "incomplete_predicted_accounting", "Alignment does not account for every predicted KO."
        )
    return oracle_records, predicted_records


def endpoint_reasons(record: dict[str, Any]) -> list[str]:
    if (
        record.get("recoverable") is True
        and record.get("identity_match") is True
        and record.get("primary_structural_status") == "one_to_one"
        and isinstance(record.get("matched_predicted_ref"), dict)
    ):
        return []
    status = record.get("primary_structural_status")
    return [STATUS_TO_REASON.get(status, "ambiguous_endpoint")]


def pair_unrecoverable_reasons(
    first: dict[str, Any], second: dict[str, Any]
) -> list[str]:
    reasons = [*endpoint_reasons(first), *endpoint_reasons(second)]
    first_match = first.get("matched_predicted_ref")
    second_match = second.get("matched_predicted_ref")
    collapsed = first_match is not None and first_match == second_match
    if not collapsed:
        first_links = first.get("linked_predicted_refs", [])
        second_links = second.get("linked_predicted_refs", [])
        collapsed = (
            len(first_links) == 1
            and len(second_links) == 1
            and first_links[0] == second_links[0]
        )
    if collapsed:
        reasons.append("collapsed_endpoints")
    unique = set(reasons)
    return [reason for reason in UNRECOVERABLE_REASON_ORDER if reason in unique]


def neutral_ref(oracle_ref: KORef, slot_id: str) -> dict[str, str]:
    return {"lecture_id": oracle_ref[0], "ko_id": slot_id}


def translate_pair_annotations(
    pair: dict[str, Any],
    *,
    slot_by_oracle: dict[KORef, str],
) -> dict[str, Any]:
    translated = copy.deepcopy(pair)
    source = ref_key(pair["source"], field=f"{pair['pair_id']}.source")
    target = ref_key(pair["target"], field=f"{pair['pair_id']}.target")
    translated["source"] = neutral_ref(source, slot_by_oracle[source])
    translated["target"] = neutral_ref(target, slot_by_oracle[target])
    for index, alternative in enumerate(translated.get("acceptable_alternatives", [])):
        source_ref = ref_key(
            alternative["source"],
            field=f"{pair['pair_id']}.acceptable_alternatives[{index}].source",
        )
        target_ref = ref_key(
            alternative["target"],
            field=f"{pair['pair_id']}.acceptable_alternatives[{index}].target",
        )
        alternative["source"] = neutral_ref(source_ref, slot_by_oracle[source_ref])
        alternative["target"] = neutral_ref(target_ref, slot_by_oracle[target_ref])
    return translated


def make_matched_ko_ground_truth(
    oracle_data: dict[str, Any],
    *,
    relation_split: str,
    slots: list[dict[str, Any]],
    oracle_raw_objects: dict[KORef, dict[str, Any]],
    oracle_lectures: dict[str, dict[str, Any]],
    provenance: dict[str, str],
) -> dict[str, Any]:
    slots_by_lecture: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for slot in slots:
        oracle_ref = ref_key(slot["oracle_ref"], field="ko_manifest.oracle_ref")
        raw = oracle_raw_objects[oracle_ref]
        slots_by_lecture[oracle_ref[0]].append({
            "id": slot["slot_id"],
            "name": raw["name"],
            "type": raw["type"],
            "category": raw.get("category", "required"),
            "aliases": copy.deepcopy(raw.get("aliases", [])),
            "source_spans": copy.deepcopy(raw["source_spans"]),
        })
    lectures: list[dict[str, Any]] = []
    for lecture_id in sorted(slots_by_lecture):
        source_lecture = oracle_lectures[lecture_id]
        lectures.append({
            "lecture_id": lecture_id,
            "path": source_lecture["path"],
            "objects": sorted(slots_by_lecture[lecture_id], key=lambda item: item["id"]),
        })
    return {
        "artifact_type": "matched_knowledge_object_ground_truth",
        "version": VERSION,
        "split": relation_split,
        "status": "derived",
        "created": oracle_data.get("created", "derived"),
        "description": "Evaluator-facing neutral-slot Oracle KO inventory derived by Step 4.3.",
        "scope": "Contains only KOs referenced by recoverable primary Relation pairs.",
        "annotation_guidelines": oracle_data.get(
            "annotation_guidelines", "benchmark/annotation_guidelines.md"
        ),
        "evaluation_protocol": oracle_data.get(
            "evaluation_protocol", "benchmark/evaluation_protocol.md"
        ),
        "notes": [
            "This artifact is deterministically derived and is not model-facing.",
            "It does not repair B-prime Knowledge Object content.",
        ],
        "allowed_object_types": copy.deepcopy(
            oracle_data.get("allowed_object_types", ["Concept", "Method", "Formula"])
        ),
        "derivation": {
            "version": DERIVATION_VERSION,
            "original_ko_ground_truth_sha256": provenance["oracle_inventory_sha256"],
            "alignment_sha256": provenance["alignment_sha256"],
            "pair_manifest_sha256": provenance["pair_manifest_sha256"],
            "ko_manifest_sha256": provenance["ko_manifest_sha256"],
        },
        "lectures": lectures,
    }


def make_matched_relation_ground_truth(
    relation_data: dict[str, Any],
    *,
    recoverable_pair_ids: list[str],
    slot_by_oracle: dict[KORef, str],
    matched_ko_path: str,
    provenance: dict[str, str],
) -> dict[str, Any]:
    by_id = {pair["pair_id"]: pair for pair in relation_data["pairs"]}
    pairs = [
        translate_pair_annotations(by_id[pair_id], slot_by_oracle=slot_by_oracle)
        for pair_id in recoverable_pair_ids
    ]
    result = copy.deepcopy(relation_data)
    result["artifact_type"] = "matched_relation_ground_truth"
    result["status"] = "derived"
    result["description"] = "Matched primary Relation ground truth using neutral KO slots."
    result["knowledge_object_ground_truths"] = [matched_ko_path]
    result["pairs"] = pairs
    result["lectures"] = sorted(
        {ref["lecture_id"] for pair in pairs for ref in [pair["source"], pair["target"]]}
    )
    result["notes"] = [
        *relation_data.get("notes", []),
        "This artifact is deterministically derived; it is never model-facing.",
    ]
    result["derivation"] = {
        "version": DERIVATION_VERSION,
        "original_ground_truth_sha256": provenance["original_ground_truth_sha256"],
        "alignment_sha256": provenance["alignment_sha256"],
        "pair_manifest_sha256": provenance["pair_manifest_sha256"],
        "ko_manifest_sha256": provenance["ko_manifest_sha256"],
        "matched_knowledge_objects_sha256": provenance[
            "matched_knowledge_objects_sha256"
        ],
        "structural_normalization_version": STRUCTURAL_NORMALIZATION_VERSION,
        "name_matching_normalization_version": NAME_MATCHING_NORMALIZATION_VERSION,
    }
    return result


def make_model_input(
    *,
    relation_data: dict[str, Any],
    pair_manifest: dict[str, Any],
    slots: list[dict[str, Any]],
    oracle_raw_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
    lectures: dict[str, str],
    condition: str,
) -> dict[str, Any]:
    referenced_lectures = sorted(
        {slot["oracle_ref"]["lecture_id"] for slot in slots}
    )
    knowledge_objects: list[dict[str, Any]] = []
    for slot in slots:
        oracle_ref = ref_key(slot["oracle_ref"], field="slot.oracle_ref")
        predicted_ref = ref_key(slot["predicted_ref"], field="slot.predicted_ref")
        content = (
            oracle_raw_objects[oracle_ref]
            if condition == "A_prime"
            else predicted_objects[predicted_ref]
        )
        knowledge_objects.append({
            "lecture_id": oracle_ref[0],
            "ko_id": slot["slot_id"],
            "name": content["name"],
            "type": content["type"],
            "source_spans": copy.deepcopy(content["source_spans"]),
        })
    candidate_pairs = [
        {
            "pair_id": pair["pair_id"],
            "ko_a": {
                "lecture_id": pair["ko_a_mapping"]["oracle_ref"]["lecture_id"],
                "ko_id": pair["ko_a_slot_id"],
            },
            "ko_b": {
                "lecture_id": pair["ko_b_mapping"]["oracle_ref"]["lecture_id"],
                "ko_id": pair["ko_b_slot_id"],
            },
        }
        for pair in pair_manifest["primary_pairs"]
    ]
    allowed = relation_data["allowed_relation_types"]
    return {
        "relation_schema": {
            "graph_relation_types": [item for item in allowed if item != "NO_RELATION"],
            "benchmark_only_relation_types": ["NO_RELATION"],
        },
        "lectures": [
            {"lecture_id": lecture_id, "text": lectures[lecture_id]}
            for lecture_id in referenced_lectures
        ],
        "knowledge_objects": knowledge_objects,
        "candidate_pairs": candidate_pairs,
    }


def make_input_artifact(
    *,
    condition: str,
    model_input: dict[str, Any],
    lecture_hashes: dict[str, str],
    provenance: dict[str, str],
    batch_plan: dict[str, Any],
) -> dict[str, Any]:
    batches = batch_plan["batches"]
    batch = batches[0] if batches else None
    return {
        "artifact_type": "matched_relation_input",
        "version": VERSION,
        "condition": condition,
        "structural_normalization_version": STRUCTURAL_NORMALIZATION_VERSION,
        "pair_manifest_sha256": provenance["pair_manifest_sha256"],
        "ko_manifest_sha256": provenance["ko_manifest_sha256"],
        "matched_ground_truth_sha256": provenance["matched_ground_truth_sha256"],
        "relation_prompt_sha256": provenance["relation_prompt_sha256"],
        "relation_schema_sha256": provenance["relation_schema_sha256"],
        "batch_plan_sha256": provenance["batch_plan_sha256"],
        "ko_content_sha256": sha256_json(model_input["knowledge_objects"]),
        "model_input_sha256": sha256_json(model_input),
        "lecture_sha256": copy.deepcopy(lecture_hashes),
        "batch_id": batch["batch_id"] if batch else None,
        "batch_index": batch["batch_index"] if batch else None,
        "batch_count": len(batches),
        "model_input": model_input,
    }


def project_artifacts(
    relation_data: Any,
    oracle_data: Any,
    predicted_data: Any,
    alignment: Any,
    lecture_data: Any,
    *,
    matched_ko_path: str,
    original_ground_truth_sha256: str | None = None,
    oracle_inventory_sha256: str | None = None,
    predicted_inventory_sha256: str | None = None,
    alignment_sha256: str | None = None,
    relation_prompt_sha256: str,
    relation_schema_sha256: str,
) -> dict[str, Any]:
    try:
        oracle_split, oracle_objects = alignment_lib.parse_oracle_inventory(oracle_data)
        predicted_split, predicted_objects = alignment_lib.parse_predicted_inventory(
            predicted_data
        )
        lectures = alignment_lib.parse_lectures(lecture_data)
    except alignment_lib.AlignmentError as exc:
        raise ProjectionError(exc.code, str(exc)) from exc
    relation_split, primary_categories, parsed_pairs = parse_relation_ground_truth(
        relation_data, oracle_refs=set(oracle_objects)
    )
    if relation_split != oracle_split or relation_split != predicted_split:
        raise ProjectionError("split_mismatch", "Projection inputs use different splits.")
    oracle_hash = oracle_inventory_sha256 or artifact_sha256(oracle_data)
    predicted_hash = predicted_inventory_sha256 or artifact_sha256(predicted_data)
    relation_hash = original_ground_truth_sha256 or artifact_sha256(relation_data)
    alignment_hash = alignment_sha256 or artifact_sha256(alignment)
    oracle_records, predicted_records = validate_final_alignment(
        alignment,
        split=relation_split,
        oracle_objects=oracle_objects,
        predicted_objects=predicted_objects,
        lectures=lectures,
        oracle_inventory_sha256=oracle_hash,
        predicted_inventory_sha256=predicted_hash,
    )
    oracle_raw_objects, oracle_lectures = raw_oracle_index(oracle_data)

    recoverable_interim: list[dict[str, Any]] = []
    unrecoverable: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for pair in sorted(parsed_pairs, key=lambda item: item["pair_id"]):
        if pair["category"] not in primary_categories:
            diagnostics.append({
                "pair_id": pair["pair_id"],
                "category": pair["category"],
                "excluded_from_primary": True,
            })
            continue
        ordered_refs = sorted([pair["source_ref"], pair["target_ref"]])
        first_record = oracle_records[ordered_refs[0]]
        second_record = oracle_records[ordered_refs[1]]
        reasons = pair_unrecoverable_reasons(first_record, second_record)
        if reasons:
            unrecoverable.append({
                "pair_id": pair["pair_id"],
                "category": pair["category"],
                "pair_status": "unrecoverable",
                "unrecoverable_reasons": reasons,
            })
            continue
        first_predicted = ref_key(
            first_record["matched_predicted_ref"], field="matched_predicted_ref"
        )
        second_predicted = ref_key(
            second_record["matched_predicted_ref"], field="matched_predicted_ref"
        )
        if first_predicted == second_predicted:
            unrecoverable.append({
                "pair_id": pair["pair_id"],
                "category": pair["category"],
                "pair_status": "unrecoverable",
                "unrecoverable_reasons": ["collapsed_endpoints"],
            })
            continue
        recoverable_interim.append({
            "pair_id": pair["pair_id"],
            "category": pair["category"],
            "ordered_oracle_refs": ordered_refs,
            "ordered_predicted_refs": [first_predicted, second_predicted],
        })

    endpoint_refs = sorted(
        {ref for pair in recoverable_interim for ref in pair["ordered_oracle_refs"]}
    )
    slot_by_oracle = {
        ref: f"ko_slot_{index:03d}" for index, ref in enumerate(endpoint_refs, start=1)
    }
    primary_pairs: list[dict[str, Any]] = []
    references_by_oracle: dict[KORef, list[str]] = defaultdict(list)
    for pair in recoverable_interim:
        first_oracle, second_oracle = pair["ordered_oracle_refs"]
        first_predicted, second_predicted = pair["ordered_predicted_refs"]
        references_by_oracle[first_oracle].append(pair["pair_id"])
        references_by_oracle[second_oracle].append(pair["pair_id"])
        primary_pairs.append({
            "pair_id": pair["pair_id"],
            "category": pair["category"],
            "ko_a_slot_id": slot_by_oracle[first_oracle],
            "ko_b_slot_id": slot_by_oracle[second_oracle],
            "ko_a_mapping": {
                "oracle_ref": ref_dict(first_oracle),
                "predicted_ref": ref_dict(first_predicted),
            },
            "ko_b_mapping": {
                "oracle_ref": ref_dict(second_oracle),
                "predicted_ref": ref_dict(second_predicted),
            },
            "pair_status": "recoverable",
        })
    primary_pair_count = sum(
        pair["category"] in primary_categories for pair in parsed_pairs
    )
    pair_manifest = {
        "artifact_type": "recoverable_pair_manifest",
        "version": VERSION,
        "split": relation_split,
        "derivation_version": DERIVATION_VERSION,
        "original_ground_truth_sha256": relation_hash,
        "alignment_sha256": alignment_hash,
        "primary_scoring_categories": primary_categories,
        "original_primary_pair_count": primary_pair_count,
        "primary_pairs": primary_pairs,
        "unrecoverable_primary_pairs": unrecoverable,
        "diagnostic_pairs": diagnostics,
    }
    pair_manifest_hash = artifact_sha256(pair_manifest)

    slots: list[dict[str, Any]] = []
    for oracle_ref in endpoint_refs:
        record = oracle_records[oracle_ref]
        predicted_ref = ref_key(
            record["matched_predicted_ref"], field="matched_predicted_ref"
        )
        slots.append({
            "slot_id": slot_by_oracle[oracle_ref],
            "oracle_ref": ref_dict(oracle_ref),
            "predicted_ref": ref_dict(predicted_ref),
            "referenced_by_pair_ids": sorted(references_by_oracle[oracle_ref]),
        })
    ko_manifest = {
        "artifact_type": "recoverable_ko_manifest",
        "version": VERSION,
        "split": relation_split,
        "derivation_version": DERIVATION_VERSION,
        "alignment_sha256": alignment_hash,
        "pair_manifest_sha256": pair_manifest_hash,
        "slots": slots,
    }
    ko_manifest_hash = artifact_sha256(ko_manifest)

    provenance = {
        "original_ground_truth_sha256": relation_hash,
        "oracle_inventory_sha256": oracle_hash,
        "predicted_inventory_sha256": predicted_hash,
        "alignment_sha256": alignment_hash,
        "pair_manifest_sha256": pair_manifest_hash,
        "ko_manifest_sha256": ko_manifest_hash,
        "relation_prompt_sha256": relation_prompt_sha256,
        "relation_schema_sha256": relation_schema_sha256,
    }
    matched_kos = make_matched_ko_ground_truth(
        oracle_data,
        relation_split=relation_split,
        slots=slots,
        oracle_raw_objects=oracle_raw_objects,
        oracle_lectures=oracle_lectures,
        provenance=provenance,
    )
    matched_kos_hash = artifact_sha256(matched_kos)
    provenance["matched_knowledge_objects_sha256"] = matched_kos_hash
    matched_ground_truth = make_matched_relation_ground_truth(
        relation_data,
        recoverable_pair_ids=[pair["pair_id"] for pair in primary_pairs],
        slot_by_oracle=slot_by_oracle,
        matched_ko_path=matched_ko_path,
        provenance=provenance,
    )
    matched_ground_truth_hash = artifact_sha256(matched_ground_truth)
    provenance["matched_ground_truth_sha256"] = matched_ground_truth_hash

    batches = []
    if primary_pairs:
        batches.append({
            "batch_id": "batch_001",
            "batch_index": 1,
            "pair_ids": [pair["pair_id"] for pair in primary_pairs],
            "ko_slot_ids": [slot["slot_id"] for slot in slots],
        })
    batch_plan = {
        "artifact_type": "matched_relation_batch_plan",
        "version": VERSION,
        "batching_strategy": "single_deterministic_batch_v0_1",
        "pair_manifest_sha256": pair_manifest_hash,
        "ko_manifest_sha256": ko_manifest_hash,
        "executable_batch_count": len(batches),
        "batches": batches,
    }
    batch_plan_hash = artifact_sha256(batch_plan)
    provenance["batch_plan_sha256"] = batch_plan_hash

    referenced_lecture_ids = sorted({ref[0] for ref in endpoint_refs})
    lecture_hashes = {
        lecture_id: sha256_text(lectures[lecture_id])
        for lecture_id in referenced_lecture_ids
    }
    oracle_model_input = make_model_input(
        relation_data=relation_data,
        pair_manifest=pair_manifest,
        slots=slots,
        oracle_raw_objects=oracle_raw_objects,
        predicted_objects=predicted_objects,
        lectures=lectures,
        condition="A_prime",
    )
    predicted_model_input = make_model_input(
        relation_data=relation_data,
        pair_manifest=pair_manifest,
        slots=slots,
        oracle_raw_objects=oracle_raw_objects,
        predicted_objects=predicted_objects,
        lectures=lectures,
        condition="B_prime",
    )
    oracle_input = make_input_artifact(
        condition="A_prime",
        model_input=oracle_model_input,
        lecture_hashes=lecture_hashes,
        provenance=provenance,
        batch_plan=batch_plan,
    )
    predicted_input = make_input_artifact(
        condition="B_prime",
        model_input=predicted_model_input,
        lecture_hashes=lecture_hashes,
        provenance=provenance,
        batch_plan=batch_plan,
    )

    upstream_flags = []
    for slot in slots:
        oracle_ref = ref_key(slot["oracle_ref"], field="slot.oracle_ref")
        record = oracle_records[oracle_ref]
        flags = []
        if record.get("type_match") is False:
            flags.append("ko_type_mismatch")
        if record.get("predicted_source_span_exact") is False:
            flags.append("predicted_source_span_invalid")
        if record.get("predicted_source_span_supports_identity") is False:
            flags.append("predicted_source_span_not_supporting_identity")
        if flags:
            upstream_flags.append({
                "slot_id": slot["slot_id"],
                "oracle_ref": slot["oracle_ref"],
                "predicted_ref": slot["predicted_ref"],
                "flags": flags,
            })
    projection_errors = {
        "artifact_type": "predicted_ko_projection_diagnostics",
        "version": VERSION,
        "evaluation_status": "final",
        "pair_recoverability": {
            "numerator": len(primary_pairs),
            "denominator": primary_pair_count,
            "value": (
                len(primary_pairs) / primary_pair_count if primary_pair_count else None
            ),
        },
        "unrecoverable_primary_pairs": copy.deepcopy(unrecoverable),
        "diagnostic_pairs": copy.deepcopy(diagnostics),
        "unmatched_extra_predicted_kos": [
            record["predicted_ref"]
            for record in alignment["predicted_records"]
            if record.get("accounting_status") == "unmatched_extra"
        ],
        "recoverable_slot_quality_flags": upstream_flags,
    }
    artifacts = {
        "recoverable_pair_manifest.json": pair_manifest,
        "recoverable_ko_manifest.json": ko_manifest,
        "matched_knowledge_objects.json": matched_kos,
        "matched_relation_ground_truth.json": matched_ground_truth,
        "oracle_normalized_input.json": oracle_input,
        "predicted_normalized_input.json": predicted_input,
        "batch_plan.json": batch_plan,
        "projection_errors.json": projection_errors,
    }
    validate_projection_artifacts(
        artifacts,
        original_pair_ids={pair["pair_id"] for pair in parsed_pairs},
        original_primary_pair_ids={
            pair["pair_id"]
            for pair in parsed_pairs
            if pair["category"] in primary_categories
        },
        original_diagnostic_pair_ids={
            pair["pair_id"]
            for pair in parsed_pairs
            if pair["category"] not in primary_categories
        },
        alignment_sha256=alignment_hash,
    )
    return artifacts


def validate_projection_artifacts(
    artifacts: dict[str, Any],
    *,
    original_pair_ids: set[str],
    original_primary_pair_ids: set[str] | None = None,
    original_diagnostic_pair_ids: set[str] | None = None,
    alignment_sha256: str,
) -> None:
    missing = set(MANAGED_FILENAMES) - set(artifacts)
    if missing:
        raise ProjectionError("incomplete_projection_bundle", f"Missing artifacts: {sorted(missing)}.")
    pair_manifest = artifacts["recoverable_pair_manifest.json"]
    ko_manifest = artifacts["recoverable_ko_manifest.json"]
    matched_kos = artifacts["matched_knowledge_objects.json"]
    matched_gt = artifacts["matched_relation_ground_truth.json"]
    oracle_input = artifacts["oracle_normalized_input.json"]
    predicted_input = artifacts["predicted_normalized_input.json"]
    batch_plan = artifacts["batch_plan.json"]
    projection_errors = artifacts["projection_errors.json"]

    if pair_manifest.get("alignment_sha256") != alignment_sha256:
        raise ProjectionError("stale_alignment_reference", "Pair manifest has stale alignment hash.")
    pair_manifest_hash = artifact_sha256(pair_manifest)
    if ko_manifest.get("pair_manifest_sha256") != pair_manifest_hash:
        raise ProjectionError("stale_pair_manifest_reference", "KO manifest has stale pair-manifest hash.")
    if ko_manifest.get("alignment_sha256") != alignment_sha256:
        raise ProjectionError("stale_alignment_reference", "KO manifest has stale alignment hash.")
    ko_manifest_hash = artifact_sha256(ko_manifest)
    pair_arrays = [
        pair_manifest.get("primary_pairs", []),
        pair_manifest.get("unrecoverable_primary_pairs", []),
        pair_manifest.get("diagnostic_pairs", []),
    ]
    flattened_ids = [pair["pair_id"] for array in pair_arrays for pair in array]
    if len(flattened_ids) != len(set(flattened_ids)):
        raise ProjectionError("duplicate_pair_id", "Pair manifest contains duplicate pair IDs.")
    if set(flattened_ids) != original_pair_ids:
        missing_ids = original_pair_ids - set(flattened_ids)
        code = "missing_pair_id" if missing_ids else "unknown_pair_id"
        raise ProjectionError(code, "Pair manifest does not partition the original pair set.")
    for array in pair_arrays:
        ids = [pair["pair_id"] for pair in array]
        if ids != sorted(ids):
            raise ProjectionError("pair_manifest_order_mismatch", "Pair manifest order is not deterministic.")
    if original_primary_pair_ids is not None:
        projected_primary_ids = {
            pair["pair_id"]
            for array in pair_arrays[:2]
            for pair in array
        }
        if projected_primary_ids != original_primary_pair_ids:
            raise ProjectionError(
                "primary_denominator_mismatch",
                "Recoverable and unrecoverable arrays do not preserve the frozen primary universe.",
            )
        if pair_manifest.get("original_primary_pair_count") != len(
            original_primary_pair_ids
        ):
            raise ProjectionError(
                "primary_denominator_mismatch",
                "original_primary_pair_count differs from frozen ground truth.",
            )
    if original_diagnostic_pair_ids is not None:
        projected_diagnostic_ids = {
            pair["pair_id"] for pair in pair_manifest.get("diagnostic_pairs", [])
        }
        if projected_diagnostic_ids != original_diagnostic_pair_ids:
            raise ProjectionError(
                "diagnostic_denominator_mismatch",
                "Diagnostic pairs differ from frozen ground truth.",
            )

    slots = ko_manifest.get("slots", [])
    slot_ids = [slot["slot_id"] for slot in slots]
    expected_slot_ids = [f"ko_slot_{index:03d}" for index in range(1, len(slots) + 1)]
    if slot_ids != expected_slot_ids:
        raise ProjectionError("matched_slot_id_mismatch", "KO slots are not consecutive and ordered.")
    oracle_refs = [ref_key(slot["oracle_ref"], field="slot.oracle_ref") for slot in slots]
    if oracle_refs != sorted(oracle_refs) or len(oracle_refs) != len(set(oracle_refs)):
        raise ProjectionError("ko_manifest_derivation_mismatch", "KO slots do not follow Oracle order.")
    slot_by_id = {slot["slot_id"]: slot for slot in slots}
    expected_references: dict[str, list[str]] = defaultdict(list)
    for pair in pair_manifest["primary_pairs"]:
        first = pair["ko_a_slot_id"]
        second = pair["ko_b_slot_id"]
        if first == second:
            raise ProjectionError("collapsed_endpoints_projected", f"{pair['pair_id']} collapses endpoints.")
        if first not in slot_by_id or second not in slot_by_id:
            raise ProjectionError("unknown_slot_reference", f"{pair['pair_id']} references an unknown slot.")
        expected_references[first].append(pair["pair_id"])
        expected_references[second].append(pair["pair_id"])
        for side in ["ko_a", "ko_b"]:
            mapping = pair[f"{side}_mapping"]
            slot = slot_by_id[pair[f"{side}_slot_id"]]
            if mapping["oracle_ref"] != slot["oracle_ref"] or mapping["predicted_ref"] != slot["predicted_ref"]:
                raise ProjectionError("ko_manifest_derivation_mismatch", "Pair mapping disagrees with KO manifest.")
    for slot in slots:
        if slot["referenced_by_pair_ids"] != sorted(expected_references[slot["slot_id"]]):
            raise ProjectionError("ko_manifest_derivation_mismatch", "Slot pair references are stale.")

    matched_ko_hash = artifact_sha256(matched_kos)
    matched_ko_ids = [
        obj["id"]
        for lecture in matched_kos.get("lectures", [])
        for obj in lecture.get("objects", [])
    ]
    if set(matched_ko_ids) != set(slot_ids):
        code = (
            "matched_inventory_extra_ko"
            if len(matched_ko_ids) > len(slot_ids)
            else "matched_inventory_missing_ko"
        )
        raise ProjectionError(code, "Matched KO ground truth differs from KO manifest.")
    if matched_kos.get("derivation", {}).get("alignment_sha256") != alignment_sha256:
        raise ProjectionError("stale_alignment_reference", "Matched KO inventory has stale alignment hash.")
    if matched_kos.get("derivation", {}).get("pair_manifest_sha256") != pair_manifest_hash:
        raise ProjectionError("stale_pair_manifest_reference", "Matched KO inventory has stale pair hash.")
    if matched_kos.get("derivation", {}).get("ko_manifest_sha256") != ko_manifest_hash:
        raise ProjectionError("stale_ko_manifest", "Matched KO inventory has stale KO manifest hash.")
    if matched_gt.get("derivation", {}).get("matched_knowledge_objects_sha256") != matched_ko_hash:
        raise ProjectionError("stale_matched_ground_truth", "Matched GT has stale KO inventory hash.")
    if matched_gt.get("derivation", {}).get("alignment_sha256") != alignment_sha256:
        raise ProjectionError("stale_matched_ground_truth", "Matched GT has stale alignment hash.")
    if matched_gt.get("derivation", {}).get("pair_manifest_sha256") != pair_manifest_hash:
        raise ProjectionError("stale_matched_ground_truth", "Matched GT has stale pair-manifest hash.")
    if matched_gt.get("derivation", {}).get("ko_manifest_sha256") != ko_manifest_hash:
        raise ProjectionError("stale_matched_ground_truth", "Matched GT has stale KO-manifest hash.")
    expected_pair_ids = [pair["pair_id"] for pair in pair_manifest["primary_pairs"]]
    matched_pair_ids = [pair["pair_id"] for pair in matched_gt.get("pairs", [])]
    if set(matched_pair_ids) != set(expected_pair_ids):
        raise ProjectionError("matched_ground_truth_pair_set_mismatch", "Matched GT pair set differs.")
    if matched_pair_ids != expected_pair_ids:
        raise ProjectionError("matched_ground_truth_pair_order_mismatch", "Matched GT pair order differs.")

    if batch_plan.get("pair_manifest_sha256") != pair_manifest_hash:
        raise ProjectionError("matched_batching_mismatch", "Batch plan has stale pair manifest.")
    if batch_plan.get("ko_manifest_sha256") != ko_manifest_hash:
        raise ProjectionError("matched_batching_mismatch", "Batch plan has stale KO manifest.")
    batches = batch_plan.get("batches", [])
    expected_batch_count = 1 if expected_pair_ids else 0
    if batch_plan.get("executable_batch_count") != expected_batch_count or len(batches) != expected_batch_count:
        raise ProjectionError("matched_batching_mismatch", "Batch plan does not match recoverability.")
    if batches:
        if batches[0]["pair_ids"] != expected_pair_ids or batches[0]["ko_slot_ids"] != slot_ids:
            raise ProjectionError("matched_batching_mismatch", "Batch plan order differs from manifests.")
        if batches[0].get("batch_id") != "batch_001" or batches[0].get("batch_index") != 1:
            raise ProjectionError("matched_batching_mismatch", "Batch identity is not deterministic.")
    batch_plan_hash = artifact_sha256(batch_plan)
    matched_gt_hash = artifact_sha256(matched_gt)

    for condition, artifact in [
        ("A_prime", oracle_input),
        ("B_prime", predicted_input),
    ]:
        if artifact.get("condition") != condition:
            raise ProjectionError("matched_condition_mismatch", f"Unexpected {condition} artifact condition.")
        if artifact.get("pair_manifest_sha256") != pair_manifest_hash:
            raise ProjectionError("stale_pair_manifest_reference", f"{condition} pair manifest is stale.")
        if artifact.get("ko_manifest_sha256") != ko_manifest_hash:
            raise ProjectionError("stale_ko_manifest", f"{condition} KO manifest is stale.")
        if artifact.get("matched_ground_truth_sha256") != matched_gt_hash:
            raise ProjectionError(
                "stale_matched_ground_truth",
                f"{condition} matched ground-truth hash is stale.",
            )
        if artifact.get("batch_plan_sha256") != batch_plan_hash:
            raise ProjectionError("matched_batching_mismatch", f"{condition} batch plan is stale.")
        if artifact.get("structural_normalization_version") != STRUCTURAL_NORMALIZATION_VERSION:
            raise ProjectionError(
                "normalization_version_mismatch",
                f"{condition} structural normalization version differs.",
            )
        expected_batch = batches[0] if batches else None
        expected_batch_fields = (
            expected_batch["batch_id"] if expected_batch else None,
            expected_batch["batch_index"] if expected_batch else None,
            expected_batch_count,
        )
        actual_batch_fields = (
            artifact.get("batch_id"),
            artifact.get("batch_index"),
            artifact.get("batch_count"),
        )
        if actual_batch_fields != expected_batch_fields:
            raise ProjectionError(
                "matched_batching_mismatch",
                f"{condition} batch metadata differs from the batch plan.",
            )
        if artifact.get("ko_content_sha256") != sha256_json(artifact["model_input"]["knowledge_objects"]):
            raise ProjectionError("matched_input_hash_mismatch", f"{condition} KO content hash is stale.")
        if artifact.get("model_input_sha256") != sha256_json(artifact["model_input"]):
            raise ProjectionError("matched_input_hash_mismatch", f"{condition} model input hash is stale.")
        expected_lecture_hashes = {
            lecture["lecture_id"]: sha256_text(lecture["text"])
            for lecture in artifact["model_input"]["lectures"]
        }
        if artifact.get("lecture_sha256") != expected_lecture_hashes:
            raise ProjectionError(
                "matched_lecture_hash_mismatch",
                f"{condition} lecture hashes do not match model-facing text.",
            )

    if oracle_input["relation_prompt_sha256"] != predicted_input["relation_prompt_sha256"]:
        raise ProjectionError("matched_relation_prompt_hash_mismatch", "Prompt hashes differ.")
    if oracle_input["relation_schema_sha256"] != predicted_input["relation_schema_sha256"]:
        raise ProjectionError("matched_relation_schema_hash_mismatch", "Schema hashes differ.")
    if oracle_input["lecture_sha256"] != predicted_input["lecture_sha256"]:
        raise ProjectionError("matched_lecture_hash_mismatch", "Lecture hashes differ.")
    if oracle_input["batch_plan_sha256"] != predicted_input["batch_plan_sha256"]:
        raise ProjectionError("matched_batching_mismatch", "Condition batch plans differ.")

    a_model = oracle_input["model_input"]
    b_model = predicted_input["model_input"]
    if a_model["relation_schema"] != b_model["relation_schema"]:
        raise ProjectionError(
            "matched_relation_schema_mismatch",
            "A-prime and B-prime Relation schemas differ.",
        )
    if a_model["lectures"] != b_model["lectures"]:
        raise ProjectionError(
            "matched_lecture_content_mismatch",
            "A-prime and B-prime lecture content differs.",
        )
    a_pair_ids = [item["pair_id"] for item in a_model["candidate_pairs"]]
    b_pair_ids = [item["pair_id"] for item in b_model["candidate_pairs"]]
    if set(a_pair_ids) != set(b_pair_ids):
        raise ProjectionError(
            "matched_pair_id_set_mismatch", "Condition pair ID sets differ."
        )
    if a_pair_ids != b_pair_ids:
        raise ProjectionError("matched_pair_order_mismatch", "Condition pair order differs.")
    if a_model["candidate_pairs"] != b_model["candidate_pairs"]:
        raise ProjectionError(
            "matched_pair_slot_incidence_mismatch",
            "Condition pair-to-slot incidence differs.",
        )
    a_kos = a_model["knowledge_objects"]
    b_kos = b_model["knowledge_objects"]
    a_refs = [(item["lecture_id"], item["ko_id"]) for item in a_kos]
    b_refs = [(item["lecture_id"], item["ko_id"]) for item in b_kos]
    if set(a_refs) != set(b_refs):
        if len(b_refs) > len(a_refs):
            code = "matched_inventory_extra_ko"
        elif len(b_refs) < len(a_refs):
            code = "matched_inventory_missing_ko"
        else:
            code = "matched_slot_id_mismatch"
        raise ProjectionError(code, "Condition KO slot sets differ.")
    if a_refs != b_refs:
        raise ProjectionError("matched_ko_order_mismatch", "Condition KO order differs.")
    if a_refs != [(slot["oracle_ref"]["lecture_id"], slot["slot_id"]) for slot in slots]:
        raise ProjectionError("matched_inventory_missing_ko", "Model input slots differ from KO manifest.")
    candidate_members = {
        pair["pair_id"]: {
            ref_key(pair["ko_a"], field="candidate.ko_a"),
            ref_key(pair["ko_b"], field="candidate.ko_b"),
        }
        for pair in a_model["candidate_pairs"]
    }
    try:
        validate_model_input(a_model, candidate_members)
        validate_model_input(b_model, candidate_members)
    except RuntimeError as exc:
        message = str(exc)
        lowered = message.lower()
        if "leakage" in lowered or "forbidden" in lowered:
            code = "gold_relation_leakage"
        elif "unrelated or missing lectures" in lowered:
            code = "unknown_lecture_reference"
        else:
            code = "invalid_matched_model_input"
        raise ProjectionError(code, message) from exc
    for model in [a_model, b_model]:
        for obj in model["knowledge_objects"]:
            if not SLOT_PATTERN.fullmatch(obj["ko_id"]):
                raise ProjectionError("raw_ko_id_leakage", "Model-facing KO ID is not neutral.")
        for pair in model["candidate_pairs"]:
            for side in ["ko_a", "ko_b"]:
                if not SLOT_PATTERN.fullmatch(pair[side]["ko_id"]):
                    raise ProjectionError("raw_ko_id_leakage", "Candidate endpoint ID is not neutral.")

    expected_recoverability = {
        "numerator": len(expected_pair_ids),
        "denominator": pair_manifest.get("original_primary_pair_count"),
        "value": (
            len(expected_pair_ids) / pair_manifest["original_primary_pair_count"]
            if pair_manifest.get("original_primary_pair_count")
            else None
        ),
    }
    if projection_errors.get("evaluation_status") != "final":
        raise ProjectionError(
            "incomplete_projection_bundle", "Projection diagnostics are not final."
        )
    if projection_errors.get("pair_recoverability") != expected_recoverability:
        raise ProjectionError(
            "projection_diagnostics_mismatch",
            "Projection diagnostics disagree with pair recoverability.",
        )
    if projection_errors.get("unrecoverable_primary_pairs") != pair_manifest.get(
        "unrecoverable_primary_pairs"
    ):
        raise ProjectionError(
            "projection_diagnostics_mismatch",
            "Projection diagnostics disagree with unrecoverable pairs.",
        )
    if projection_errors.get("diagnostic_pairs") != pair_manifest.get(
        "diagnostic_pairs"
    ):
        raise ProjectionError(
            "projection_diagnostics_mismatch",
            "Projection diagnostics disagree with diagnostic pairs.",
        )


def validate_alignment_completion_marker(
    alignment_path: Path, alignment_raw: bytes
) -> str:
    marker_path = alignment_path.parent / "alignment_bundle_complete.json"
    marker, marker_raw = load_json_bytes(
        marker_path, code="incomplete_alignment_bundle"
    )
    if marker.get("artifact_type") != "predicted_ko_alignment_bundle_complete":
        raise ProjectionError("incomplete_alignment_bundle", "Invalid alignment completion marker.")
    if marker.get("evaluation_status") != "final":
        raise ProjectionError("unresolved_alignment_projected", "Alignment bundle is not final.")
    if marker.get("artifacts", {}).get(alignment_path.name) != sha256_bytes(alignment_raw):
        raise ProjectionError("incomplete_alignment_bundle", "Alignment marker hash is stale.")
    return sha256_bytes(marker_raw)


def write_projection_bundle(
    output_dir: Path,
    artifacts: dict[str, Any],
    *,
    alignment_bundle_complete_sha256: str,
    overwrite: bool,
) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", alignment_bundle_complete_sha256):
        raise ProjectionError(
            "incomplete_alignment_bundle",
            "Alignment completion-marker hash must be SHA-256.",
        )
    managed = [*MANAGED_FILENAMES, COMPLETION_FILENAME]
    existing = [output_dir / name for name in managed if (output_dir / name).exists()]
    if existing and not overwrite:
        raise ProjectionError(
            "output_exists",
            "Projection output already exists: " + ", ".join(str(path) for path in existing),
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_paths: dict[str, Path] = {}
    try:
        for name in MANAGED_FILENAMES:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output_dir,
                prefix=f".{name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(serialize_json(artifacts[name]))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_paths[name] = Path(temporary_file.name)
        completion = {
            "artifact_type": "predicted_ko_projection_bundle_complete",
            "version": VERSION,
            "evaluation_status": "final",
            "upstream": {
                "alignment_bundle_complete_sha256": (
                    alignment_bundle_complete_sha256
                )
            },
            "artifacts": {
                name: artifact_sha256(artifacts[name]) for name in MANAGED_FILENAMES
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{COMPLETION_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialize_json(completion))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_paths[COMPLETION_FILENAME] = Path(temporary_file.name)
        marker = output_dir / COMPLETION_FILENAME
        if marker.exists():
            marker.unlink()
        for name in MANAGED_FILENAMES:
            temporary_paths[name].replace(output_dir / name)
        temporary_paths[COMPLETION_FILENAME].replace(marker)
    finally:
        for path in temporary_paths.values():
            if path.exists():
                path.unlink()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project final predicted-KO alignment into matched Relation artifacts."
    )
    parser.add_argument("--relation-ground-truth", required=True)
    parser.add_argument("--oracle-inventory", required=True)
    parser.add_argument("--predicted-inventory", required=True)
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--lectures", required=True)
    parser.add_argument(
        "--relation-prompt",
        default="experiments/relation_extraction/002_prompt_refinement/prompt.md",
    )
    parser.add_argument(
        "--relation-schema",
        default="docs/decisions/004-relation-schema.md",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        relation_path = resolve_path(args.relation_ground_truth)
        oracle_path = resolve_path(args.oracle_inventory)
        predicted_path = resolve_path(args.predicted_inventory)
        alignment_path = resolve_path(args.alignment)
        lecture_path = resolve_path(args.lectures)
        prompt_path = resolve_path(args.relation_prompt)
        schema_path = resolve_path(args.relation_schema)
        output_dir = resolve_path(args.output_dir)
        relation_data, relation_raw = load_json_bytes(
            relation_path, code="invalid_relation_ground_truth"
        )
        oracle_data, oracle_raw = load_json_bytes(
            oracle_path, code="invalid_oracle_inventory"
        )
        predicted_data, predicted_raw = load_json_bytes(
            predicted_path, code="invalid_predicted_inventory"
        )
        alignment, alignment_raw = load_json_bytes(
            alignment_path, code="invalid_alignment"
        )
        lecture_data, _ = load_json_bytes(
            lecture_path, code="invalid_lecture_inventory"
        )
        try:
            prompt_raw = prompt_path.read_bytes()
            schema_raw = schema_path.read_bytes()
        except OSError as exc:
            raise ProjectionError("missing_frozen_method", str(exc)) from exc
        alignment_marker_hash = validate_alignment_completion_marker(
            alignment_path, alignment_raw
        )
        matched_ko_path = display_path(output_dir / "matched_knowledge_objects.json")
        artifacts = project_artifacts(
            relation_data,
            oracle_data,
            predicted_data,
            alignment,
            lecture_data,
            matched_ko_path=matched_ko_path,
            original_ground_truth_sha256=sha256_bytes(relation_raw),
            oracle_inventory_sha256=sha256_bytes(oracle_raw),
            predicted_inventory_sha256=sha256_bytes(predicted_raw),
            alignment_sha256=sha256_bytes(alignment_raw),
            relation_prompt_sha256=sha256_bytes(prompt_raw),
            relation_schema_sha256=sha256_bytes(schema_raw),
        )
        write_projection_bundle(
            output_dir,
            artifacts,
            alignment_bundle_complete_sha256=alignment_marker_hash,
            overwrite=args.overwrite,
        )
    except ProjectionError as exc:
        print(f"Projection failed [{exc.code}]: {exc}", file=sys.stderr)
        return 2 if exc.code == "output_exists" else 1
    print(f"Wrote final Step 4.3 projection bundle to {display_path(output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
