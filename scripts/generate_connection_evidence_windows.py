#!/usr/bin/env python3
"""Generate minimal endpoint-linked Evidence windows for Connection verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "benchmark" / "connection_discovery" / "development_v0_1"
DEFAULT_CANDIDATES = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_1_candidate_generation"
    / "runs"
    / "development_v0_1"
    / "overlap_bridge"
    / "run_01"
    / "generation"
    / "candidate_selection.json"
)
DEFAULT_INVENTORY = DEFAULT_BENCHMARK / "oracle_canonical_inventory.json"
DEFAULT_EVIDENCE = DEFAULT_BENCHMARK / "evidence_catalogs.json"
GENERATOR_VERSION = "connection_evidence_window_generator_v0.1"
METHOD_ID = "minimal_endpoint_linked_windows_v0.1"
FORBIDDEN_GOLD_FIELDS = {
    "category",
    "primary_scoring_eligible",
    "primary_scoring_status",
    "gold_edge",
    "gold_relation_type",
    "gold_evidence",
    "acceptable_alternatives",
    "rationale",
    "evidence_support_scope",
    "annotation_origin",
    "schema_gap_relation",
    "annotation_rationale",
    "symmetric",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")


class EvidenceWindowError(ValueError):
    """Raised when Evidence-window generation violates its contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
        raise EvidenceWindowError(f"Missing required file: {display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceWindowError(f"Invalid JSON in {display_path(path)}: {exc}") from exc


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(serialize_json(value))
        temporary = Path(handle.name)
    os.replace(temporary, path)


def binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def repository_state() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceWindowError("Unable to inspect repository state") from exc
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise EvidenceWindowError("Current repository commit is invalid")
    return commit, dirty


def collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(collect_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(collect_keys(item))
        return result
    return set()


def normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized.strip())


def token_text(value: str) -> str:
    return " ".join(TOKEN_RE.findall(normalized_text(value)))


def phrase_present(phrase: str, span: str) -> bool:
    phrase_normalized = normalized_text(phrase)
    span_normalized = normalized_text(span)
    if phrase_normalized and phrase_normalized in span_normalized:
        return True
    phrase_tokens = token_text(phrase)
    span_tokens = token_text(span)
    if not phrase_tokens or not span_tokens:
        return False
    return re.search(rf"(?:^| ){re.escape(phrase_tokens)}(?: |$)", span_tokens) is not None


def endpoint_matches(knowledge_object: dict[str, Any], span: str) -> list[dict[str, str]]:
    candidates: list[tuple[str, str]] = [
        ("canonical_name", knowledge_object["canonical_name"]),
        *(("alias", alias) for alias in knowledge_object.get("aliases", [])),
    ]
    candidates.extend(
        ("mention_source_span", source_span)
        for mention in knowledge_object["mentions"]
        for source_span in mention["source_spans"]
    )
    matches: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for kind, value in candidates:
        key = (kind, normalized_text(value))
        if key in seen or not phrase_present(value, span):
            continue
        seen.add(key)
        matches.append({"match_kind": kind, "matched_value": value})
    return matches


def validate_inputs(
    candidate_selection: dict[str, Any],
    inventory: dict[str, Any],
    evidence_catalogs: dict[str, Any],
) -> None:
    errors: list[str] = []
    if candidate_selection.get("artifact_type") != "connection_candidate_selection":
        errors.append("candidate selection artifact_type is invalid")
    if inventory.get("artifact_type") != "connection_discovery_oracle_canonical_inventory":
        errors.append("canonical inventory artifact_type is invalid")
    if evidence_catalogs.get("artifact_type") != "connection_evidence_catalog_bundle":
        errors.append("Evidence catalogs artifact_type is invalid")
    leaked = sorted(
        (
            collect_keys(candidate_selection)
            | collect_keys(inventory)
            | collect_keys(evidence_catalogs)
        )
        & FORBIDDEN_GOLD_FIELDS
    )
    if leaked:
        errors.append(f"gold leakage fields present: {leaked}")

    objects = inventory.get("canonical_objects")
    selected_pairs = candidate_selection.get("selected_pairs")
    catalogs = evidence_catalogs.get("catalogs")
    if not isinstance(objects, list) or not objects:
        errors.append("canonical_objects must be a non-empty list")
        objects = []
    if not isinstance(selected_pairs, list) or not selected_pairs:
        errors.append("selected_pairs must be a non-empty list")
        selected_pairs = []
    if not isinstance(catalogs, list) or not catalogs:
        errors.append("catalogs must be a non-empty list")
        catalogs = []

    object_ids = [item.get("canonical_ko_id") for item in objects]
    pair_ids = [item.get("canonical_pair_id") for item in selected_pairs]
    catalog_ids = [item.get("canonical_pair_id") for item in catalogs]
    if len(object_ids) != len(set(object_ids)):
        errors.append("canonical inventory contains duplicate IDs")
    if len(pair_ids) != len(set(pair_ids)):
        errors.append("candidate selection contains duplicate pair IDs")
    if len(catalog_ids) != len(set(catalog_ids)):
        errors.append("Evidence catalogs contain duplicate pair IDs")
    if not set(pair_ids).issubset(set(catalog_ids)):
        errors.append("Evidence catalog is missing selected pairs")

    object_id_set = set(object_ids)
    catalog_map = {item.get("canonical_pair_id"): item for item in catalogs}
    for pair in selected_pairs:
        pair_id = pair.get("canonical_pair_id")
        endpoint_ids = [
            pair.get("ko_a", {}).get("canonical_ko_id"),
            pair.get("ko_b", {}).get("canonical_ko_id"),
        ]
        if len(set(endpoint_ids)) != 2 or not set(endpoint_ids) <= object_id_set:
            errors.append(f"{pair_id}: invalid candidate endpoints")
            continue
        catalog = catalog_map.get(pair_id, {})
        if catalog.get("endpoint_ids") != endpoint_ids:
            errors.append(f"{pair_id}: Evidence catalog endpoint mismatch")
        evidence_items = catalog.get("evidence_items")
        if not isinstance(evidence_items, list) or not evidence_items:
            errors.append(f"{pair_id}: evidence_items must be non-empty")
            continue
        evidence_ids = [item.get("evidence_id") for item in evidence_items]
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"{pair_id}: duplicate Evidence IDs")
        for item in evidence_items:
            if not isinstance(item.get("lecture_id"), str):
                errors.append(f"{pair_id}: invalid Evidence lecture_id")
            if not isinstance(item.get("block_index"), int):
                errors.append(f"{pair_id}: invalid Evidence block_index")
            if not isinstance(item.get("span"), str) or not item["span"].strip():
                errors.append(f"{pair_id}: invalid Evidence span")
    if errors:
        raise EvidenceWindowError("; ".join(sorted(set(errors))))


