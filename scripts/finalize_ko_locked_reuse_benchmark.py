#!/usr/bin/env python3
"""Validate and freeze the complete 002C-3 locked-reuse benchmark."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ko_canonicalization_ground_truth import validate_bundle
from scripts.generate_candidate_pair_universe import display_path, sha256_file


DEFAULT_ROOT = ROOT / "benchmark" / "ko_canonicalization" / "locked_reuse_v0_1"
VERSION = "ko_locked_reuse_benchmark_finalizer_v0.1"


class LockedReuseBenchmarkError(ValueError):
    """Raised when the locked-reuse benchmark is incomplete or stale."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise LockedReuseBenchmarkError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LockedReuseBenchmarkError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise LockedReuseBenchmarkError(f"{label} must be a JSON object.")
    return value


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def build_marker(root: Path) -> dict[str, Any]:
    source_manifest_path = root / "source_manifest.json"
    source_manifest = load_json(source_manifest_path, label="source manifest")
    if source_manifest.get("status") != "final" or source_manifest.get("data_role") != "locked_reuse":
        raise LockedReuseBenchmarkError("Source selection is not final locked reuse.")
    artifacts = {
        "source_manifest": source_manifest_path,
        "mention_inventory": root / "mention_inventory.json",
        "mention_inventory_completion_marker": root / "mention_inventory_complete.json",
        "ground_truth_annotation_plan": root / "ground_truth_annotation_plan.json",
        "ground_truth": root / "ground_truth.json",
        "ground_truth_completion_marker": root / "ground_truth_complete.json",
        "success_criteria": root / "success_criteria.json",
        "ground_truth_generator": ROOT / "scripts" / "create_ko_locked_reuse_ground_truth.py",
    }
    errors, counts = validate_bundle(
        inventory_path=artifacts["mention_inventory"],
        ground_truth_path=artifacts["ground_truth"],
        completion_marker_path=artifacts["ground_truth_completion_marker"],
        allow_draft=False,
        require_completion_marker=True,
    )
    if errors:
        raise LockedReuseBenchmarkError("Ground Truth invalid: " + "; ".join(errors))
    expected_counts = {
        "mentions": 49, "canonical_clusters": 46, "singleton_clusters": 44,
        "multi_mention_clusters": 2, "same_object_pairs": 4,
        "distinct_object_pairs": 1172,
    }
    if any(counts[key] != value for key, value in expected_counts.items()):
        raise LockedReuseBenchmarkError("Locked-reuse denominator mismatch.")
    inventory = load_json(artifacts["mention_inventory"], label="mention inventory")
    if inventory["counts"]["exact_source_spans"] != 35 or inventory["counts"]["nonexact_source_spans"] != 14:
        raise LockedReuseBenchmarkError("Upstream source-grounding denominator mismatch.")
    criteria = load_json(artifacts["success_criteria"], label="success criteria")
    if criteria.get("scope") != "002C-3 locked_reuse_v0_1":
        raise LockedReuseBenchmarkError("Success criteria scope is invalid.")
    lecture_binding = source_manifest["artifacts"]["lecture_inventory"]
    lecture_path = ROOT / lecture_binding["path"]
    if binding(lecture_path) != lecture_binding:
        raise LockedReuseBenchmarkError("Selected lecture inventory is stale.")
    return {
        "artifact_type": "ko_canonicalization_locked_reuse_benchmark_complete",
        "version": "v0.1", "status": "final", "data_role": "locked_reuse",
        "claim_boundary": "Previously inspected 002B-1 development outputs; not unseen evidence.",
        "artifacts": {name: binding(path) for name, path in artifacts.items()},
        "lecture_inventory": lecture_binding,
        "counts": {**expected_counts, "lectures": 6, "exact_source_spans": 35, "nonexact_source_spans": 14},
        "finalizer": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.benchmark_root).resolve()
    output = Path(args.output).resolve() if args.output else root / "benchmark_complete.json"
    try:
        if args.check and args.overwrite:
            raise LockedReuseBenchmarkError("--check and --overwrite cannot be combined.")
        expected = build_marker(root)
        if args.check:
            if load_json(output, label="benchmark marker") != expected:
                raise LockedReuseBenchmarkError("Locked-reuse benchmark marker is stale.")
        else:
            if output.exists() and not args.overwrite:
                raise LockedReuseBenchmarkError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except LockedReuseBenchmarkError as exc:
        print(f"Locked-reuse benchmark finalization failed: {exc}")
        return 1
    print(f"{'Validated' if args.check else 'Wrote'} locked-reuse benchmark marker.")
    print(json.dumps(expected["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
