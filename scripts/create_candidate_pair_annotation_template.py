#!/usr/bin/env python3
"""Create an unlabelled annotation scaffold for a candidate pair universe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_candidate_pair_universe import (
    ROOT,
    CandidatePairUniverseError,
    display_path,
    serialize_json,
    sha256_file,
)


DEFAULT_UNIVERSE = (
    ROOT
    / "benchmark"
    / "candidate_pairs"
    / "development_v0_1"
    / "pair_universe.json"
)
DEFAULT_OUTPUT = (
    ROOT / "benchmark" / "ground_truth" / "candidate_pairs_development_v0_1.json"
)
DEFAULT_GUIDELINES = ROOT / "benchmark" / "candidate_pair_annotation_guidelines.md"
DEFAULT_EVALUATION_PROTOCOL = (
    ROOT / "benchmark" / "candidate_pair_generation_protocol.md"
)
DEFAULT_SUCCESS_CRITERIA = (
    ROOT / "benchmark" / "candidate_pair_generation_success_criteria_v0_1.json"
)
DEFAULT_RELATION_GUIDELINES = ROOT / "benchmark" / "relation_annotation_guidelines.md"
DEFAULT_PAIR_UNIVERSE_SCHEMA = (
    ROOT / "benchmark" / "schema" / "candidate_pair_universe.schema.json"
)
DEFAULT_GROUND_TRUTH_SCHEMA = (
    ROOT / "benchmark" / "schema" / "candidate_pair_ground_truth.schema.json"
)


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidatePairUniverseError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CandidatePairUniverseError(f"{label} must be a JSON object.")
    return data


def validate_universe_for_template(universe: dict[str, Any]) -> list[str]:
    if universe.get("artifact_type") != "candidate_pair_universe":
        raise CandidatePairUniverseError(
            "Pair universe artifact_type must be candidate_pair_universe."
        )
    pairs = universe.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise CandidatePairUniverseError("Pair universe pairs must be non-empty.")
    if universe.get("total_pair_count") != len(pairs):
        raise CandidatePairUniverseError(
            "Pair universe total_pair_count does not match pairs."
        )
    pair_ids: list[str] = []
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise CandidatePairUniverseError(f"pairs[{index}] must be an object.")
        pair_id = pair.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise CandidatePairUniverseError(f"pairs[{index}] has invalid pair_id.")
        pair_ids.append(pair_id)
    if len(pair_ids) != len(set(pair_ids)):
        raise CandidatePairUniverseError("Pair universe contains duplicate pair IDs.")
    return pair_ids


def document_binding(path: Path, *, version: str) -> dict[str, str]:
    if not path.is_file():
        raise CandidatePairUniverseError(f"Missing required document: {path}")
    return {
        "path": display_path(path),
        "version": version,
        "sha256": sha256_file(path),
    }


def build_annotation_template(
    universe: dict[str, Any],
    *,
    pair_universe_path: Path,
    guidelines_path: Path,
    evaluation_protocol_path: Path,
    success_criteria_path: Path,
    relation_guidelines_path: Path,
    pair_universe_schema_path: Path,
    ground_truth_schema_path: Path,
) -> dict[str, Any]:
    pair_ids = validate_universe_for_template(universe)
    return {
        "artifact_type": "candidate_pair_ground_truth",
        "version": "v0.1",
        "benchmark_split": universe.get("benchmark_split"),
        "status": "draft_annotation_required",
        "pair_universe": {
            "path": display_path(pair_universe_path),
            "sha256": sha256_file(pair_universe_path),
        },
        "source_inventory": universe.get("source_inventory"),
        "lecture_inventory": universe.get("lecture_inventory"),
        "annotation_guidelines": document_binding(
            guidelines_path, version="candidate_pair_annotation_v0.1"
        ),
        "relation_annotation_guidelines": document_binding(
            relation_guidelines_path, version="relation_annotation_v0.1"
        ),
        "evaluation_protocol": document_binding(
            evaluation_protocol_path, version="candidate_pair_evaluation_v0.1-draft"
        ),
        "success_criteria": document_binding(
            success_criteria_path, version="candidate_pair_success_criteria_v0.1"
        ),
        "schema_bindings": {
            "pair_universe": document_binding(
                pair_universe_schema_path, version="candidate_pair_universe_v0.1"
            ),
            "ground_truth": document_binding(
                ground_truth_schema_path, version="candidate_pair_ground_truth_v0.1"
            ),
        },
        "allowed_candidate_labels": [
            "IN_SCHEMA_RELATION",
            "NO_IN_SCHEMA_RELATION",
            "OUT_OF_SCHEMA_RELATION",
            "AMBIGUOUS",
        ],
        "allowed_relation_types": [
            "REQUIRES",
            "APPLIED_IN",
            "EXTENDS",
            "CONTRASTS_WITH",
            "FORMALIZES",
            "RELATED_TO",
        ],
        "primary_scoring_labels": [
            "IN_SCHEMA_RELATION",
            "NO_IN_SCHEMA_RELATION",
        ],
        "annotations": [
            {
                "pair_id": pair_id,
                "candidate_label": None,
                "annotation_status": "draft",
                "gold_relations": [],
                "out_of_schema_relation": None,
                "ambiguity": None,
                "negative_rationale": None,
                "annotation_source": None,
                "source_annotation": None,
                "notes": None,
            }
            for pair_id in pair_ids
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a separate draft annotation artifact for a pair universe."
    )
    parser.add_argument("--pair-universe", default=str(DEFAULT_UNIVERSE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--annotation-guidelines", default=str(DEFAULT_GUIDELINES))
    parser.add_argument("--evaluation-protocol", default=str(DEFAULT_EVALUATION_PROTOCOL))
    parser.add_argument("--success-criteria", default=str(DEFAULT_SUCCESS_CRITERIA))
    parser.add_argument(
        "--relation-annotation-guidelines", default=str(DEFAULT_RELATION_GUIDELINES)
    )
    parser.add_argument("--pair-universe-schema", default=str(DEFAULT_PAIR_UNIVERSE_SCHEMA))
    parser.add_argument("--ground-truth-schema", default=str(DEFAULT_GROUND_TRUTH_SCHEMA))
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing draft. Never use after annotation has begun.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe_path = resolve_path(args.pair_universe)
    output_path = resolve_path(args.output)
    guidelines_path = resolve_path(args.annotation_guidelines)
    evaluation_protocol_path = resolve_path(args.evaluation_protocol)
    success_criteria_path = resolve_path(args.success_criteria)
    relation_guidelines_path = resolve_path(args.relation_annotation_guidelines)
    pair_universe_schema_path = resolve_path(args.pair_universe_schema)
    ground_truth_schema_path = resolve_path(args.ground_truth_schema)
    try:
        if output_path.exists() and not args.overwrite:
            raise CandidatePairUniverseError(
                f"Refusing to overwrite existing artifact: {display_path(output_path)}."
            )
        universe = load_json_object(universe_path, label="pair universe")
        template = build_annotation_template(
            universe,
            pair_universe_path=universe_path,
            guidelines_path=guidelines_path,
            evaluation_protocol_path=evaluation_protocol_path,
            success_criteria_path=success_criteria_path,
            relation_guidelines_path=relation_guidelines_path,
            pair_universe_schema_path=pair_universe_schema_path,
            ground_truth_schema_path=ground_truth_schema_path,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialize_json(template), encoding="utf-8")
    except CandidatePairUniverseError as exc:
        print(f"Candidate annotation template creation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {len(template['annotations'])} draft annotations to "
        f"{display_path(output_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