def stable_window_id(pair_id: str, lecture_id: str, evidence_ids: list[str]) -> str:
    payload = canonical_json([pair_id, lecture_id, evidence_ids])
    return f"conn_window_{sha256_bytes(payload)[:16]}"


def build_pair_windows(
    pair: dict[str, Any],
    *,
    object_map: dict[str, dict[str, Any]],
    catalog: dict[str, Any],
    max_blocks: int,
) -> dict[str, Any]:
    pair_id = pair["canonical_pair_id"]
    endpoint_ids = [
        pair["ko_a"]["canonical_ko_id"],
        pair["ko_b"]["canonical_ko_id"],
    ]
    endpoint_objects = [object_map[item] for item in endpoint_ids]
    enriched: list[dict[str, Any]] = []
    for item in catalog["evidence_items"]:
        coverage = {
            endpoint_ids[0]: endpoint_matches(endpoint_objects[0], item["span"]),
            endpoint_ids[1]: endpoint_matches(endpoint_objects[1], item["span"]),
        }
        enriched.append({**item, "endpoint_matches": coverage})

    by_lecture: dict[str, list[dict[str, Any]]] = {}
    for item in enriched:
        by_lecture.setdefault(item["lecture_id"], []).append(item)
    candidate_windows: list[tuple[str, int, int, list[dict[str, Any]]]] = []
    for lecture_id, items in sorted(by_lecture.items()):
        items.sort(key=lambda value: (value["block_index"], value["evidence_id"]))
        for start in range(len(items)):
            for end in range(start, min(start + max_blocks, len(items))):
                window_items = items[start : end + 1]
                indices = [value["block_index"] for value in window_items]
                if indices != list(range(indices[0], indices[0] + len(indices))):
                    break
                covers_a = any(value["endpoint_matches"][endpoint_ids[0]] for value in window_items)
                covers_b = any(value["endpoint_matches"][endpoint_ids[1]] for value in window_items)
                if covers_a and covers_b:
                    candidate_windows.append((lecture_id, start, end, window_items))

    minimal: list[tuple[str, int, int, list[dict[str, Any]]]] = []
    for candidate in candidate_windows:
        lecture_id, start, end, _ = candidate
        has_strict_subwindow = any(
            other_lecture == lecture_id
            and other_start >= start
            and other_end <= end
            and (other_start, other_end) != (start, end)
            for other_lecture, other_start, other_end, _ in candidate_windows
        )
        if not has_strict_subwindow:
            minimal.append(candidate)

    windows: list[dict[str, Any]] = []
    for lecture_id, _, _, items in minimal:
        evidence_ids = [item["evidence_id"] for item in items]
        windows.append(
            {
                "window_id": stable_window_id(pair_id, lecture_id, evidence_ids),
                "lecture_id": lecture_id,
                "evidence_ids": evidence_ids,
                "block_indices": [item["block_index"] for item in items],
                "evidence_blocks": items,
            }
        )
    windows.sort(key=lambda item: (len(item["evidence_ids"]), item["window_id"]))
    return {
        "canonical_pair_id": pair_id,
        "endpoint_ids": endpoint_ids,
        "endpoint_objects": [
            {
                "canonical_ko_id": item["canonical_ko_id"],
                "canonical_name": item["canonical_name"],
                "canonical_type": item["canonical_type"],
            }
            for item in endpoint_objects
        ],
        "window_count": len(windows),
        "deterministic_no_window": not windows,
        "windows": windows,
    }


