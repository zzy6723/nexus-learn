#!/usr/bin/env python3
"""Validate and freeze the complete 002C-2 authored challenge bundle."""

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

from scripts.check_ko_canonicalization_ground_truth import validate_bundle  # noqa: E402
from scripts.generate_candidate_pair_universe import display_path, sha256_file  # noqa: E402


DEFAULT_ROOT = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"
FINALIZER_VERSION = "ko_resolution_challenge_finalizer_v0.1"
REQUIRED_FILES = {
    "lecture_inventory": "lecture_inventory.json",
    "normalized_predicted_kos": "normalized_predicted_kos.json",
    "mention_inventory": "mention_inventory.json",
    "mention_inventory_completion_marker": "mention_inventory_complete.json",
    "ground_truth": "ground_truth.json",
    "ground_truth_completion_marker": "ground_truth_complete.json",
    "coverage_manifest": "coverage_manifest.json",
    "challenge_protocol": "challenge_protocol.md",
    "success_criteria": "success_criteria.json",
}


class ChallengeFinalizationError(ValueError):
    """Raised when challenge freeze requirements are not satisfied."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenge-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output", help="Defaults to CHALLENGE_ROOT/challenge_complete.json")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate an existing completion marker without writing artifacts.",
    )
    return parser.parse_args(argv)


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChallengeFinalizationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ChallengeFinalizationError(f"{label} must be a JSON object.")
    return value


def binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


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


def validate_semantic_coverage(
    inventory: dict[str, Any],
    ground_truth: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, int]:
    if coverage.get("artifact_type") != "ko_resolution_challenge_coverage":
        raise ChallengeFinalizationError("Coverage manifest artifact_type is invalid.")
    mentions = inventory["mentions"]
    mention_by_id = {item["mention_id"]: item for item in mentions}
    clusters = ground_truth["clusters"]
    cluster_by_id = {item["canonical_id"]: item for item in clusters}
    cluster_for_mention = {
        mention_id: cluster["canonical_id"]
        for cluster in clusters
        for mention_id in cluster["mention_ids"]
    }
    multi_cases = coverage.get("multi_mention_cases")
    hard_negatives = coverage.get("hard_negative_cases")
    if not isinstance(multi_cases, list) or not isinstance(hard_negatives, list):
        raise ChallengeFinalizationError("Coverage case lists are invalid.")
    case_names: set[str] = set()
    for case in multi_cases:
        if not isinstance(case, dict) or set(case) != {"case", "canonical_id"}:
            raise ChallengeFinalizationError("Multi-mention coverage case is malformed.")
        if case["case"] in case_names:
            raise ChallengeFinalizationError("Duplicate semantic coverage case name.")
        case_names.add(case["case"])
        cluster = cluster_by_id.get(case["canonical_id"])
        if cluster is None or len(cluster["mention_ids"]) < 2:
            raise ChallengeFinalizationError(
                f"Coverage case does not reference a multi-mention cluster: {case}."
            )
    for case in hard_negatives:
        if not isinstance(case, dict) or set(case) != {"case", "mention_ids"}:
            raise ChallengeFinalizationError("Hard-negative coverage case is malformed.")
        member_ids = case["mention_ids"]
        if not isinstance(member_ids, list) or len(member_ids) != 2:
            raise ChallengeFinalizationError("Hard-negative case requires two mentions.")
        if any(mention_id not in mention_by_id for mention_id in member_ids):
            raise ChallengeFinalizationError("Hard-negative case references unknown mention.")
        if cluster_for_mention[member_ids[0]] == cluster_for_mention[member_ids[1]]:
            raise ChallengeFinalizationError("Hard-negative mentions share a gold cluster.")
    required_cases = {
        "descriptive_alias",
        "qualified_name_alias",
        "abbreviation_and_orthography_three_mentions",
        "method_alias",
        "abbreviation",
        "symbol_and_natural_language_formula",
    }
    if case_names != required_cases:
        raise ChallengeFinalizationError("Multi-mention semantic coverage set is incomplete.")
    homonym = next(
        (case for case in hard_negatives if case["case"] == "same_name_same_type_different_referent"),
        None,
    )
    if homonym is None:
        raise ChallengeFinalizationError("Same-name homonym hard negative is missing.")
    left, right = [mention_by_id[item] for item in homonym["mention_ids"]]
    if left["name"] != right["name"] or left["type"] != right["type"]:
        raise ChallengeFinalizationError("Homonym hard negative is not same-name and same-type.")
    return {
        "multi_mention_coverage_cases": len(multi_cases),
        "hard_negative_coverage_cases": len(hard_negatives),
    }


def validate_completion_marker(
    marker: dict[str, Any],
    *,
    paths: dict[str, Path],
) -> None:
    if marker.get("artifact_type") != "ko_resolution_challenge_complete":
        raise ChallengeFinalizationError("Challenge marker artifact_type is invalid.")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        raise ChallengeFinalizationError("Challenge marker is not final v0.1.")
    if marker.get("data_role") != "authored_development_challenge":
        raise ChallengeFinalizationError("Challenge marker data_role is invalid.")
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(paths):
        raise ChallengeFinalizationError("Challenge marker artifact set is invalid.")
    for name, path in paths.items():
        expected = binding(path)
        if artifacts.get(name) != expected:
            raise ChallengeFinalizationError(
                f"Challenge marker has a stale binding for {name}."
            )
    expected_finalizer = {
        **binding(Path(__file__).resolve()),
        "version": FINALIZER_VERSION,
    }
    if marker.get("finalizer") != expected_finalizer:
        raise ChallengeFinalizationError("Challenge finalizer binding is stale.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    challenge_root = Path(args.challenge_root).resolve()
    output = Path(args.output).resolve() if args.output else challenge_root / "challenge_complete.json"
    try:
        paths = {name: challenge_root / filename for name, filename in REQUIRED_FILES.items()}
        missing = [name for name, path in paths.items() if not path.is_file()]
        if missing:
            raise ChallengeFinalizationError(f"Required challenge files are missing: {missing}.")
        if args.check:
            if args.overwrite:
                raise ChallengeFinalizationError("--check and --overwrite cannot be combined.")
            marker = load_json(output, label="challenge completion marker")
            validate_completion_marker(marker, paths=paths)
        elif output.exists() and not args.overwrite:
            raise ChallengeFinalizationError(f"Refusing to overwrite: {display_path(output)}")
        errors, summary = validate_bundle(
            inventory_path=paths["mention_inventory"],
            ground_truth_path=paths["ground_truth"],
            completion_marker_path=paths["ground_truth_completion_marker"],
            allow_draft=False,
            require_completion_marker=True,
        )
        if errors:
            raise ChallengeFinalizationError("Ground Truth bundle invalid: " + "; ".join(errors))
        inventory = load_json(paths["mention_inventory"], label="mention inventory")
        ground_truth = load_json(paths["ground_truth"], label="Ground Truth")
        coverage = load_json(paths["coverage_manifest"], label="coverage manifest")
        criteria = load_json(paths["success_criteria"], label="success criteria")
        if criteria.get("artifact_type") != "ko_context_resolution_success_criteria":
            raise ChallengeFinalizationError("Success criteria artifact_type is invalid.")
        coverage_counts = validate_semantic_coverage(inventory, ground_truth, coverage)
        expected_counts = {
            "mentions": 21,
            "canonical_clusters": 13,
            "singleton_clusters": 7,
            "multi_mention_clusters": 6,
            "same_object_pairs": 10,
            "distinct_object_pairs": 200,
        }
        if any(summary[key] != value for key, value in expected_counts.items()):
            raise ChallengeFinalizationError("Frozen challenge denominator mismatch.")
        if inventory["counts"]["exact_source_spans"] != 21:
            raise ChallengeFinalizationError("Challenge requires 21 exact source spans.")
        expected_marker_counts = {
            **expected_counts,
            **coverage_counts,
            "exact_source_spans": 21,
        }
        if args.check:
            if marker.get("counts") != expected_marker_counts:
                raise ChallengeFinalizationError("Challenge marker counts are stale.")
        else:
            marker = {
                "artifact_type": "ko_resolution_challenge_complete",
                "version": "v0.1",
                "status": "final",
                "data_role": "authored_development_challenge",
                "artifacts": {name: binding(path) for name, path in paths.items()},
                "finalizer": {
                    **binding(Path(__file__).resolve()),
                    "version": FINALIZER_VERSION,
                },
                "counts": expected_marker_counts,
            }
            atomic_write(output, marker)
    except ChallengeFinalizationError as exc:
        print(f"Challenge finalization failed: {exc}")
        return 1
    action = "Validated" if args.check else "Wrote final"
    print(f"{action} challenge marker: {display_path(output)}")
    print(json.dumps(marker["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
