#!/usr/bin/env python3
"""Create a hash-bound repository freeze manifest for Connection Discovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_binding(binding: dict[str, Any], repository_root: Path) -> None:
    path = repository_root / binding["path"]
    if not path.is_file():
        raise ValueError(f"Missing bound artifact: {path}")
    actual = sha256_path(path)
    if actual != binding["sha256"]:
        raise ValueError(f"Stale artifact binding: {binding['path']}")


def create_manifest(
    completion: dict[str, Any],
    *,
    completion_path: Path,
    benchmark_content_commit: str,
    repository_root: Path,
) -> dict[str, Any]:
    if not COMMIT_RE.fullmatch(benchmark_content_commit):
        raise ValueError("benchmark_content_commit must be a 40-character SHA-1 hash.")
    if completion.get("status") != "ready_for_repository_freeze":
        raise ValueError("003-0 completion is not ready for repository freeze.")
    if completion.get("model_execution_allowed") is not False:
        raise ValueError("Pre-freeze completion unexpectedly permits model execution.")

    artifacts = completion.get("artifacts", {})
    for name, binding in artifacts.items():
        if name == "schemas":
            for schema_binding in binding:
                verify_binding(schema_binding, repository_root)
        else:
            verify_binding(binding, repository_root)

    return {
        "artifact_type": "connection_discovery_benchmark_freeze_manifest",
        "version": "v0.1",
        "status": "frozen_content_binding",
        "benchmark_id": "connection_discovery_development_v0_1",
        "benchmark_content_commit": benchmark_content_commit,
        "freeze_effective_when_manifest_is_committed": True,
        "completion": {
            "path": str(completion_path),
            "sha256": sha256_path(repository_root / completion_path),
        },
        "frozen_artifacts": artifacts,
        "frozen_counts": completion["counts"],
        "scope_limitations": completion.get("scope_limitations", []),
        "execution_rules": {
            "model_execution_before_manifest_commit": "forbidden",
            "benchmark_content_changes": "require a new benchmark version",
            "annotation_changes_after_model_output": "forbidden",
            "candidate_method_development": "allowed only as Experiment 003 development",
            "independent_validation_claim": "forbidden for this development source",
            "required_run_binding": [
                "freeze manifest SHA-256",
                "execution repository commit",
                "candidate method and parameter hashes",
                "input pair universe and canonical inventory hashes"
            ]
        },
        "next_stage": "003-1_oracle_canonical_candidate_generation"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completion", required=True, type=Path)
    parser.add_argument("--benchmark-content-commit", required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repository_root.resolve()
    manifest = create_manifest(
        load_json(args.completion),
        completion_path=args.completion,
        benchmark_content_commit=args.benchmark_content_commit,
        repository_root=root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote benchmark freeze manifest to {args.output}")
    print("The freeze becomes effective only after this manifest is committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
