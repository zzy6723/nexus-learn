#!/usr/bin/env python3
"""Run one prepared 002B-2 downstream Relation diagnostic condition."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_candidate_relation_diagnostic as preparer  # noqa: E402
from scripts import project_candidate_pairs_to_relations as projector  # noqa: E402
from scripts import run_relation_extraction as base_runner  # noqa: E402


DEFAULT_CONTRACT = ROOT / "benchmark" / "candidate_relation_downstream_diagnostic_v0_1.json"
DEFAULT_PREPARATION_ROOT = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "downstream_diagnostic_v0_1"
    / "preparation"
)
DEFAULT_EXECUTION_ROOT = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "downstream_diagnostic_v0_1"
)
CONDITIONS = {"all_pairs", "rule_filtered_v0_1"}
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
AGGREGATE_METADATA_NAME = "selected_relation_ground_truth.json"
RUN_MARKER_NAME = "diagnostic_run_complete.json"


class DiagnosticRunError(RuntimeError):
    """Raised when a downstream diagnostic run violates its frozen contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a prepared candidate-scoped downstream Relation diagnostic."
    )
    parser.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--run-id", default="run_01")
    parser.add_argument("--prepared-dir")
    parser.add_argument("--run-dir")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT.relative_to(ROOT)))
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--preceding-all-pairs-metadata")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    return projector.display_path(path)


def read_json(path: Path, *, label: str) -> dict[str, Any]:
    return projector.read_json(path, label=label)


def binding(path: Path) -> dict[str, str]:
    return projector.binding(path)


def validate_repository_state(
    *,
    expected_commit: str,
    current_commit: str | None,
    dirty: bool | None,
) -> None:
    if not COMMIT_RE.fullmatch(expected_commit):
        raise DiagnosticRunError("--expected-commit must be a full lowercase commit hash.")
    if current_commit != expected_commit:
        raise DiagnosticRunError(
            f"Current commit {current_commit!r} differs from {expected_commit!r}."
        )
    if dirty is not False:
        raise DiagnosticRunError("Diagnostic execution requires a clean working tree.")


