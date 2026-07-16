#!/usr/bin/env python3
"""Generate deterministic candidate-pair selections without reading gold data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAIR_UNIVERSE = (
    ROOT
    / "benchmark"
    / "candidate_pairs"
    / "development_v0_1"
    / "pair_universe.json"
)
DEFAULT_PAIR_UNIVERSE_MARKER = DEFAULT_PAIR_UNIVERSE.with_name(
    "pair_universe_complete.json"
)
DEFAULT_OUTPUT_SCHEMA = (
    ROOT / "benchmark" / "schema" / "candidate_pair_generation_output.schema.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "development_v0_1"
    / "all_pairs"
    / "run_01"
)
SELECTION_FILENAME = "candidate_pairs.json"
METADATA_FILENAME = "metadata.json"
COMPLETION_FILENAME = "candidate_generation_complete.json"
GENERATOR_VERSION = "v0.1"
GENERATOR_ID = "all_pairs_v0_1"
GENERATOR_CONFIG = {
    "strategy": "all_pairs",
    "selection_scope": "complete_pair_universe",
    "candidate_reasons": ["all_pairs_control"],
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
PAIR_ID_PATTERN = re.compile(r"cand_(dev|holdout)_[0-9]{3,}")


class CandidatePairGenerationError(ValueError):
    """Raised when candidate generation or artifact validation fails."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidatePairGenerationError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidatePairGenerationError(f"{label} must be a JSON object.")
    return value


