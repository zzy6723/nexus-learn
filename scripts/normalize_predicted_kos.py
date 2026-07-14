#!/usr/bin/env python3
"""Structurally normalize Entity Extraction outputs without semantic repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .knowledge_object_matching import (
        NAME_MATCHING_NORMALIZATION_VERSION,
        name_matching_key,
    )
except ImportError:  # Direct execution: python3 scripts/normalize_predicted_kos.py
    from knowledge_object_matching import (
        NAME_MATCHING_NORMALIZATION_VERSION,
        name_matching_key,
    )


ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_NORMALIZATION_VERSION = "predicted_ko_structural_normalization_v0_1"
ALLOWED_KO_TYPES = {"Concept", "Method", "Formula"}


class NormalizationError(RuntimeError):
    """A fatal predicted-KO structural-normalization error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert raw Entity Extraction JSON into a content-preserving "
            "predicted-KO inventory."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        dest="inputs",
        help="Raw Entity prediction JSON. Repeat for multiple lecture files.",
    )
    parser.add_argument("--output", required=True, help="Normalized output JSON.")
    parser.add_argument(
        "--split",
        help="Optional split override when source artifacts do not declare one.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file.",
    )
    return parser.parse_args(argv)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_json_bytes(path: Path) -> tuple[Any, bytes]:
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise NormalizationError(
            "input_read_error", f"Unable to read {path}: {exc}"
        ) from exc
    try:
        return json.loads(raw_bytes.decode("utf-8")), raw_bytes
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "invalid_input_json", f"Unable to parse UTF-8 JSON {path}: {exc}"
        ) from exc


