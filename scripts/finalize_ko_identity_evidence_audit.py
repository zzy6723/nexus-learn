#!/usr/bin/env python3
"""Validate blind adjudication and finalize a snapshot-bound Evidence audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


LABELS = {"supported", "not_supported", "pending"}
VERSION = "ko_identity_evidence_audit_finalizer_v0.1"


class EvidenceAuditError(ValueError):
    """Raised when Evidence adjudication is stale, incomplete, or malformed."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", required=True)
    parser.add_argument("--review-set", required=True)
    parser.add_argument("--adjudication", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceAuditError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceAuditError(f"{label} must be a JSON object.")
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


def finalize_audit(
    *, prediction_path: Path, review_path: Path,
    review_set: dict[str, Any], adjudication: dict[str, Any]
) -> dict[str, Any]:
    prediction_hash = sha256_file(prediction_path)
    review_hash = sha256_file(review_path)
    if review_set.get("prediction_sha256") != prediction_hash:
        raise EvidenceAuditError("Review set targets a stale prediction snapshot.")
    if adjudication.get("prediction_sha256") != prediction_hash:
        raise EvidenceAuditError("Adjudication prediction hash is stale.")
    if adjudication.get("review_set_sha256") != review_hash:
        raise EvidenceAuditError("Adjudication review-set hash is stale.")
    items = review_set.get("items")
    decisions = adjudication.get("decisions")
    if not isinstance(items, list) or not isinstance(decisions, list):
        raise EvidenceAuditError("Review items and adjudication decisions must be lists.")
    item_by_id = {item.get("review_item_id"): item for item in items}
    if len(item_by_id) != len(items) or None in item_by_id:
        raise EvidenceAuditError("Review set has duplicate or invalid item IDs.")
    decision_by_id: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        review_id = decision.get("review_item_id")
        label = decision.get("decision")
        rationale = decision.get("rationale")
        if review_id not in item_by_id or review_id in decision_by_id:
            raise EvidenceAuditError("Adjudication has unknown or duplicate review IDs.")
        if label not in LABELS:
            raise EvidenceAuditError("Adjudication label is invalid.")
        if not isinstance(rationale, str):
            raise EvidenceAuditError("Adjudication rationale must be a string.")
        if label != "supported" and not rationale.strip():
            raise EvidenceAuditError("Non-supported decisions require a rationale.")
        decision_by_id[review_id] = decision
    missing = set(item_by_id) - set(decision_by_id)
    if missing:
        raise EvidenceAuditError("Adjudication does not cover every review item.")
    rows = []
    counts = {label: 0 for label in LABELS}
    for review_id in sorted(item_by_id):
        decision = decision_by_id[review_id]
        counts[decision["decision"]] += 1
        rows.append(
            {
                "review_item_id": review_id,
                "candidate_id": item_by_id[review_id]["candidate_id"],
                "decision": decision["decision"],
                "rationale": decision["rationale"],
            }
        )
    status = "final" if counts["pending"] == 0 else "draft_pending_adjudication"
    return {
        "artifact_type": "ko_resolution_evidence_semantic_audit",
        "version": "v0.1",
        "status": status,
        "prediction_sha256": prediction_hash,
        "review_set_sha256": review_hash,
        "adjudication_sha256": None,
        "reviewed_blind": True,
        "counts": {
            "reviewed_candidates": len(rows),
            "supported": counts["supported"],
            "not_supported": counts["not_supported"],
            "pending": counts["pending"],
            "stale_decisions": 0,
            "unused_decisions": 0,
        },
        "decisions": rows,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    prediction = Path(args.prediction).resolve()
    review = Path(args.review_set).resolve()
    adjudication_path = Path(args.adjudication).resolve()
    output = Path(args.output).resolve()
    try:
        if output.exists() and not args.overwrite:
            raise EvidenceAuditError(f"Refusing to overwrite: {output}")
        audit = finalize_audit(
            prediction_path=prediction,
            review_path=review,
            review_set=load_json(review, label="review set"),
            adjudication=load_json(adjudication_path, label="adjudication"),
        )
        audit["adjudication_sha256"] = sha256_file(adjudication_path)
        atomic_write(output, audit)
    except EvidenceAuditError as exc:
        print(f"Evidence audit finalization failed: {exc}")
        return 1
    print(f"Wrote Evidence audit with status: {audit['status']}")
    return 0 if audit["status"] == "final" else 2


if __name__ == "__main__":
    raise SystemExit(main())
