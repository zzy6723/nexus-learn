#!/usr/bin/env python3
"""Materialize frozen 002C-5 canonical clusters from a reviewed plan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.create_ko_locked_reuse_ground_truth import (
    GroundTruthCreationError,
    atomic_write,
    build_ground_truth,
    display_path,
    load_json,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", required=True)
    parser.add_argument("--annotation-plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    plan_path = Path(args.annotation_plan).resolve()
    output_path = Path(args.output).resolve()
    try:
        if output_path.exists() and not args.overwrite:
            raise GroundTruthCreationError(f"Refusing to overwrite: {display_path(output_path)}")
        ground_truth = build_ground_truth(
            load_json(inventory_path, label="mention inventory"),
            load_json(plan_path, label="annotation plan"),
            inventory_path,
            expected_status="final_pre_independent_execution",
            expected_data_role="independent_canonicalization_validation",
            canonical_id_prefix="canonical_ko_holdout",
        )
        atomic_write(output_path, ground_truth)
    except GroundTruthCreationError as exc:
        print(f"Independent Ground Truth creation failed: {exc}")
        return 1
    print(f"Wrote {len(ground_truth['clusters'])} independent canonical clusters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