def build_bundle(
    candidate_selection: dict[str, Any],
    inventory: dict[str, Any],
    evidence_catalogs: dict[str, Any],
    *,
    max_blocks: int = 3,
    inputs: dict[str, dict[str, str]] | None = None,
    method_commit: str | None = None,
) -> dict[str, Any]:
    if not 1 <= max_blocks <= 3:
        raise EvidenceWindowError("max_blocks must be between 1 and 3")
    validate_inputs(candidate_selection, inventory, evidence_catalogs)
    object_map = {
        item["canonical_ko_id"]: item for item in inventory["canonical_objects"]
    }
    catalog_map = {
        item["canonical_pair_id"]: item for item in evidence_catalogs["catalogs"]
    }
    pairs = [
        build_pair_windows(
            pair,
            object_map=object_map,
            catalog=catalog_map[pair["canonical_pair_id"]],
            max_blocks=max_blocks,
        )
        for pair in candidate_selection["selected_pairs"]
    ]
    window_count = sum(item["window_count"] for item in pairs)
    pairs_with_windows = sum(not item["deterministic_no_window"] for item in pairs)
    return {
        "artifact_type": "connection_evidence_window_bundle",
        "version": "v0.1",
        "status": "prepared",
        "split": candidate_selection.get("split"),
        "method": {
            "id": METHOD_ID,
            "generator_version": GENERATOR_VERSION,
            "method_commit": method_commit,
            "max_blocks": max_blocks,
            "same_lecture_only": True,
            "minimal_windows_only": True,
            "matching": "nfkc_casefold_whitespace_and_token_phrase_v0.1",
        },
        "inputs": inputs or {},
        "gold_fields_present": False,
        "counts": {
            "selected_pair_count": len(pairs),
            "pairs_with_windows": pairs_with_windows,
            "pairs_without_windows": len(pairs) - pairs_with_windows,
            "window_count": window_count,
        },
        "pairs": pairs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-selection", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--canonical-inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--evidence-catalogs", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--max-blocks", type=int, default=3)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        candidate_path = resolve_path(args.candidate_selection)
        inventory_path = resolve_path(args.canonical_inventory)
        evidence_path = resolve_path(args.evidence_catalogs)
        output_path = resolve_path(args.output)
        if output_path.exists():
            raise EvidenceWindowError(f"Output already exists: {display_path(output_path)}")
        current_commit, dirty = repository_state()
        if args.method_commit != current_commit:
            raise EvidenceWindowError("method_commit does not match the current repository commit")
        if dirty:
            raise EvidenceWindowError("repository must be clean before formal generation")
        bundle = build_bundle(
            load_json(candidate_path),
            load_json(inventory_path),
            load_json(evidence_path),
            max_blocks=args.max_blocks,
            inputs={
                "candidate_selection": binding(candidate_path),
                "canonical_inventory": binding(inventory_path),
                "evidence_catalogs": binding(evidence_path),
            },
            method_commit=current_commit,
        )
        atomic_write(output_path, bundle)
    except EvidenceWindowError as exc:
        print(f"Evidence-window generation failed: {exc}")
        return 1
    print(
        f"Generated {bundle['counts']['window_count']} minimal Evidence windows "
        f"for {bundle['counts']['selected_pair_count']} pairs at {display_path(output_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
