#!/usr/bin/env python3
"""Generate deterministic canonical Connection candidate selections."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "benchmark" / "connection_discovery" / "development_v0_1"
DEFAULT_PAIR_UNIVERSE = DEFAULT_BENCHMARK / "pair_universe.json"
DEFAULT_INVENTORY = DEFAULT_BENCHMARK / "oracle_canonical_inventory.json"
DEFAULT_SOURCE_MANIFEST = DEFAULT_BENCHMARK / "source_manifest.json"
DEFAULT_FREEZE_MANIFEST = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_0_benchmark_preparation"
    / "benchmark_freeze_manifest_v0_1.json"
)
SELECTION_FILENAME = "candidate_selection.json"
METADATA_FILENAME = "metadata.json"
COMPLETION_FILENAME = "generation_complete.json"
GENERATOR_VERSION = "connection_candidate_generator_v0.1"
METHODS = (
    "all_pairs",
    "overlap_bridge",
    "lexical_only",
    "hybrid_provenance_lexical",
)
FORBIDDEN_GOLD_FIELDS = {
    "category",
    "primary_scoring_eligible",
    "gold_edge",
    "acceptable_alternatives",
    "evidence",
    "evidence_support_scope",
    "rationale",
    "annotation_origin",
    "schema_gap_relation",
    "relation_type",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_TOKENS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "their", "this",
    "to", "uses", "using", "with",
}


class CandidateGenerationError(ValueError):
    """Raised when a candidate run violates its artifact contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=False) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CandidateGenerationError(f"Missing required file: {display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise CandidateGenerationError(
            f"Invalid JSON in {display_path(path)}: {exc}"
        ) from exc


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def _iter_bindings(value: Any):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            yield value
        else:
            for item in value.values():
                yield from _iter_bindings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_bindings(item)


def validate_freeze_manifest(
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    pair_universe_path: Path,
    inventory_path: Path,
    source_manifest_path: Path,
) -> None:
    errors: list[str] = []
    if manifest.get("artifact_type") != "connection_discovery_benchmark_freeze_manifest":
        errors.append("freeze_manifest.artifact_type is invalid")
    if manifest.get("version") != "v0.1":
        errors.append("freeze_manifest.version is invalid")
    if manifest.get("status") != "frozen_content_binding":
        errors.append("freeze_manifest.status is not frozen_content_binding")
    commit = manifest.get("benchmark_content_commit")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        errors.append("freeze_manifest.benchmark_content_commit is invalid")

    frozen = manifest.get("frozen_artifacts")
    if not isinstance(frozen, dict):
        errors.append("freeze_manifest.frozen_artifacts is invalid")
        frozen = {}
    expected_paths = {
        "pair_universe": pair_universe_path,
        "oracle_canonical_inventory": inventory_path,
        "source_manifest": source_manifest_path,
    }
    for key, expected_path in expected_paths.items():
        item = frozen.get(key)
        if not isinstance(item, dict):
            errors.append(f"freeze_manifest.frozen_artifacts.{key} is missing")
            continue
        bound_path = resolve_path(item.get("path", ""))
        if bound_path.resolve() != expected_path.resolve():
            errors.append(f"freeze_manifest.frozen_artifacts.{key}.path mismatch")
        elif not bound_path.is_file() or item.get("sha256") != sha256_file(bound_path):
            errors.append(f"freeze_manifest.frozen_artifacts.{key} binding is stale")

    for item in _iter_bindings({"completion": manifest.get("completion"), "frozen": frozen}):
        path = resolve_path(item["path"])
        if not path.is_file():
            errors.append(f"freeze binding is missing: {display_path(path)}")
        elif sha256_file(path) != item["sha256"]:
            errors.append(f"freeze binding is stale: {display_path(path)}")
    if not manifest_path.is_file():
        errors.append("freeze manifest file is missing")
    if errors:
        raise CandidateGenerationError("; ".join(sorted(set(errors))))


def _collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_collect_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_collect_keys(item))
        return result
    return set()