def validate_preparation(
    *,
    prepared_dir: Path,
    contract_path: Path,
    condition: str,
) -> dict[str, Any]:
    marker_path = prepared_dir / "preparation_complete.json"
    marker = read_json(marker_path, label="diagnostic preparation marker")
    if (
        marker.get("artifact_type")
        != "candidate_relation_diagnostic_preparation_complete"
        or marker.get("version") != "v0.1"
        or marker.get("status") != "final"
        or marker.get("condition") != condition
    ):
        raise DiagnosticRunError("Prepared diagnostic condition is not final or mismatched.")
    if marker.get("contract") != binding(contract_path):
        raise DiagnosticRunError("Preparation marker points to a different contract.")
    implementation = marker.get("implementation")
    if implementation != binding(Path(preparer.__file__).resolve()):
        raise DiagnosticRunError("Preparation implementation hash is stale.")
    artifacts = marker.get("artifacts")
    expected_names = {
        "selected_relation_ground_truth",
        "model_input",
        "batch_plan",
        "source_manifest",
    }
    if not isinstance(artifacts, dict) or set(artifacts) != expected_names:
        raise DiagnosticRunError("Preparation artifact set is invalid.")
    paths = {
        name: projector.validate_binding(value, label=f"prepared {name}")
        for name, value in artifacts.items()
    }
    for path in paths.values():
        if path.parent.resolve() != prepared_dir.resolve():
            raise DiagnosticRunError("Prepared artifacts must share one condition directory.")

    model_artifact = read_json(paths["model_input"], label="diagnostic model input")
    selected_gt = read_json(
        paths["selected_relation_ground_truth"], label="selected Relation Ground Truth"
    )
    batch_plan = read_json(paths["batch_plan"], label="diagnostic batch plan")
    source_manifest = read_json(paths["source_manifest"], label="diagnostic source manifest")
    if (
        model_artifact.get("artifact_type") != "candidate_relation_model_input"
        or model_artifact.get("condition") != condition
        or model_artifact.get("request_partitioning")
        != base_runner.CANDIDATE_SCOPED_PARTITIONING
    ):
        raise DiagnosticRunError("Prepared model input has an invalid contract.")
    model_input = model_artifact.get("model_input")
    if not isinstance(model_input, dict):
        raise DiagnosticRunError("Prepared model_input must be an object.")
    if model_artifact.get("model_input_sha256") != projector.sha256_json(model_input):
        raise DiagnosticRunError("Prepared model input hash is stale.")
    if model_artifact.get("selected_ground_truth_sha256") != projector.sha256_file(
        paths["selected_relation_ground_truth"]
    ):
        raise DiagnosticRunError("Prepared model input points to stale Ground Truth.")

    candidate_members: dict[str, set[base_runner.Ref]] = {}
    for pair in model_input.get("candidate_pairs", []):
        pair_id = pair.get("pair_id")
        if not isinstance(pair_id, str) or pair_id in candidate_members:
            raise DiagnosticRunError("Prepared model input has invalid pair IDs.")
        candidate_members[pair_id] = {
            base_runner.parse_ref(pair.get("ko_a"), f"{pair_id}.ko_a"),
            base_runner.parse_ref(pair.get("ko_b"), f"{pair_id}.ko_b"),
        }
    leakage_audit = base_runner.validate_model_input(model_input, candidate_members)
    relation_ids = [pair.get("pair_id") for pair in selected_gt.get("pairs", [])]
    model_ids = [pair.get("pair_id") for pair in model_input["candidate_pairs"]]
    if relation_ids != model_ids or len(model_ids) != len(set(model_ids)):
        raise DiagnosticRunError("Prepared Ground Truth and model input pair order differ.")
    rebuilt_plan, _ = base_runner.build_candidate_scoped_batches(
        model_input, candidate_members
    )
    for field in (
        "artifact_type",
        "version",
        "request_partitioning",
        "batch_count",
        "pair_ids",
        "batches",
    ):
        if batch_plan.get(field) != rebuilt_plan.get(field):
            raise DiagnosticRunError(f"Prepared batch plan has stale field {field}.")
    if batch_plan.get("model_input_sha256") != projector.sha256_json(model_input):
        raise DiagnosticRunError("Prepared batch plan has a stale model input hash.")
    if source_manifest.get("condition") != condition:
        raise DiagnosticRunError("Prepared source manifest condition differs.")
    if marker.get("counts", {}).get("selected_pairs") != len(model_ids):
        raise DiagnosticRunError("Preparation count differs from model input.")
    if marker.get("counts", {}).get("request_batches") != len(model_ids):
        raise DiagnosticRunError("Preparation request count differs from model input.")
    if marker.get("gold_leakage_audit") != leakage_audit:
        raise DiagnosticRunError("Preparation leakage audit is stale.")
    return {
        "marker_path": marker_path,
        "marker": marker,
        "paths": paths,
        "model_artifact": model_artifact,
        "selected_gt": selected_gt,
        "batch_plan": batch_plan,
        "source_manifest": source_manifest,
        "model_input": model_input,
        "candidate_members": candidate_members,
        "leakage_audit": leakage_audit,
    }


def validate_execution_parameters(contract: dict[str, Any], args: argparse.Namespace) -> None:
    execution = contract.get("execution")
    expected = {
        "provider": base_runner.PROVIDER,
        "model": args.model,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "request_partitioning": base_runner.CANDIDATE_SCOPED_PARTITIONING,
        "condition_order": ["all_pairs", "rule_filtered_v0_1"],
        "overwrite": False,
        "retry_policy": "new_complete_condition_attempt_only",
    }
    if execution != expected:
        raise DiagnosticRunError("Requested execution parameters differ from the contract.")