def _exact_keys(
    value: Any,
    *,
    expected: set[str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: must be an object")
        return False
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"{label}: missing fields {missing}")
    if extra:
        errors.append(f"{label}: forbidden fields {extra}")
    return not missing and not extra


def _valid_binding(value: Any, *, label: str, errors: list[str]) -> bool:
    if not _exact_keys(value, expected={"path", "sha256"}, label=label, errors=errors):
        return False
    if not isinstance(value["path"], str) or not value["path"]:
        errors.append(f"{label}.path: must be non-empty text")
    if not isinstance(value["sha256"], str) or not SHA256_PATTERN.fullmatch(
        value["sha256"]
    ):
        errors.append(f"{label}.sha256: must be lowercase SHA-256")
    return True


def validate_pair_universe(
    pair_universe: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    required = {
        "artifact_type",
        "version",
        "benchmark_split",
        "scope",
        "endpoint_order",
        "pair_order",
        "source_inventory",
        "lecture_inventory",
        "lectures",
        "total_ko_count",
        "total_pair_count",
        "pairs",
    }
    _exact_keys(pair_universe, expected=required, label="pair_universe", errors=errors)
    if pair_universe.get("artifact_type") != "candidate_pair_universe":
        errors.append("pair_universe.artifact_type: expected candidate_pair_universe")
    if pair_universe.get("version") != "v0.1":
        errors.append("pair_universe.version: expected v0.1")
    if pair_universe.get("benchmark_split") not in {"development", "holdout"}:
        errors.append("pair_universe.benchmark_split: invalid split")
    if pair_universe.get("scope") != "lecture_local_unordered_nonself":
        errors.append("pair_universe.scope: frozen scope mismatch")
    if pair_universe.get("endpoint_order") != "ascending_fully_qualified_ko_reference":
        errors.append("pair_universe.endpoint_order: frozen order mismatch")
    if pair_universe.get("pair_order") != "ascending_lecture_then_endpoint_references":
        errors.append("pair_universe.pair_order: frozen order mismatch")

    pairs = pair_universe.get("pairs")
    if not isinstance(pairs, list):
        errors.append("pair_universe.pairs: must be a list")
        pairs = []
    if pair_universe.get("total_pair_count") != len(pairs):
        errors.append("pair_universe.total_pair_count: does not match pairs")

    seen_ids: set[str] = set()
    seen_endpoints: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    previous_order_key: tuple[str, str, str] | None = None
    for index, pair in enumerate(pairs):
        label = f"pair_universe.pairs[{index}]"
        if not _exact_keys(
            pair,
            expected={"pair_id", "lecture_id", "ko_a", "ko_b"},
            label=label,
            errors=errors,
        ):
            continue
        pair_id = pair.get("pair_id")
        lecture_id = pair.get("lecture_id")
        if not isinstance(pair_id, str) or not PAIR_ID_PATTERN.fullmatch(pair_id):
            errors.append(f"{label}.pair_id: invalid pair ID")
            continue
        if pair_id in seen_ids:
            errors.append(f"{label}.pair_id: duplicate pair ID {pair_id}")
        seen_ids.add(pair_id)
        refs: list[tuple[str, str]] = []
        for endpoint_name in ("ko_a", "ko_b"):
            endpoint = pair.get(endpoint_name)
            endpoint_label = f"{label}.{endpoint_name}"
            if not _exact_keys(
                endpoint,
                expected={"lecture_id", "ko_id"},
                label=endpoint_label,
                errors=errors,
            ):
                continue
            ref = (endpoint.get("lecture_id"), endpoint.get("ko_id"))
            if not all(isinstance(item, str) and item for item in ref):
                errors.append(f"{endpoint_label}: invalid endpoint reference")
                continue
            refs.append(ref)  # type: ignore[arg-type]
        if len(refs) != 2:
            continue
        if not isinstance(lecture_id, str) or not lecture_id:
            errors.append(f"{label}.lecture_id: invalid lecture ID")
            continue
        if refs[0][0] != lecture_id or refs[1][0] != lecture_id:
            errors.append(f"{label}: endpoints must belong to pair lecture")
        if refs[0] >= refs[1]:
            errors.append(f"{label}: endpoints are not in canonical ascending order")
        endpoint_key = (refs[0], refs[1])
        if endpoint_key in seen_endpoints:
            errors.append(f"{label}: duplicate unordered endpoints")
        seen_endpoints.add(endpoint_key)
        order_key = (lecture_id, refs[0][1], refs[1][1])
        if previous_order_key is not None and order_key <= previous_order_key:
            errors.append(f"{label}: pair order is not deterministic ascending order")
        previous_order_key = order_key
    return pairs, errors


def validate_pair_universe_marker(
    marker: dict[str, Any],
    *,
    marker_path: Path,
    pair_universe_path: Path,
    pair_universe: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if marker.get("artifact_type") != "candidate_pair_universe_complete":
        errors.append("pair_universe_marker.artifact_type: invalid")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        errors.append("pair_universe_marker: must be final v0.1")
    binding = marker.get("pair_universe")
    if _valid_binding(binding, label="pair_universe_marker.pair_universe", errors=errors):
        if binding["path"] != display_path(pair_universe_path):
            errors.append("pair_universe_marker.pair_universe.path: stale binding")
        if binding["sha256"] != sha256_file(pair_universe_path):
            errors.append("pair_universe_marker.pair_universe.sha256: stale binding")
    counts = marker.get("counts")
    if not isinstance(counts, dict) or counts.get("pairs") != pair_universe.get(
        "total_pair_count"
    ):
        errors.append("pair_universe_marker.counts.pairs: count mismatch")
    if not marker_path.is_file():
        errors.append("pair_universe_marker: missing completion marker")
    return errors


def build_all_pairs_selection(
    pair_universe: dict[str, Any],
    *,
    pair_universe_path: Path,
) -> dict[str, Any]:
    pairs, errors = validate_pair_universe(pair_universe)
    if errors:
        raise CandidatePairGenerationError("; ".join(errors))
    implementation_path = Path(__file__).resolve()
    config_hash = sha256_json(GENERATOR_CONFIG)
    selected_pairs = [
        {
            "pair_id": pair["pair_id"],
            "lecture_id": pair["lecture_id"],
            "ko_a": dict(pair["ko_a"]),
            "ko_b": dict(pair["ko_b"]),
            "candidate_reasons": list(GENERATOR_CONFIG["candidate_reasons"]),
        }
        for pair in pairs
    ]
    source_inventory = pair_universe["source_inventory"]
    return {
        "artifact_type": "candidate_pair_selection",
        "version": "v0.1",
        "benchmark_split": pair_universe["benchmark_split"],
        "scope": pair_universe["scope"],
        "selection_order": "pair_universe_order",
        "generator": {
            "id": GENERATOR_ID,
            "name": "all_pairs",
            "version": GENERATOR_VERSION,
            "implementation": {
                "path": display_path(implementation_path),
                "sha256": sha256_file(implementation_path),
            },
            "config": dict(GENERATOR_CONFIG),
            "config_sha256": config_hash,
        },
        "pair_universe": {
            "path": display_path(pair_universe_path),
            "sha256": sha256_file(pair_universe_path),
        },
        "source_inventory": {
            "path": source_inventory["path"],
            "sha256": source_inventory["sha256"],
            "normalized_content_sha256": source_inventory[
                "normalized_content_sha256"
            ],
        },
        "selected_pair_count": len(selected_pairs),
        "selected_pairs": selected_pairs,
    }


def validate_candidate_selection(
    selection: dict[str, Any],
    *,
    pair_universe: dict[str, Any],
    pair_universe_path: Path,
    require_all_pairs_contract: bool | None = None,
) -> list[str]:
    errors: list[str] = []
    top_keys = {
        "artifact_type",
        "version",
        "benchmark_split",
        "scope",
        "selection_order",
        "generator",
        "pair_universe",
        "source_inventory",
        "selected_pair_count",
        "selected_pairs",
    }
    _exact_keys(selection, expected=top_keys, label="selection", errors=errors)
    if selection.get("artifact_type") != "candidate_pair_selection":
        errors.append("selection.artifact_type: invalid")
    if selection.get("version") != "v0.1":
        errors.append("selection.version: invalid")
    if selection.get("benchmark_split") != pair_universe.get("benchmark_split"):
        errors.append("selection.benchmark_split: universe mismatch")
    if selection.get("scope") != pair_universe.get("scope"):
        errors.append("selection.scope: universe mismatch")
    if selection.get("selection_order") != "pair_universe_order":
        errors.append("selection.selection_order: invalid")

    generator = selection.get("generator")
    generator_keys = {
        "id",
        "name",
        "version",
        "implementation",
        "config",
        "config_sha256",
    }
    if _exact_keys(generator, expected=generator_keys, label="selection.generator", errors=errors):
        _valid_binding(
            generator.get("implementation"),
            label="selection.generator.implementation",
            errors=errors,
        )
        config = generator.get("config")
        if not isinstance(config, dict):
            errors.append("selection.generator.config: must be an object")
        elif generator.get("config_sha256") != sha256_json(config):
            errors.append("selection.generator.config_sha256: content mismatch")

    binding = selection.get("pair_universe")
    if _valid_binding(binding, label="selection.pair_universe", errors=errors):
        if binding["path"] != display_path(pair_universe_path):
            errors.append("selection.pair_universe.path: universe mismatch")
        if binding["sha256"] != sha256_file(pair_universe_path):
            errors.append("selection.pair_universe.sha256: universe mismatch")

    source = selection.get("source_inventory")
    source_keys = {"path", "sha256", "normalized_content_sha256"}
    if _exact_keys(source, expected=source_keys, label="selection.source_inventory", errors=errors):
        expected_source = pair_universe.get("source_inventory", {})
        for field in source_keys:
            if source.get(field) != expected_source.get(field):
                errors.append(f"selection.source_inventory.{field}: universe mismatch")

    selected_pairs = selection.get("selected_pairs")
    if not isinstance(selected_pairs, list):
        errors.append("selection.selected_pairs: must be a list")
        selected_pairs = []
    if selection.get("selected_pair_count") != len(selected_pairs):
        errors.append("selection.selected_pair_count: does not match selected_pairs")

    universe_pairs = pair_universe.get("pairs", [])
    universe_by_id = {
        item.get("pair_id"): item for item in universe_pairs if isinstance(item, dict)
    }
    universe_order = {pair_id: index for index, pair_id in enumerate(universe_by_id)}
    seen_ids: set[str] = set()
    selected_ids: list[str] = []
    previous_position = -1
    for index, item in enumerate(selected_pairs):
        label = f"selection.selected_pairs[{index}]"
        if not _exact_keys(
            item,
            expected={"pair_id", "lecture_id", "ko_a", "ko_b", "candidate_reasons"},
            label=label,
            errors=errors,
        ):
            continue
        pair_id = item.get("pair_id")
        if not isinstance(pair_id, str) or not PAIR_ID_PATTERN.fullmatch(pair_id):
            errors.append(f"{label}.pair_id: invalid")
            continue
        if pair_id in seen_ids:
            errors.append(f"{label}.pair_id: duplicate selected pair {pair_id}")
        seen_ids.add(pair_id)
        selected_ids.append(pair_id)
        expected = universe_by_id.get(pair_id)
        if expected is None:
            errors.append(f"{label}.pair_id: unknown pair {pair_id}")
            continue
        position = universe_order[pair_id]
        if position <= previous_position:
            errors.append(f"{label}: selected pair order differs from universe order")
        previous_position = position
        for field in ("lecture_id", "ko_a", "ko_b"):
            if item.get(field) != expected.get(field):
                errors.append(f"{label}.{field}: endpoint mismatch")
        reasons = item.get("candidate_reasons")
        if not isinstance(reasons, list) or not reasons or not all(
            isinstance(reason, str) and reason for reason in reasons
        ):
            errors.append(f"{label}.candidate_reasons: invalid")
        elif len(reasons) != len(set(reasons)):
            errors.append(f"{label}.candidate_reasons: duplicate reason")

    if require_all_pairs_contract is None:
        require_all_pairs_contract = isinstance(generator, dict) and generator.get(
            "name"
        ) == "all_pairs"
    if require_all_pairs_contract:
        expected_ids = [item["pair_id"] for item in universe_pairs]
        if selected_ids != expected_ids:
            errors.append("selection: all_pairs contract requires every universe pair")
        if isinstance(generator, dict):
            if generator.get("id") != GENERATOR_ID:
                errors.append("selection.generator.id: all_pairs contract mismatch")
            if generator.get("version") != GENERATOR_VERSION:
                errors.append("selection.generator.version: all_pairs contract mismatch")
            if generator.get("config") != GENERATOR_CONFIG:
                errors.append("selection.generator.config: all_pairs contract mismatch")
        for index, item in enumerate(selected_pairs):
            if isinstance(item, dict) and item.get("candidate_reasons") != [
                "all_pairs_control"
            ]:
                errors.append(
                    f"selection.selected_pairs[{index}].candidate_reasons: "
                    "all_pairs contract mismatch"
                )
    return errors


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def build_generation_metadata(
    *,
    selection_path: Path,
    selection: dict[str, Any],
    pair_universe_path: Path,
    pair_universe_marker_path: Path,
    output_schema_path: Path,
) -> dict[str, Any]:
    return {
        "artifact_type": "candidate_pair_generation_metadata",
        "version": "v0.1",
        "status": "final",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": selection["generator"],
        "inputs": {
            "pair_universe": {
                "path": display_path(pair_universe_path),
                "sha256": sha256_file(pair_universe_path),
            },
            "pair_universe_completion_marker": {
                "path": display_path(pair_universe_marker_path),
                "sha256": sha256_file(pair_universe_marker_path),
            },
            "output_schema": {
                "path": display_path(output_schema_path),
                "sha256": sha256_file(output_schema_path),
            },
        },
        "output": {
            "path": display_path(selection_path),
            "sha256": sha256_file(selection_path),
            "selected_pair_count": selection["selected_pair_count"],
        },
        "integrity": {
            "duplicate_pair_count": 0,
            "unknown_pair_count": 0,
            "endpoint_mismatch_count": 0,
            "order_matches_universe": True,
            "gold_artifacts_read": False,
        },
    }


def build_generation_completion_marker(
    *,
    selection_path: Path,
    metadata_path: Path,
    pair_universe_path: Path,
    pair_universe_marker_path: Path,
    output_schema_path: Path,
    selected_pair_count: int,
    universe_pair_count: int,
) -> dict[str, Any]:
    return {
        "artifact_type": "candidate_pair_generation_complete",
        "version": "v0.1",
        "status": "final",
        "artifacts": {
            "candidate_selection": {
                "path": display_path(selection_path),
                "sha256": sha256_file(selection_path),
            },
            "metadata": {
                "path": display_path(metadata_path),
                "sha256": sha256_file(metadata_path),
            },
            "pair_universe": {
                "path": display_path(pair_universe_path),
                "sha256": sha256_file(pair_universe_path),
            },
            "pair_universe_completion_marker": {
                "path": display_path(pair_universe_marker_path),
                "sha256": sha256_file(pair_universe_marker_path),
            },
            "output_schema": {
                "path": display_path(output_schema_path),
                "sha256": sha256_file(output_schema_path),
            },
        },
        "generator": {
            "id": GENERATOR_ID,
            "version": GENERATOR_VERSION,
            "implementation": {
                "path": display_path(Path(__file__)),
                "sha256": sha256_file(Path(__file__)),
            },
            "config_sha256": sha256_json(GENERATOR_CONFIG),
        },
        "counts": {
            "universe_pairs": universe_pair_count,
            "selected_pairs": selected_pair_count,
            "missing_universe_pairs": universe_pair_count - selected_pair_count,
            "extra_pairs": 0,
            "duplicate_pairs": 0,
            "endpoint_mismatches": 0,
        },
    }


def write_generation_bundle(
    *,
    output_dir: Path,
    selection: dict[str, Any],
    pair_universe: dict[str, Any],
    pair_universe_path: Path,
    pair_universe_marker_path: Path,
    output_schema_path: Path,
) -> tuple[Path, Path, Path]:
    selection_path = output_dir / SELECTION_FILENAME
    metadata_path = output_dir / METADATA_FILENAME
    marker_path = output_dir / COMPLETION_FILENAME
    targets = (selection_path, metadata_path, marker_path)
    existing = [display_path(path) for path in targets if path.exists()]
    if existing:
        raise CandidatePairGenerationError(
            f"Refusing to overwrite existing artifact(s): {', '.join(existing)}."
        )

    _atomic_write_text(selection_path, serialize_json(selection))
    metadata = build_generation_metadata(
        selection_path=selection_path,
        selection=selection,
        pair_universe_path=pair_universe_path,
        pair_universe_marker_path=pair_universe_marker_path,
        output_schema_path=output_schema_path,
    )
    _atomic_write_text(metadata_path, serialize_json(metadata))
    marker = build_generation_completion_marker(
        selection_path=selection_path,
        metadata_path=metadata_path,
        pair_universe_path=pair_universe_path,
        pair_universe_marker_path=pair_universe_marker_path,
        output_schema_path=output_schema_path,
        selected_pair_count=selection["selected_pair_count"],
        universe_pair_count=pair_universe["total_pair_count"],
    )
    _atomic_write_text(marker_path, serialize_json(marker))
    return selection_path, metadata_path, marker_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic candidate-pair selection."
    )
    parser.add_argument("--strategy", choices=["all_pairs"], required=True)
    parser.add_argument("--pair-universe", default=str(DEFAULT_PAIR_UNIVERSE))
    parser.add_argument(
        "--pair-universe-completion-marker",
        default=str(DEFAULT_PAIR_UNIVERSE_MARKER),
    )
    parser.add_argument("--output-schema", default=str(DEFAULT_OUTPUT_SCHEMA))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pair_universe_path = resolve_path(args.pair_universe)
    pair_universe_marker_path = resolve_path(args.pair_universe_completion_marker)
    output_schema_path = resolve_path(args.output_schema)
    output_dir = resolve_path(args.output_dir)
    try:
        pair_universe = load_json_object(pair_universe_path, label="pair universe")
        marker = load_json_object(
            pair_universe_marker_path,
            label="pair-universe completion marker",
        )
        _, universe_errors = validate_pair_universe(pair_universe)
        universe_errors.extend(
            validate_pair_universe_marker(
                marker,
                marker_path=pair_universe_marker_path,
                pair_universe_path=pair_universe_path,
                pair_universe=pair_universe,
            )
        )
        if universe_errors:
            raise CandidatePairGenerationError("; ".join(universe_errors))
        if not output_schema_path.is_file():
            raise CandidatePairGenerationError(
                f"Missing output schema: {display_path(output_schema_path)}"
            )
        selection = build_all_pairs_selection(
            pair_universe,
            pair_universe_path=pair_universe_path,
        )
        selection_errors = validate_candidate_selection(
            selection,
            pair_universe=pair_universe,
            pair_universe_path=pair_universe_path,
            require_all_pairs_contract=True,
        )
        if selection_errors:
            raise CandidatePairGenerationError("; ".join(selection_errors))
        selection_path, metadata_path, marker_path = write_generation_bundle(
            output_dir=output_dir,
            selection=selection,
            pair_universe=pair_universe,
            pair_universe_path=pair_universe_path,
            pair_universe_marker_path=pair_universe_marker_path,
            output_schema_path=output_schema_path,
        )
    except (OSError, CandidatePairGenerationError) as exc:
        print(f"Candidate pair generation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Selected {selection['selected_pair_count']} pairs with {GENERATOR_ID}."
    )
    print(f"Candidates {display_path(selection_path)}")
    print(f"Metadata {display_path(metadata_path)}")
    print(f"Completion marker {display_path(marker_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
