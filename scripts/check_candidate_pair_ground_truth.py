#!/usr/bin/env python3
"""Strictly validate candidate-pair ground truth in draft or final mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_candidate_pair_universe import (
    CandidatePairUniverseError,
    build_pair_universe,
    display_path,
    serialize_json,
    sha256_file,
    validate_inventory,
    validate_lecture_inventory,
)


DEFAULT_PAIR_UNIVERSE = (
    ROOT
    / "benchmark"
    / "candidate_pairs"
    / "development_v0_1"
    / "pair_universe.json"
)
DEFAULT_GROUND_TRUTH = (
    ROOT / "benchmark" / "ground_truth" / "candidate_pairs_development_v0_1.json"
)
DEFAULT_COMPLETION_MARKER = DEFAULT_GROUND_TRUTH.with_name(
    "candidate_pairs_development_v0_1_complete.json"
)
CHECKER_VERSION = "candidate_pair_ground_truth_checker_v0.1"
ALLOWED_CANDIDATE_LABELS = [
    "IN_SCHEMA_RELATION",
    "NO_IN_SCHEMA_RELATION",
    "OUT_OF_SCHEMA_RELATION",
    "AMBIGUOUS",
]
ALLOWED_RELATION_TYPES = [
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
]
PRIMARY_SCORING_LABELS = [
    "IN_SCHEMA_RELATION",
    "NO_IN_SCHEMA_RELATION",
]
ALLOWED_ANNOTATION_STATUSES = {"draft", "pending_review", "final"}
ALLOWED_ANNOTATION_SOURCES = {
    "new_exhaustive_annotation",
    "reused_existing_relation_annotation",
    "adjudicated",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

UNIVERSE_TOP_LEVEL_KEYS = {
    "artifact_type",
    "version",
    "benchmark_split",
    "scope",
    "endpoint_order",
    "pair_order",
    "source_inventory",
    "lecture_inventory",
    "lectures",
    "total_ko_count",
    "total_pair_count",
    "pairs",
}
GROUND_TRUTH_TOP_LEVEL_KEYS = {
    "artifact_type",
    "version",
    "benchmark_split",
    "status",
    "pair_universe",
    "source_inventory",
    "lecture_inventory",
    "annotation_guidelines",
    "relation_annotation_guidelines",
    "evaluation_protocol",
    "success_criteria",
    "schema_bindings",
    "allowed_candidate_labels",
    "allowed_relation_types",
    "primary_scoring_labels",
    "annotations",
}
ANNOTATION_KEYS = {
    "pair_id",
    "candidate_label",
    "annotation_status",
    "gold_relations",
    "out_of_schema_relation",
    "ambiguity",
    "negative_rationale",
    "annotation_source",
    "source_annotation",
    "notes",
}
RELATION_KEYS = {
    "role",
    "relation_type",
    "source",
    "target",
    "symmetric",
    "evidence_spans",
    "rationale",
}
PAIR_UNIVERSE_MARKER_KEYS = {
    "artifact_type",
    "version",
    "status",
    "pair_universe",
    "source_inventory",
    "lecture_inventory",
    "generator",
    "counts",
}


class CandidateGroundTruthError(ValueError):
    """Raised when a bundle cannot be loaded for validation."""


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateGroundTruthError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CandidateGroundTruthError(f"{label} must be a JSON object.")
    return data


def qualified_ref(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict) or set(value) != {"lecture_id", "ko_id"}:
        return None
    lecture_id = value.get("lecture_id")
    ko_id = value.get("ko_id")
    if not isinstance(lecture_id, str) or not lecture_id:
        return None
    if not isinstance(ko_id, str) or not ko_id:
        return None
    return lecture_id, ko_id


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_exact_keys(
    value: Any,
    *,
    expected: set[str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: must be an object")
        return False
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"{label}: missing keys {missing}")
    if extra:
        errors.append(f"{label}: unexpected keys {extra}")
    return not missing and not extra


def validate_binding(
    value: Any,
    *,
    label: str,
    errors: list[str],
    require_version: bool,
    extra_keys: set[str] | None = None,
) -> Path | None:
    expected = {"path", "sha256"}
    if require_version:
        expected.add("version")
    if extra_keys:
        expected.update(extra_keys)
    if not validate_exact_keys(value, expected=expected, label=label, errors=errors):
        return None
    path_text = value.get("path")
    expected_hash = value.get("sha256")
    if not nonempty_text(path_text):
        errors.append(f"{label}.path: must be non-empty")
        return None
    if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash):
        errors.append(f"{label}.sha256: must be lowercase SHA-256")
        return None
    if require_version and not nonempty_text(value.get("version")):
        errors.append(f"{label}.version: must be non-empty")
    path = resolve_path(path_text)
    if not path.is_file():
        errors.append(f"{label}: bound file does not exist: {path_text}")
        return None
    if sha256_file(path) != expected_hash:
        errors.append(f"{label}: stale SHA-256 binding")
    return path


def validate_evidence(
    value: Any,
    *,
    pair_id: str,
    field: str,
    lecture_id: str,
    lecture_text: str,
    errors: list[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{pair_id}:{field}: requires at least one evidence span")
        return
    for index, item in enumerate(value):
        prefix = f"{pair_id}:{field}[{index}]"
        if not validate_exact_keys(
            item,
            expected={"lecture_id", "span"},
            label=prefix,
            errors=errors,
        ):
            continue
        if item.get("lecture_id") != lecture_id:
            errors.append(f"{prefix}: evidence lecture must equal pair lecture")
        span = item.get("span")
        if not nonempty_text(span):
            errors.append(f"{prefix}: span must be non-empty")
        elif span not in lecture_text:
            errors.append(f"{prefix}: span is not an exact lecture substring")


def validate_pair_universe_marker(
    pair_universe_path: Path,
    universe: dict[str, Any],
    *,
    errors: list[str],
) -> Path | None:
    marker_path = pair_universe_path.with_name("pair_universe_complete.json")
    if not marker_path.is_file():
        errors.append("pair_universe_complete: missing completion marker")
        return None
    try:
        marker = load_json_object(marker_path, label="pair universe completion marker")
    except CandidateGroundTruthError as exc:
        errors.append(str(exc))
        return None
    validate_exact_keys(
        marker,
        expected=PAIR_UNIVERSE_MARKER_KEYS,
        label="pair_universe_complete",
        errors=errors,
    )
    if marker.get("artifact_type") != "candidate_pair_universe_complete":
        errors.append("pair_universe_complete.artifact_type: invalid")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        errors.append("pair_universe_complete: version/status mismatch")
    checked_universe_path = validate_binding(
        marker.get("pair_universe"),
        label="pair_universe_complete.pair_universe",
        errors=errors,
        require_version=False,
    )
    if (
        checked_universe_path is not None
        and checked_universe_path.resolve() != pair_universe_path.resolve()
    ):
        errors.append("pair_universe_complete: bound pair universe path mismatch")
    for field in ("source_inventory", "lecture_inventory"):
        validate_binding(
            marker.get(field),
            label=f"pair_universe_complete.{field}",
            errors=errors,
            require_version=False,
        )
        universe_binding = universe.get(field)
        expected_binding = (
            {
                "path": universe_binding.get("path"),
                "sha256": universe_binding.get("sha256"),
            }
            if isinstance(universe_binding, dict)
            else None
        )
        if marker.get(field) != expected_binding:
            errors.append(f"pair_universe_complete.{field}: binding mismatch")
    validate_binding(
        marker.get("generator"),
        label="pair_universe_complete.generator",
        errors=errors,
        require_version=True,
    )
    expected_counts = {
        "lectures": len(universe.get("lectures", [])),
        "knowledge_objects": universe.get("total_ko_count"),
        "pairs": universe.get("total_pair_count"),
    }
    if marker.get("counts") != expected_counts:
        errors.append("pair_universe_complete.counts: mismatch")
    return marker_path


def validate_relation(
    relation: Any,
    *,
    pair_id: str,
    index: int,
    endpoints: set[tuple[str, str]],
    lecture_id: str,
    lecture_text: str,
    ko_types: dict[tuple[str, str], str],
    errors: list[str],
) -> tuple[Any, ...] | None:
    prefix = f"{pair_id}:gold_relations[{index}]"
    if not validate_exact_keys(
        relation, expected=RELATION_KEYS, label=prefix, errors=errors
    ):
        return None
    role = relation.get("role")
    relation_type = relation.get("relation_type")
    source = qualified_ref(relation.get("source"))
    target = qualified_ref(relation.get("target"))
    symmetric = relation.get("symmetric")
    if not isinstance(role, str) or role not in {"primary", "acceptable_alternative"}:
        errors.append(f"{prefix}: invalid role {role!r}")
    if relation_type not in ALLOWED_RELATION_TYPES:
        errors.append(f"{prefix}: invalid relation_type {relation_type!r}")
    if source is None or source not in endpoints:
        errors.append(f"{prefix}: source must be one endpoint of the candidate pair")
    if target is None or target not in endpoints:
        errors.append(f"{prefix}: target must be one endpoint of the candidate pair")
    if source is not None and target is not None and source == target:
        errors.append(f"{prefix}: source and target must differ")
    if not isinstance(symmetric, bool):
        errors.append(f"{prefix}: symmetric must be boolean")
    elif symmetric and relation_type != "CONTRASTS_WITH":
        errors.append(
            f"{prefix}: only CONTRASTS_WITH may be marked symmetric in v0.1"
        )
    if relation_type == "FORMALIZES" and source is not None:
        if ko_types.get(source) != "Formula":
            errors.append(f"{prefix}: FORMALIZES source must be a Formula")
    validate_evidence(
        relation.get("evidence_spans"),
        pair_id=pair_id,
        field=f"gold_relations[{index}].evidence_spans",
        lecture_id=lecture_id,
        lecture_text=lecture_text,
        errors=errors,
    )
    if not nonempty_text(relation.get("rationale")):
        errors.append(f"{prefix}: rationale must be non-empty")
    if (
        source is None
        or target is None
        or not isinstance(relation_type, str)
        or not isinstance(symmetric, bool)
    ):
        return None
    return relation_type, source, target, symmetric


def validate_annotation(
    annotation: Any,
    *,
    expected_pair: dict[str, Any],
    lecture_texts: dict[str, str],
    ko_types: dict[tuple[str, str], str],
    allow_draft: bool,
    errors: list[str],
) -> tuple[str | None, str | None]:
    pair_id = expected_pair["pair_id"]
    if not validate_exact_keys(
        annotation, expected=ANNOTATION_KEYS, label=pair_id, errors=errors
    ):
        return None, None
    if annotation.get("pair_id") != pair_id:
        errors.append(
            f"{pair_id}: annotation order/identity mismatch: {annotation.get('pair_id')!r}"
        )
    label = annotation.get("candidate_label")
    status = annotation.get("annotation_status")
    if label is not None and label not in ALLOWED_CANDIDATE_LABELS:
        errors.append(f"{pair_id}: invalid candidate_label {label!r}")
    if not isinstance(status, str) or status not in ALLOWED_ANNOTATION_STATUSES:
        errors.append(f"{pair_id}: invalid annotation_status {status!r}")
    if not allow_draft and status != "final":
        errors.append(f"{pair_id}: final mode requires annotation_status = final")
    if status == "final" and label is None:
        errors.append(f"{pair_id}: final annotation requires candidate_label")
    if status == "pending_review" and label is None:
        errors.append(f"{pair_id}: pending_review requires a completed first-pass label")

    gold_relations = annotation.get("gold_relations")
    if not isinstance(gold_relations, list):
        errors.append(f"{pair_id}: gold_relations must be a list")
        gold_relations = []
    pair_refs = {
        qualified_ref(expected_pair["ko_a"]),
        qualified_ref(expected_pair["ko_b"]),
    }
    endpoints = {ref for ref in pair_refs if ref is not None}
    lecture_id = expected_pair["lecture_id"]
    lecture_text = lecture_texts.get(lecture_id, "")
    relation_keys: list[tuple[Any, ...]] = []
    primary_count = 0
    for index, relation in enumerate(gold_relations):
        key = validate_relation(
            relation,
            pair_id=pair_id,
            index=index,
            endpoints=endpoints,
            lecture_id=lecture_id,
            lecture_text=lecture_text,
            ko_types=ko_types,
            errors=errors,
        )
        if isinstance(relation, dict) and relation.get("role") == "primary":
            primary_count += 1
        if key is not None:
            relation_keys.append(key)
    if len(relation_keys) != len(set(relation_keys)):
        errors.append(f"{pair_id}: duplicate gold relation")

    out_of_schema = annotation.get("out_of_schema_relation")
    ambiguity = annotation.get("ambiguity")
    negative_rationale = annotation.get("negative_rationale")

    if label is None:
        if gold_relations or out_of_schema is not None or ambiguity is not None:
            errors.append(f"{pair_id}: unlabelled draft must not contain positive content")
        if negative_rationale is not None:
            errors.append(f"{pair_id}: unlabelled draft must not contain negative rationale")
    elif label == "IN_SCHEMA_RELATION":
        if not gold_relations:
            errors.append(f"{pair_id}: IN_SCHEMA_RELATION requires gold_relations")
        if primary_count != 1:
            errors.append(f"{pair_id}: IN_SCHEMA_RELATION requires exactly one primary relation")
        if out_of_schema is not None or ambiguity is not None:
            errors.append(f"{pair_id}: in-schema positive cannot contain diagnostic payloads")
        if negative_rationale is not None:
            errors.append(f"{pair_id}: in-schema positive cannot contain negative_rationale")
    elif label == "NO_IN_SCHEMA_RELATION":
        if gold_relations:
            errors.append(f"{pair_id}: negative annotation must not contain gold_relations")
        if out_of_schema is not None or ambiguity is not None:
            errors.append(f"{pair_id}: negative annotation cannot contain diagnostic payloads")
        if not nonempty_text(negative_rationale):
            errors.append(f"{pair_id}: negative annotation requires negative_rationale")
    elif label == "OUT_OF_SCHEMA_RELATION":
        if gold_relations:
            errors.append(f"{pair_id}: out-of-schema annotation must not contain gold_relations")
        if ambiguity is not None or negative_rationale is not None:
            errors.append(f"{pair_id}: out-of-schema annotation has incompatible fields")
        if not validate_exact_keys(
            out_of_schema,
            expected={
                "relation_description",
                "schema_exclusion_rationale",
                "evidence_spans",
            },
            label=f"{pair_id}:out_of_schema_relation",
            errors=errors,
        ):
            pass
        else:
            if not nonempty_text(out_of_schema.get("relation_description")):
                errors.append(f"{pair_id}: out-of-schema relation_description required")
            if not nonempty_text(out_of_schema.get("schema_exclusion_rationale")):
                errors.append(f"{pair_id}: schema_exclusion_rationale required")
            validate_evidence(
                out_of_schema.get("evidence_spans"),
                pair_id=pair_id,
                field="out_of_schema_relation.evidence_spans",
                lecture_id=lecture_id,
                lecture_text=lecture_text,
                errors=errors,
            )
    elif label == "AMBIGUOUS":
        if out_of_schema is not None or negative_rationale is not None:
            errors.append(f"{pair_id}: ambiguous annotation has incompatible fields")
        if primary_count:
            errors.append(f"{pair_id}: ambiguous annotation cannot select a primary relation")
        if not validate_exact_keys(
            ambiguity,
            expected={"rationale", "competing_interpretations", "adjudication_status"},
            label=f"{pair_id}:ambiguity",
            errors=errors,
        ):
            pass
        else:
            if not nonempty_text(ambiguity.get("rationale")):
                errors.append(f"{pair_id}: ambiguity rationale required")
            interpretations = ambiguity.get("competing_interpretations")
            if not isinstance(interpretations, list) or len(interpretations) < 2:
                errors.append(f"{pair_id}: at least two competing interpretations required")
            elif not all(nonempty_text(item) for item in interpretations):
                errors.append(f"{pair_id}: competing interpretations must be non-empty")
            adjudication_status = ambiguity.get("adjudication_status")
            if not isinstance(adjudication_status, str) or adjudication_status not in {
                "pending_review",
                "adjudicated_final",
            }:
                errors.append(f"{pair_id}: invalid ambiguity adjudication_status")
            if status == "final" and adjudication_status != "adjudicated_final":
                errors.append(f"{pair_id}: final AMBIGUOUS requires adjudicated_final")

    annotation_source = annotation.get("annotation_source")
    source_annotation = annotation.get("source_annotation")
    if label is None and (annotation_source is not None or source_annotation is not None):
        errors.append(f"{pair_id}: unlabelled draft must not contain provenance")
    if label is not None and (
        not isinstance(annotation_source, str)
        or annotation_source not in ALLOWED_ANNOTATION_SOURCES
    ):
        errors.append(f"{pair_id}: completed label requires annotation_source")
    if label == "AMBIGUOUS" and status == "final" and annotation_source != "adjudicated":
        errors.append(f"{pair_id}: final AMBIGUOUS requires adjudicated source")
    if annotation_source == "reused_existing_relation_annotation":
        if validate_exact_keys(
            source_annotation,
            expected={
                "source_relation_id",
                "source_artifact_path",
                "source_artifact_sha256",
            },
            label=f"{pair_id}:source_annotation",
            errors=errors,
        ):
            if not nonempty_text(source_annotation.get("source_relation_id")):
                errors.append(f"{pair_id}: source_relation_id required")
            source_path = source_annotation.get("source_artifact_path")
            source_hash = source_annotation.get("source_artifact_sha256")
            if not nonempty_text(source_path):
                errors.append(f"{pair_id}: source_artifact_path required")
            elif not isinstance(source_hash, str) or not SHA256_PATTERN.fullmatch(source_hash):
                errors.append(f"{pair_id}: source_artifact_sha256 invalid")
            else:
                resolved = resolve_path(source_path)
                if not resolved.is_file():
                    errors.append(f"{pair_id}: reused source artifact does not exist")
                elif sha256_file(resolved) != source_hash:
                    errors.append(f"{pair_id}: stale reused source artifact hash")
                else:
                    try:
                        source_data = load_json_object(
                            resolved, label=f"{pair_id} reused source artifact"
                        )
                    except CandidateGroundTruthError as exc:
                        errors.append(str(exc))
                    else:
                        source_ids = {
                            item.get("pair_id")
                            for item in source_data.get("pairs", [])
                            if isinstance(item, dict)
                        }
                        if source_annotation.get("source_relation_id") not in source_ids:
                            errors.append(
                                f"{pair_id}: source_relation_id not found in reused artifact"
                            )
    elif source_annotation is not None:
        errors.append(f"{pair_id}: source_annotation is only valid for reused annotations")

    notes = annotation.get("notes")
    if notes is not None and not nonempty_text(notes):
        errors.append(f"{pair_id}: notes must be null or non-empty")
    normalized_label = label if isinstance(label, str) or label is None else "INVALID_LABEL"
    normalized_status = status if isinstance(status, str) else "INVALID_STATUS"
    return normalized_label, normalized_status


def validate_candidate_pair_ground_truth(
    pair_universe_path: Path,
    ground_truth_path: Path,
    *,
    allow_draft: bool,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    universe = load_json_object(pair_universe_path, label="pair universe")
    ground_truth = load_json_object(ground_truth_path, label="ground truth")

    validate_exact_keys(
        universe,
        expected=UNIVERSE_TOP_LEVEL_KEYS,
        label="pair_universe",
        errors=errors,
    )
    pair_universe_marker_path = validate_pair_universe_marker(
        pair_universe_path, universe, errors=errors
    )
    source_binding = universe.get("source_inventory")
    lecture_binding = universe.get("lecture_inventory")
    source_path = validate_binding(
        source_binding,
        label="pair_universe.source_inventory",
        errors=errors,
        require_version=False,
        extra_keys={
            "normalized_content_sha256",
            "source_split",
            "structural_normalization_version",
        },
    )
    lecture_path = validate_binding(
        lecture_binding,
        label="pair_universe.lecture_inventory",
        errors=errors,
        require_version=False,
    )

    inventory: dict[str, Any] = {}
    lecture_inventory: dict[str, Any] = {}
    objects: list[dict[str, Any]] = []
    lecture_texts: dict[str, str] = {}
    if source_path is not None:
        inventory = load_json_object(source_path, label="source inventory")
        try:
            objects = validate_inventory(inventory)
        except CandidatePairUniverseError as exc:
            errors.append(f"source inventory: {exc}")
    if lecture_path is not None:
        lecture_inventory = load_json_object(lecture_path, label="lecture inventory")
        expected_ids = {item.get("lecture_id") for item in objects if isinstance(item, dict)}
        try:
            validate_lecture_inventory(
                lecture_inventory,
                expected_lecture_ids={item for item in expected_ids if isinstance(item, str)},
            )
        except CandidatePairUniverseError as exc:
            errors.append(f"lecture inventory: {exc}")
        lectures = lecture_inventory.get("lectures", [])
        if isinstance(lectures, list):
            for item in lectures:
                if isinstance(item, dict) and isinstance(item.get("lecture_id"), str):
                    if isinstance(item.get("text"), str):
                        lecture_texts[item["lecture_id"]] = item["text"]

    if source_path is not None and lecture_path is not None and objects:
        try:
            expected_universe = build_pair_universe(
                inventory,
                source_inventory_path=source_binding["path"],
                source_inventory_sha256=source_binding["sha256"],
                lecture_inventory=lecture_inventory,
                lecture_inventory_path=lecture_binding["path"],
                lecture_inventory_sha256=lecture_binding["sha256"],
                benchmark_split=universe.get("benchmark_split"),
            )
            if universe != expected_universe:
                errors.append(
                    "pair_universe: artifact does not match deterministic regeneration"
                )
        except CandidatePairUniverseError as exc:
            errors.append(f"pair_universe: deterministic regeneration failed: {exc}")

    pairs = universe.get("pairs")
    if not isinstance(pairs, list):
        errors.append("pair_universe.pairs: must be a list")
        pairs = []
    known_refs = {
        (item["lecture_id"], item["predicted_ko_id"])
        for item in objects
        if isinstance(item, dict)
        and isinstance(item.get("lecture_id"), str)
        and isinstance(item.get("predicted_ko_id"), str)
    }
    seen_unordered: set[frozenset[tuple[str, str]]] = set()
    pair_ids: list[str] = []
    for index, pair in enumerate(pairs):
        prefix = f"pair_universe.pairs[{index}]"
        if not validate_exact_keys(
            pair,
            expected={"pair_id", "lecture_id", "ko_a", "ko_b"},
            label=prefix,
            errors=errors,
        ):
            continue
        pair_id = pair.get("pair_id")
        pair_ids.append(pair_id if isinstance(pair_id, str) else "")
        a = qualified_ref(pair.get("ko_a"))
        b = qualified_ref(pair.get("ko_b"))
        lecture_id = pair.get("lecture_id")
        if a is None or b is None:
            errors.append(f"{prefix}: invalid endpoint shape")
            continue
        if a == b:
            errors.append(f"{prefix}: self pair is forbidden")
        if a not in known_refs or b not in known_refs:
            errors.append(f"{prefix}: unknown endpoint")
        if a[0] != lecture_id or b[0] != lecture_id:
            errors.append(f"{prefix}: endpoints must belong to pair lecture")
        if a > b:
            errors.append(f"{prefix}: endpoint order is not canonical")
        unordered = frozenset((a, b))
        if unordered in seen_unordered:
            errors.append(f"{prefix}: duplicate or reversed-duplicate pair")
        seen_unordered.add(unordered)
    if len(pair_ids) != len(set(pair_ids)):
        errors.append("pair_universe: duplicate pair_id")

    validate_exact_keys(
        ground_truth,
        expected=GROUND_TRUTH_TOP_LEVEL_KEYS,
        label="ground_truth",
        errors=errors,
    )
    if ground_truth.get("artifact_type") != "candidate_pair_ground_truth":
        errors.append("ground_truth.artifact_type: invalid")
    if ground_truth.get("version") != "v0.1":
        errors.append("ground_truth.version: must be v0.1")
    if ground_truth.get("benchmark_split") != universe.get("benchmark_split"):
        errors.append("ground_truth.benchmark_split: does not match pair universe")
    if allow_draft:
        if ground_truth.get("status") not in {"draft_annotation_required", "frozen"}:
            errors.append("ground_truth.status: invalid")
    elif ground_truth.get("status") != "frozen":
        errors.append("ground_truth.status: final mode requires frozen")

    pair_binding_path = validate_binding(
        ground_truth.get("pair_universe"),
        label="ground_truth.pair_universe",
        errors=errors,
        require_version=False,
    )
    if pair_binding_path is not None:
        try:
            if pair_binding_path.resolve() != pair_universe_path.resolve():
                errors.append("ground_truth.pair_universe: path does not match checked artifact")
        except OSError:
            pass
    if ground_truth.get("source_inventory") != universe.get("source_inventory"):
        errors.append("ground_truth.source_inventory: does not match pair universe")
    if ground_truth.get("lecture_inventory") != universe.get("lecture_inventory"):
        errors.append("ground_truth.lecture_inventory: does not match pair universe")

    for field in (
        "annotation_guidelines",
        "relation_annotation_guidelines",
        "evaluation_protocol",
        "success_criteria",
    ):
        validate_binding(
            ground_truth.get(field),
            label=f"ground_truth.{field}",
            errors=errors,
            require_version=True,
        )
    schema_bindings = ground_truth.get("schema_bindings")
    if validate_exact_keys(
        schema_bindings,
        expected={"pair_universe", "ground_truth"},
        label="ground_truth.schema_bindings",
        errors=errors,
    ):
        for field in ("pair_universe", "ground_truth"):
            validate_binding(
                schema_bindings.get(field),
                label=f"ground_truth.schema_bindings.{field}",
                errors=errors,
                require_version=True,
            )

    if ground_truth.get("allowed_candidate_labels") != ALLOWED_CANDIDATE_LABELS:
        errors.append("ground_truth.allowed_candidate_labels: frozen list mismatch")
    if ground_truth.get("allowed_relation_types") != ALLOWED_RELATION_TYPES:
        errors.append("ground_truth.allowed_relation_types: frozen list mismatch")
    if ground_truth.get("primary_scoring_labels") != PRIMARY_SCORING_LABELS:
        errors.append("ground_truth.primary_scoring_labels: frozen list mismatch")

    annotations = ground_truth.get("annotations")
    if not isinstance(annotations, list):
        errors.append("ground_truth.annotations: must be a list")
        annotations = []
    annotation_ids: list[str] = []
    for index, item in enumerate(annotations):
        pair_id = item.get("pair_id") if isinstance(item, dict) else None
        if not isinstance(pair_id, str) or not pair_id:
            errors.append(f"ground_truth.annotations[{index}]: invalid pair_id")
            annotation_ids.append(f"__invalid_pair_id_{index}__")
        else:
            annotation_ids.append(pair_id)
    if len(annotation_ids) != len(set(annotation_ids)):
        errors.append("ground_truth.annotations: duplicate pair_id")
    if annotation_ids != pair_ids:
        missing = sorted(set(pair_ids) - set(annotation_ids))
        extra = sorted(set(annotation_ids) - set(pair_ids))
        if missing:
            errors.append(f"ground_truth.annotations: missing pair IDs {missing}")
        if extra:
            errors.append(f"ground_truth.annotations: extra pair IDs {extra}")
        if not missing and not extra:
            errors.append("ground_truth.annotations: pair order differs from universe")

    ko_types = {
        (item["lecture_id"], item["predicted_ko_id"]): item["type"]
        for item in objects
        if isinstance(item, dict)
        and all(key in item for key in ("lecture_id", "predicted_ko_id", "type"))
    }
    labels: list[str | None] = []
    statuses: list[str | None] = []
    for index, pair in enumerate(pairs):
        if index >= len(annotations):
            break
        label, status = validate_annotation(
            annotations[index],
            expected_pair=pair,
            lecture_texts=lecture_texts,
            ko_types=ko_types,
            allow_draft=allow_draft,
            errors=errors,
        )
        labels.append(label)
        statuses.append(status)

    label_counts = Counter("UNLABELLED" if item is None else item for item in labels)
    status_counts = Counter("INVALID" if item is None else item for item in statuses)
    primary_denominator = sum(label_counts[label] for label in PRIMARY_SCORING_LABELS)
    diagnostic_denominator = sum(
        label_counts[label] for label in ("OUT_OF_SCHEMA_RELATION", "AMBIGUOUS")
    )
    pending_count = sum(status != "final" for status in statuses)
    summary = {
        "validation_mode": "draft" if allow_draft else "final",
        "pair_count": len(pairs),
        "annotation_count": len(annotations),
        "label_counts": dict(sorted(label_counts.items())),
        "annotation_status_counts": dict(sorted(status_counts.items())),
        "primary_denominator": primary_denominator,
        "diagnostic_denominator": diagnostic_denominator,
        "pending_workflow_items": pending_count,
        "error_count": len(errors),
        "evaluation_status": (
            "invalid"
            if errors
            else "valid_draft"
            if pending_count
            else "final"
        ),
        "pair_universe_completion_marker": (
            display_path(pair_universe_marker_path)
            if pair_universe_marker_path is not None
            else None
        ),
    }
    return errors, summary


def build_completion_marker(
    *,
    pair_universe_path: Path,
    ground_truth_path: Path,
    ground_truth: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    checker_path = Path(__file__).resolve()
    bound_artifacts = {
        "pair_universe": {
            "path": display_path(pair_universe_path),
            "sha256": sha256_file(pair_universe_path),
        },
        "ground_truth": {
            "path": display_path(ground_truth_path),
            "sha256": sha256_file(ground_truth_path),
        },
        "pair_universe_completion_marker": {
            "path": display_path(
                pair_universe_path.with_name("pair_universe_complete.json")
            ),
            "sha256": sha256_file(
                pair_universe_path.with_name("pair_universe_complete.json")
            ),
        },
        "annotation_guidelines": ground_truth["annotation_guidelines"],
        "relation_annotation_guidelines": ground_truth[
            "relation_annotation_guidelines"
        ],
        "evaluation_protocol": ground_truth["evaluation_protocol"],
        "success_criteria": ground_truth["success_criteria"],
        "pair_universe_schema": ground_truth["schema_bindings"]["pair_universe"],
        "ground_truth_schema": ground_truth["schema_bindings"]["ground_truth"],
    }
    return {
        "artifact_type": "candidate_pair_ground_truth_complete",
        "version": "v0.1",
        "completion_status": "final",
        "artifacts": bound_artifacts,
        "checker": {
            "path": display_path(checker_path),
            "sha256": sha256_file(checker_path),
            "version": CHECKER_VERSION,
        },
        "counts": {
            "total_pairs": summary["pair_count"],
            "labels": summary["label_counts"],
            "annotation_statuses": summary["annotation_status_counts"],
            "primary_denominator": summary["primary_denominator"],
            "diagnostic_denominator": summary["diagnostic_denominator"],
            "pending_workflow_items": summary["pending_workflow_items"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate exhaustive candidate-pair ground truth."
    )
    parser.add_argument("--pair-universe", default=str(DEFAULT_PAIR_UNIVERSE))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument(
        "--allow-draft",
        action="store_true",
        help="Permit draft/pending annotations while validating filled records strictly.",
    )
    parser.add_argument(
        "--write-completion-marker",
        action="store_true",
        help="Write the final marker. Valid only in final mode with zero errors.",
    )
    parser.add_argument("--completion-marker", default=str(DEFAULT_COMPLETION_MARKER))
    parser.add_argument("--overwrite-completion-marker", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pair_universe_path = resolve_path(args.pair_universe)
    ground_truth_path = resolve_path(args.ground_truth)
    marker_path = resolve_path(args.completion_marker)
    if args.allow_draft and args.write_completion_marker:
        print("Completion marker cannot be written in draft mode.", file=sys.stderr)
        return 1
    try:
        errors, summary = validate_candidate_pair_ground_truth(
            pair_universe_path,
            ground_truth_path,
            allow_draft=args.allow_draft,
        )
    except CandidateGroundTruthError as exc:
        print(f"Candidate ground-truth validation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        print("\nValidation errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.write_completion_marker:
        if marker_path.exists() and not args.overwrite_completion_marker:
            print(
                f"Refusing to overwrite completion marker: {display_path(marker_path)}",
                file=sys.stderr,
            )
            return 1
        ground_truth = load_json_object(ground_truth_path, label="ground truth")
        marker = build_completion_marker(
            pair_universe_path=pair_universe_path,
            ground_truth_path=ground_truth_path,
            ground_truth=ground_truth,
            summary=summary,
        )
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(serialize_json(marker), encoding="utf-8")
        print(f"Completion marker {display_path(marker_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
