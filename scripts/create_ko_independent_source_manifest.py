#!/usr/bin/env python3
"""Freeze a pre-existing Entity bundle for 002C-5 independent validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.create_ko_locked_reuse_source_manifest import (
    SourceManifestError,
    atomic_write,
    binding,
    build_manifest,
    display_path,
    load_json,
)


DEFAULT_SOURCE_RUN = (
    ROOT
    / "experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_2/run_01"
)
DEFAULT_OUTPUT = (
    ROOT / "benchmark/ko_canonicalization/independent_v0_1/source_manifest.json"
)
VERSION = "ko_independent_source_manifest_v0.1"
FROZEN_METHOD_COMMIT = "46d5a2937f0a33a3c7eb157da8c8d58bd4451a14"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", default=str(DEFAULT_SOURCE_RUN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def build_independent_manifest(source_run: Path) -> dict:
    base = build_manifest(source_run)
    return {
        **base,
        "artifact_type": "ko_canonicalization_independent_source_manifest",
        "data_role": "independent_canonicalization_validation",
        "claim_boundary": (
            "Pre-existing 002B Relation holdout Entity outputs that were not consumed "
            "by 002C-0 through 002C-4. The lectures were previously inspected for "
            "Relation work, so this is independent with respect to canonicalization "
            "method development, not a universally unseen source."
        ),
        "selection_order": {
            "selected_after_v0_2_1_method_freeze": True,
            "selected_before_002c_5_ground_truth_freeze": True,
            "selected_before_002c_5_candidate_generation": True,
            "selected_before_002c_5_resolver_execution": True,
        },
        "canonicalization_independence": {
            "frozen_method_commit": FROZEN_METHOD_COMMIT,
            "consumed_by_002c_0_through_002c_4": False,
            "identity_ground_truth_previously_annotated": False,
            "context_resolver_previously_run_on_source": False,
            "method_changes_after_source_selection_allowed": False,
        },
        "source_experiment": "002B-1 locked_reuse_v0_2",
        "generator": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_run = Path(args.source_run).resolve()
    output = Path(args.output).resolve()
    try:
        if args.check and args.overwrite:
            raise SourceManifestError("--check and --overwrite cannot be combined.")
        expected = build_independent_manifest(source_run)
        if args.check:
            if load_json(output, label="independent source manifest") != expected:
                raise SourceManifestError("Independent source manifest is stale.")
        else:
            if output.exists() and not args.overwrite:
                raise SourceManifestError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except SourceManifestError as exc:
        print(f"Independent source selection failed: {exc}")
        return 1
    print(f"{'Validated' if args.check else 'Wrote'} independent source manifest: {display_path(output)}")
    print(json.dumps(expected["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
