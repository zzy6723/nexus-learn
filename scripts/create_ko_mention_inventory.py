#!/usr/bin/env python3
"""Create a deterministic provenance-preserving KO mention inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_candidate_pair_universe import (  # noqa: E402
    CandidatePairUniverseError,
    display_path,
    sha256_file,
    validate_inventory,
    validate_lecture_inventory,
)


DEFAULT_SOURCE_INVENTORY = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_predicted_ko"
    / "runs"
    / "locked_reuse_v0_2"
    / "run_01"
    / "normalization"
    / "normalized_predicted_kos.json"
)
DEFAULT_LECTURE_INVENTORY = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_predicted_ko"
    / "runs"
    / "locked_reuse_v0_2"
    / "run_01"
    / "lecture_inventory.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "benchmark"
    / "ko_mentions"
    / "development_v0_1"
    / "mention_inventory.json"
)
DEFAULT_MARKER = DEFAULT_OUTPUT.with_name("mention_inventory_complete.json")
DEFAULT_SCHEMA = ROOT / "benchmark" / "schema" / "ko_mention_inventory.schema.json"
MENTION_PREFIX = {"development": "ko_mention_dev", "holdout": "ko_mention_holdout"}
GENERATOR_VERSION = "ko_mention_inventory_generator_v0.1"
PROVENANCE_KEYS = {
    "source_prediction_id",
    "source_file",
    "source_object_index",
}


class MentionInventoryError(RuntimeError):
    """A fatal source or output-contract error."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-inventory",
        default=str(DEFAULT_SOURCE_INVENTORY),
        help="Normalized predicted-KO inventory.",
    )
    parser.add_argument(
        "--lecture-inventory",
        default=str(DEFAULT_LECTURE_INVENTORY),
        help="Hash-bound lecture inventory with model text.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Mention inventory output path.",
    )
    parser.add_argument(
        "--completion-marker",
        default=str(DEFAULT_MARKER),
        help="Completion marker output path.",
    )
    parser.add_argument(
        "--benchmark-split",
        choices=sorted(MENTION_PREFIX),
        default="development",
    )
    parser.add_argument(
        "--source-data-role",
        choices=["development_reuse", "fresh_holdout"],
        default="development_reuse",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MentionInventoryError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MentionInventoryError(f"{label} must be a JSON object.")
    return value


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def atomic_write(path: Path, value: Any) -> None:
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
        ) as handle:
            handle.write(serialize_json(value))
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def validate_source_file_bindings(source: dict[str, Any]) -> dict[str, str]:
    input_files = source.get("input_files")
    if not isinstance(input_files, list) or not input_files:
        raise MentionInventoryError("Source inventory requires non-empty input_files.")
    bindings: dict[str, str] = {}
    for index, item in enumerate(input_files):
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise MentionInventoryError(
                f"input_files[{index}] must contain exactly path and sha256."
            )
        path_text = item.get("path")
        expected_hash = item.get("sha256")
        if not isinstance(path_text, str) or not path_text:
            raise MentionInventoryError(f"input_files[{index}].path is invalid.")
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            raise MentionInventoryError(f"Bound prediction file is missing: {path_text}.")
        if sha256_file(path) != expected_hash:
            raise MentionInventoryError(f"Stale prediction file binding: {path_text}.")
        if path_text in bindings:
            raise MentionInventoryError(f"Duplicate prediction file binding: {path_text}.")
        bindings[path_text] = expected_hash
    return bindings


def lecture_texts(lecture_inventory: dict[str, Any]) -> dict[str, str]:
    lectures = lecture_inventory.get("lectures")
    if not isinstance(lectures, list):
        raise MentionInventoryError("Lecture inventory requires a lectures list.")
    result: dict[str, str] = {}
    for index, item in enumerate(lectures):
        if not isinstance(item, dict):
            raise MentionInventoryError(f"lectures[{index}] must be an object.")
        lecture_id = item.get("lecture_id")
        text = item.get("text")
        if not isinstance(lecture_id, str) or not lecture_id:
            raise MentionInventoryError(f"lectures[{index}].lecture_id is invalid.")
        if not isinstance(text, str) or not text:
            raise MentionInventoryError(f"lectures[{index}].text is invalid.")
        if lecture_id in result:
            raise MentionInventoryError(f"Duplicate lecture text: {lecture_id}.")
        result[lecture_id] = text
    return result


