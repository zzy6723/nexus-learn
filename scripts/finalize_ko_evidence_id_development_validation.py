#!/usr/bin/env python3
"""Validate and freeze the complete 002C-4 development result bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments/knowledge_object_resolution/002c_4_evidence_id_resolution"
DEFAULT_OUTPUT = BASE / "development_validation_complete.json"
METHOD_ID = "candidate_scoped_context_resolution_evidence_ids_v0_2_1"
METHOD_COMMIT = "46d5a2937f0a33a3c7eb157da8c8d58bd4451a14"
RUNNER_SHA256 = "30d7878f03af7b922f24d2359fdeb66fa2a8dcae30f5d4ca7217ff3dd11556ea"
PROMPT_SHA256 = "11531eff52fa8b0e76c05cb7f33eabe5cfc06b9b4c394452ab6929989c329b1d"
VERSION = "ko_evidence_id_development_validation_finalizer_v0.1"


class DevelopmentValidationError(ValueError):
    """Raised when the 002C-4 development bundle is incomplete or stale."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
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
        raise DevelopmentValidationError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentValidationError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DevelopmentValidationError(f"{label} must be a JSON object.")
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


def validate_run(run_root: Path, *, expected_candidates: int) -> dict[str, Any]:
    paths = {
        "resolution_completion": run_root / "context/run_01/resolution_complete.json",
        "identity_decisions": run_root / "context/run_01/output/identity_decisions.json",
        "resolution_metadata": run_root / "context/run_01/metadata/run_metadata.json",
        "cluster_completion": run_root / "clusters/run_01/generation_complete.json",
        "canonical_clusters": run_root / "clusters/run_01/canonical_clusters.json",
        "mention_assignments": run_root / "clusters/run_01/mention_assignments.json",
        "metrics": run_root / "evaluation/run_01/metrics.json",
        "evaluation_completion": run_root / "evaluation/run_01/evaluation_complete.json",
        "evidence_semantic_audit": run_root / "evaluation/run_01/evidence_semantic_audit.json",
    }
    resolution = load_json(paths["resolution_completion"], label="resolution completion")
    cluster = load_json(paths["cluster_completion"], label="cluster completion")
    evaluation = load_json(paths["evaluation_completion"], label="evaluation completion")
    metrics = load_json(paths["metrics"], label="metrics")
    audit = load_json(paths["evidence_semantic_audit"], label="evidence audit")
    metadata = load_json(paths["resolution_metadata"], label="resolution metadata")
    decisions = load_json(paths["identity_decisions"], label="identity decisions")

    for label, artifact in (
        ("resolution", resolution),
        ("cluster", cluster),
        ("evaluation", evaluation),
    ):
        if artifact.get("status") != "final":
            raise DevelopmentValidationError(f"{label} artifact is not final.")
        if artifact.get("method_id") != METHOD_ID or artifact.get("method_commit") != METHOD_COMMIT:
            raise DevelopmentValidationError(f"{label} method identity differs from v0.2.1.")
    if metadata.get("method_id") != METHOD_ID or metadata.get("method_commit") != METHOD_COMMIT:
        raise DevelopmentValidationError("Resolution metadata differs from v0.2.1.")
    if metadata.get("runner", {}).get("sha256") != RUNNER_SHA256:
        raise DevelopmentValidationError("Resolution runner bytes differ from v0.2.1.")
    results = decisions.get("results")
    if not isinstance(results, list) or len(results) != expected_candidates:
        raise DevelopmentValidationError("Development decision denominator is invalid.")
    if metrics.get("success_criteria", {}).get("passed") is not True:
        raise DevelopmentValidationError("Development structural criteria did not pass.")
    counts = audit.get("counts", {})
    if (
        audit.get("status") != "final"
        or audit.get("method_id") != METHOD_ID
        or counts.get("reviewed_candidates") != expected_candidates
        or counts.get("supported") != expected_candidates
        or counts.get("not_supported") != 0
        or counts.get("pending") != 0
    ):
        raise DevelopmentValidationError("Development Evidence audit is not fully supported.")
    if audit.get("prediction_sha256") != sha256_file(paths["identity_decisions"]):
        raise DevelopmentValidationError("Development Evidence audit is stale.")
    if evaluation.get("outputs", {}).get("metrics") != binding(paths["metrics"]):
        raise DevelopmentValidationError("Evaluation completion does not bind current metrics.")
    if cluster.get("artifacts", {}).get("canonical_clusters") != binding(paths["canonical_clusters"]):
        raise DevelopmentValidationError("Cluster completion is stale.")
    if cluster.get("artifacts", {}).get("mention_assignments") != binding(paths["mention_assignments"]):
        raise DevelopmentValidationError("Mention assignments are stale.")
    return {name: binding(path) for name, path in paths.items()}


def build_marker() -> dict[str, Any]:
    challenge_root = BASE / "runs/challenge_v0_1_v0_2_1"
    diagnostic_root = BASE / "runs/locked_reuse_diagnostic_v0_1_v0_2_1"
    method_paths = {
        "runner": ROOT / "scripts/run_context_ko_resolution_v0_2.py",
        "prompt": BASE / "prompt.md",
        "contract": BASE / "method_contract_v0_2.md",
        "cluster_finalizer": ROOT / "scripts/finalize_context_ko_clusters.py",
        "challenge_success_criteria": ROOT / "benchmark/ko_canonicalization/challenge_v0_1/success_criteria.json",
        "diagnostic_success_criteria": ROOT / "benchmark/ko_canonicalization/locked_reuse_v0_1/success_criteria.json",
        "development_results": BASE / "development_results.md",
        "conclusion": BASE / "conclusion.md",
    }
    method_bindings = {name: binding(path) for name, path in method_paths.items()}
    if method_bindings["runner"]["sha256"] != RUNNER_SHA256:
        raise DevelopmentValidationError("Selected runner bytes have changed.")
    if method_bindings["prompt"]["sha256"] != PROMPT_SHA256:
        raise DevelopmentValidationError("Selected prompt bytes have changed.")
    return {
        "artifact_type": "ko_evidence_id_development_validation_complete",
        "version": "v0.2",
        "status": "final",
        "selected_method_id": METHOD_ID,
        "selected_method_commit": METHOD_COMMIT,
        "claim_boundary": {
            "development_validation_completed": True,
            "independent_validation_completed": False,
            "production_method_selected": False,
            "development_reviews_blind": False,
        },
        "method": method_bindings,
        "runs": {
            "challenge_v0_1_v0_2_1": validate_run(challenge_root, expected_candidates=11),
            "locked_reuse_diagnostic_v0_1_v0_2_1": validate_run(
                diagnostic_root, expected_candidates=6
            ),
        },
        "generator": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output).resolve()
    try:
        if args.check and args.overwrite:
            raise DevelopmentValidationError("--check and --overwrite cannot be combined.")
        expected = build_marker()
        if args.check:
            if load_json(output, label="development completion marker") != expected:
                raise DevelopmentValidationError("Development completion marker is stale.")
        else:
            if output.exists() and not args.overwrite:
                raise DevelopmentValidationError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except DevelopmentValidationError as exc:
        print(f"002C-4 finalization failed: {exc}")
        return 1
    print(f"{'Validated' if args.check else 'Wrote'} 002C-4 completion marker: {display_path(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
