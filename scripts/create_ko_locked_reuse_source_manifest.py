#!/usr/bin/env python3
"""Freeze the previously inspected predicted-KO source selected for 002C-3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_RUN = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_predicted_ko"
    / "runs"
    / "development_v0_1"
    / "run_03"
)
DEFAULT_OUTPUT = (
    ROOT
    / "benchmark"
    / "ko_canonicalization"
    / "locked_reuse_v0_1"
    / "source_manifest.json"
)
MANIFEST_VERSION = "ko_locked_reuse_source_manifest_v0.1"


class SourceManifestError(ValueError):
    """Raised when the selected source is incomplete or internally stale."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", default=str(DEFAULT_SOURCE_RUN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SourceManifestError(f"Missing required source artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceManifestError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SourceManifestError(f"{label} must be a JSON object.")
    return value


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
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def build_manifest(source_run: Path) -> dict[str, Any]:
    paths = {
        "execution_manifest": source_run / "execution_manifest.json",
        "lecture_inventory": source_run / "lecture_inventory.json",
        "normalized_predicted_kos": (
            source_run / "normalization" / "normalized_predicted_kos.json"
        ),
        "entity_source_bundle": (
            source_run / "entity_predictions" / "entity_source_bundle.json"
        ),
        "entity_predictions_completion_marker": (
            source_run / "entity_predictions" / "entity_predictions_complete.json"
        ),
    }
    documents = {
        name: load_json(path, label=name.replace("_", " "))
        for name, path in paths.items()
    }
    bundle = documents["entity_source_bundle"]
    completion = documents["entity_predictions_completion_marker"]
    execution = documents["execution_manifest"]
    normalized = documents["normalized_predicted_kos"]
    lecture_inventory = documents["lecture_inventory"]
    if bundle.get("status") != "final":
        raise SourceManifestError("Entity source bundle is not final.")
    if completion.get("status") != "final":
        raise SourceManifestError("Entity prediction completion marker is not final.")
    if completion.get("method_commit") != execution.get("method_commit"):
        raise SourceManifestError("Entity completion marker method commit is stale.")
    if completion.get("entity_source_bundle_sha256") != sha256_file(
        paths["entity_source_bundle"]
    ):
        raise SourceManifestError("Entity completion marker has a stale source-bundle hash.")
    if completion.get("execution_manifest_sha256") != sha256_file(
        paths["execution_manifest"]
    ):
        raise SourceManifestError("Entity completion marker has a stale execution hash.")
    if normalized.get("artifact_type") != "predicted_ko_normalized_inventory":
        raise SourceManifestError("Normalized predicted-KO artifact_type is invalid.")
    knowledge_objects = normalized.get("knowledge_objects")
    if not isinstance(knowledge_objects, list) or not knowledge_objects:
        raise SourceManifestError("Normalized predicted-KO inventory is empty.")
    input_files = normalized.get("input_files")
    if not isinstance(input_files, list):
        raise SourceManifestError("Normalized predicted-KO input bindings are missing.")
    expected_output_bindings = []
    for item in input_files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise SourceManifestError("A normalized input binding is malformed.")
        path = ROOT / item["path"]
        actual = binding(path)
        if actual != item:
            raise SourceManifestError(f"Stale normalized input binding: {item['path']}")
        expected_output_bindings.append(actual)
    lectures = bundle.get("lectures")
    if not isinstance(lectures, list) or len(lectures) != len(input_files):
        raise SourceManifestError("Entity lecture count does not match normalized inputs.")
    lecture_ids = [item.get("lecture_id") for item in lectures]
    if any(not isinstance(item, str) or not item for item in lecture_ids):
        raise SourceManifestError("Entity source bundle contains an invalid lecture ID.")
    if len(lecture_ids) != len(set(lecture_ids)):
        raise SourceManifestError("Entity source bundle contains duplicate lecture IDs.")
    inventory_ids = lecture_inventory.get("lecture_ids")
    if inventory_ids is None:
        inventory_rows = lecture_inventory.get("lectures", [])
        inventory_ids = [item.get("lecture_id") for item in inventory_rows]
    if set(inventory_ids) != set(lecture_ids):
        raise SourceManifestError("Lecture inventory and Entity source bundle disagree.")
    return {
        "artifact_type": "ko_canonicalization_locked_reuse_source_manifest",
        "version": "v0.1",
        "status": "final",
        "data_role": "locked_reuse",
        "claim_boundary": (
            "Previously inspected 002B-1 development Entity outputs; this source is "
            "not an unseen holdout."
        ),
        "selection_order": {
            "selected_before_context_resolver_execution": True,
            "selected_without_context_resolver_predictions": True,
        },
        "source_experiment": "002B-1",
        "source_run": display_path(source_run),
        "source_method_commit": completion["method_commit"],
        "artifacts": {name: binding(path) for name, path in paths.items()},
        "entity_output_artifacts": expected_output_bindings,
        "lecture_ids": lecture_ids,
        "counts": {
            "lectures": len(lecture_ids),
            "knowledge_object_mentions": len(knowledge_objects),
            "entity_outputs": len(expected_output_bindings),
        },
        "generator": {
            **binding(Path(__file__).resolve()),
            "version": MANIFEST_VERSION,
        },
    }


def validate_existing(manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    if manifest != expected:
        raise SourceManifestError("Locked-reuse source manifest is stale or changed.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_run = Path(args.source_run).resolve()
    output = Path(args.output).resolve()
    try:
        if args.check and args.overwrite:
            raise SourceManifestError("--check and --overwrite cannot be combined.")
        expected = build_manifest(source_run)
        if args.check:
            validate_existing(
                load_json(output, label="locked-reuse source manifest"), expected
            )
        else:
            if output.exists() and not args.overwrite:
                raise SourceManifestError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except SourceManifestError as exc:
        print(f"Locked-reuse source selection failed: {exc}")
        return 1
    action = "Validated" if args.check else "Wrote"
    print(f"{action} locked-reuse source manifest: {display_path(output)}")
    print(json.dumps(expected["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