def build_mention_inventory(
    source: dict[str, Any],
    *,
    source_path: Path,
    lecture_inventory: dict[str, Any],
    lecture_inventory_path: Path,
    benchmark_split: str,
    source_data_role: str,
) -> dict[str, Any]:
    if benchmark_split not in MENTION_PREFIX:
        raise MentionInventoryError(f"Unsupported benchmark split: {benchmark_split}.")
    source_split = source.get("split")
    if source_data_role == "development_reuse" and benchmark_split != "development":
        raise MentionInventoryError(
            "development_reuse requires benchmark_split = development."
        )
    if source_data_role == "fresh_holdout" and (
        benchmark_split != "holdout" or source_split != "holdout"
    ):
        raise MentionInventoryError(
            "fresh_holdout requires both source and benchmark split = holdout."
        )

    try:
        objects = validate_inventory(source)
        expected_lectures = {item["lecture_id"] for item in objects}
        validate_lecture_inventory(
            lecture_inventory,
            expected_lecture_ids=expected_lectures,
        )
    except CandidatePairUniverseError as exc:
        raise MentionInventoryError(str(exc)) from exc

    bound_source_files = validate_source_file_bindings(source)
    texts = lecture_texts(lecture_inventory)

    indexed_objects = sorted(
        enumerate(objects),
        key=lambda pair: (pair[1]["lecture_id"], pair[1]["predicted_ko_id"]),
    )
    prefix = MENTION_PREFIX[benchmark_split]
    mentions: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    exact_flags: list[bool] = []

    for mention_number, (source_index, item) in enumerate(indexed_objects, start=1):
        provenance = item.get("provenance")
        if not isinstance(provenance, dict) or set(provenance) != PROVENANCE_KEYS:
            raise MentionInventoryError(
                f"knowledge_objects[{source_index}].provenance has invalid keys."
            )
        if provenance.get("source_prediction_id") != item["predicted_ko_id"]:
            raise MentionInventoryError(
                f"knowledge_objects[{source_index}] source_prediction_id mismatch."
            )
        source_file = provenance.get("source_file")
        if source_file not in bound_source_files:
            raise MentionInventoryError(
                f"knowledge_objects[{source_index}] references an unbound source file."
            )
        source_object_index = provenance.get("source_object_index")
        if not isinstance(source_object_index, int) or source_object_index < 0:
            raise MentionInventoryError(
                f"knowledge_objects[{source_index}] has invalid source_object_index."
            )

        flags = [span in texts[item["lecture_id"]] for span in item["source_spans"]]
        exact_flags.extend(flags)
        type_counts[item["type"]] += 1
        mentions.append(
            {
                "mention_id": f"{prefix}_{mention_number:03d}",
                "source_inventory_index": source_index,
                "lecture_id": item["lecture_id"],
                "predicted_ko_id": item["predicted_ko_id"],
                "name": item["name"],
                "type": item["type"],
                "source_spans": list(item["source_spans"]),
                "source_span_exact_flags": flags,
                "provenance": dict(provenance),
            }
        )

    return {
        "artifact_type": "ko_mention_inventory",
        "version": "v0.1",
        "benchmark_split": benchmark_split,
        "source_data_role": source_data_role,
        "mention_order": "ascending_lecture_then_predicted_ko_id",
        "source_inventory": {
            "path": display_path(source_path),
            "sha256": sha256_file(source_path),
            "normalized_content_sha256": source["normalized_content_sha256"],
            "source_declared_split": source_split,
            "structural_normalization_version": source.get(
                "structural_normalization_version"
            ),
        },
        "lecture_inventory": {
            "path": display_path(lecture_inventory_path),
            "sha256": sha256_file(lecture_inventory_path),
        },
        "counts": {
            "lectures": len(expected_lectures),
            "mentions": len(mentions),
            "source_spans": len(exact_flags),
            "exact_source_spans": sum(exact_flags),
            "nonexact_source_spans": sum(not value for value in exact_flags),
            "types": {
                "Concept": type_counts["Concept"],
                "Method": type_counts["Method"],
                "Formula": type_counts["Formula"],
            },
        },
        "mentions": mentions,
    }


def build_completion_marker(
    *,
    output_path: Path,
    source_path: Path,
    lecture_inventory_path: Path,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    generator_path = Path(__file__).resolve()
    return {
        "artifact_type": "ko_mention_inventory_complete",
        "version": "v0.1",
        "status": "final",
        "mention_inventory": {
            "path": display_path(output_path),
            "sha256": sha256_file(output_path),
        },
        "source_inventory": {
            "path": display_path(source_path),
            "sha256": sha256_file(source_path),
        },
        "lecture_inventory": {
            "path": display_path(lecture_inventory_path),
            "sha256": sha256_file(lecture_inventory_path),
        },
        "schema": {
            "path": display_path(DEFAULT_SCHEMA),
            "sha256": sha256_file(DEFAULT_SCHEMA),
        },
        "generator": {
            "path": display_path(generator_path),
            "sha256": sha256_file(generator_path),
            "version": GENERATOR_VERSION,
        },
        "counts": inventory["counts"],
    }


def write_outputs(
    *,
    output_path: Path,
    marker_path: Path,
    inventory: dict[str, Any],
    source_path: Path,
    lecture_inventory_path: Path,
    overwrite: bool,
) -> None:
    existing = [path for path in (output_path, marker_path) if path.exists()]
    if existing and not overwrite:
        rendered = ", ".join(display_path(path) for path in existing)
        raise MentionInventoryError(f"Refusing to overwrite: {rendered}.")

    atomic_write(output_path, inventory)
    marker = build_completion_marker(
        output_path=output_path,
        source_path=source_path,
        lecture_inventory_path=lecture_inventory_path,
        inventory=inventory,
    )
    atomic_write(marker_path, marker)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_path = Path(args.source_inventory).resolve()
    lecture_inventory_path = Path(args.lecture_inventory).resolve()
    output_path = Path(args.output).resolve()
    marker_path = Path(args.completion_marker).resolve()
    try:
        source = load_json_object(source_path, label="source inventory")
        lecture_inventory = load_json_object(
            lecture_inventory_path,
            label="lecture inventory",
        )
        inventory = build_mention_inventory(
            source,
            source_path=source_path,
            lecture_inventory=lecture_inventory,
            lecture_inventory_path=lecture_inventory_path,
            benchmark_split=args.benchmark_split,
            source_data_role=args.source_data_role,
        )
        write_outputs(
            output_path=output_path,
            marker_path=marker_path,
            inventory=inventory,
            source_path=source_path,
            lecture_inventory_path=lecture_inventory_path,
            overwrite=args.overwrite,
        )
    except MentionInventoryError as exc:
        print(f"Mention inventory generation failed: {exc}")
        return 1

    print(f"Wrote {len(inventory['mentions'])} KO mentions to {display_path(output_path)}")
    print(f"Completion marker: {display_path(marker_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
