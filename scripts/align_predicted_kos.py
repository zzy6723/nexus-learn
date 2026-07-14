#!/usr/bin/env python3
"""Align normalized predicted Knowledge Objects to Oracle inventories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

try:
    from .knowledge_object_matching import (
        NAME_MATCHING_NORMALIZATION_VERSION,
        name_matching_key,
    )
    from .normalize_predicted_kos import STRUCTURAL_NORMALIZATION_VERSION
except ImportError:  # Direct execution: python3 scripts/align_predicted_kos.py
    from knowledge_object_matching import (
        NAME_MATCHING_NORMALIZATION_VERSION,
        name_matching_key,
    )
    from normalize_predicted_kos import STRUCTURAL_NORMALIZATION_VERSION


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT_VERSION = "v0.1"
ALLOWED_KO_TYPES = {"Concept", "Method", "Formula"}
STRUCTURAL_STATUSES = {
    "duplicate",
    "split",
    "merge",
    "ambiguous",
    "granularity_mismatch",
}
FORBIDDEN_RELATION_KEYS = {
    "relation_type",
    "direction",
    "pair_id",
    "category",
    "primary_scored",
    "gold_source",
    "gold_target",
    "gold_evidence",
    "gold_rationale",
}
STRUCTURAL_ERROR_CODES = {
    "duplicate": "duplicate_predicted_identity",
    "split": "split_oracle_identity",
    "merge": "merged_oracle_identities",
    "ambiguous": "ambiguous_identity_match",
    "granularity_mismatch": "granularity_mismatch",
}
PREDICTED_STRUCTURAL_STATUS = {
    "duplicate": "duplicate",
    "split": "split_component",
    "merge": "merge",
    "ambiguous": "unresolved",
    "granularity_mismatch": "granularity_mismatch",
}

KORef = tuple[str, str]


class AlignmentError(RuntimeError):
    """A fatal alignment input, integrity, or adjudication error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def serialize_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def ref_dict(ref: KORef) -> dict[str, str]:
    return {"lecture_id": ref[0], "ko_id": ref[1]}


def ref_key(value: Any, *, field: str) -> KORef:
    if not isinstance(value, dict):
        raise AlignmentError("invalid_ko_ref", f"{field} must be an object.")
    lecture_id = require_nonempty_string(
        value.get("lecture_id"), field=f"{field}.lecture_id"
    )
    ko_id = require_nonempty_string(value.get("ko_id"), field=f"{field}.ko_id")
    return lecture_id, ko_id


def ref_label(ref: KORef) -> str:
    return f"{ref[0]}::{ref[1]}"


def require_nonempty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlignmentError("invalid_alignment_input", f"{field} must be a non-empty string.")
    return value


