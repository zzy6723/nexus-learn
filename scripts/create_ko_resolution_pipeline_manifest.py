#!/usr/bin/env python3
"""Freeze the complete 002C-5 canonicalization pipeline by artifact hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "experiments/knowledge_object_resolution/002c_5_independent_validation"
    / "full_pipeline_manifest_v0_1.json"
)
SELECTED_RESOLVER_COMMIT = "46d5a2937f0a33a3c7eb157da8c8d58bd4451a14"
SELECTED_RUNNER_SHA256 = "30d7878f03af7b922f24d2359fdeb66fa2a8dcae30f5d4ca7217ff3dd11556ea"
SELECTED_PROMPT_SHA256 = "11531eff52fa8b0e76c05cb7f33eabe5cfc06b9b4c394452ab6929989c329b1d"
VERSION = "ko_resolution_full_pipeline_manifest_v0.1"


class PipelineManifestError(ValueError):
    """Raised when the frozen full-pipeline artifact set is incomplete."""


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
        raise PipelineManifestError(f"Missing component: {display_path(path)}")
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


def build_manifest() -> dict[str, Any]:
    components = {
        "benchmark_completion": ROOT / "benchmark/ko_canonicalization/independent_v0_1/benchmark_complete.json",
        "success_criteria": ROOT / "benchmark/ko_canonicalization/independent_v0_1/success_criteria.json",
        "normalization_config": ROOT / "benchmark/ko_name_normalization_v0_1.json",
        "alias_resource": ROOT / "benchmark/ko_aliases_v0_1.json",
        "candidate_generator": ROOT / "scripts/generate_ko_identity_candidates.py",
        "candidate_completion": ROOT / "experiments/knowledge_object_resolution/002c_5_independent_validation/runs/independent_v0_1/candidates/candidate_generation_complete.json",
        "resolver_runner": ROOT / "scripts/run_context_ko_resolution_v0_2.py",
        "resolver_prompt": ROOT / "experiments/knowledge_object_resolution/002c_4_evidence_id_resolution/prompt.md",
        "resolver_contract": ROOT / "experiments/knowledge_object_resolution/002c_4_evidence_id_resolution/method_contract_v0_2.md",
        "cluster_finalizer": ROOT / "scripts/finalize_context_ko_clusters.py",
        "stable_id_implementation": ROOT / "scripts/run_deterministic_ko_canonicalization.py",
        "pipeline_evaluator": ROOT / "scripts/evaluate_context_ko_resolution.py",
        "determinism_checker": ROOT / "scripts/check_context_ko_resolution_determinism.py",
        "evidence_review_protocol": ROOT / "benchmark/ko_identity_evidence_review_protocol.md",
        "evidence_review_set_generator": ROOT / "scripts/create_ko_identity_evidence_review_set.py",
        "evidence_audit_finalizer": ROOT / "scripts/finalize_ko_identity_evidence_audit.py",
        "independent_validation_finalizer": ROOT / "scripts/finalize_ko_independent_validation.py",
        "annotation_guidelines": ROOT / "benchmark/ko_canonicalization_annotation_guidelines.md",
        "evaluation_protocol": ROOT / "benchmark/ko_canonicalization_protocol.md",
    }
    bindings = {name: binding(path) for name, path in components.items()}
    if bindings["resolver_runner"]["sha256"] != SELECTED_RUNNER_SHA256:
        raise PipelineManifestError("Resolver runner differs from selected v0.2.1 bytes.")
    if bindings["resolver_prompt"]["sha256"] != SELECTED_PROMPT_SHA256:
        raise PipelineManifestError("Resolver prompt differs from selected v0.2.1 bytes.")
    return {
        "artifact_type": "ko_resolution_full_pipeline_manifest",
        "version": "v0.1",
        "status": "frozen_pre_independent_execution",
        "pipeline_id": "ko_canonicalization_pipeline_v0_2_1",
        "selected_resolver": {
            "method_id": "candidate_scoped_context_resolution_evidence_ids_v0_2_1",
            "development_selection_commit": SELECTED_RESOLVER_COMMIT,
            "runner_sha256": SELECTED_RUNNER_SHA256,
            "prompt_sha256": SELECTED_PROMPT_SHA256,
        },
        "components": bindings,
        "model_request": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "request_partitioning": "one_identity_candidate_per_request_v0_1",
        },
        "pipeline_contract": {
            "normalization": "frozen deterministic normalization before candidate generation",
            "candidate_generation": "Ground-Truth-blind frozen rules with no manual pair additions",
            "evidence_catalog": "candidate-scoped exact paragraph blocks with opaque IDs",
            "resolution": "SAME_OBJECT, DISTINCT_OBJECT, or UNRESOLVED under v0.2.1",
            "clustering": "SAME_OBJECT connected components with DISTINCT_OBJECT contradiction checks",
            "canonical_id": "SHA-256-derived from type, context identity key, and sorted mention IDs",
            "provenance": "every mention assigned once with original upstream source spans retained",
            "evidence_review": "snapshot-bound blind human review before aggregate metrics are opened",
        },
        "freeze_rules": {
            "component_changes_after_independent_execution": "forbidden",
            "failure_handling": "downgrade source to development and require a new independent source",
            "production_claim_from_single_source": "forbidden",
        },
        "generator": {**binding(Path(__file__).resolve()), "version": VERSION},
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output).resolve()
    try:
        if args.check and args.overwrite:
            raise PipelineManifestError("--check and --overwrite cannot be combined.")
        expected = build_manifest()
        if args.check:
            try:
                current = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PipelineManifestError(f"Unable to read pipeline manifest: {exc}") from exc
            if current != expected:
                raise PipelineManifestError("Full pipeline manifest is stale.")
        else:
            if output.exists() and not args.overwrite:
                raise PipelineManifestError(f"Refusing to overwrite: {display_path(output)}")
            atomic_write(output, expected)
    except PipelineManifestError as exc:
        print(f"Full pipeline freeze failed: {exc}")
        return 1
    print(f"{'Validated' if args.check else 'Wrote'} full pipeline manifest: {display_path(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
