#!/usr/bin/env python3
"""Generate a deterministic exhaustive lecture-local predicted-KO pair universe."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_predicted_ko"
    / "runs"
    / "locked_reuse_v0_2"
    / "run_01"
    / "normalization"
    / "normalized_predicted_kos.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "benchmark"
    / "candidate_pairs"
    / "development_v0_1"
    / "pair_universe.json"
)
DEFAULT_MARKER = DEFAULT_OUTPUT.with_name("pair_universe_complete.json")
PAIR_ID_PREFIX = {"development": "cand_dev", "holdout": "cand_holdout"}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class CandidatePairUniverseError(ValueError):
    """Raised when the source inventory cannot define a valid pair universe."""


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


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidatePairUniverseError(f"Unable to read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CandidatePairUniverseError("Predicted-KO inventory must be a JSON object.")
    return data


def validate_inventory(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("artifact_type") != "predicted_ko_normalized_inventory":
        raise CandidatePairUniverseError(
            "Source artifact_type must be predicted_ko_normalized_inventory."
        )
    if not isinstance(data.get("split"), str) or not data["split"]:
        raise CandidatePairUniverseError("Source inventory requires a non-empty split.")
    objects = data.get("knowledge_objects")
    if not isinstance(objects, list) or not objects:
        raise CandidatePairUniverseError(
            "Source inventory knowledge_objects must be a non-empty list."
        )

    declared_content_hash = data.get("normalized_content_sha256")
    if not isinstance(declared_content_hash, str) or not SHA256_PATTERN.fullmatch(
        declared_content_hash
    ):
        raise CandidatePairUniverseError(
            "Source inventory requires a valid normalized_content_sha256."
        )
    actual_content_hash = sha256_json(objects)
    if actual_content_hash != declared_content_hash:
        raise CandidatePairUniverseError(
            "Source inventory normalized_content_sha256 does not match its objects."
        )

    seen: set[tuple[str, str]] = set()
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            raise CandidatePairUniverseError(
                f"knowledge_objects[{index}] must be an object."
            )
        lecture_id = item.get("lecture_id")
        ko_id = item.get("predicted_ko_id")
        name = item.get("name")
        ko_type = item.get("type")
        source_spans = item.get("source_spans")
        if not isinstance(lecture_id, str) or not lecture_id:
            raise CandidatePairUniverseError(
                f"knowledge_objects[{index}] has an invalid lecture_id."
            )
        if not isinstance(ko_id, str) or not ko_id:
            raise CandidatePairUniverseError(
                f"knowledge_objects[{index}] has an invalid predicted_ko_id."
            )
        if not isinstance(name, str) or not name:
            raise CandidatePairUniverseError(
                f"knowledge_objects[{index}] has an invalid name."
            )
        if ko_type not in {"Concept", "Method", "Formula"}:
            raise CandidatePairUniverseError(
                f"knowledge_objects[{index}] has an invalid type {ko_type!r}."
            )
        if not isinstance(source_spans, list) or not all(
            isinstance(span, str) and span for span in source_spans
        ):
            raise CandidatePairUniverseError(
                f"knowledge_objects[{index}] has invalid source_spans."
            )
        ref = (lecture_id, ko_id)
        if ref in seen:
            raise CandidatePairUniverseError(
                f"Duplicate predicted Knowledge Object reference: {ref}."
            )
        seen.add(ref)
        validated.append(item)
    return validated


def build_pair_universe(
    inventory: dict[str, Any],
    *,
    source_inventory_path: str,
    source_inventory_sha256: str,
    benchmark_split: str,
) -> dict[str, Any]:
    if benchmark_split not in PAIR_ID_PREFIX:
        raise CandidatePairUniverseError(
            f"Unsupported benchmark split: {benchmark_split!r}."
        )
    if not SHA256_PATTERN.fullmatch(source_inventory_sha256):
        raise CandidatePairUniverseError("source_inventory_sha256 must be SHA-256.")

    objects = validate_inventory(inventory)
    by_lecture: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in objects:
        by_lecture[item["lecture_id"]].append(item)

    lecture_summaries: list[dict[str, Any]] = []
    endpoint_pairs: list[tuple[str, str, str]] = []
    for lecture_id in sorted(by_lecture):
        lecture_objects = sorted(
            by_lecture[lecture_id], key=lambda item: item["predicted_ko_id"]
        )
        for ko_a, ko_b in itertools.combinations(lecture_objects, 2):
            endpoint_pairs.append(
                (lecture_id, ko_a["predicted_ko_id"], ko_b["predicted_ko_id"])
            )
        ko_count = len(lecture_objects)
        lecture_summaries.append(
            {
                "lecture_id": lecture_id,
                "ko_count": ko_count,
                "pair_count": ko_count * (ko_count - 1) // 2,
            }
        )

    prefix = PAIR_ID_PREFIX[benchmark_split]
    pairs = []
    for index, (lecture_id, ko_a, ko_b) in enumerate(endpoint_pairs, start=1):
        pairs.append(
            {
                "pair_id": f"{prefix}_{index:03d}",
                "lecture_id": lecture_id,
                "ko_a": {"lecture_id": lecture_id, "ko_id": ko_a},
                "ko_b": {"lecture_id": lecture_id, "ko_id": ko_b},
            }
        )

    return {
        "artifact_type": "candidate_pair_universe",
        "version": "v0.1",
        "benchmark_split": benchmark_split,
        "scope": "lecture_local_unordered_nonself",
        "endpoint_order": "ascending_fully_qualified_ko_reference",
        "pair_order": "ascending_lecture_then_endpoint_references",
        "source_inventory": {
            "path": source_inventory_path,
            "sha256": source_inventory_sha256,
            "normalized_content_sha256": inventory["normalized_content_sha256"],
            "source_split": inventory["split"],
            "structural_normalization_version": inventory.get(
                "structural_normalization_version"
            ),
        },
        "lectures": lecture_summaries,
        "total_ko_count": len(objects),
        "total_pair_count": len(pairs),
        "pairs": pairs,
    }


def build_completion_marker(
    *,
    pair_universe_path: Path,
    pair_universe_sha256: str,
    source_inventory_path: Path,
    source_inventory_sha256: str,
    pair_universe: dict[str, Any],
) -> dict[str, Any]:
    generator_path = Path(__file__).resolve()
    return {
        "artifact_type": "candidate_pair_universe_complete",
        "version": "v0.1",
        "status": "final",
        "pair_universe": {
            "path": display_path(pair_universe_path),
            "sha256": pair_universe_sha256,
        },
        "source_inventory": {
            "path": display_path(source_inventory_path),
            "sha256": source_inventory_sha256,
        },
        "generator": {
            "path": display_path(generator_path),
            "sha256": sha256_file(generator_path),
            "version": "candidate_pair_universe_v0.1",
        },
        "counts": {
            "lectures": len(pair_universe["lectures"]),
            "knowledge_objects": pair_universe["total_ko_count"],
            "pairs": pair_universe["total_pair_count"],
        },
    }


def write_outputs(
    *,
    output_path: Path,
    marker_path: Path,
    pair_universe: dict[str, Any],
    source_inventory_path: Path,
    source_inventory_sha256: str,
    overwrite: bool,
) -> None:
    existing = [path for path in (output_path, marker_path) if path.exists()]
    if existing and not overwrite:
        joined = ", ".join(display_path(path) for path in existing)
        raise CandidatePairUniverseError(
            f"Refusing to overwrite existing artifact(s): {joined}."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = serialize_json(pair_universe)
    output_path.write_text(output_text, encoding="utf-8")
    marker = build_completion_marker(
        pair_universe_path=output_path,
        pair_universe_sha256=sha256_bytes(output_text.encode("utf-8")),
        source_inventory_path=source_inventory_path,
        source_inventory_sha256=source_inventory_sha256,
        pair_universe=pair_universe,
    )
    marker_path.write_text(serialize_json(marker), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate every unordered non-self pair within each lecture of a "
            "normalized predicted-KO inventory."
        )
    )
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--completion-marker", default=str(DEFAULT_MARKER))
    parser.add_argument(
        "--benchmark-split",
        choices=sorted(PAIR_ID_PREFIX),
        default="development",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace both output artifacts. Omit for the first formal generation.",
    )
    return parser.parse_args()


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    inventory_path = resolve_path(args.inventory)
    output_path = resolve_path(args.output)
    marker_path = resolve_path(args.completion_marker)
    try:
        inventory_raw = inventory_path.read_bytes()
        inventory = json.loads(inventory_raw.decode("utf-8"))
        if not isinstance(inventory, dict):
            raise CandidatePairUniverseError(
                "Predicted-KO inventory must be a JSON object."
            )
        inventory_hash = sha256_bytes(inventory_raw)
        pair_universe = build_pair_universe(
            inventory,
            source_inventory_path=display_path(inventory_path),
            source_inventory_sha256=inventory_hash,
            benchmark_split=args.benchmark_split,
        )
        write_outputs(
            output_path=output_path,
            marker_path=marker_path,
            pair_universe=pair_universe,
            source_inventory_path=inventory_path,
            source_inventory_sha256=inventory_hash,
            overwrite=args.overwrite,
        )
    except (OSError, json.JSONDecodeError, CandidatePairUniverseError) as exc:
        print(f"Candidate pair universe generation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {pair_universe['total_pair_count']} pairs to "
        f"{display_path(output_path)}"
    )
    print(f"Completion marker {display_path(marker_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