def validate_inputs(
    pair_universe: dict[str, Any],
    inventory: dict[str, Any],
    source_manifest: dict[str, Any],
) -> None:
    errors: list[str] = []
    if pair_universe.get("artifact_type") != "canonical_connection_pair_universe":
        errors.append("pair_universe.artifact_type is invalid")
    if pair_universe.get("gold_fields_present") is not False:
        errors.append("pair_universe.gold_fields_present must be false")
    if (
        inventory.get("artifact_type")
        != "connection_discovery_oracle_canonical_inventory"
    ):
        errors.append("inventory.artifact_type is invalid")
    if source_manifest.get("artifact_type") != "connection_discovery_source_manifest":
        errors.append("source_manifest.artifact_type is invalid")
    leaked = sorted(
        (_collect_keys(pair_universe) | _collect_keys(inventory) | _collect_keys(source_manifest))
        & FORBIDDEN_GOLD_FIELDS
    )
    if leaked:
        errors.append(f"gold leakage fields present: {leaked}")

    objects = inventory.get("canonical_objects")
    pairs = pair_universe.get("pairs")
    if not isinstance(objects, list) or not objects:
        errors.append("inventory.canonical_objects must be a non-empty list")
        objects = []
    if not isinstance(pairs, list) or not pairs:
        errors.append("pair_universe.pairs must be a non-empty list")
        pairs = []
    object_ids = [item.get("canonical_ko_id") for item in objects]
    if len(object_ids) != len(set(object_ids)):
        errors.append("inventory contains duplicate canonical KO IDs")
    pair_ids = [item.get("canonical_pair_id") for item in pairs]
    if len(pair_ids) != len(set(pair_ids)):
        errors.append("pair universe contains duplicate pair IDs")
    for pair in pairs:
        a = pair.get("ko_a", {}).get("canonical_ko_id")
        b = pair.get("ko_b", {}).get("canonical_ko_id")
        if a == b:
            errors.append(f"self pair is forbidden: {pair.get('canonical_pair_id')}")
        if a not in object_ids or b not in object_ids:
            errors.append(f"unknown endpoint: {pair.get('canonical_pair_id')}")
    if errors:
        raise CandidateGenerationError("; ".join(errors))


def tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOP_TOKENS}


def object_tokens(item: dict[str, Any]) -> set[str]:
    values = [item["canonical_name"], *item.get("aliases", [])]
    for mention in item["mentions"]:
        values.extend(mention["source_spans"])
    return tokens(" ".join(values))


