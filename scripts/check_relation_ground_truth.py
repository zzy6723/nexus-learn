#!/usr/bin/env python3
"""Validate Typed Relation Extraction ground truth before model execution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROUND_TRUTH = (
    ROOT / "benchmark" / "ground_truth" / "relations_development_v0_1.json"
)
GRAPH_RELATIONS = {
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
}
ALLOWED_RELATIONS = GRAPH_RELATIONS | {"NO_RELATION"}
ALLOWED_CATEGORIES = {"positive", "hard_negative", "ambiguous", "schema_gap"}
REQUIRED_TOP_LEVEL_KEYS = {
    "version",
    "split",
    "status",
    "description",
    "annotation_guidelines",
    "evaluation_protocol",
    "knowledge_object_ground_truths",
    "notes",
    "allowed_relation_types",
    "relation_coverage",
    "primary_scoring_categories",
    "lectures",
    "pairs",
}
REQUIRED_PAIR_KEYS = {
    "pair_id",
    "category",
    "source",
    "target",
    "relation_type",
    "symmetric",
    "evidence_spans",
    "rationale",
}
PAIR_ID_PREFIX_BY_SPLIT = {
    "development": "rel_dev",
    "holdout": "rel_holdout",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
MATCHED_DERIVATION_VERSION = "predicted_ko_projection_v0_1"
MATCHED_DERIVATION_HASH_FIELDS = {
    "original_ground_truth_sha256",
    "alignment_sha256",
    "pair_manifest_sha256",
    "ko_manifest_sha256",
    "matched_knowledge_objects_sha256",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate relation extraction ground-truth structure and grounding."
    )
    parser.add_argument(
        "--ground-truth",
        default=str(DEFAULT_GROUND_TRUTH.relative_to(ROOT)),
        help="Relation ground-truth JSON path relative to the repository root.",
    )
    return parser.parse_args()


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read {path}: {exc}") from exc


def qualified_ref(ref: dict[str, Any]) -> tuple[str, str] | None:
    lecture_id = ref.get("lecture_id")
    ko_id = ref.get("ko_id")
    if not isinstance(lecture_id, str) or not lecture_id:
        return None
    if not isinstance(ko_id, str) or not ko_id:
        return None
    return lecture_id, ko_id


def load_knowledge_objects(
    paths: list[str],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str], list[str]]:
    objects: dict[tuple[str, str], dict[str, Any]] = {}
    lecture_paths: dict[str, str] = {}
    errors: list[str] = []

    for path_text in paths:
        path = resolve_path(path_text)
        try:
            data = load_json(path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue

        lectures = data.get("lectures")
        if not isinstance(lectures, list):
            errors.append(f"{path_text}: lectures must be a list")
            continue

        for lecture in lectures:
            if not isinstance(lecture, dict):
                errors.append(f"{path_text}: lecture entry must be an object")
                continue
            lecture_id = lecture.get("lecture_id")
            lecture_path = lecture.get("path")
            if not isinstance(lecture_id, str) or not lecture_id:
                errors.append(f"{path_text}: invalid lecture_id")
                continue
            if not isinstance(lecture_path, str) or not lecture_path:
                errors.append(f"{path_text}:{lecture_id}: invalid lecture path")
                continue
            previous_path = lecture_paths.get(lecture_id)
            if previous_path and previous_path != lecture_path:
                errors.append(
                    f"{lecture_id}: conflicting lecture paths {previous_path} and {lecture_path}"
                )
            lecture_paths[lecture_id] = lecture_path

            lecture_objects = lecture.get("objects")
            if not isinstance(lecture_objects, list):
                errors.append(f"{path_text}:{lecture_id}: objects must be a list")
                continue
            for obj in lecture_objects:
                if not isinstance(obj, dict):
                    errors.append(f"{path_text}:{lecture_id}: object must be an object")
                    continue
                ko_id = obj.get("id")
                if not isinstance(ko_id, str) or not ko_id:
                    errors.append(f"{path_text}:{lecture_id}: invalid object id")
                    continue
                key = (lecture_id, ko_id)
                if key in objects:
                    errors.append(f"duplicate Knowledge Object reference {key}")
                objects[key] = obj

    return objects, lecture_paths, errors


def load_lecture_texts(
    lecture_paths: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    errors: list[str] = []
    for lecture_id, path_text in lecture_paths.items():
        path = resolve_path(path_text)
        try:
            texts[lecture_id] = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{lecture_id}: unable to read {path_text}: {exc}")
    return texts, errors


def validate_reference(
    value: Any,
    *,
    field: str,
    pair_id: str,
    objects: dict[tuple[str, str], dict[str, Any]],
    errors: list[str],
) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        errors.append(f"{pair_id}:{field}: must be an object")
        return None
    ref = qualified_ref(value)
    if ref is None:
        errors.append(f"{pair_id}:{field}: requires lecture_id and ko_id")
        return None
    if ref not in objects:
        errors.append(f"{pair_id}:{field}: unknown Knowledge Object {ref}")
        return None
    return ref


def validate_evidence(
    pair: dict[str, Any],
    *,
    pair_id: str,
    relation_type: str,
    lecture_texts: dict[str, str],
    errors: list[str],
) -> None:
    evidence = pair.get("evidence_spans")
    if not isinstance(evidence, list):
        errors.append(f"{pair_id}: evidence_spans must be a list")
        return

    if relation_type == "NO_RELATION" and evidence:
        errors.append(f"{pair_id}: NO_RELATION must have no evidence spans")
    if relation_type in GRAPH_RELATIONS and not evidence:
        errors.append(f"{pair_id}: positive Relation requires evidence spans")

    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"{pair_id}:evidence[{index}]: must be an object")
            continue
        lecture_id = item.get("lecture_id")
        span = item.get("span")
        if not isinstance(lecture_id, str) or lecture_id not in lecture_texts:
            errors.append(f"{pair_id}:evidence[{index}]: unknown lecture_id")
            continue
        if not isinstance(span, str) or not span:
            errors.append(f"{pair_id}:evidence[{index}]: span must be non-empty")
            continue
        if span not in lecture_texts[lecture_id]:
            errors.append(
                f"{pair_id}:evidence[{index}]: span is not an exact lecture substring: {span!r}"
            )


def validate_alternatives(
    pair: dict[str, Any],
    *,
    pair_id: str,
    candidate_refs: set[tuple[str, str]],
    objects: dict[tuple[str, str], dict[str, Any]],
    errors: list[str],
) -> None:
    alternatives = pair.get("acceptable_alternatives", [])
    if not isinstance(alternatives, list):
        errors.append(f"{pair_id}: acceptable_alternatives must be a list")
        return

    for index, alternative in enumerate(alternatives):
        prefix = f"{pair_id}:acceptable_alternatives[{index}]"
        if not isinstance(alternative, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        relation_type = alternative.get("relation_type")
        if relation_type not in GRAPH_RELATIONS:
            errors.append(f"{prefix}: invalid relation_type {relation_type!r}")
        source = validate_reference(
            alternative.get("source"),
            field=f"acceptable_alternatives[{index}].source",
            pair_id=pair_id,
            objects=objects,
            errors=errors,
        )
        target = validate_reference(
            alternative.get("target"),
            field=f"acceptable_alternatives[{index}].target",
            pair_id=pair_id,
            objects=objects,
            errors=errors,
        )
        if source and target and {source, target} != candidate_refs:
            errors.append(f"{prefix}: must use the same unordered candidate pair")


def validate_ground_truth(data: Any) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["top-level JSON value must be an object"], {}

    missing = REQUIRED_TOP_LEVEL_KEYS - set(data)
    if missing:
        errors.append(f"missing top-level keys: {sorted(missing)}")

    split = data.get("split")
    pair_id_prefix = PAIR_ID_PREFIX_BY_SPLIT.get(split)
    if pair_id_prefix is None:
        errors.append(
            "split must be one of "
            + ", ".join(sorted(PAIR_ID_PREFIX_BY_SPLIT))
        )
        pair_id_prefix = "rel_invalid"
    pair_id_pattern = re.compile(rf"{re.escape(pair_id_prefix)}_\d{{3}}")

    gt_paths = data.get("knowledge_object_ground_truths")
    if not isinstance(gt_paths, list) or not all(isinstance(item, str) for item in gt_paths):
        errors.append("knowledge_object_ground_truths must be a list of paths")
        gt_paths = []
    objects, lecture_paths, object_errors = load_knowledge_objects(gt_paths)
    errors.extend(object_errors)
    lecture_texts, lecture_errors = load_lecture_texts(lecture_paths)
    errors.extend(lecture_errors)

    if data.get("allowed_relation_types") != [
        "REQUIRES",
        "APPLIED_IN",
        "EXTENDS",
        "CONTRASTS_WITH",
        "FORMALIZES",
        "RELATED_TO",
        "NO_RELATION",
    ]:
        errors.append("allowed_relation_types does not match the v0.1 canonical order")

    primary_categories = data.get("primary_scoring_categories")
    if primary_categories != ["positive", "hard_negative"]:
        errors.append("primary_scoring_categories must be positive and hard_negative")

    declared_lectures = data.get("lectures")
    if not isinstance(declared_lectures, list) or not all(
        isinstance(item, str) for item in declared_lectures
    ):
        errors.append("lectures must be a list of lecture IDs")
        declared_lectures = []

    pairs = data.get("pairs")
    if not isinstance(pairs, list):
        return errors + ["pairs must be a list"], {}

    seen_ids: set[str] = set()
    seen_unordered_pairs: dict[frozenset[tuple[str, str]], str] = {}
    category_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    primary_relation_counts: Counter[str] = Counter()

    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            errors.append(f"pairs[{index}]: must be an object")
            continue
        missing_pair = REQUIRED_PAIR_KEYS - set(pair)
        pair_id = pair.get("pair_id", f"pairs[{index}]")
        if missing_pair:
            errors.append(f"{pair_id}: missing keys {sorted(missing_pair)}")
        if not isinstance(pair_id, str) or not pair_id_pattern.fullmatch(pair_id):
            errors.append(
                f"{pair_id}: pair_id must match {pair_id_prefix}_NNN for split {split!r}"
            )
            pair_id = f"pairs[{index}]"
        elif pair_id in seen_ids:
            errors.append(f"{pair_id}: duplicate pair_id")
        seen_ids.add(pair_id)

        category = pair.get("category")
        relation_type = pair.get("relation_type")
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"{pair_id}: invalid category {category!r}")
        else:
            category_counts[category] += 1
        if relation_type not in ALLOWED_RELATIONS:
            errors.append(f"{pair_id}: invalid relation_type {relation_type!r}")
        else:
            relation_counts[relation_type] += 1
            if category in {"positive", "hard_negative"}:
                primary_relation_counts[relation_type] += 1

        if category == "hard_negative" and relation_type != "NO_RELATION":
            errors.append(f"{pair_id}: hard_negative must use NO_RELATION")
        if category == "positive" and relation_type == "NO_RELATION":
            errors.append(f"{pair_id}: positive pair cannot use NO_RELATION")

        source = validate_reference(
            pair.get("source"), field="source", pair_id=pair_id, objects=objects, errors=errors
        )
        target = validate_reference(
            pair.get("target"), field="target", pair_id=pair_id, objects=objects, errors=errors
        )
        candidate_refs: set[tuple[str, str]] = set()
        if source and target:
            if source == target:
                errors.append(f"{pair_id}: source and target must differ")
            candidate_refs = {source, target}
            unordered_key = frozenset(candidate_refs)
            previous_pair = seen_unordered_pairs.get(unordered_key)
            if previous_pair:
                errors.append(
                    f"{pair_id}: duplicates unordered candidate pair from {previous_pair}"
                )
            seen_unordered_pairs[unordered_key] = pair_id

            if relation_type == "FORMALIZES" and objects[source].get("type") != "Formula":
                errors.append(f"{pair_id}: FORMALIZES source must have type Formula")

        symmetric = pair.get("symmetric")
        if not isinstance(symmetric, bool):
            errors.append(f"{pair_id}: symmetric must be boolean")
        elif symmetric and relation_type != "CONTRASTS_WITH":
            errors.append(f"{pair_id}: only CONTRASTS_WITH may be symmetric in v0.1")

        rationale = pair.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{pair_id}: rationale must be non-empty")

        validate_evidence(
            pair,
            pair_id=pair_id,
            relation_type=relation_type,
            lecture_texts=lecture_texts,
            errors=errors,
        )
        if candidate_refs:
            validate_alternatives(
                pair,
                pair_id=pair_id,
                candidate_refs=candidate_refs,
                objects=objects,
                errors=errors,
            )

    derivation = data.get("derivation")
    is_matched_artifact = data.get("artifact_type") == "matched_relation_ground_truth"
    is_derived_matched_subset = False
    if is_matched_artifact:
        if data.get("status") not in {"derived", "test_fixture"}:
            errors.append("matched Relation ground truth requires derived status")
        elif not isinstance(derivation, dict):
            errors.append("matched Relation ground truth requires derivation metadata")
        elif derivation.get("version") != MATCHED_DERIVATION_VERSION:
            errors.append("matched Relation ground truth has invalid derivation version")
        else:
            invalid_hash_fields = sorted(
                field
                for field in MATCHED_DERIVATION_HASH_FIELDS
                if not isinstance(derivation.get(field), str)
                or not SHA256_PATTERN.fullmatch(derivation[field])
            )
            if invalid_hash_fields:
                errors.append(
                    "matched Relation ground truth has invalid derivation hashes: "
                    + str(invalid_hash_fields)
                )
            else:
                is_derived_matched_subset = True
    if is_derived_matched_subset:
        ordered_ids = [
            pair.get("pair_id") for pair in pairs if isinstance(pair, dict)
        ]
        if ordered_ids != sorted(ordered_ids):
            errors.append("derived matched pair IDs must be lexicographically ordered")
    else:
        expected_ids = {
            f"{pair_id_prefix}_{index:03d}" for index in range(1, len(pairs) + 1)
        }
        if seen_ids != expected_ids:
            missing_ids = sorted(expected_ids - seen_ids)
            extra_ids = sorted(seen_ids - expected_ids)
            errors.append(
                f"pair IDs must be contiguous; missing={missing_ids}, extra={extra_ids}"
            )

    referenced_lectures = {
        lecture_id for candidate in seen_unordered_pairs for lecture_id, _ in candidate
    }
    if set(declared_lectures) != referenced_lectures:
        errors.append(
            "declared lectures do not match pair references: "
            f"declared={sorted(declared_lectures)}, referenced={sorted(referenced_lectures)}"
        )

    coverage = data.get("relation_coverage")
    if not isinstance(coverage, dict) or set(coverage) != ALLOWED_RELATIONS:
        errors.append("relation_coverage must contain every graph label and NO_RELATION")

    primary_count = sum(category_counts[name] for name in {"positive", "hard_negative"})
    negative_count = category_counts["hard_negative"]
    summary = {
        "pair_count": len(pairs),
        "primary_scored_pair_count": primary_count,
        "primary_hard_negative_count": negative_count,
        "primary_hard_negative_rate": (
            round(negative_count / primary_count, 4) if primary_count else None
        ),
        "category_counts": dict(sorted(category_counts.items())),
        "all_relation_counts": dict(sorted(relation_counts.items())),
        "primary_relation_counts": dict(sorted(primary_relation_counts.items())),
        "knowledge_object_count": len(objects),
        "lecture_count": len(referenced_lectures),
    }
    return errors, summary


def main() -> int:
    args = parse_args()
    path = resolve_path(args.ground_truth)
    try:
        data = load_json(path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors, summary = validate_ground_truth(data)
    if errors:
        print(f"Relation ground-truth validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Relation ground-truth validation passed: {path.relative_to(ROOT)}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