def require_nonempty_string(value: Any, *, field: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NormalizationError(code, f"{field} must be a non-empty string.")
    return value


def extract_raw_objects(
    data: Any,
    *,
    source_file: str,
) -> tuple[list[tuple[str, int, dict[str, Any]]], str | None]:
    if not isinstance(data, dict):
        raise NormalizationError(
            "invalid_prediction_schema",
            f"{source_file}: top-level JSON value must be an object.",
        )

    raw_objects = data.get("knowledge_objects")
    if not isinstance(raw_objects, list):
        raise NormalizationError(
            "invalid_prediction_schema",
            f"{source_file}: knowledge_objects must be a list.",
        )

    enclosing_lecture_id = data.get("lecture_id")
    if enclosing_lecture_id is not None:
        enclosing_lecture_id = require_nonempty_string(
            enclosing_lecture_id,
            field=f"{source_file}.lecture_id",
            code="invalid_lecture_id",
        )

    extracted: list[tuple[str, int, dict[str, Any]]] = []
    for index, raw_object in enumerate(raw_objects):
        if not isinstance(raw_object, dict):
            raise NormalizationError(
                "invalid_prediction_schema",
                f"{source_file}.knowledge_objects[{index}] must be an object.",
            )
        object_lecture_id = raw_object.get("lecture_id")
        if object_lecture_id is not None:
            object_lecture_id = require_nonempty_string(
                object_lecture_id,
                field=f"{source_file}.knowledge_objects[{index}].lecture_id",
                code="invalid_lecture_id",
            )
        if enclosing_lecture_id and object_lecture_id:
            if enclosing_lecture_id != object_lecture_id:
                raise NormalizationError(
                    "conflicting_lecture_id",
                    f"{source_file}.knowledge_objects[{index}] conflicts with "
                    "the enclosing lecture_id.",
                )
        lecture_id = enclosing_lecture_id or object_lecture_id
        if lecture_id is None:
            raise NormalizationError(
                "missing_lecture_id",
                f"{source_file}.knowledge_objects[{index}] has no lecture provenance.",
            )
        extracted.append((lecture_id, index, raw_object))

    split = data.get("split")
    if split is not None:
        split = require_nonempty_string(
            split,
            field=f"{source_file}.split",
            code="invalid_split",
        )
    return extracted, split


def normalize_raw_object(
    raw_object: dict[str, Any],
    *,
    lecture_id: str,
    source_file: str,
    source_object_index: int,
) -> dict[str, Any]:
    predicted_ko_id = require_nonempty_string(
        raw_object.get("id"),
        field=f"{source_file}.knowledge_objects[{source_object_index}].id",
        code="invalid_predicted_ko_id",
    )
    name = require_nonempty_string(
        raw_object.get("name"),
        field=f"{source_file}.knowledge_objects[{source_object_index}].name",
        code="invalid_ko_name",
    )
    ko_type = require_nonempty_string(
        raw_object.get("type"),
        field=f"{source_file}.knowledge_objects[{source_object_index}].type",
        code="invalid_ko_type",
    )
    if ko_type not in ALLOWED_KO_TYPES:
        raise NormalizationError(
            "invalid_ko_type",
            f"{source_file}.knowledge_objects[{source_object_index}].type "
            f"must be one of {sorted(ALLOWED_KO_TYPES)}.",
        )
    source_span = require_nonempty_string(
        raw_object.get("source_span"),
        field=f"{source_file}.knowledge_objects[{source_object_index}].source_span",
        code="invalid_source_span",
    )

    return {
        "lecture_id": lecture_id,
        "predicted_ko_id": predicted_ko_id,
        "name": name,
        "type": ko_type,
        "source_spans": [source_span],
        "provenance": {
            "source_prediction_id": predicted_ko_id,
            "source_file": source_file,
            "source_object_index": source_object_index,
        },
    }


def normalize_prediction_files(
    input_paths: list[Path],
    *,
    split: str | None = None,
) -> dict[str, Any]:
    if not input_paths:
        raise NormalizationError("missing_input", "At least one input is required.")

    loaded: list[tuple[str, Any, bytes]] = []
    seen_source_files: set[str] = set()
    for path in input_paths:
        source_file = display_path(path)
        if source_file in seen_source_files:
            raise NormalizationError(
                "duplicate_input_file", f"Input file repeated: {source_file}"
            )
        seen_source_files.add(source_file)
        data, raw_bytes = load_json_bytes(path)
        loaded.append((source_file, data, raw_bytes))
    loaded.sort(key=lambda item: item[0])

    input_files: list[dict[str, str]] = []
    normalized_objects: list[dict[str, Any]] = []
    source_splits: set[str] = set()
    seen_refs: set[tuple[str, str]] = set()

    for source_file, data, raw_bytes in loaded:
        input_files.append({
            "path": source_file,
            "sha256": sha256_bytes(raw_bytes),
        })
        extracted, source_split = extract_raw_objects(
            data,
            source_file=source_file,
        )
        if source_split is not None:
            source_splits.add(source_split)
        for lecture_id, source_object_index, raw_object in extracted:
            normalized = normalize_raw_object(
                raw_object,
                lecture_id=lecture_id,
                source_file=source_file,
                source_object_index=source_object_index,
            )
            ref = (lecture_id, normalized["predicted_ko_id"])
            if ref in seen_refs:
                raise NormalizationError(
                    "duplicate_predicted_ko_id",
                    f"Duplicate lecture-local predicted KO ID: {lecture_id}::{ref[1]}",
                )
            seen_refs.add(ref)
            normalized_objects.append(normalized)

    if len(source_splits) > 1:
        raise NormalizationError(
            "conflicting_split", f"Source artifacts declare splits: {sorted(source_splits)}"
        )
    if split is not None:
        split = require_nonempty_string(
            split,
            field="split",
            code="invalid_split",
        )
        if source_splits and split not in source_splits:
            raise NormalizationError(
                "conflicting_split",
                f"Requested split {split!r} conflicts with source split "
                f"{next(iter(source_splits))!r}.",
            )
        output_split = split
    else:
        output_split = next(iter(source_splits), "unspecified")

    normalized_objects.sort(
        key=lambda item: (item["lecture_id"], item["predicted_ko_id"])
    )
    return {
        "artifact_type": "predicted_ko_normalized_inventory",
        "version": "v0.1",
        "split": output_split,
        "structural_normalization_version": STRUCTURAL_NORMALIZATION_VERSION,
        "input_files": input_files,
        "input_set_sha256": sha256_json(input_files),
        "normalized_content_sha256": sha256_json(normalized_objects),
        "knowledge_objects": normalized_objects,
    }


def serialize_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


def write_output(path: Path, value: Any, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise NormalizationError(
            "output_exists",
            f"Output already exists: {path}. Use --overwrite or a new path.",
        )
    serialized = serialize_json(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        output_path = resolve_path(args.output)
        normalized = normalize_prediction_files(
            [resolve_path(path_text) for path_text in args.inputs],
            split=args.split,
        )
        write_output(output_path, normalized, overwrite=args.overwrite)
    except NormalizationError as exc:
        print(f"Normalization failed [{exc.code}]: {exc}", file=sys.stderr)
        return 2 if exc.code == "output_exists" else 1

    print(f"Wrote normalized predicted KOs to {display_path(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
