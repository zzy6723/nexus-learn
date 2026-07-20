#!/usr/bin/env python3
"""Validate and freeze the 002C-5 pre-execution artifact graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments/knowledge_object_resolution/002c_5_independent_validation"
BENCHMARK = ROOT / "benchmark/ko_canonicalization/independent_v0_1"
RUN_ROOT = BASE / "runs/independent_v0_1"
DEFAULT_OUTPUT = BASE / "preflight_complete.json"
VERSION = "ko_independent_preflight_finalizer_v0.1"


class IndependentPreflightError(ValueError):
    """Raised when the independent validation preflight is incomplete or stale."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise IndependentPreflightError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentPreflightError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise IndependentPreflightError(f"{label} must be a JSON object.")
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


def build_marker() -> dict[str, Any]:
    benchmark_path = BENCHMARK / "benchmark_complete.json"
    pipeline_path = BASE / "full_pipeline_manifest_v0_1.json"
    candidate_path = RUN_ROOT / "candidates/candidate_generation_complete.json"
    benchmark = load_json(benchmark_path, label="independent benchmark marker")
    pipeline = load_json(pipeline_path, label="full pipeline manifest")
    candidates = load_json(candidate_path, label="candidate completion marker")

    if benchmark.get("status") != "final" or benchmark.get("data_role") != "independent_canonicalization_validation":
        raise IndependentPreflightError("Independent benchmark is not final.")
    if pipeline.get("status") != "frozen_pre_independent_execution":
        raise IndependentPreflightError("Full pipeline manifest is not frozen.")
    if candidates.get("status") != "final":
        raise IndependentPreflightError("Candidate bundle is not final.")
    components = pipeline.get("components", {})
    if components.get("benchmark_completion") != binding(benchmark_path):
        raise IndependentPreflightError("Pipeline manifest binds a stale benchmark.")
    if components.get("candidate_completion") != binding(candidate_path):
        raise IndependentPreflightError("Pipeline manifest binds a stale candidate bundle.")
    if pipeline.get("pipeline_id") != "ko_canonicalization_pipeline_v0_2_1":
        raise IndependentPreflightError("Unexpected independent pipeline ID.")

    candidate_metadata_path = RUN_ROOT / "candidates/metadata.json"
    candidate_pairs_path = RUN_ROOT / "candidates/candidate_pairs.json"
    metadata = load_json(candidate_metadata_path, label="candidate metadata")
    pairs = load_json(candidate_pairs_path, label="candidate pairs")
    counts = metadata.get("counts", {})
    if (
        counts.get("mentions") != 39
        or counts.get("selected_candidates") != 7
        or counts.get("all_unordered_pairs") != 741
    ):
        raise IndependentPreflightError("Candidate denominator differs from the frozen plan.")
    candidate_rows = pairs.get("candidates")
    if not isinstance(candidate_rows, list) or len(candidate_rows) != 7:
        raise IndependentPreflightError("Candidate bundle must contain exactly seven pairs.")
    candidate_ids = [item.get("candidate_id") for item in candidate_rows]
    if len(set(candidate_ids)) != 7 or None in candidate_ids:
        raise IndependentPreflightError("Candidate IDs are invalid or duplicated.")

    prohibited_outputs = [
        RUN_ROOT / "context/run_01",
        RUN_ROOT / "clusters/run_01",
        RUN_ROOT / "evaluation/run_01",
        RUN_ROOT / "evidence_review/run_01",
    ]
    existing_outputs = [display_path(path) for path in prohibited_outputs if path.exists()]
    if existing_outputs:
        raise IndependentPreflightError(
            "Formal independent outputs already exist before preflight freeze: "
            + ", ".join(existing_outputs)
        )

    return {
        "artifact_type": "ko_independent_validation_preflight_complete",
        "version": "v0.1",
        "status": "frozen_pre_execution",
        "execution_scope": "002C-5 independent_v0_1",
        "model_run_started": False,
        "artifacts": {
            "benchmark_completion": binding(benchmark_path),
            "full_pipeline_manifest": binding(pipeline_path),
            "candidate_completion": binding(candidate_path),
            "candidate_pairs": binding(candidate_pairs_path),
            "candidate_metadata": binding(candidate_metadata_path),
        },
        "counts": {
            "lectures": 4,
            "mentions": 39,
            "all_unordered_pairs": 741,
            "selected_candidates": 7,
            "expected_same_object_candidates": 1,
            "expected_hard_negative_candidates": 6,
        },
        "execution_rules": {
            "method_changes_after_freeze": "forbidden",
            "manual_candidate_additions": "forbidden",
            "blind_evidence_review_before_metrics": True,
            "failure_reuses_source_as_independent": False,
        },
        "generator": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output).resolve()
    try:
        if args.check and args.overwrite:
            raise IndependentPreflightError("--check and --overwrite cannot be combined.")
        expected = build_marker()
        if args.check:
            if load_json(output, label="independent preflight marker") != expected:
                raise IndependentPreflightError("Independent preflight marker is stale.")
        else:
            if output.exists() and not args.overwrite:
                raise IndependentPreflightError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except IndependentPreflightError as exc:
        print(f"002C-5 preflight failed: {exc}")
        return 1
    print(f"{'Validated' if args.check else 'Wrote'} 002C-5 preflight: {display_path(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