def validate_preceding_condition(
    *,
    condition: str,
    dry_run: bool,
    metadata_path_text: str | None,
    expected_commit: str,
    args: argparse.Namespace,
) -> dict[str, str] | None:
    if condition == "all_pairs":
        if metadata_path_text:
            raise DiagnosticRunError("All-Pairs does not accept preceding metadata.")
        return None
    if dry_run and not metadata_path_text:
        return None
    if not metadata_path_text:
        raise DiagnosticRunError(
            "Formal Rule-Filtered execution requires completed All-Pairs metadata."
        )
    path = resolve_path(metadata_path_text)
    metadata = read_json(path, label="preceding All-Pairs metadata")
    if (
        metadata.get("condition") != "all_pairs"
        or metadata.get("run_status") != "completed"
        or metadata.get("git_commit_at_start") != expected_commit
        or metadata.get("request_success") is not True
        or metadata.get("json_parse_success") is not True
        or metadata.get("prediction_schema_valid") is not True
        or metadata.get("finish_reason") != "stop"
    ):
        raise DiagnosticRunError("Preceding All-Pairs execution is not a valid completed run.")
    expected_parameters = {
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    if metadata.get("model_requested") != args.model or metadata.get(
        "request_parameters"
    ) != expected_parameters:
        raise DiagnosticRunError("All-Pairs and Rule-Filtered execution parameters differ.")
    return binding(path)


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def run_condition(args: argparse.Namespace) -> int:
    contract_path = resolve_path(args.contract)
    contract = read_json(contract_path, label="diagnostic contract")
    projector.validate_contract(contract)
    validate_execution_parameters(contract, args)
    prepared_dir = (
        resolve_path(args.prepared_dir)
        if args.prepared_dir
        else DEFAULT_PREPARATION_ROOT / args.condition
    )
    run_dir = (
        resolve_path(args.run_dir)
        if args.run_dir
        else DEFAULT_EXECUTION_ROOT
        / ("dry_runs" if args.dry_run else "formal")
        / args.condition
        / args.run_id
    )
    run_marker_path = run_dir / RUN_MARKER_NAME
    if run_marker_path.exists():
        raise DiagnosticRunError("Diagnostic run marker already exists; choose a new run ID.")

    prepared = validate_preparation(
        prepared_dir=prepared_dir,
        contract_path=contract_path,
        condition=args.condition,
    )
    current_commit = base_runner.git_commit()
    dirty = base_runner.git_dirty()
    validate_repository_state(
        expected_commit=args.expected_commit,
        current_commit=current_commit,
        dirty=dirty,
    )
    preceding = validate_preceding_condition(
        condition=args.condition,
        dry_run=args.dry_run,
        metadata_path_text=args.preceding_all_pairs_metadata,
        expected_commit=args.expected_commit,
        args=args,
    )

    relation_method = contract["relation_method"]
    prompt_path = projector.validate_binding(
        relation_method["prompt"], label="Relation prompt"
    )
    schema_path = projector.validate_binding(
        relation_method["schema"], label="Relation schema"
    )
    projector.validate_binding(
        relation_method["base_runner_dependency"], label="base Relation runner"
    )
    projector.validate_binding(
        relation_method["base_evaluator"], label="base Relation evaluator"
    )
    prompt_text = prompt_path.read_text(encoding="utf-8")

    model_input = prepared["model_input"]
    model_artifact_path = prepared["paths"]["model_input"]
    batch_plan_path = prepared["paths"]["batch_plan"]
    selected_gt_path = prepared["paths"]["selected_relation_ground_truth"]
    model_artifact = prepared["model_artifact"]
    source_manifest = prepared["source_manifest"]
    matched_context = {
        "condition": args.condition,
        "input_artifact": display_path(model_artifact_path),
        "input_artifact_sha256": projector.sha256_file(model_artifact_path),
        "batch_plan": display_path(batch_plan_path),
        "batch_plan_sha256": projector.sha256_file(batch_plan_path),
    }
    execution_context = {
        "diagnostic_contract": display_path(contract_path),
        "diagnostic_contract_sha256": projector.sha256_file(contract_path),
        "diagnostic_preparation_marker": display_path(prepared["marker_path"]),
        "diagnostic_preparation_marker_sha256": projector.sha256_file(
            prepared["marker_path"]
        ),
        "diagnostic_runner": display_path(Path(__file__).resolve()),
        "diagnostic_runner_sha256": projector.sha256_file(Path(__file__).resolve()),
        "candidate_method": next(
            item["method_id"]
            for item in contract["candidate_conditions"]
            if item["condition"] == args.condition
        ),
        "method_commit": args.expected_commit,
        "preceding_all_pairs_metadata": preceding,
    }
    base_args = SimpleNamespace(
        experiment=relation_method["experiment"],
        run_id=args.run_id,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        dry_run=args.dry_run,
        overwrite=False,
        input_artifact=display_path(model_artifact_path),
    )
    output_dir = run_dir / "output"
    rendered_inputs_dir = run_dir / "rendered_inputs"
    raw_responses_dir = run_dir / "raw_responses"
    metadata_dir = run_dir / "metadata"
    return_code = base_runner.run_candidate_scoped_execution(
        args=base_args,
        relation_ground_truth=prepared["selected_gt"],
        ground_truth_path=selected_gt_path,
        prompt_path=prompt_path,
        schema_path=schema_path,
        prompt_text=prompt_text,
        run_dir=run_dir,
        output_dir=output_dir,
        rendered_inputs_dir=rendered_inputs_dir,
        raw_responses_dir=raw_responses_dir,
        metadata_dir=metadata_dir,
        model_input=model_input,
        candidate_members=prepared["candidate_members"],
        leakage_audit=prepared["leakage_audit"],
        ko_ground_truth_hashes=source_manifest["knowledge_object_ground_truth_hashes"],
        lecture_hashes=model_artifact["lecture_sha256"],
        matched_context=matched_context,
        execution_context=execution_context,
        git_commit_at_start=current_commit,
        git_dirty_at_start=dirty,
    )
    if return_code != 0:
        return return_code

    metadata_path = metadata_dir / AGGREGATE_METADATA_NAME
    metadata = read_json(metadata_path, label="aggregate diagnostic metadata")
    expected_status = "dry_run_complete" if args.dry_run else "completed"
    if metadata.get("run_status") != expected_status:
        raise DiagnosticRunError("Aggregate diagnostic metadata has an unexpected status.")
    artifacts = {
        "execution_batch_plan": binding(run_dir / "execution_batch_plan.json"),
        "aggregate_metadata": binding(metadata_path),
    }
    if not args.dry_run:
        prediction_path = output_dir / "selected_relation_ground_truth.json"
        artifacts["predictions"] = binding(prediction_path)
        if metadata.get("prediction_sha256") != projector.sha256_file(prediction_path):
            raise DiagnosticRunError("Aggregate prediction hash is stale.")
    marker = {
        "artifact_type": "candidate_relation_diagnostic_run_complete",
        "version": "v0.1",
        "status": expected_status,
        "condition": args.condition,
        "run_id": args.run_id,
        "method_commit": args.expected_commit,
        "contract": binding(contract_path),
        "preparation": binding(prepared["marker_path"]),
        "implementation": binding(Path(__file__).resolve()),
        "base_runner_dependency": relation_method["base_runner_dependency"],
        "artifacts": artifacts,
        "counts": {
            "candidate_pairs": len(model_input["candidate_pairs"]),
            "request_batches": len(model_input["candidate_pairs"]),
            "completed_batches": metadata.get("completed_batch_count", 0),
        },
        "repository": {
            "git_commit_at_start": current_commit,
            "git_dirty_at_start": dirty,
        },
    }
    atomic_write(run_marker_path, marker)
    print(
        f"Completed {args.condition} {expected_status}: "
        f"{marker['counts']['candidate_pairs']} candidate-scoped batches"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    base_runner.load_dotenv()
    args = parse_args(argv)
    try:
        return run_condition(args)
    except (
        DiagnosticRunError,
        preparer.PreparationError,
        projector.ProjectionError,
        RuntimeError,
    ) as exc:
        print(f"Candidate Relation diagnostic failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