def require_string_list(value: Any, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise AlignmentError("invalid_alignment_input", f"{field} must be {qualifier} of strings.")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(require_nonempty_string(item, field=f"{field}[{index}]"))
    return result


def reject_relation_leakage(value: Any, *, location: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_RELATION_KEYS:
                raise AlignmentError(
                    "relation_information_leakage",
                    f"Forbidden Relation field {key!r} found at {location}.",
                )
            reject_relation_leakage(nested, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            reject_relation_leakage(nested, location=f"{location}[{index}]")


def parse_oracle_inventory(data: Any) -> tuple[str, dict[KORef, dict[str, Any]]]:
    if not isinstance(data, dict) or not isinstance(data.get("lectures"), list):
        raise AlignmentError(
            "invalid_oracle_inventory", "Oracle inventory must contain a lectures list."
        )
    split = require_nonempty_string(data.get("split"), field="oracle.split")
    objects: dict[KORef, dict[str, Any]] = {}
    for lecture_index, lecture in enumerate(data["lectures"]):
        if not isinstance(lecture, dict):
            raise AlignmentError(
                "invalid_oracle_inventory",
                f"oracle.lectures[{lecture_index}] must be an object.",
            )
        lecture_id = require_nonempty_string(
            lecture.get("lecture_id"),
            field=f"oracle.lectures[{lecture_index}].lecture_id",
        )
        lecture_objects = lecture.get("objects")
        if not isinstance(lecture_objects, list):
            raise AlignmentError(
                "invalid_oracle_inventory",
                f"oracle.lectures[{lecture_index}].objects must be a list.",
            )
        for object_index, obj in enumerate(lecture_objects):
            location = f"oracle.lectures[{lecture_index}].objects[{object_index}]"
            if not isinstance(obj, dict):
                raise AlignmentError("invalid_oracle_inventory", f"{location} must be an object.")
            ko_id = require_nonempty_string(obj.get("id"), field=f"{location}.id")
            ref = lecture_id, ko_id
            if ref in objects:
                raise AlignmentError(
                    "duplicate_oracle_ko_id", f"Duplicate Oracle KO {ref_label(ref)}."
                )
            name = require_nonempty_string(obj.get("name"), field=f"{location}.name")
            ko_type = require_nonempty_string(obj.get("type"), field=f"{location}.type")
            if ko_type not in ALLOWED_KO_TYPES:
                raise AlignmentError("invalid_oracle_inventory", f"Invalid KO type at {location}.type.")
            aliases = require_string_list(
                obj.get("aliases", []), field=f"{location}.aliases", allow_empty=True
            )
            source_spans = require_string_list(
                obj.get("source_spans"), field=f"{location}.source_spans"
            )
            objects[ref] = {
                "lecture_id": lecture_id,
                "ko_id": ko_id,
                "name": name,
                "type": ko_type,
                "aliases": aliases,
                "source_spans": source_spans,
            }
    return split, objects


def parse_predicted_inventory(data: Any) -> tuple[str, dict[KORef, dict[str, Any]]]:
    if not isinstance(data, dict) or not isinstance(data.get("knowledge_objects"), list):
        raise AlignmentError(
            "invalid_predicted_inventory",
            "Predicted inventory must contain a knowledge_objects list.",
        )
    if data.get("artifact_type") != "predicted_ko_normalized_inventory":
        raise AlignmentError(
            "invalid_predicted_inventory",
            "Predicted inventory must be structurally normalized before alignment.",
        )
    if data.get("structural_normalization_version") != STRUCTURAL_NORMALIZATION_VERSION:
        raise AlignmentError(
            "normalization_version_mismatch",
            "Predicted inventory uses an unexpected structural normalization version.",
        )
    split = require_nonempty_string(data.get("split"), field="predicted.split")
    objects: dict[KORef, dict[str, Any]] = {}
    for index, obj in enumerate(data["knowledge_objects"]):
        location = f"predicted.knowledge_objects[{index}]"
        if not isinstance(obj, dict):
            raise AlignmentError("invalid_predicted_inventory", f"{location} must be an object.")
        lecture_id = require_nonempty_string(
            obj.get("lecture_id"), field=f"{location}.lecture_id"
        )
        ko_id = require_nonempty_string(
            obj.get("predicted_ko_id"), field=f"{location}.predicted_ko_id"
        )
        ref = lecture_id, ko_id
        if ref in objects:
            raise AlignmentError(
                "duplicate_predicted_ko_id", f"Duplicate predicted KO {ref_label(ref)}."
            )
        name = require_nonempty_string(obj.get("name"), field=f"{location}.name")
        ko_type = require_nonempty_string(obj.get("type"), field=f"{location}.type")
        if ko_type not in ALLOWED_KO_TYPES:
            raise AlignmentError("invalid_predicted_inventory", f"Invalid KO type at {location}.type.")
        source_spans = require_string_list(
            obj.get("source_spans"), field=f"{location}.source_spans"
        )
        objects[ref] = {
            "lecture_id": lecture_id,
            "ko_id": ko_id,
            "name": name,
            "type": ko_type,
            "source_spans": source_spans,
            "provenance": obj.get("provenance"),
        }
    return split, objects


def parse_lectures(data: Any) -> dict[str, str]:
    if not isinstance(data, dict) or not isinstance(data.get("lectures"), list):
        raise AlignmentError(
            "invalid_lecture_inventory", "Lecture inventory must contain a lectures list."
        )
    lectures: dict[str, str] = {}
    for index, lecture in enumerate(data["lectures"]):
        if not isinstance(lecture, dict):
            raise AlignmentError(
                "invalid_lecture_inventory", f"lectures[{index}] must be an object."
            )
        lecture_id = require_nonempty_string(
            lecture.get("lecture_id"), field=f"lectures[{index}].lecture_id"
        )
        text = require_nonempty_string(lecture.get("text"), field=f"lectures[{index}].text")
        if lecture_id in lectures:
            raise AlignmentError(
                "duplicate_lecture_id", f"Duplicate lecture text for {lecture_id}."
            )
        lectures[lecture_id] = text
    return lectures


def parse_review_items(
    data: Any | None,
    *,
    oracle_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
) -> list[dict[str, Any]]:
    if data is None:
        return []
    reject_relation_leakage(data, location="review_items")
    raw_items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(raw_items, list):
        raise AlignmentError("invalid_review_items", "Review items must be a list or an object with items.")
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    used_oracle: set[KORef] = set()
    used_predicted: set[KORef] = set()
    for index, item in enumerate(raw_items):
        location = f"review_items[{index}]"
        if not isinstance(item, dict):
            raise AlignmentError("invalid_review_items", f"{location} must be an object.")
        item_id = require_nonempty_string(item.get("item_id"), field=f"{location}.item_id")
        if item_id in seen_ids:
            raise AlignmentError("duplicate_review_item", f"Duplicate review item {item_id}.")
        seen_ids.add(item_id)
        oracle_refs_raw = item.get("oracle_refs")
        predicted_refs_raw = item.get("candidate_predicted_refs")
        if not isinstance(oracle_refs_raw, list) or not oracle_refs_raw:
            raise AlignmentError("invalid_review_items", f"{location}.oracle_refs must be non-empty.")
        if not isinstance(predicted_refs_raw, list) or not predicted_refs_raw:
            raise AlignmentError(
                "invalid_review_items",
                f"{location}.candidate_predicted_refs must be non-empty.",
            )
        oracle_refs = [ref_key(value, field=f"{location}.oracle_refs") for value in oracle_refs_raw]
        predicted_refs = [
            ref_key(value, field=f"{location}.candidate_predicted_refs")
            for value in predicted_refs_raw
        ]
        if len(set(oracle_refs)) != len(oracle_refs) or len(set(predicted_refs)) != len(predicted_refs):
            raise AlignmentError("duplicate_review_ref", f"{location} repeats a KO reference.")
        unknown_oracle = [ref for ref in oracle_refs if ref not in oracle_objects]
        unknown_predicted = [ref for ref in predicted_refs if ref not in predicted_objects]
        if unknown_oracle or unknown_predicted:
            raise AlignmentError(
                "unknown_review_ref",
                f"{location} contains unknown Oracle or predicted references.",
            )
        if used_oracle.intersection(oracle_refs) or used_predicted.intersection(predicted_refs):
            raise AlignmentError(
                "overlapping_review_scope",
                f"{location} overlaps another manual review scope.",
            )
        lecture_ids = {ref[0] for ref in [*oracle_refs, *predicted_refs]}
        if len(lecture_ids) != 1:
            raise AlignmentError(
                "cross_lecture_review_scope",
                f"{location} may not align KOs across lectures.",
            )
        used_oracle.update(oracle_refs)
        used_predicted.update(predicted_refs)
        proposed_level = item.get("proposed_alignment_level", "unresolved")
        proposed_status = item.get("proposed_primary_structural_status", "ambiguous")
        reason_code = require_nonempty_string(
            item.get("reason_code", "manual_identity_adjudication_pending"),
            field=f"{location}.reason_code",
        )
        if proposed_level not in {"manual", "unresolved"}:
            raise AlignmentError(
                "invalid_review_items",
                f"{location}.proposed_alignment_level is invalid.",
            )
        if proposed_status not in STRUCTURAL_STATUSES:
            raise AlignmentError(
                "invalid_review_items",
                f"{location}.proposed_primary_structural_status is invalid.",
            )
        items.append({
            "item_id": item_id,
            "oracle_refs": sorted(oracle_refs),
            "candidate_predicted_refs": sorted(predicted_refs),
            "proposed_alignment_level": proposed_level,
            "proposed_primary_structural_status": proposed_status,
            "reason_code": reason_code,
        })
    return sorted(items, key=lambda item: item["item_id"])


def make_pending_item(
    scope: dict[str, Any],
    *,
    oracle_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
    lectures: dict[str, str],
) -> dict[str, Any]:
    lecture_id = scope["oracle_refs"][0][0]
    item = {
        "item_id": scope["item_id"],
        "oracle_snapshots": [oracle_objects[ref] for ref in scope["oracle_refs"]],
        "candidate_predicted_snapshots": [
            predicted_objects[ref] for ref in scope["candidate_predicted_refs"]
        ],
        "lecture_snapshot": {
            "lecture_id": lecture_id,
            "text": lectures[lecture_id],
            "sha256": sha256_text(lectures[lecture_id]),
        },
        "proposed_alignment_level": scope["proposed_alignment_level"],
        "proposed_primary_structural_status": scope[
            "proposed_primary_structural_status"
        ],
        "reason_code": scope["reason_code"],
        "status": "pending",
    }
    item["item_snapshot_sha256"] = sha256_json(item)
    return item


def parse_adjudication(
    data: Any,
    *,
    pending: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("decisions"), list):
        raise AlignmentError(
            "invalid_alignment_adjudication",
            "Alignment adjudication must be an object with a decisions list.",
        )
    reject_relation_leakage(data, location="adjudication")
    if data.get("artifact_type") != "predicted_ko_alignment_resolved":
        raise AlignmentError(
            "invalid_alignment_adjudication", "Unexpected adjudication artifact_type."
        )
    if data.get("version") != ALIGNMENT_VERSION:
        raise AlignmentError("invalid_alignment_adjudication", "Unexpected adjudication version.")
    if data.get("alignment_snapshot_sha256") != pending["alignment_snapshot_sha256"]:
        raise AlignmentError(
            "stale_alignment_adjudication", "Adjudication targets a different alignment snapshot."
        )
    if data.get("name_matching_normalization_version") != NAME_MATCHING_NORMALIZATION_VERSION:
        raise AlignmentError(
            "stale_alignment_adjudication", "Adjudication uses a different name normalization."
        )
    for field in [
        "oracle_inventory_sha256",
        "predicted_inventory_sha256",
        "lecture_sha256",
    ]:
        if data.get(field) != pending.get(field):
            raise AlignmentError(
                "stale_alignment_adjudication",
                f"Adjudication targets a different {field}.",
            )
    pending_by_id = {item["item_id"]: item for item in pending["items"]}
    decisions: dict[str, dict[str, Any]] = {}
    for index, decision in enumerate(data["decisions"]):
        if not isinstance(decision, dict):
            raise AlignmentError(
                "invalid_alignment_adjudication", f"decisions[{index}] must be an object."
            )
        item_id = require_nonempty_string(
            decision.get("item_id"), field=f"decisions[{index}].item_id"
        )
        if item_id in decisions:
            raise AlignmentError(
                "duplicate_alignment_adjudication", f"Duplicate decision for {item_id}."
            )
        item = pending_by_id.get(item_id)
        if item is None:
            raise AlignmentError(
                "unused_alignment_adjudication", f"Decision {item_id} is not pending."
            )
        for field in [
            "item_snapshot_sha256",
            "oracle_snapshots",
            "candidate_predicted_snapshots",
            "lecture_snapshot",
        ]:
            if decision.get(field) != item.get(field):
                raise AlignmentError(
                    "changed_alignment_adjudication_snapshot",
                    f"Decision {item_id} changed bound field {field}.",
                )
        rationale = require_nonempty_string(
            decision.get("rationale"), field=f"decisions[{index}].rationale"
        )
        outcome = decision.get("decision")
        if outcome not in {"matched", "not_matched", "structural_error"}:
            raise AlignmentError(
                "invalid_alignment_adjudication", f"Invalid decision for {item_id}."
            )
        status = decision.get("resulting_primary_structural_status")
        level = decision.get("resulting_alignment_level")
        matched_ref = decision.get("matched_predicted_ref")
        if outcome == "matched":
            if len(item["oracle_snapshots"]) != 1 or len(item["candidate_predicted_snapshots"]) != 1:
                raise AlignmentError(
                    "invalid_alignment_adjudication",
                    f"Matched decision {item_id} must bind one Oracle and one prediction.",
                )
            expected_ref = {
                "lecture_id": item["candidate_predicted_snapshots"][0]["lecture_id"],
                "ko_id": item["candidate_predicted_snapshots"][0]["ko_id"],
            }
            if status != "one_to_one" or level != "manual" or matched_ref != expected_ref:
                raise AlignmentError(
                    "invalid_alignment_adjudication",
                    f"Matched decision {item_id} has inconsistent result fields.",
                )
        elif outcome == "not_matched":
            if status != "missing" or level != "unresolved" or matched_ref is not None:
                raise AlignmentError(
                    "invalid_alignment_adjudication",
                    f"Not-matched decision {item_id} has inconsistent result fields.",
                )
        else:
            if status not in STRUCTURAL_STATUSES or level != "unresolved" or matched_ref is not None:
                raise AlignmentError(
                    "invalid_alignment_adjudication",
                    f"Structural decision {item_id} has inconsistent result fields.",
                )
        decisions[item_id] = {**decision, "rationale": rationale}
    missing = sorted(set(pending_by_id) - set(decisions))
    if missing:
        raise AlignmentError(
            "missing_alignment_adjudication", f"Missing decisions for: {', '.join(missing)}."
        )
    return decisions


def oracle_record_base(ref: KORef) -> dict[str, Any]:
    return {
        "oracle_ref": ref_dict(ref),
        "matched_predicted_ref": None,
        "linked_predicted_refs": [],
        "alignment_level": "unresolved",
        "identity_match": False,
        "type_match": None,
        "predicted_source_span_exact": None,
        "predicted_source_span_supports_identity": None,
        "primary_structural_status": "missing",
        "structural_flags": [],
        "recoverable": False,
        "adjudication_required": False,
        "notes": "",
    }


def predicted_record_base(ref: KORef) -> dict[str, Any]:
    return {
        "predicted_ref": ref_dict(ref),
        "matched_oracle_ref": None,
        "linked_oracle_refs": [],
        "accounting_status": "unmatched_extra",
        "identity_match": False,
        "recoverable": False,
        "notes": "",
    }


def add_error(errors: list[dict[str, Any]], code: str, **details: Any) -> None:
    errors.append({"error_code": code, **details})


def assign_one_to_one(
    oracle_ref: KORef,
    predicted_ref: KORef,
    *,
    level: str,
    note: str,
    oracle_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
    lectures: dict[str, str],
    oracle_records: dict[KORef, dict[str, Any]],
    predicted_records: dict[KORef, dict[str, Any]],
    errors: list[dict[str, Any]],
    support_override: bool | None = None,
) -> None:
    oracle = oracle_objects[oracle_ref]
    predicted = predicted_objects[predicted_ref]
    source_span_exact = all(
        span in lectures[predicted_ref[0]] for span in predicted["source_spans"]
    )
    supports_identity = support_override
    if supports_identity is None and any(
        span in oracle["source_spans"] for span in predicted["source_spans"]
    ):
        supports_identity = True
    type_match = oracle["type"] == predicted["type"]
    oracle_records[oracle_ref] = {
        **oracle_record_base(oracle_ref),
        "matched_predicted_ref": ref_dict(predicted_ref),
        "linked_predicted_refs": [ref_dict(predicted_ref)],
        "alignment_level": level,
        "identity_match": True,
        "type_match": type_match,
        "predicted_source_span_exact": source_span_exact,
        "predicted_source_span_supports_identity": supports_identity,
        "primary_structural_status": "one_to_one",
        "recoverable": True,
        "notes": note,
    }
    predicted_records[predicted_ref] = {
        **predicted_record_base(predicted_ref),
        "matched_oracle_ref": ref_dict(oracle_ref),
        "linked_oracle_refs": [ref_dict(oracle_ref)],
        "accounting_status": "one_to_one",
        "identity_match": True,
        "recoverable": True,
        "notes": note,
    }
    if not type_match:
        add_error(
            errors,
            "ko_type_mismatch",
            oracle_ref=ref_dict(oracle_ref),
            predicted_ref=ref_dict(predicted_ref),
        )
    if not source_span_exact:
        add_error(
            errors,
            "predicted_source_span_invalid",
            oracle_ref=ref_dict(oracle_ref),
            predicted_ref=ref_dict(predicted_ref),
        )


def assign_structural(
    oracle_refs: list[KORef],
    predicted_refs: list[KORef],
    *,
    status: str,
    note: str,
    oracle_records: dict[KORef, dict[str, Any]],
    predicted_records: dict[KORef, dict[str, Any]],
    errors: list[dict[str, Any]],
    error_code: str | None = None,
) -> None:
    for oracle_ref in oracle_refs:
        oracle_records[oracle_ref] = {
            **oracle_record_base(oracle_ref),
            "linked_predicted_refs": [ref_dict(ref) for ref in predicted_refs],
            "primary_structural_status": status,
            "structural_flags": [status],
            "notes": note,
        }
    predicted_status = PREDICTED_STRUCTURAL_STATUS[status]
    for predicted_ref in predicted_refs:
        predicted_records[predicted_ref] = {
            **predicted_record_base(predicted_ref),
            "linked_oracle_refs": [ref_dict(ref) for ref in oracle_refs],
            "accounting_status": predicted_status,
            "notes": note,
        }
    add_error(
        errors,
        error_code or STRUCTURAL_ERROR_CODES[status],
        oracle_refs=[ref_dict(ref) for ref in oracle_refs],
        predicted_refs=[ref_dict(ref) for ref in predicted_refs],
    )


def assign_pending(
    scope: dict[str, Any],
    *,
    oracle_records: dict[KORef, dict[str, Any]],
    predicted_records: dict[KORef, dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    status = scope["proposed_primary_structural_status"]
    if status not in STRUCTURAL_STATUSES:
        status = "ambiguous"
    for oracle_ref in scope["oracle_refs"]:
        oracle_records[oracle_ref] = {
            **oracle_record_base(oracle_ref),
            "linked_predicted_refs": [
                ref_dict(ref) for ref in scope["candidate_predicted_refs"]
            ],
            "primary_structural_status": status,
            "structural_flags": [status],
            "adjudication_required": True,
            "notes": "Manual identity or structural adjudication is pending.",
        }
    for predicted_ref in scope["candidate_predicted_refs"]:
        predicted_records[predicted_ref] = {
            **predicted_record_base(predicted_ref),
            "linked_oracle_refs": [ref_dict(ref) for ref in scope["oracle_refs"]],
            "accounting_status": "unresolved",
            "notes": "Manual identity or structural adjudication is pending.",
        }
    add_error(
        errors,
        scope["reason_code"],
        item_id=scope["item_id"],
        oracle_refs=[ref_dict(ref) for ref in scope["oracle_refs"]],
        predicted_refs=[ref_dict(ref) for ref in scope["candidate_predicted_refs"]],
    )


def automatic_candidate_components(
    oracle_refs: Iterable[KORef],
    predicted_refs: Iterable[KORef],
    *,
    oracle_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
) -> tuple[list[tuple[list[KORef], list[KORef], dict[tuple[KORef, KORef], str]]], set[KORef], set[KORef]]:
    oracle_refs = set(oracle_refs)
    predicted_refs = set(predicted_refs)
    edges: dict[tuple[KORef, KORef], str] = {}
    oracle_adjacency: dict[KORef, set[KORef]] = defaultdict(set)
    predicted_adjacency: dict[KORef, set[KORef]] = defaultdict(set)
    for oracle_ref in sorted(oracle_refs):
        oracle = oracle_objects[oracle_ref]
        canonical = name_matching_key(oracle["name"])
        aliases = {name_matching_key(alias) for alias in oracle["aliases"]}
        for predicted_ref in sorted(predicted_refs):
            if oracle_ref[0] != predicted_ref[0]:
                continue
            predicted_key = name_matching_key(predicted_objects[predicted_ref]["name"])
            level: str | None = None
            if predicted_key == canonical:
                level = "exact"
            elif predicted_key in aliases:
                level = "alias"
            if level is not None:
                edges[(oracle_ref, predicted_ref)] = level
                oracle_adjacency[oracle_ref].add(predicted_ref)
                predicted_adjacency[predicted_ref].add(oracle_ref)

    components: list[tuple[list[KORef], list[KORef], dict[tuple[KORef, KORef], str]]] = []
    seen_oracle: set[KORef] = set()
    seen_predicted: set[KORef] = set()
    for start in sorted(oracle_adjacency):
        if start in seen_oracle:
            continue
        queue: deque[tuple[str, KORef]] = deque([("oracle", start)])
        component_oracle: set[KORef] = set()
        component_predicted: set[KORef] = set()
        while queue:
            side, ref = queue.popleft()
            if side == "oracle":
                if ref in component_oracle:
                    continue
                component_oracle.add(ref)
                seen_oracle.add(ref)
                queue.extend(("predicted", other) for other in oracle_adjacency[ref])
            else:
                if ref in component_predicted:
                    continue
                component_predicted.add(ref)
                seen_predicted.add(ref)
                queue.extend(("oracle", other) for other in predicted_adjacency[ref])
        component_edges = {
            key: value
            for key, value in edges.items()
            if key[0] in component_oracle and key[1] in component_predicted
        }
        components.append(
            (sorted(component_oracle), sorted(component_predicted), component_edges)
        )
    return components, seen_oracle, seen_predicted


def build_alignment_records(
    *,
    oracle_objects: dict[KORef, dict[str, Any]],
    predicted_objects: dict[KORef, dict[str, Any]],
    lectures: dict[str, str],
    review_scopes: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> tuple[dict[KORef, dict[str, Any]], dict[KORef, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    oracle_records: dict[KORef, dict[str, Any]] = {}
    predicted_records: dict[KORef, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    pending_items: list[dict[str, Any]] = []

    reserved_oracle = {ref for scope in review_scopes for ref in scope["oracle_refs"]}
    reserved_predicted = {
        ref for scope in review_scopes for ref in scope["candidate_predicted_refs"]
    }
    free_oracle = set(oracle_objects) - reserved_oracle
    free_predicted = set(predicted_objects) - reserved_predicted
    components, matched_oracle, matched_predicted = automatic_candidate_components(
        free_oracle,
        free_predicted,
        oracle_objects=oracle_objects,
        predicted_objects=predicted_objects,
    )

    automatic_review_scopes: list[dict[str, Any]] = []
    for component_index, (oracle_refs, predicted_refs, edges) in enumerate(components, start=1):
        if len(oracle_refs) == 1 and len(predicted_refs) == 1:
            level = edges[(oracle_refs[0], predicted_refs[0])]
            assign_one_to_one(
                oracle_refs[0],
                predicted_refs[0],
                level=level,
                note=f"Unique {level} one-to-one identity match.",
                oracle_objects=oracle_objects,
                predicted_objects=predicted_objects,
                lectures=lectures,
                oracle_records=oracle_records,
                predicted_records=predicted_records,
                errors=errors,
            )
        elif len(oracle_refs) == 1:
            assign_structural(
                oracle_refs,
                predicted_refs,
                status="duplicate",
                note="Multiple predictions independently match one Oracle identity.",
                oracle_records=oracle_records,
                predicted_records=predicted_records,
                errors=errors,
            )
        else:
            automatic_review_scopes.append({
                "item_id": f"automatic_alignment_review_{component_index:03d}",
                "oracle_refs": oracle_refs,
                "candidate_predicted_refs": predicted_refs,
                "proposed_alignment_level": "unresolved",
                "proposed_primary_structural_status": "ambiguous",
                "reason_code": "ambiguous_identity_match",
            })

    all_scopes = sorted(
        [*review_scopes, *automatic_review_scopes], key=lambda item: item["item_id"]
    )
    for scope in all_scopes:
        decision = decisions.get(scope["item_id"])
        if decision is None:
            assign_pending(
                scope,
                oracle_records=oracle_records,
                predicted_records=predicted_records,
                errors=errors,
            )
            pending_items.append(
                make_pending_item(
                    scope,
                    oracle_objects=oracle_objects,
                    predicted_objects=predicted_objects,
                    lectures=lectures,
                )
            )
            continue
        oracle_refs = scope["oracle_refs"]
        predicted_refs = scope["candidate_predicted_refs"]
        outcome = decision["decision"]
        if outcome == "matched":
            assign_one_to_one(
                oracle_refs[0],
                predicted_refs[0],
                level="manual",
                note=decision["rationale"],
                oracle_objects=oracle_objects,
                predicted_objects=predicted_objects,
                lectures=lectures,
                oracle_records=oracle_records,
                predicted_records=predicted_records,
                errors=errors,
                support_override=decision.get("predicted_source_span_supports_identity"),
            )
        elif outcome == "not_matched":
            for oracle_ref in oracle_refs:
                oracle_records[oracle_ref] = {
                    **oracle_record_base(oracle_ref),
                    "notes": decision["rationale"],
                }
            for predicted_ref in predicted_refs:
                predicted_records[predicted_ref] = {
                    **predicted_record_base(predicted_ref),
                    "notes": decision["rationale"],
                }
            add_error(
                errors,
                scope["reason_code"],
                oracle_refs=[ref_dict(ref) for ref in oracle_refs],
                predicted_refs=[ref_dict(ref) for ref in predicted_refs],
            )
        else:
            assign_structural(
                oracle_refs,
                predicted_refs,
                status=decision["resulting_primary_structural_status"],
                note=decision["rationale"],
                oracle_records=oracle_records,
                predicted_records=predicted_records,
                errors=errors,
                error_code=scope["reason_code"],
            )

    cross_lecture_oracle: set[KORef] = set()
    cross_lecture_predicted: set[KORef] = set()
    unmatched_oracle = free_oracle - matched_oracle
    unmatched_predicted = free_predicted - matched_predicted
    for oracle_ref in unmatched_oracle:
        oracle_key = name_matching_key(oracle_objects[oracle_ref]["name"])
        for predicted_ref in unmatched_predicted:
            if oracle_ref[0] == predicted_ref[0]:
                continue
            if oracle_key == name_matching_key(predicted_objects[predicted_ref]["name"]):
                cross_lecture_oracle.add(oracle_ref)
                cross_lecture_predicted.add(predicted_ref)
                add_error(
                    errors,
                    "lecture_provenance_mismatch",
                    oracle_ref=ref_dict(oracle_ref),
                    predicted_ref=ref_dict(predicted_ref),
                )

    for oracle_ref in sorted(unmatched_oracle):
        oracle_records[oracle_ref] = oracle_record_base(oracle_ref)
        if oracle_ref not in cross_lecture_oracle:
            add_error(errors, "missing_oracle_ko", oracle_ref=ref_dict(oracle_ref))
    for predicted_ref in sorted(unmatched_predicted):
        predicted_records[predicted_ref] = predicted_record_base(predicted_ref)
        if predicted_ref not in cross_lecture_predicted:
            add_error(
                errors,
                "unmatched_extra_predicted_ko",
                predicted_ref=ref_dict(predicted_ref),
            )

    if set(oracle_records) != set(oracle_objects):
        raise AlignmentError("incomplete_oracle_accounting", "Not every Oracle KO was accounted for.")
    if set(predicted_records) != set(predicted_objects):
        raise AlignmentError(
            "incomplete_predicted_accounting", "Not every predicted KO was accounted for."
        )
    return oracle_records, predicted_records, errors, pending_items


def validate_bidirectional_accounting(alignment: dict[str, Any]) -> None:
    oracle_by_ref = {
        ref_key(item["oracle_ref"], field="oracle_record.oracle_ref"): item
        for item in alignment["oracle_records"]
    }
    predicted_by_ref = {
        ref_key(item["predicted_ref"], field="predicted_record.predicted_ref"): item
        for item in alignment["predicted_records"]
    }
    if len(oracle_by_ref) != len(alignment["oracle_records"]):
        raise AlignmentError("duplicate_oracle_accounting", "Oracle accounting contains duplicates.")
    if len(predicted_by_ref) != len(alignment["predicted_records"]):
        raise AlignmentError(
            "duplicate_predicted_accounting", "Predicted accounting contains duplicates."
        )
    for oracle_ref, record in oracle_by_ref.items():
        matched = record["matched_predicted_ref"]
        if matched is None:
            continue
        predicted_ref = ref_key(matched, field="matched_predicted_ref")
        predicted = predicted_by_ref.get(predicted_ref)
        if predicted is None or predicted.get("matched_oracle_ref") != ref_dict(oracle_ref):
            raise AlignmentError(
                "inconsistent_bidirectional_alignment",
                f"Oracle match {ref_label(oracle_ref)} is not reciprocated.",
            )
    for predicted_ref, record in predicted_by_ref.items():
        matched = record["matched_oracle_ref"]
        if matched is None:
            continue
        oracle_ref = ref_key(matched, field="matched_oracle_ref")
        oracle = oracle_by_ref.get(oracle_ref)
        if oracle is None or oracle.get("matched_predicted_ref") != ref_dict(predicted_ref):
            raise AlignmentError(
                "inconsistent_bidirectional_alignment",
                f"Predicted match {ref_label(predicted_ref)} is not reciprocated.",
            )


def align_inventories(
    oracle_data: Any,
    predicted_data: Any,
    lecture_data: Any,
    *,
    review_data: Any | None = None,
    adjudication_data: Any | None = None,
    oracle_inventory_sha256: str | None = None,
    predicted_inventory_sha256: str | None = None,
) -> dict[str, Any]:
    reject_relation_leakage(review_data, location="review_data")
    oracle_split, oracle_objects = parse_oracle_inventory(oracle_data)
    predicted_split, predicted_objects = parse_predicted_inventory(predicted_data)
    if oracle_split != predicted_split:
        raise AlignmentError(
            "split_mismatch",
            f"Oracle split {oracle_split!r} differs from predicted split {predicted_split!r}.",
        )
    lectures = parse_lectures(lecture_data)
    referenced_lectures = {ref[0] for ref in [*oracle_objects, *predicted_objects]}
    missing_lectures = sorted(referenced_lectures - set(lectures))
    if missing_lectures:
        raise AlignmentError(
            "missing_lecture_text", f"Missing lecture text for: {', '.join(missing_lectures)}."
        )
    review_scopes = parse_review_items(
        review_data,
        oracle_objects=oracle_objects,
        predicted_objects=predicted_objects,
    )
    oracle_hash = oracle_inventory_sha256 or sha256_json(oracle_data)
    predicted_hash = predicted_inventory_sha256 or sha256_json(predicted_data)
    lecture_hashes = {lecture_id: sha256_text(lectures[lecture_id]) for lecture_id in sorted(lectures)}

    draft_oracle, draft_predicted, draft_errors, draft_pending_items = build_alignment_records(
        oracle_objects=oracle_objects,
        predicted_objects=predicted_objects,
        lectures=lectures,
        review_scopes=review_scopes,
        decisions={},
    )
    draft_alignment = {
        "artifact_type": "predicted_ko_alignment",
        "version": ALIGNMENT_VERSION,
        "split": oracle_split,
        "structural_normalization_version": STRUCTURAL_NORMALIZATION_VERSION,
        "name_matching_normalization_version": NAME_MATCHING_NORMALIZATION_VERSION,
        "oracle_inventory_sha256": oracle_hash,
        "predicted_inventory_sha256": predicted_hash,
        "lecture_sha256": lecture_hashes,
        "evaluation_status": (
            "draft_pending_adjudication" if draft_pending_items else "final"
        ),
        "oracle_records": [draft_oracle[ref] for ref in sorted(draft_oracle)],
        "predicted_records": [draft_predicted[ref] for ref in sorted(draft_predicted)],
        "errors": sorted(draft_errors, key=canonical_json),
    }
    validate_bidirectional_accounting(draft_alignment)
    draft_snapshot_hash = sha256_json(draft_alignment)
    draft_pending = {
        "artifact_type": "predicted_ko_alignment_pending",
        "version": ALIGNMENT_VERSION,
        "alignment_snapshot_sha256": draft_snapshot_hash,
        "oracle_inventory_sha256": oracle_hash,
        "predicted_inventory_sha256": predicted_hash,
        "lecture_sha256": lecture_hashes,
        "name_matching_normalization_version": NAME_MATCHING_NORMALIZATION_VERSION,
        "items": sorted(draft_pending_items, key=lambda item: item["item_id"]),
    }

    if adjudication_data is None:
        return {"alignment": draft_alignment, "pending": draft_pending, "resolved": None}
    decisions = parse_adjudication(adjudication_data, pending=draft_pending)
    final_oracle, final_predicted, final_errors, final_pending_items = build_alignment_records(
        oracle_objects=oracle_objects,
        predicted_objects=predicted_objects,
        lectures=lectures,
        review_scopes=review_scopes,
        decisions=decisions,
    )
    if final_pending_items:
        raise AlignmentError(
            "missing_alignment_adjudication", "Resolved alignment still contains pending items."
        )
    final_alignment = {
        **draft_alignment,
        "evaluation_status": "final",
        "oracle_records": [final_oracle[ref] for ref in sorted(final_oracle)],
        "predicted_records": [final_predicted[ref] for ref in sorted(final_predicted)],
        "errors": sorted(final_errors, key=canonical_json),
    }
    validate_bidirectional_accounting(final_alignment)
    final_pending = {
        **draft_pending,
        "alignment_snapshot_sha256": sha256_json(final_alignment),
        "items": [],
    }
    return {
        "alignment": final_alignment,
        "pending": final_pending,
        "resolved": adjudication_data,
    }


def load_json_bytes(path: Path, *, code: str) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8")), raw
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AlignmentError(code, f"Unable to read {path}: {exc}") from exc


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def write_artifacts(output_dir: Path, result: dict[str, Any], *, overwrite: bool) -> None:
    artifacts = {
        "alignment.json": result["alignment"],
        "alignment_pending.json": result["pending"],
    }
    if result["resolved"] is not None:
        artifacts["alignment_resolved.json"] = result["resolved"]
    targets = {name: output_dir / name for name in artifacts}
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing and not overwrite:
        raise AlignmentError(
            "output_exists",
            "Alignment output already exists: " + ", ".join(existing),
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_paths: dict[str, Path] = {}
    try:
        for name, value in artifacts.items():
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output_dir,
                prefix=f".{name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(serialize_json(value))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_paths[name] = Path(temporary_file.name)
        for name in sorted(artifacts):
            temporary_paths[name].replace(targets[name])
    finally:
        for temporary_path in temporary_paths.values():
            if temporary_path.exists():
                temporary_path.unlink()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Align normalized predicted KOs to an Oracle KO inventory."
    )
    parser.add_argument("--oracle-inventory", required=True)
    parser.add_argument("--predicted-inventory", required=True)
    parser.add_argument("--lectures", required=True)
    parser.add_argument(
        "--review-items",
        help="Optional Relation-blind manual review scopes for semantic/structural cases.",
    )
    parser.add_argument("--adjudication", help="Optional snapshot-bound resolved decisions.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        oracle_path = resolve_path(args.oracle_inventory)
        predicted_path = resolve_path(args.predicted_inventory)
        lecture_path = resolve_path(args.lectures)
        oracle_data, oracle_raw = load_json_bytes(oracle_path, code="invalid_oracle_inventory")
        predicted_data, predicted_raw = load_json_bytes(
            predicted_path, code="invalid_predicted_inventory"
        )
        lecture_data, _ = load_json_bytes(lecture_path, code="invalid_lecture_inventory")
        review_data = None
        if args.review_items:
            review_data, _ = load_json_bytes(
                resolve_path(args.review_items), code="invalid_review_items"
            )
        adjudication_data = None
        if args.adjudication:
            adjudication_data, _ = load_json_bytes(
                resolve_path(args.adjudication), code="invalid_alignment_adjudication"
            )
        result = align_inventories(
            oracle_data,
            predicted_data,
            lecture_data,
            review_data=review_data,
            adjudication_data=adjudication_data,
            oracle_inventory_sha256=sha256_bytes(oracle_raw),
            predicted_inventory_sha256=sha256_bytes(predicted_raw),
        )
        write_artifacts(resolve_path(args.output_dir), result, overwrite=args.overwrite)
    except AlignmentError as exc:
        print(f"Alignment failed [{exc.code}]: {exc}", file=sys.stderr)
        return 2 if exc.code == "output_exists" else 1
    print(
        "Wrote predicted-KO alignment artifacts "
        f"({result['alignment']['evaluation_status']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
