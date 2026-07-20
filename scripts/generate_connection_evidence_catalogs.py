#!/usr/bin/env python3
"""Generate gold-blind candidate-scoped Evidence catalogs for Connection pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_blocks(text: str) -> list[str]:
    if "\n---\n" not in text:
        raise ValueError("Lecture is missing the metadata/content separator.")
    content = text.split("\n---\n", 1)[1].strip()
    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    if not blocks:
        raise ValueError("Lecture has no semantic Evidence blocks.")
    for block in blocks:
        if block not in text:
            raise AssertionError("Generated Evidence block is not an exact substring.")
    return blocks


def build_catalogs(
    source_manifest: dict[str, Any],
    pair_universe: dict[str, Any],
    *,
    repository_root: Path,
    source_manifest_path: Path,
    pair_universe_path: Path,
) -> dict[str, Any]:
    lecture_records = source_manifest.get("lectures")
    pairs = pair_universe.get("pairs")
    if not isinstance(lecture_records, list) or not lecture_records:
        raise ValueError("Source manifest must contain lectures.")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Pair universe must contain pairs.")
    if pair_universe.get("gold_fields_present") is not False:
        raise ValueError("Evidence catalogs require a gold-free pair universe.")

    lectures: dict[str, dict[str, Any]] = {}
    for order, record in enumerate(lecture_records):
        lecture_id = record.get("lecture_id")
        path_value = record.get("path")
        if not lecture_id or not path_value or lecture_id in lectures:
            raise ValueError("Lecture IDs and paths must be non-empty and unique.")
        path = repository_root / path_value
        if not path.is_file():
            raise ValueError(f"Missing lecture file: {path}")
        text = path.read_text(encoding="utf-8")
        lectures[lecture_id] = {
            "order": order,
            "path": path_value,
            "sha256": sha256_path(path),
            "blocks": semantic_blocks(text),
        }

    catalogs: list[dict[str, Any]] = []
    seen_pair_ids: set[str] = set()
    total_items = 0
    for pair in pairs:
        pair_id = pair.get("canonical_pair_id")
        if not pair_id or pair_id in seen_pair_ids:
            raise ValueError(f"Invalid or duplicate pair ID: {pair_id!r}")
        seen_pair_ids.add(pair_id)
        lecture_ids = set(pair["ko_a"].get("lecture_ids", [])) | set(
            pair["ko_b"].get("lecture_ids", [])
        )
        unknown = lecture_ids - set(lectures)
        if unknown:
            raise ValueError(f"Pair {pair_id} references unknown lectures: {unknown}")

        evidence_items: list[dict[str, Any]] = []
        ordered_lectures = sorted(lecture_ids, key=lambda item: lectures[item]["order"])
        for lecture_id in ordered_lectures:
            for block_index, block in enumerate(lectures[lecture_id]["blocks"], start=1):
                evidence_items.append(
                    {
                        "evidence_id": f"evidence_{len(evidence_items) + 1:03d}",
                        "lecture_id": lecture_id,
                        "block_index": block_index,
                        "span": block,
                    }
                )
        if not evidence_items:
            raise AssertionError(f"Pair {pair_id} has an empty Evidence catalog.")
        total_items += len(evidence_items)
        catalogs.append(
            {
                "canonical_pair_id": pair_id,
                "endpoint_ids": sorted(
                    [pair["ko_a"]["canonical_ko_id"], pair["ko_b"]["canonical_ko_id"]]
                ),
                "evidence_items": evidence_items,
            }
        )

    return {
        "artifact_type": "connection_evidence_catalog_bundle",
        "version": "v0.1",
        "status": "ready_to_freeze",
        "split": pair_universe.get("split", "development"),
        "catalog_scope": "one_opaque_id_namespace_per_canonical_pair",
        "inputs": {
            "source_manifest": {
                "path": str(source_manifest_path),
                "sha256": sha256_path(source_manifest_path),
            },
            "pair_universe": {
                "path": str(pair_universe_path),
                "sha256": sha256_path(pair_universe_path),
            },
            "lectures": [
                {
                    "lecture_id": record["lecture_id"],
                    "path": record["path"],
                    "sha256": lectures[record["lecture_id"]]["sha256"],
                }
                for record in lecture_records
            ],
        },
        "counts": {
            "pairs": len(catalogs),
            "catalogs": len(catalogs),
            "evidence_items": total_items,
        },
        "gold_fields_present": False,
        "catalogs": catalogs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--pair-universe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalogs = build_catalogs(
        load_json(args.source_manifest),
        load_json(args.pair_universe),
        repository_root=args.repository_root.resolve(),
        source_manifest_path=args.source_manifest,
        pair_universe_path=args.pair_universe,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalogs, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {catalogs['counts']['catalogs']} candidate-scoped Evidence catalogs "
        f"with {catalogs['counts']['evidence_items']} items to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
