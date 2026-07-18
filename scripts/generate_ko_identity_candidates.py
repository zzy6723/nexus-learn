#!/usr/bin/env python3
"""Generate deterministic, Ground-Truth-blind KO identity candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_CHALLENGE = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"
DEFAULT_NORMALIZATION = ROOT / "benchmark" / "ko_name_normalization_v0_1.json"
DEFAULT_ALIASES = ROOT / "benchmark" / "ko_aliases_v0_1.json"
GENERATOR_VERSION = "ko_identity_candidate_generator_v0.1"
FILES = {
    "candidates": "candidate_pairs.json",
    "audit": "candidate_generation_audit.json",
    "metadata": "metadata.json",
    "completion": "candidate_generation_complete.json",
}
REASON_ORDER = (
    "exact_normalized_name",
    "frozen_alias_identity",
    "name_token_equivalence",
    "initialism_name_match",
    "name_token_containment",
    "exact_source_span",
)


class CandidateGenerationError(ValueError):
    """Raised when candidate generation inputs or outputs are invalid."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mention-inventory",
        default=str(DEFAULT_CHALLENGE / "mention_inventory.json"),
    )
    parser.add_argument(
        "--lecture-inventory",
        default=str(DEFAULT_CHALLENGE / "lecture_inventory.json"),
    )
    parser.add_argument("--normalization-config", default=str(DEFAULT_NORMALIZATION))
    parser.add_argument("--alias-resource", default=str(DEFAULT_ALIASES))
    parser.add_argument("--challenge-marker", "--benchmark-marker", dest="challenge_marker")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise CandidateGenerationError(f"Missing input: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateGenerationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateGenerationError(f"{label} must be a JSON object.")
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


def name_tokens(normalized_name: str) -> frozenset[str]:
    tokens = [token for token in re.findall(r"[a-z0-9]+", normalized_name) if token != "s"]
    return frozenset(tokens)


def ordered_name_tokens(normalized_name: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", normalized_name) if token != "s"]


def initialism(tokens: list[str]) -> str:
    return "".join(token[0] for token in tokens if token)


def candidate_reasons(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    normalized_by_id: dict[str, str],
    alias_key_by_id: dict[str, str],
) -> list[str]:
    if left["type"] != right["type"]:
        return []
    left_id, right_id = left["mention_id"], right["mention_id"]
    left_name = normalized_by_id[left_id]
    right_name = normalized_by_id[right_id]
    reasons: list[str] = []
    if left_name == right_name:
        reasons.append("exact_normalized_name")
    if alias_key_by_id[left_id] == alias_key_by_id[right_id] and left_name != right_name:
        reasons.append("frozen_alias_identity")
    left_ordered = ordered_name_tokens(left_name)
    right_ordered = ordered_name_tokens(right_name)
    left_tokens, right_tokens = frozenset(left_ordered), frozenset(right_ordered)
    if left_ordered == right_ordered and left_name != right_name:
        reasons.append("name_token_equivalence")
    if (
        len(left_ordered) == 1
        and len(left_ordered[0]) >= 2
        and left_ordered[0] == initialism(right_ordered)
    ) or (
        len(right_ordered) == 1
        and len(right_ordered[0]) >= 2
        and right_ordered[0] == initialism(left_ordered)
    ):
        reasons.append("initialism_name_match")
    if (
        left_tokens
        and right_tokens
        and left_tokens != right_tokens
        and (left_tokens < right_tokens or right_tokens < left_tokens)
    ):
        reasons.append("name_token_containment")
    if set(left["source_spans"]) & set(right["source_spans"]):
        reasons.append("exact_source_span")
    return [reason for reason in REASON_ORDER if reason in reasons]


def mention_snapshot(mention: dict[str, Any]) -> dict[str, Any]:
    return {
        "mention_id": mention["mention_id"],
        "lecture_id": mention["lecture_id"],
        "name": mention["name"],
        "type": mention["type"],
        "source_spans": mention["source_spans"],
    }


def build_candidate_bundle(
    inventory: dict[str, Any],
    normalization_config: dict[str, Any],
    alias_resource: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from scripts.run_deterministic_ko_canonicalization import (
        build_alias_index,
        normalize_name,
        validate_normalization_config,
    )

    mentions = inventory.get("mentions")
    if not isinstance(mentions, list) or not mentions:
        raise CandidateGenerationError("Mention inventory is empty.")
    forbidden = {"canonical_id", "gold", "gold_cluster", "identity_label"}
    for mention in mentions:
        if forbidden & set(mention):
            raise CandidateGenerationError("Mention inventory contains forbidden gold fields.")
    wrappers = validate_normalization_config(normalization_config)
    alias_index, _ = build_alias_index(alias_resource, wrappers=wrappers)
    normalized_by_id: dict[str, str] = {}
    alias_key_by_id: dict[str, str] = {}
    for mention in mentions:
        normalized, _ = normalize_name(mention["name"], wrappers=wrappers)
        normalized_by_id[mention["mention_id"]] = normalized
        alias_key_by_id[mention["mention_id"]] = alias_index.get(
            (mention["type"], normalized), normalized
        )
    candidates: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for pair_index, (left, right) in enumerate(combinations(mentions, 2), start=1):
        reasons = candidate_reasons(
            left,
            right,
            normalized_by_id=normalized_by_id,
            alias_key_by_id=alias_key_by_id,
        )
        pair_key = f"ko_pair_{pair_index:03d}"
        decisions.append(
            {
                "pair_key": pair_key,
                "mention_ids": [left["mention_id"], right["mention_id"]],
                "same_type": left["type"] == right["type"],
                "selected": bool(reasons),
                "reasons": reasons,
            }
        )
        if reasons:
            candidate_id = f"ko_identity_candidate_{len(candidates) + 1:03d}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "mention_a": mention_snapshot(left),
                    "mention_b": mention_snapshot(right),
                    "selection_reasons": reasons,
                }
            )
    bundle = {
        "artifact_type": "ko_identity_candidate_bundle",
        "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"],
        "candidate_order": "ascending_unordered_mention_inventory_pair",
        "generation_rules": list(REASON_ORDER),
        "counts": {
            "mentions": len(mentions),
            "all_unordered_pairs": len(decisions),
            "same_type_pairs": sum(item["same_type"] for item in decisions),
            "selected_candidates": len(candidates),
            "rejected_pairs": len(decisions) - len(candidates),
        },
        "candidates": candidates,
    }
    audit = {
        "artifact_type": "ko_identity_candidate_generation_audit",
        "version": "v0.1",
        "candidate_bundle_sha256": sha256_json(bundle),
        "decisions": decisions,
    }
    return bundle, audit


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    lecture_path = Path(args.lecture_inventory).resolve()
    normalization_path = Path(args.normalization_config).resolve()
    alias_path = Path(args.alias_resource).resolve()
    challenge_marker_path = (
        Path(args.challenge_marker).resolve()
        if args.challenge_marker
        else inventory_path.with_name("challenge_complete.json")
    )
    output_dir = Path(args.output_dir).resolve()
    paths = {name: output_dir / filename for name, filename in FILES.items()}
    try:
        existing = [path for path in paths.values() if path.exists()]
        if existing and not args.overwrite:
            raise CandidateGenerationError(
                "Refusing to overwrite: " + ", ".join(display_path(path) for path in existing)
            )
        inventory = load_json(inventory_path, label="mention inventory")
        lecture_inventory = load_json(lecture_path, label="lecture inventory")
        normalization = load_json(normalization_path, label="normalization config")
        aliases = load_json(alias_path, label="alias resource")
        challenge_marker = load_json(challenge_marker_path, label="challenge marker")
        if challenge_marker.get("status") != "final":
            raise CandidateGenerationError("Challenge marker is not final.")
        marker_artifacts = challenge_marker.get("artifacts", {})
        marker_inventory = marker_artifacts.get("mention_inventory")
        if marker_inventory != binding(inventory_path):
            raise CandidateGenerationError("Benchmark marker mention binding is stale.")
        marker_lecture = marker_artifacts.get("lecture_inventory") or challenge_marker.get(
            "lecture_inventory"
        )
        if marker_lecture != binding(lecture_path):
            raise CandidateGenerationError("Benchmark marker lecture binding is stale.")
        lecture_ids = {item["lecture_id"] for item in lecture_inventory.get("lectures", [])}
        if {item["lecture_id"] for item in inventory["mentions"]} - lecture_ids:
            raise CandidateGenerationError("Mention inventory references an unknown lecture.")
        bundle, audit = build_candidate_bundle(inventory, normalization, aliases)
        if args.overwrite:
            for path in paths.values():
                if path.exists():
                    path.unlink()
        atomic_write(paths["candidates"], bundle)
        atomic_write(paths["audit"], audit)
        metadata = {
            "artifact_type": "ko_identity_candidate_generation_metadata",
            "version": "v0.1",
            "status": "completed",
            "generator": {**binding(Path(__file__).resolve()), "version": GENERATOR_VERSION},
            "inputs": {
                "mention_inventory": binding(inventory_path),
                "lecture_inventory": binding(lecture_path),
                "normalization_config": binding(normalization_path),
                "alias_resource": binding(alias_path),
                "challenge_marker": binding(challenge_marker_path),
            },
            "counts": bundle["counts"],
        }
        atomic_write(paths["metadata"], metadata)
        marker = {
            "artifact_type": "ko_identity_candidate_generation_complete",
            "version": "v0.1",
            "status": "final",
            "artifacts": {
                name: binding(path)
                for name, path in paths.items()
                if name != "completion"
            },
        }
        atomic_write(paths["completion"], marker)
    except CandidateGenerationError as exc:
        print(f"Candidate generation failed: {exc}")
        return 1
    print(f"Wrote {bundle['counts']['selected_candidates']} KO identity candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
