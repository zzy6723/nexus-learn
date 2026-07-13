#!/usr/bin/env python3
"""Validate benchmark ground-truth files before freeze."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_DIR = ROOT / "benchmark" / "ground_truth"

ALLOWED_TYPES = {"Concept", "Method", "Formula"}
ALLOWED_CATEGORIES = {"required", "optional", "excluded"}
REQUIRED_TOP_LEVEL_KEYS = {
    "version",
    "split",
    "status",
    "created",
    "description",
    "annotation_guidelines",
    "evaluation_protocol",
    "allowed_object_types",
    "lectures",
}
REQUIRED_OBJECT_KEYS = {
    "id",
    "name",
    "type",
    "category",
    "aliases",
    "source_spans",
}
DASH_TRANSLATION = str.maketrans({
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
})
APOSTROPHE_TRANSLATION = str.maketrans({
    "‘": "'",
    "’": "'",
    "‛": "'",
    "`": "'",
    "´": "'",
})


@dataclass(frozen=True)
class LectureRecord:
    ground_truth_file: str
    split: str
    lecture_id: str
    path: str
    content_hash: str


def normalize_label(label: str) -> str:
    normalized = unicodedata.normalize("NFKC", label)
    normalized = normalized.translate(APOSTROPHE_TRANSLATION)
    normalized = normalized.translate(DASH_TRANSLATION)
    normalized = normalized.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.casefold()


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{path.name}: unable to read or parse JSON: {exc}"]


def validate_alias_conflicts(
    *,
    path_name: str,
    lecture_id: str,
    objects: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    canonical_by_normalized: dict[str, str] = {}
    alias_by_normalized: dict[str, tuple[str, str]] = {}

    for obj in objects:
        obj_id = obj.get("id", "<missing>")
        name = obj.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        normalized_name = normalize_label(name)
        if normalized_name in canonical_by_normalized:
            errors.append(
                f"{path_name}:{lecture_id}:{obj_id}: canonical label conflicts with "
                f"{canonical_by_normalized[normalized_name]}"
            )
        canonical_by_normalized[normalized_name] = obj_id

    for obj in objects:
        obj_id = obj.get("id", "<missing>")
        name = obj.get("name")
        normalized_name = normalize_label(name) if isinstance(name, str) else None
        aliases = obj.get("aliases")
        if not isinstance(aliases, list):
            continue

        for alias in aliases:
            if not isinstance(alias, str) or not alias.strip():
                continue
            normalized_alias = normalize_label(alias)

            if normalized_alias == normalized_name:
                errors.append(
                    f"{path_name}:{lecture_id}:{obj_id}: alias duplicates canonical label: {alias}"
                )

            canonical_owner = canonical_by_normalized.get(normalized_alias)
            if canonical_owner and canonical_owner != obj_id:
                errors.append(
                    f"{path_name}:{lecture_id}:{obj_id}: alias conflicts with canonical "
                    f"label of {canonical_owner}: {alias}"
                )

            previous_alias = alias_by_normalized.get(normalized_alias)
            if previous_alias and previous_alias[0] != obj_id:
                errors.append(
                    f"{path_name}:{lecture_id}:{obj_id}: alias conflicts with alias of "
                    f"{previous_alias[0]}: {alias}"
                )
            alias_by_normalized[normalized_alias] = (obj_id, alias)

    return errors


def validate_file(path: Path) -> tuple[list[str], list[LectureRecord]]:
    errors: list[str] = []
    records: list[LectureRecord] = []
    data, load_errors = load_json(path)
    if load_errors:
        return load_errors, records
    assert data is not None

    missing = REQUIRED_TOP_LEVEL_KEYS - set(data)
    if missing:
        errors.append(f"{path.name}: missing top-level keys: {sorted(missing)}")

    split = data.get("split")
    if not isinstance(split, str) or not split.strip():
        errors.append(f"{path.name}: split must be a non-empty string")
        split = "<missing>"

    if data.get("allowed_object_types") != ["Concept", "Method", "Formula"]:
        errors.append(f"{path.name}: allowed_object_types must be Concept/Method/Formula")

    lectures = data.get("lectures")
    if not isinstance(lectures, list):
        errors.append(f"{path.name}: lectures must be a list")
        return errors, records

    seen_lecture_ids: set[str] = set()
    seen_lecture_paths: set[str] = set()
    seen_content_hashes: set[str] = set()

    for lecture in lectures:
        if not isinstance(lecture, dict):
            errors.append(f"{path.name}: lecture entry must be an object")
            continue

        lecture_id = lecture.get("lecture_id")
        if not isinstance(lecture_id, str) or not lecture_id.strip():
            errors.append(f"{path.name}: lecture_id must be a non-empty string")
            lecture_id = "<missing>"
        if lecture_id in seen_lecture_ids:
            errors.append(f"{path.name}:{lecture_id}: duplicate lecture_id")
        seen_lecture_ids.add(lecture_id)

        path_value = lecture.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"{path.name}:{lecture_id}: path must be a non-empty string")
            continue
        if path_value in seen_lecture_paths:
            errors.append(f"{path.name}:{lecture_id}: duplicate lecture path {path_value}")
        seen_lecture_paths.add(path_value)

        relative_path = Path(path_value)
        expected_prefix = Path("benchmark") / "lectures" / str(split)
        if expected_prefix not in relative_path.parents:
            errors.append(
                f"{path.name}:{lecture_id}: lecture path does not match split {split}: "
                f"{path_value}"
            )

        lecture_path = ROOT / relative_path
        if not lecture_path.is_file():
            errors.append(f"{path.name}:{lecture_id}: missing lecture file {lecture_path}")
            continue

        try:
            lecture_text = lecture_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path.name}:{lecture_id}: unable to read lecture file: {exc}")
            continue

        content_hash = hashlib.sha256(lecture_text.encode("utf-8")).hexdigest()
        if content_hash in seen_content_hashes:
            errors.append(f"{path.name}:{lecture_id}: duplicate lecture content hash")
        seen_content_hashes.add(content_hash)
        records.append(
            LectureRecord(
                ground_truth_file=path.name,
                split=str(split),
                lecture_id=lecture_id,
                path=path_value,
                content_hash=content_hash,
            )
        )

        if "expected_objects" in lecture:
            errors.append(f"{path.name}:{lecture_id}: uses old expected_objects key")

        objects = lecture.get("objects")
        if not isinstance(objects, list):
            errors.append(f"{path.name}:{lecture_id}: missing objects list")
            continue

        errors.extend(
            validate_alias_conflicts(
                path_name=path.name,
                lecture_id=lecture_id,
                objects=objects,
            )
        )

        seen_ids: set[str] = set()
        for obj in objects:
            if not isinstance(obj, dict):
                errors.append(f"{path.name}:{lecture_id}: object entry must be an object")
                continue

            obj_id = obj.get("id")
            if not isinstance(obj_id, str) or not obj_id.strip():
                errors.append(f"{path.name}:{lecture_id}: object id must be a non-empty string")
                obj_id = "<missing>"
            if obj_id in seen_ids:
                errors.append(f"{path.name}:{lecture_id}:{obj_id}: duplicate id")
            seen_ids.add(obj_id)

            name = obj.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{path.name}:{lecture_id}:{obj_id}: name must be non-empty")

            missing_obj_keys = REQUIRED_OBJECT_KEYS - set(obj)
            if missing_obj_keys:
                errors.append(
                    f"{path.name}:{lecture_id}:{obj_id}: missing object keys: "
                    f"{sorted(missing_obj_keys)}"
                )

            if obj.get("type") not in ALLOWED_TYPES:
                errors.append(f"{path.name}:{lecture_id}:{obj_id}: invalid type {obj.get('type')}")
            if obj.get("category") not in ALLOWED_CATEGORIES:
                errors.append(
                    f"{path.name}:{lecture_id}:{obj_id}: invalid category {obj.get('category')}"
                )

            aliases = obj.get("aliases")
            if not isinstance(aliases, list):
                errors.append(f"{path.name}:{lecture_id}:{obj_id}: aliases must be a list")
            else:
                for alias in aliases:
                    if not isinstance(alias, str) or not alias.strip():
                        errors.append(
                            f"{path.name}:{lecture_id}:{obj_id}: aliases must contain "
                            "non-empty strings"
                        )

            spans = obj.get("source_spans")
            if not isinstance(spans, list) or not spans:
                errors.append(f"{path.name}:{lecture_id}:{obj_id}: source_spans must be non-empty")
                continue
            for span in spans:
                if not isinstance(span, str) or not span.strip():
                    errors.append(
                        f"{path.name}:{lecture_id}:{obj_id}: source_spans must contain "
                        "non-empty strings"
                    )
                    continue
                if span not in lecture_text:
                    errors.append(
                        f"{path.name}:{lecture_id}:{obj_id}: source span not exact substring: "
                        f"{span}"
                    )

    return errors, records


def validate_cross_file(records: list[LectureRecord]) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, LectureRecord] = {}
    seen_paths: dict[str, LectureRecord] = {}
    seen_hashes: dict[str, LectureRecord] = {}

    for record in records:
        previous = seen_ids.get(record.lecture_id)
        if previous:
            errors.append(
                f"{record.ground_truth_file}:{record.lecture_id}: lecture_id also appears "
                f"in {previous.ground_truth_file}"
            )
        seen_ids[record.lecture_id] = record

        previous = seen_paths.get(record.path)
        if previous:
            errors.append(
                f"{record.ground_truth_file}:{record.lecture_id}: path also appears in "
                f"{previous.ground_truth_file}: {record.path}"
            )
        seen_paths[record.path] = record

        previous = seen_hashes.get(record.content_hash)
        if previous:
            errors.append(
                f"{record.ground_truth_file}:{record.lecture_id}: lecture content duplicates "
                f"{previous.ground_truth_file}:{previous.lecture_id}"
            )
        seen_hashes[record.content_hash] = record

    return errors


def main() -> int:
    paths = sorted(
        path
        for path in GROUND_TRUTH_DIR.glob("*_v0_1.json")
        if not path.name.startswith("relations_")
    )
    if not paths:
        print("No ground-truth files found.", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    all_records: list[LectureRecord] = []
    for path in paths:
        errors, records = validate_file(path)
        if errors:
            all_errors.extend(errors)
        else:
            print(f"OK {path.relative_to(ROOT)}")
        all_records.extend(records)

    all_errors.extend(validate_cross_file(all_records))

    if all_errors:
        for error in all_errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    print("Ground truth validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
