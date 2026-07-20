#!/usr/bin/env python3
"""Validate and freeze the complete 002C-5 independent benchmark."""

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


DEFAULT_ROOT = ROOT / "benchmark/ko_canonicalization/independent_v0_1"
VERSION = "ko_independent_benchmark_finalizer_v0.1"
FROZEN_METHOD_COMMIT = "46d5a2937f0a33a3c7eb157da8c8d58bd4451a14"


class IndependentBenchmarkError(ValueError):
    """Raised when the independent benchmark is incomplete or stale."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise IndependentBenchmarkError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentBenchmarkError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise IndependentBenchmarkError(f"{label} must be a JSON object.")
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
    paths = {
        "source_manifest": root / "source_manifest.json",
        "mention_inventory": root / "mention_inventory.json",
        "mention_inventory_completion_marker": root / "mention_inventory_complete.json",
        "ground_truth_annotation_plan": root / "ground_truth_annotation_plan.json",
        "ground_truth": root / "ground_truth.json",
        "ground_truth_completion_marker": root / "ground_truth_complete.json",
        "success_criteria": root / "success_criteria.json",
        "annotation_guidelines": ROOT / "benchmark/ko_canonicalization_annotation_guidelines.md",
        "evaluation_protocol": ROOT / "benchmark/ko_canonicalization_protocol.md",
        "evidence_review_protocol": ROOT / "benchmark/ko_identity_evidence_review_protocol.md",
        "ground_truth_generator": ROOT / "scripts/create_ko_independent_ground_truth.py",
    }
    source = load_json(paths["source_manifest"], label="source manifest")
    if (
        source.get("status") != "final"
        or source.get("data_role") != "independent_canonicalization_validation"
        or source.get("canonicalization_independence", {}).get("frozen_method_commit")
        != FROZEN_METHOD_COMMIT
    ):
        raise IndependentBenchmarkError("Source independence declaration is invalid.")
    errors, counts = validate_bundle(
        inventory_path=paths["mention_inventory"],
        ground_truth_path=paths["ground_truth"],
        completion_marker_path=paths["ground_truth_completion_marker"],
        allow_draft=False,
        require_completion_marker=True,
    )
    if errors:
        raise IndependentBenchmarkError("Ground Truth invalid: " + "; ".join(errors))
    expected = {
        "mentions": 39,
        "canonical_clusters": 38,
        "singleton_clusters": 37,
        "multi_mention_clusters": 1,
        "same_object_pairs": 1,
        "distinct_object_pairs": 740,
    }
    if any(counts[key] != value for key, value in expected.items()):
        raise IndependentBenchmarkError("Independent benchmark denominator mismatch.")
    inventory = load_json(paths["mention_inventory"], label="mention inventory")
    if inventory.get("source_data_role") != "fresh_holdout":
        raise IndependentBenchmarkError("Mention inventory is not holdout-scoped.")
    if inventory["counts"]["exact_source_spans"] != 34 or inventory["counts"]["nonexact_source_spans"] != 5:
        raise IndependentBenchmarkError("Upstream grounding denominator mismatch.")
    plan = load_json(paths["ground_truth_annotation_plan"], label="annotation plan")
    if len(plan.get("reviewed_hard_negatives", [])) != 6:
        raise IndependentBenchmarkError("Hard-negative review denominator mismatch.")
    criteria = load_json(paths["success_criteria"], label="success criteria")
    if criteria.get("scope") != "002C-5 independent_v0_1":
        raise IndependentBenchmarkError("Success criteria scope is invalid.")
    lecture_binding = source["artifacts"]["lecture_inventory"]
    lecture_path = ROOT / lecture_binding["path"]
    if binding(lecture_path) != lecture_binding:
        raise IndependentBenchmarkError("Source lecture inventory is stale.")
    return {
        "artifact_type": "ko_canonicalization_independent_benchmark_complete",
        "version": "v0.1",
        "status": "final",
        "data_role": "independent_canonicalization_validation",
        "frozen_method_commit": FROZEN_METHOD_COMMIT,
        "claim_boundary": (
            "Independent locked reuse relative to 002C method development; one "
            "positive identity pair limits recall and generalization claims."
        ),
        "artifacts": {name: binding(path) for name, path in paths.items()},
        "lecture_inventory": lecture_binding,
        "counts": {
            **expected,
            "lectures": 4,
            "resolver_expected_positive_candidates": 1,
            "resolver_expected_hard_negatives": 6,
            "exact_source_spans": 34,
            "nonexact_source_spans": 5,
        },
        "finalizer": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.benchmark_root).resolve()
    output = Path(args.output).resolve() if args.output else root / "benchmark_complete.json"
    try:
        if args.check and args.overwrite:
            raise IndependentBenchmarkError("--check and --overwrite cannot be combined.")
        expected = build_marker(root)
        if args.check:
            if load_json(output, label="benchmark marker") != expected:
                raise IndependentBenchmarkError("Independent benchmark marker is stale.")
        else:
            if output.exists() and not args.overwrite:
                raise IndependentBenchmarkError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except IndependentBenchmarkError as exc:
        print(f"Independent benchmark finalization failed: {exc}")
        return 1
    print(f"{'Validated' if args.check else 'Wrote'} independent benchmark marker.")
    print(json.dumps(expected["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
