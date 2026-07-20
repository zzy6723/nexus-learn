#!/usr/bin/env python3
"""Create a method-blind semantic Evidence review package for KO identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.finalize_context_ko_clusters import validate_sources


PROTOCOL = ROOT / "benchmark/ko_identity_evidence_review_protocol.md"
VERSION = "ko_identity_evidence_review_set_v0.1"


class EvidenceReviewSetError(ValueError):
    """Raised when a blind review package cannot be created safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--resolution-run-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise EvidenceReviewSetError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


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


def build_review_set(
    candidates: dict[str, Any], decisions: dict[str, Any], prediction_path: Path
) -> dict[str, Any]:
    candidate_by_id = {item["candidate_id"]: item for item in candidates["candidates"]}
    results = decisions.get("results")
    if not isinstance(results, list) or {item.get("candidate_id") for item in results} != set(candidate_by_id):
        raise EvidenceReviewSetError("Predictions do not align with the candidate set.")
    items = []
    for index, result in enumerate(sorted(results, key=lambda item: item["candidate_id"]), start=1):
        candidate = candidate_by_id[result["candidate_id"]]
        evidence_ids = result.get("evidence_ids")
        evidence_spans = result.get("evidence_spans")
        if not isinstance(evidence_ids, list) or not isinstance(evidence_spans, list):
            raise EvidenceReviewSetError("Prediction lacks Evidence ID materialization.")
        if len(evidence_ids) != len(evidence_spans):
            raise EvidenceReviewSetError("Evidence IDs and spans do not align.")
        items.append(
            {
                "review_item_id": f"ko_evidence_review_{index:03d}",
                "candidate_id": result["candidate_id"],
                "mention_a": {
                    key: candidate["mention_a"][key]
                    for key in ("mention_id", "lecture_id", "name", "type")
                },
                "mention_b": {
                    key: candidate["mention_b"][key]
                    for key in ("mention_id", "lecture_id", "name", "type")
                },
                "predicted_decision": result["decision"],
                "selected_evidence": [
                    {"evidence_id": evidence_id, **span}
                    for evidence_id, span in zip(evidence_ids, evidence_spans, strict=True)
                ],
                "rationale": result["rationale"],
            }
        )
    return {
        "artifact_type": "ko_identity_evidence_blind_review_set",
        "version": "v0.1",
        "status": "ready_for_blind_review",
        "prediction_sha256": sha256_file(prediction_path),
        "review_protocol": binding(PROTOCOL),
        "blinding": {
            "method_identity_removed": True,
            "model_identity_removed": True,
            "run_identity_removed": True,
            "gold_identity_removed": True,
            "aggregate_metrics_removed": True,
        },
        "review_item_count": len(items),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidate_dir = Path(args.candidate_dir).resolve()
    resolution_dir = Path(args.resolution_run_dir).resolve()
    output = Path(args.output).resolve()
    try:
        if output.exists() and not args.overwrite:
            raise EvidenceReviewSetError(f"Refusing to overwrite: {display_path(output)}")
        candidates, decisions, _ = validate_sources(candidate_dir, resolution_dir)
        prediction_path = resolution_dir / "output/identity_decisions.json"
        review_set = build_review_set(candidates, decisions, prediction_path)
        atomic_write(output, review_set)
    except (OSError, ValueError) as exc:
        print(f"Evidence review-set creation failed: {exc}")
        return 1
    print(f"Wrote {review_set['review_item_count']} blind Evidence review items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
