#!/usr/bin/env python3
"""Finalize the immutable six-lecture Entity source bundle for 002B-1."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import prepare_predicted_ko_relation_run as preflight
    from . import run_entity_extraction as entity_runner
except ImportError:  # Direct execution: python3 scripts/finalize_entity_prediction_bundle.py
    import prepare_predicted_ko_relation_run as preflight
    import run_entity_extraction as entity_runner


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILENAME = "entity_source_bundle.json"
MARKER_FILENAME = "entity_predictions_complete.json"
MANAGED_DIRECTORIES = {
    "output": "output",
    "metadata": "metadata",
    "raw_response": "raw_responses",
    "rendered_input": "rendered_inputs",
}


class EntityBundleError(RuntimeError):
    """A fatal Entity source-bundle readiness error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate all reused and newly generated Entity artifacts for one "
            "002B-1 execution manifest, then write an immutable source bundle "
            "and completion marker."
        )
    )
    parser.add_argument("--execution-manifest", required=True)
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def read_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EntityBundleError(
            "invalid_json", f"Unable to read {label} {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise EntityBundleError("invalid_shape", f"{label} must be an object.")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def required_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EntityBundleError("invalid_shape", f"{label} must be an object.")
    return value


def required_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise EntityBundleError("invalid_shape", f"{label} must be a list.")
    return value


def validate_exact_directory_contents(
    *, entity_dir: Path, lecture_ids: list[str]
) -> None:
    expected = {f"{lecture_id}.json" for lecture_id in lecture_ids}
    for directory_name in MANAGED_DIRECTORIES.values():
        directory = entity_dir / directory_name
        if not directory.is_dir():
            raise EntityBundleError(
                "missing_artifact_directory", f"Missing Entity directory: {directory}"
            )
        actual = {path.name for path in directory.iterdir() if path.is_file()}
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise EntityBundleError(
                "artifact_set_mismatch",
                f"{directory_name} artifact set mismatch; missing={missing}, "
                f"unexpected={unexpected}.",
            )


def validate_common_artifacts(
    *,
    lecture_id: str,
    paths: dict[str, Path],
    lecture_text: str,
    prompt_path: Path,
    entity_execution: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    output = read_object(paths["output"], label=f"{lecture_id} parsed output")
    metadata = read_object(paths["metadata"], label=f"{lecture_id} metadata")
    raw_response = read_object(
        paths["raw_response"], label=f"{lecture_id} raw response"
    )
    rendered_input = read_object(
        paths["rendered_input"], label=f"{lecture_id} rendered input"
    )

    try:
        entity_runner.validate_prediction_envelope(output, lecture_id=lecture_id)
    except RuntimeError as exc:
        raise EntityBundleError(
            "invalid_prediction_schema", f"{lecture_id}: {exc}"
        ) from exc

    parameters = required_object(
        entity_execution.get("request_parameters"),
        label="entity_execution.request_parameters",
    )
    expected_payload = preflight.expected_entity_payload(
        prompt_path=prompt_path,
        lecture_id=lecture_id,
        lecture_text=lecture_text,
        model=entity_execution.get("model"),
        temperature=parameters.get("temperature"),
        top_p=parameters.get("top_p"),
        max_tokens=parameters.get("max_tokens"),
    )
    if rendered_input != expected_payload:
        raise EntityBundleError(
            "rendered_payload_mismatch",
            f"{lecture_id} rendered request differs from the frozen method.",
        )
    try:
        raw_prediction = preflight.raw_prediction_from_response(raw_response)
    except preflight.PreflightError as exc:
        raise EntityBundleError(
            "invalid_raw_response", f"{lecture_id}: {exc}"
        ) from exc
    if raw_prediction != output:
        raise EntityBundleError(
            "raw_parsed_mismatch",
            f"{lecture_id} parsed output differs from raw response content.",
        )

    expected_metadata = {
        "provider": entity_execution.get("provider"),
        "lecture_id": lecture_id,
        "model_requested": entity_execution.get("model"),
        "temperature": parameters.get("temperature"),
        "top_p": parameters.get("top_p"),
        "max_tokens": parameters.get("max_tokens"),
        "prompt_sha256": preflight.sha256_file(prompt_path),
        "input_sha256": preflight.sha256_text(lecture_text),
        "request_success": True,
        "json_parse_success": True,
        "finish_reason": "stop",
    }
    mismatches = [
        field
        for field, expected in expected_metadata.items()
        if metadata.get(field) != expected
    ]
    if mismatches:
        raise EntityBundleError(
            "metadata_mismatch",
            f"{lecture_id} metadata mismatch: {sorted(mismatches)}.",
        )
    if metadata.get("request_payload_sha256") not in {
        None,
        preflight.sha256_json(expected_payload),
    }:
        raise EntityBundleError(
            "request_payload_hash_mismatch",
            f"{lecture_id} metadata has a stale request payload hash.",
        )
    return output, metadata


def validate_rerun_metadata(
    *,
    lecture_id: str,
    metadata: dict[str, Any],
    method_commit: str,
    execution_manifest_path: Path,
    source_manifest_path: Path,
    expected_input_sha256: str,
    paths: dict[str, Path],
) -> None:
    if (
        metadata.get("run_status") != "completed"
        or metadata.get("prediction_schema_valid") is not True
        or metadata.get("git_commit_at_start") != method_commit
        or metadata.get("git_dirty_at_start") is not False
        or metadata.get("retry_count") != 0
        or metadata.get("repair_status") != "not_attempted"
    ):
        raise EntityBundleError(
            "invalid_rerun_metadata",
            f"{lecture_id} is not a clean completed manifest-bound rerun.",
        )

    binding = required_object(
        metadata.get("execution_binding"),
        label=f"{lecture_id}.execution_binding",
    )
    expected_binding = {
        "execution_manifest": display_path(execution_manifest_path),
        "execution_manifest_sha256": preflight.sha256_file(
            execution_manifest_path
        ),
        "method_commit": method_commit,
        "source_manifest": display_path(source_manifest_path),
        "source_manifest_sha256": preflight.sha256_file(source_manifest_path),
        "expected_input_sha256": expected_input_sha256,
    }
    if binding != expected_binding:
        raise EntityBundleError(
            "stale_execution_binding",
            f"{lecture_id} metadata is not bound to the current execution plan.",
        )
    if metadata.get("raw_response_sha256") != preflight.sha256_file(
        paths["raw_response"]
    ) or metadata.get("prediction_sha256") != preflight.sha256_file(
        paths["output"]
    ):
        raise EntityBundleError(
            "rerun_artifact_hash_mismatch",
            f"{lecture_id} rerun metadata has stale artifact hashes.",
        )


def validate_reused_hashes(
    *,
    lecture_id: str,
    source_record: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    source_hashes = required_object(
        source_record.get("source_sha256"),
        label=f"{lecture_id}.source_sha256",
    )
    mismatches = [
        artifact
        for artifact, path in paths.items()
        if source_hashes.get(artifact) != preflight.sha256_file(path)
    ]
    if mismatches:
        raise EntityBundleError(
            "reused_artifact_hash_mismatch",
            f"{lecture_id} reusable artifact changed: {sorted(mismatches)}.",
        )


def finalize_entity_bundle(execution_manifest_path: Path) -> dict[str, Any]:
    execution_manifest_path = execution_manifest_path.resolve()
    execution = read_object(
        execution_manifest_path, label="002B-1 execution manifest"
    )
    if (
        execution.get("artifact_type")
        != "predicted_ko_relation_execution_manifest"
        or execution.get("version") != "v0.1"
        or execution.get("status") != "prepared_pending_entity_reruns"
    ):
        raise EntityBundleError(
            "invalid_execution_manifest",
            "Execution manifest is not a prepared 002B-1 Entity-rerun plan.",
        )

    entity_dir = execution_manifest_path.parent / "entity_predictions"
    bundle_path = entity_dir / BUNDLE_FILENAME
    marker_path = entity_dir / MARKER_FILENAME
    existing = [path for path in [bundle_path, marker_path] if path.exists()]
    if existing:
        raise EntityBundleError(
            "output_exists",
            f"Entity source bundle already exists: {[str(path) for path in existing]}",
        )

    method_commit = execution.get("method_commit")
    if not isinstance(method_commit, str):
        raise EntityBundleError("invalid_execution_manifest", "Missing method commit.")
    repository_state = required_object(
        execution.get("repository_state"), label="repository_state"
    )
    if (
        repository_state.get("head_commit") != method_commit
        or repository_state.get("worktree_clean") is not True
    ):
        raise EntityBundleError(
            "invalid_repository_state", "Execution repository state is not verified."
        )

    frozen_methods = required_object(
        execution.get("frozen_methods"), label="frozen_methods"
    )
    implementation = required_list(
        frozen_methods.get("implementation"),
        label="frozen_methods.implementation",
    )
    finalizer_path = Path(__file__).resolve()
    finalizer_records = [
        item
        for item in implementation
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and resolve_path(item["path"]).resolve() == finalizer_path
    ]
    if (
        len(finalizer_records) != 1
        or finalizer_records[0].get("sha256")
        != preflight.sha256_file(finalizer_path)
    ):
        raise EntityBundleError(
            "stale_finalizer", "Entity bundle finalizer differs from the frozen method."
        )
    prompt_record = required_object(
        frozen_methods.get("entity_prompt"), label="frozen_methods.entity_prompt"
    )
    prompt_path_text = prompt_record.get("path")
    if not isinstance(prompt_path_text, str):
        raise EntityBundleError("invalid_execution_manifest", "Missing Entity prompt path.")
    prompt_path = resolve_path(prompt_path_text)
    if prompt_record.get("sha256") != preflight.sha256_file(prompt_path):
        raise EntityBundleError("stale_prompt", "Frozen Entity prompt hash is stale.")

    entity_execution = required_object(
        execution.get("entity_execution"), label="entity_execution"
    )
    source_manifest_text = entity_execution.get("source_manifest")
    if not isinstance(source_manifest_text, str):
        raise EntityBundleError(
            "invalid_execution_manifest", "Missing source manifest path."
        )
    source_manifest_path = resolve_path(source_manifest_text)
    if entity_execution.get("source_manifest_sha256") != preflight.sha256_file(
        source_manifest_path
    ):
        raise EntityBundleError("stale_source_manifest", "Source manifest hash is stale.")
    source_manifest = read_object(source_manifest_path, label="Entity source manifest")
    if (
        source_manifest.get("artifact_type") != "entity_prediction_source_manifest"
        or source_manifest.get("status") != "prepared_pending_entity_reruns"
        or source_manifest.get("method_commit") != method_commit
    ):
        raise EntityBundleError(
            "invalid_source_manifest", "Source manifest is not the frozen rerun plan."
        )

    benchmark = required_object(execution.get("benchmark"), label="benchmark")
    lecture_ids = required_list(benchmark.get("lecture_ids"), label="lecture_ids")
    if (
        not lecture_ids
        or not all(isinstance(value, str) and value for value in lecture_ids)
        or len(lecture_ids) != len(set(lecture_ids))
    ):
        raise EntityBundleError("invalid_lecture_set", "Lecture IDs are invalid.")
    source_records = required_list(
        source_manifest.get("lectures"), label="source_manifest.lectures"
    )
    source_by_id = {
        item.get("lecture_id"): item
        for item in source_records
        if isinstance(item, dict) and isinstance(item.get("lecture_id"), str)
    }
    if len(source_by_id) != len(source_records) or set(source_by_id) != set(lecture_ids):
        raise EntityBundleError(
            "source_plan_lecture_mismatch",
            "Source manifest lecture set differs from the execution manifest.",
        )

    lecture_inventory_record = required_object(
        benchmark.get("lecture_inventory"), label="benchmark.lecture_inventory"
    )
    lecture_inventory_text = lecture_inventory_record.get("path")
    if not isinstance(lecture_inventory_text, str):
        raise EntityBundleError(
            "invalid_execution_manifest", "Missing lecture inventory path."
        )
    lecture_inventory_path = resolve_path(lecture_inventory_text)
    if lecture_inventory_record.get("sha256") != preflight.sha256_file(
        lecture_inventory_path
    ):
        raise EntityBundleError("stale_lecture_inventory", "Lecture inventory is stale.")
    lecture_inventory = read_object(
        lecture_inventory_path, label="lecture inventory"
    )
    lecture_records = required_list(
        lecture_inventory.get("lectures"), label="lecture_inventory.lectures"
    )
    lecture_text_by_id = {
        item.get("lecture_id"): item.get("text")
        for item in lecture_records
        if isinstance(item, dict)
        and isinstance(item.get("lecture_id"), str)
        and isinstance(item.get("text"), str)
    }
    if set(lecture_text_by_id) != set(lecture_ids):
        raise EntityBundleError(
            "lecture_inventory_mismatch", "Lecture inventory does not cover the plan."
        )
    lecture_hashes = required_object(
        benchmark.get("lecture_model_text_sha256"),
        label="benchmark.lecture_model_text_sha256",
    )
    for lecture_id in lecture_ids:
        if lecture_hashes.get(lecture_id) != preflight.sha256_text(
            lecture_text_by_id[lecture_id]
        ):
            raise EntityBundleError(
                "lecture_hash_mismatch", f"Frozen lecture hash is stale: {lecture_id}."
            )

    validate_exact_directory_contents(entity_dir=entity_dir, lecture_ids=lecture_ids)

    finalized_records: list[dict[str, Any]] = []
    reused_count = 0
    rerun_count = 0
    for lecture_id in lecture_ids:
        source_record = source_by_id[lecture_id]
        decision = source_record.get("decision")
        if decision not in {"reuse", "rerun_required"}:
            raise EntityBundleError(
                "invalid_source_decision", f"Invalid source decision for {lecture_id}."
            )
        paths = {
            artifact: entity_dir / directory / f"{lecture_id}.json"
            for artifact, directory in MANAGED_DIRECTORIES.items()
        }
        _, metadata = validate_common_artifacts(
            lecture_id=lecture_id,
            paths=paths,
            lecture_text=lecture_text_by_id[lecture_id],
            prompt_path=prompt_path,
            entity_execution=entity_execution,
        )
        if decision == "reuse":
            reused_count += 1
            validate_reused_hashes(
                lecture_id=lecture_id,
                source_record=source_record,
                paths=paths,
            )
            provenance = "reused"
            source_run = source_record.get("source_run")
        else:
            rerun_count += 1
            validate_rerun_metadata(
                lecture_id=lecture_id,
                metadata=metadata,
                method_commit=method_commit,
                execution_manifest_path=execution_manifest_path,
                source_manifest_path=source_manifest_path,
                expected_input_sha256=lecture_hashes[lecture_id],
                paths=paths,
            )
            provenance = "new_rerun"
            source_run = display_path(execution_manifest_path.parent)

        finalized_records.append({
            "lecture_id": lecture_id,
            "provenance": provenance,
            "source_run": source_run,
            "artifacts": {
                artifact: {
                    "path": display_path(path),
                    "sha256": preflight.sha256_file(path),
                }
                for artifact, path in paths.items()
            },
            "request_id": metadata.get("request_id"),
            "run_timestamp": metadata.get("run_timestamp"),
            "model_returned": metadata.get("model_returned"),
            "finish_reason": metadata.get("finish_reason"),
        })

    source_counts = required_object(
        source_manifest.get("counts"), label="source_manifest.counts"
    )
    if (
        source_counts.get("lectures") != len(lecture_ids)
        or source_counts.get("reused") != reused_count
        or source_counts.get("rerun_required") != rerun_count
    ):
        raise EntityBundleError(
            "source_count_mismatch", "Source manifest counts are inconsistent."
        )

    artifact_set = [
        {
            "lecture_id": item["lecture_id"],
            "provenance": item["provenance"],
            "hashes": {
                name: record["sha256"]
                for name, record in item["artifacts"].items()
            },
        }
        for item in finalized_records
    ]
    counts = {
        "lectures": len(lecture_ids),
        "reused": reused_count,
        "new_reruns": rerun_count,
        "missing": 0,
        "invalid": 0,
        "plan_violations": 0,
    }
    bundle = {
        "artifact_type": "entity_prediction_source_bundle",
        "version": "v0.1",
        "status": "final",
        "experiment": execution.get("experiment"),
        "split": execution.get("split"),
        "method_commit": method_commit,
        "execution_manifest": {
            "path": display_path(execution_manifest_path),
            "sha256": preflight.sha256_file(execution_manifest_path),
        },
        "source_plan": {
            "path": display_path(source_manifest_path),
            "sha256": preflight.sha256_file(source_manifest_path),
        },
        "entity_prompt": prompt_record,
        "entity_execution": {
            "provider": entity_execution.get("provider"),
            "model": entity_execution.get("model"),
            "request_parameters": entity_execution.get("request_parameters"),
        },
        "counts": counts,
        "artifact_set_sha256": preflight.sha256_json(artifact_set),
        "lectures": finalized_records,
    }
    write_json_atomic(bundle_path, bundle)
    marker = {
        "artifact_type": "entity_predictions_completion_marker",
        "version": "v0.1",
        "status": "final",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "method_commit": method_commit,
        "execution_manifest_sha256": preflight.sha256_file(
            execution_manifest_path
        ),
        "source_manifest_sha256": preflight.sha256_file(source_manifest_path),
        "entity_source_bundle": display_path(bundle_path),
        "entity_source_bundle_sha256": preflight.sha256_file(bundle_path),
        "artifact_set_sha256": bundle["artifact_set_sha256"],
        "counts": counts,
    }
    try:
        write_json_atomic(marker_path, marker)
    except Exception:
        bundle_path.unlink(missing_ok=True)
        raise
    return marker


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        marker = finalize_entity_bundle(resolve_path(args.execution_manifest))
    except EntityBundleError as exc:
        print(
            f"Entity bundle finalization failed [{exc.code}]: {exc}",
            file=sys.stderr,
        )
        return 1
    print(
        "Wrote final Entity source bundle "
        f"({marker['counts']['lectures']} lectures)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
