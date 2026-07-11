#!/usr/bin/env python3
"""Check whether extracted source spans are exact substrings of benchmark inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LECTURE_DIR = ROOT / "benchmark" / "lectures" / "development"
ENTITY_EXTRACTION_DIR = ROOT / "experiments" / "entity_extraction"


LECTURE_FILES = {
    "calculus_001": LECTURE_DIR / "calculus_001.md",
    "linear_algebra_001": LECTURE_DIR / "linear_algebra_001.md",
    "optimisation_001": LECTURE_DIR / "optimisation_001.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check exact source-span grounding for an entity extraction experiment."
    )
    parser.add_argument(
        "--experiment",
        default="002_prompt_refinement",
        help="Experiment directory under experiments/entity_extraction/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = ENTITY_EXTRACTION_DIR / args.experiment / "output"

    total = 0
    exact = 0

    for lecture_id, lecture_path in LECTURE_FILES.items():
        output_path = output_dir / f"{lecture_id}.json"
        if not output_path.exists():
            continue

        lecture_text = lecture_path.read_text(encoding="utf-8")
        output = json.loads(output_path.read_text(encoding="utf-8"))

        print(lecture_id)
        for obj in output.get("knowledge_objects", []):
            total += 1
            span = obj.get("source_span", "")
            ok = span in lecture_text
            exact += int(ok)
            status = "OK" if ok else "NO"
            print(f"  {status}  {obj.get('id')}: {span[:80]}")

    print(f"\nExact source spans: {exact}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