def inverse_document_frequency(objects: list[dict[str, Any]]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for item in objects:
        document_frequency.update(object_tokens(item))
    count = len(objects)
    return {
        token: math.log((count + 1) / (frequency + 1)) + 1
        for token, frequency in document_frequency.items()
    }


def lexical_score(
    pair: dict[str, Any],
    *,
    object_map: dict[str, dict[str, Any]],
    idf: dict[str, float],
) -> tuple[float, dict[str, Any]]:
    object_a = object_map[pair["ko_a"]["canonical_ko_id"]]
    object_b = object_map[pair["ko_b"]["canonical_ko_id"]]
    tokens_a = object_tokens(object_a)
    tokens_b = object_tokens(object_b)
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    weighted_intersection = sum(idf.get(token, 0.0) for token in intersection)
    weighted_union = sum(idf.get(token, 0.0) for token in union)
    weighted_jaccard = weighted_intersection / weighted_union if weighted_union else 0.0
    shared_lectures = sorted(
        set(pair["ko_a"]["lecture_ids"]) & set(pair["ko_b"]["lecture_ids"])
    )
    same_type = object_a["canonical_type"] == object_b["canonical_type"]
    type_diversity_bonus = 0.03 if not same_type else 0.0
    score = weighted_jaccard + type_diversity_bonus
    return score, {
        "shared_lecture_count": len(shared_lectures),
        "shared_lectures": shared_lectures,
        "shared_tokens": sorted(intersection),
        "weighted_jaccard": round(weighted_jaccard, 12),
        "type_diversity_bonus": type_diversity_bonus,
    }


def build_selection(
    *,
    method: str,
    pair_universe: dict[str, Any],
    inventory: dict[str, Any],
    retention_fraction: float,
    inputs: dict[str, dict[str, str]],
) -> dict[str, Any]:
    if method not in METHODS:
        raise CandidateGenerationError(f"Unsupported method: {method}")
    pairs = pair_universe["pairs"]
    object_map = {
        item["canonical_ko_id"]: item for item in inventory["canonical_objects"]
    }
    idf = inverse_document_frequency(inventory["canonical_objects"])
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for pair in pairs:
        if method == "all_pairs":
            score = 1.0
            features = {"control": "all_eligible_pairs"}
        elif method == "overlap_bridge":
            score = 1.0 if pair["provenance_stratum"] == "overlap_bridge" else 0.0
            features = {"provenance_stratum": pair["provenance_stratum"]}
        else:
            score, features = lexical_score(pair, object_map=object_map, idf=idf)
            if method == "hybrid_provenance_lexical":
                score += 1.0 if features["shared_lecture_count"] else 0.0
        ranked.append((score, pair["canonical_pair_id"], {**pair, "score": score, "features": features}))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    if method == "all_pairs":
        selected_count = len(ranked)
    elif method == "overlap_bridge":
        selected_count = sum(score > 0 for score, _, _ in ranked)
    else:
        if not 0 < retention_fraction <= 1:
            raise CandidateGenerationError("retention_fraction must be in (0, 1]")
        selected_count = math.floor(len(ranked) * retention_fraction)
        if selected_count == 0:
            selected_count = 1

    selected = []
    for rank, (_, _, pair) in enumerate(ranked[:selected_count], start=1):
        selected.append({**pair, "rank": rank})
    config = {
        "method": method,
        "retention_fraction": (
            retention_fraction
            if method in {"lexical_only", "hybrid_provenance_lexical"}
            else None
        ),
        "tie_breaker": "canonical_pair_id_ascending",
        "lexical_normalization": "lowercase_alphanumeric_stop_tokens_idf_weighted_jaccard_v0.1",
    }
    return {
        "artifact_type": "connection_candidate_selection",
        "version": "v0.1",
        "status": "final",
        "split": pair_universe["split"],
        "method": {
            "id": f"{method}_v0.1",
            "name": method,
            "generator_version": GENERATOR_VERSION,
            "config": config,
            "config_sha256": sha256_json(config),
        },
        "inputs": inputs,
        "universe_pair_count": len(pairs),
        "selected_pair_count": len(selected),
        "selected_pairs": selected,
    }


def validate_selection(
    selection: dict[str, Any], pair_universe: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    expected_top_keys = {
        "artifact_type",
        "version",
        "status",
        "split",
        "method",
        "inputs",
        "universe_pair_count",
        "selected_pair_count",
        "selected_pairs",
    }
    if set(selection) != expected_top_keys:
        errors.append("selection top-level field set mismatch")
    if selection.get("artifact_type") != "connection_candidate_selection":
        errors.append("selection artifact_type is invalid")
    if selection.get("version") != "v0.1" or selection.get("status") != "final":
        errors.append("selection must be final v0.1")
    universe_by_id = {
        item["canonical_pair_id"]: item for item in pair_universe["pairs"]
    }
    selected = selection.get("selected_pairs")
    if not isinstance(selected, list):
        return ["selected_pairs must be a list"]
    ids = [item.get("canonical_pair_id") for item in selected]
    if len(ids) != len(set(ids)):
        errors.append("duplicate selected pair IDs")
    for rank, item in enumerate(selected, start=1):
        pair_id = item.get("canonical_pair_id")
        expected = universe_by_id.get(pair_id)
        if expected is None:
            errors.append(f"unknown selected pair: {pair_id}")
            continue
        expected_fields = set(expected) | {"score", "features", "rank"}
        if set(item) != expected_fields:
            errors.append(f"selected pair {pair_id} field set mismatch")
        for field in ("ko_a", "ko_b", "provenance_stratum", "scope_flags"):
            if item.get(field) != expected[field]:
                errors.append(f"selected pair {pair_id} changed {field}")
        if item.get("rank") != rank:
            errors.append(f"selected pair {pair_id} has invalid rank")
        if not isinstance(item.get("score"), (int, float)):
            errors.append(f"selected pair {pair_id} has invalid score")
    if selection.get("selected_pair_count") != len(selected):
        errors.append("selected_pair_count mismatch")
    if selection.get("universe_pair_count") != len(universe_by_id):
        errors.append("universe_pair_count mismatch")
    return errors


def write_bundle(
    *,
    output_dir: Path,
    selection: dict[str, Any],
    execution_commit: str,
    freeze_manifest_path: Path,
    input_paths: dict[str, Path],
) -> None:
    output_paths = [
        output_dir / SELECTION_FILENAME,
        output_dir / METADATA_FILENAME,
        output_dir / COMPLETION_FILENAME,
    ]
    existing = [path for path in output_paths if path.exists()]
    if existing:
        raise CandidateGenerationError(
            "Refusing to overwrite existing artifacts: "
            + ", ".join(display_path(path) for path in existing)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    selection_path, metadata_path, completion_path = output_paths
    atomic_write(selection_path, serialize_json(selection))
    metadata = {
        "artifact_type": "connection_candidate_generation_metadata",
        "version": "v0.1",
        "status": "final",
        "execution_commit_declared": execution_commit,
        "execution_commit_attestation": "supplied_by_operator",
        "freeze_manifest": binding(freeze_manifest_path),
        "inputs": {name: binding(path) for name, path in input_paths.items()},
        "method": selection["method"],
        "counts": {
            "universe_pairs": selection["universe_pair_count"],
            "selected_pairs": selection["selected_pair_count"],
        },
        "integrity": {
            "gold_artifacts_read": False,
            "duplicate_pair_count": 0,
            "unknown_pair_count": 0,
            "endpoint_mismatch_count": 0,
            "self_pair_count": 0,
        },
        "output": binding(selection_path),
        "generator": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": GENERATOR_VERSION,
        },
    }
    atomic_write(metadata_path, serialize_json(metadata))
    completion = {
        "artifact_type": "connection_candidate_generation_complete",
        "version": "v0.1",
        "status": "final",
        "execution_commit_declared": execution_commit,
        "artifacts": {
            "selection": binding(selection_path),
            "metadata": binding(metadata_path),
        },
        "counts": metadata["counts"],
        "method": selection["method"],
    }
    atomic_write(completion_path, serialize_json(completion))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--pair-universe", default=str(DEFAULT_PAIR_UNIVERSE))
    parser.add_argument("--canonical-inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--source-manifest", default=str(DEFAULT_SOURCE_MANIFEST))
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE_MANIFEST))
    parser.add_argument("--execution-commit", required=True)
    parser.add_argument("--retention-fraction", type=float, default=0.80)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if re.fullmatch(r"[0-9a-f]{40}", args.execution_commit) is None:
            raise CandidateGenerationError("execution_commit must be a 40-character SHA-1")
        pair_universe_path = resolve_path(args.pair_universe)
        inventory_path = resolve_path(args.canonical_inventory)
        source_manifest_path = resolve_path(args.source_manifest)
        freeze_manifest_path = resolve_path(args.freeze_manifest)
        output_dir = resolve_path(args.output_dir)
        pair_universe = load_json(pair_universe_path)
        inventory = load_json(inventory_path)
        source_manifest = load_json(source_manifest_path)
        freeze_manifest = load_json(freeze_manifest_path)
        validate_freeze_manifest(
            freeze_manifest,
            manifest_path=freeze_manifest_path,
            pair_universe_path=pair_universe_path,
            inventory_path=inventory_path,
            source_manifest_path=source_manifest_path,
        )
        validate_inputs(pair_universe, inventory, source_manifest)
        input_paths = {
            "pair_universe": pair_universe_path,
            "canonical_inventory": inventory_path,
            "source_manifest": source_manifest_path,
        }
        selection = build_selection(
            method=args.method,
            pair_universe=pair_universe,
            inventory=inventory,
            retention_fraction=args.retention_fraction,
            inputs={name: binding(path) for name, path in input_paths.items()},
        )
        errors = validate_selection(selection, pair_universe)
        if errors:
            raise CandidateGenerationError("; ".join(errors))
        write_bundle(
            output_dir=output_dir,
            selection=selection,
            execution_commit=args.execution_commit,
            freeze_manifest_path=freeze_manifest_path,
            input_paths=input_paths,
        )
    except CandidateGenerationError as exc:
        print(f"Candidate generation failed: {exc}")
        return 1
    print(
        f"Selected {selection['selected_pair_count']} of "
        f"{selection['universe_pair_count']} canonical pairs with {args.method}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
