#!/usr/bin/env python3
"""Run two-stage direct-edge gating and canonical Connection typing."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import run_connection_discovery as base
except ModuleNotFoundError:  # Direct execution via `python3 scripts/...`.
    import run_connection_discovery as base


ROOT = base.ROOT
EXPERIMENT_ROOT = (
    ROOT / "experiments" / "connection_discovery" / "003_2b_direct_edge_gate"
)
DEFAULT_GATE_PROMPT = EXPERIMENT_ROOT / "direct_edge_prompt.md"
DEFAULT_TYPE_PROMPT = EXPERIMENT_ROOT / "relation_typing_prompt.md"
RUNNER_VERSION = "two_stage_connection_runner_v0.1.1"
GATE_RESULT_KEYS = {
    "canonical_pair_id",
    "ko_a_id",
    "ko_b_id",
    "decision",
    "evidence_ids",
    "rationale",
}
GATE_DECISIONS = {"DIRECT_CONNECTION", "NO_RELATION"}


class TwoStageRunError(base.ConnectionRunError):
    """Raised when the two-stage execution contract is violated."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-selection", default=str(base.DEFAULT_SELECTION))
    parser.add_argument(
        "--candidate-completion", default=str(base.DEFAULT_CANDIDATE_COMPLETION)
    )
    parser.add_argument(
        "--candidate-validation", default=str(base.DEFAULT_CANDIDATE_VALIDATION)
    )
    parser.add_argument("--canonical-inventory", default=str(base.DEFAULT_INVENTORY))
    parser.add_argument("--evidence-catalogs", default=str(base.DEFAULT_CATALOGS))
    parser.add_argument("--freeze-manifest", default=str(base.DEFAULT_FREEZE_MANIFEST))
    parser.add_argument("--gate-prompt", default=str(DEFAULT_GATE_PROMPT))
    parser.add_argument("--type-prompt", default=str(DEFAULT_TYPE_PROMPT))
    parser.add_argument("--prediction-schema", default=str(base.DEFAULT_SCHEMA))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--run-id", default="run_01")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", base.DEFAULT_MODEL))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--gate-max-tokens", type=int, default=700)
    parser.add_argument("--type-max-tokens", type=int, default=900)
    parser.add_argument(
        "--schema-repair-attempts",
        type=int,
        choices=(0, 1),
        default=0,
        help="Maximum validator-guided repair attempts after a schema-invalid Stage-B JSON response.",
    )
    parser.add_argument("--only")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "candidate_selection": base.resolve_path(args.candidate_selection),
        "candidate_completion": base.resolve_path(args.candidate_completion),
        "candidate_validation": base.resolve_path(args.candidate_validation),
        "canonical_inventory": base.resolve_path(args.canonical_inventory),
        "evidence_catalogs": base.resolve_path(args.evidence_catalogs),
        "freeze_manifest": base.resolve_path(args.freeze_manifest),
    }


def load_items(args: argparse.Namespace) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    paths = _paths(args)
    selection = base.load_json(paths["candidate_selection"])
    completion = base.load_json(paths["candidate_completion"])
    validation = base.load_json(paths["candidate_validation"])
    inventory = base.load_json(paths["canonical_inventory"])
    catalogs = base.load_json(paths["evidence_catalogs"])
    freeze = base.load_json(paths["freeze_manifest"])
    base.validate_input_chain(
        selection=selection,
        selection_path=paths["candidate_selection"],
        candidate_completion=completion,
        candidate_validation=validation,
        inventory=inventory,
        catalogs=catalogs,
        freeze_manifest=freeze,
        paths=paths,
    )
    items = base.build_execution_items(selection, inventory, catalogs)
    if args.only:
        if base.PAIR_ID_RE.fullmatch(args.only) is None:
            raise TwoStageRunError("--only has an invalid canonical pair ID")
        items = [item for item in items if item["canonical_pair_id"] == args.only]
        if not items:
            raise TwoStageRunError("--only pair is not in the selected candidate set")
    return paths, items


def gate_model_input(item: dict[str, Any]) -> dict[str, Any]:
    pair = item["model_input"]["candidate_pair"]
    return {
        "candidate_pair": {
            "canonical_pair_id": pair["canonical_pair_id"],
            "ko_a": pair["ko_a"],
            "ko_b": pair["ko_b"],
        },
        "evidence_catalog": item["model_input"]["evidence_catalog"],
    }


def validate_gate_prediction(
    prediction: dict[str, Any], item: dict[str, Any]
) -> dict[str, Any]:
    if set(prediction) != {"result"} or not isinstance(prediction["result"], dict):
        raise TwoStageRunError("Gate prediction must contain exactly one result")
    result = prediction["result"]
    if set(result) != GATE_RESULT_KEYS:
        raise TwoStageRunError("Gate prediction result field set is invalid")
    pair_id = item["canonical_pair_id"]
    if result["canonical_pair_id"] != pair_id:
        raise TwoStageRunError(f"{pair_id}: gate changed canonical_pair_id")
    if [result["ko_a_id"], result["ko_b_id"]] != item["endpoint_ids"]:
        raise TwoStageRunError(f"{pair_id}: gate changed or reordered endpoints")
    if result["decision"] not in GATE_DECISIONS:
        raise TwoStageRunError(f"{pair_id}: invalid direct-gate decision")
    evidence_ids = result["evidence_ids"]
    if not isinstance(evidence_ids, list) or any(
        not isinstance(value, str) for value in evidence_ids
    ):
        raise TwoStageRunError(f"{pair_id}: gate evidence_ids must be a string list")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise TwoStageRunError(f"{pair_id}: duplicate gate Evidence IDs")
    unknown = set(evidence_ids) - item["allowed_evidence_ids"]
    if unknown:
        raise TwoStageRunError(f"{pair_id}: unknown gate Evidence IDs {sorted(unknown)}")
    if result["decision"] == "DIRECT_CONNECTION" and not evidence_ids:
        raise TwoStageRunError(f"{pair_id}: positive gate requires Evidence")
    if result["decision"] == "NO_RELATION" and evidence_ids:
        raise TwoStageRunError(f"{pair_id}: negative gate must not include Evidence")
    if not isinstance(result["rationale"], str) or not result["rationale"].strip():
        raise TwoStageRunError(f"{pair_id}: gate rationale must be non-empty")
    return result


def typing_model_input(
    item: dict[str, Any], gate_result: dict[str, Any]
) -> dict[str, Any]:
    selected = set(gate_result["evidence_ids"])
    catalog = [
        evidence
        for evidence in item["model_input"]["evidence_catalog"]
        if evidence["evidence_id"] in selected
    ]
    if len(catalog) != len(selected):
        raise TwoStageRunError(f"{item['canonical_pair_id']}: gate Evidence mismatch")
    return {
        "candidate_pair": item["model_input"]["candidate_pair"],
        "selected_evidence": catalog,
    }


def validate_typed_prediction(
    prediction: dict[str, Any],
    item: dict[str, Any],
    gate_result: dict[str, Any],
) -> dict[str, Any]:
    result = base.validate_prediction(prediction, item)
    pair_id = item["canonical_pair_id"]
    selected = set(gate_result["evidence_ids"])
    if not set(result["evidence_ids"]).issubset(selected):
        raise TwoStageRunError(f"{pair_id}: typed edge used Evidence outside gate selection")
    if result["relation_type"] == "NO_RELATION":
        if result["evidence_ids"]:
            raise TwoStageRunError(f"{pair_id}: typed NO_RELATION must have no Evidence")
    elif not result["evidence_ids"]:
        raise TwoStageRunError(f"{pair_id}: positive typed edge requires Evidence")
    if not result["rationale"].strip():
        raise TwoStageRunError(f"{pair_id}: typed rationale must be non-empty")
    if result["relation_type"] == "FORMALIZES":
        pair = item["model_input"]["candidate_pair"]
        types = {
            pair["ko_a"]["canonical_ko_id"]: pair["ko_a"]["canonical_type"],
            pair["ko_b"]["canonical_ko_id"]: pair["ko_b"]["canonical_type"],
        }
        if types[result["source_canonical_ko_id"]] != "Formula":
            raise TwoStageRunError(f"{pair_id}: FORMALIZES source must be Formula")
    return result


def _payload(args: argparse.Namespace, prompt: str, model_input: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    return base.build_payload(
        model=args.model,
        prompt=prompt,
        model_input=model_input,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=max_tokens,
    )


def repair_payload(
    original_payload: dict[str, Any],
    api_response: dict[str, Any],
    validation_error: str,
) -> dict[str, Any]:
    try:
        previous_content = api_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TwoStageRunError("Cannot construct schema repair from malformed response") from exc
    if not isinstance(previous_content, str) or not previous_content.strip():
        raise TwoStageRunError("Cannot construct schema repair from empty response")
    return {
        **original_payload,
        "messages": [
            *original_payload["messages"],
            {"role": "assistant", "content": previous_content},
            {
                "role": "user",
                "content": (
                    "Your previous JSON response violated the output contract: "
                    f"{validation_error}. Return one corrected JSON object only. "
                    "Use the same candidate endpoints and supplied Evidence. Do not "
                    "invent IDs or add outside knowledge."
                ),
            },
        ],
    }


def _pair_metadata(pair_id: str, stage: str) -> dict[str, Any]:
    return {
        "canonical_pair_id": pair_id,
        "stage": stage,
        "request_success": False,
        "json_parse_success": False,
        "prediction_schema_valid": False,
        "finish_reason": None,
        "latency_ms": None,
        "failure": None,
    }


def _usage_total(usages: list[dict[str, Any]]) -> dict[str, int]:
    keys = sorted({key for usage in usages for key in usage})
    return {
        key: sum(
            usage.get(key, 0)
            for usage in usages
            if isinstance(usage.get(key), int)
        )
        for key in keys
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = base.resolve_path(args.run_dir)
    if run_dir.exists():
        print(f"Two-stage Connection run failed: run directory already exists: {base.display_path(run_dir)}")
        return 1
    if base.SHA1_RE.fullmatch(args.method_commit) is None:
        print("Two-stage Connection run failed: method_commit must be a 40-character SHA-1")
        return 1
    commit = base.git_commit()
    dirty = base.git_dirty()
    if commit != args.method_commit or dirty is not False:
        print("Two-stage Connection run failed: repository must be clean at the supplied method commit")
        return 1

    gate_prompt_path = base.resolve_path(args.gate_prompt)
    type_prompt_path = base.resolve_path(args.type_prompt)
    schema_path = base.resolve_path(args.prediction_schema)
    try:
        paths, items = load_items(args)
        gate_prompt = gate_prompt_path.read_text(encoding="utf-8")
        type_prompt = type_prompt_path.read_text(encoding="utf-8")
        stage_a_payloads = [
            _payload(args, gate_prompt, gate_model_input(item), args.gate_max_tokens)
            for item in items
        ]
    except (base.ConnectionRunError, OSError) as exc:
        print(f"Two-stage Connection run failed: {exc}")
        return 1

    stage_dirs: dict[str, dict[str, Path]] = {}
    for stage in ("stage_a", "stage_b"):
        stage_dirs[stage] = {
            "rendered": run_dir / stage / "rendered_inputs" / "pairs",
            "raw": run_dir / stage / "raw_responses" / "pairs",
            "output": run_dir / stage / "output" / "pairs",
            "metadata": run_dir / stage / "metadata" / "pairs",
        }
        for directory in stage_dirs[stage].values():
            directory.mkdir(parents=True, exist_ok=False)

    run_metadata_path = run_dir / "metadata" / "run_metadata.json"
    started_at = datetime.now(timezone.utc).isoformat()
    metadata: dict[str, Any] = {
        "artifact_type": "two_stage_canonical_connection_run_metadata",
        "version": "v0.1",
        "run_id": args.run_id,
        "run_status": "prepared",
        "method_id": "direct_edge_gate_then_relation_typing_v0.1",
        "method_commit": args.method_commit,
        "git_commit_at_start": commit,
        "git_dirty_at_start": dirty,
        "provider": "deepseek",
        "request_partitioning": "one_canonical_pair_per_request_per_stage_v0.1",
        "execution_scope": "subset" if args.only else "full_selected_candidate_set",
        "request_parameters": {
            "model": args.model,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "gate_max_tokens": args.gate_max_tokens,
            "type_max_tokens": args.type_max_tokens,
            "schema_repair_attempts": args.schema_repair_attempts,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        },
        "inputs": {name: base.binding(path) for name, path in paths.items()},
        "prompts": {
            "direct_edge_gate": base.binding(gate_prompt_path),
            "relation_typing": base.binding(type_prompt_path),
        },
        "prediction_schema": base.binding(schema_path),
        "runner": {
            "path": base.display_path(Path(__file__)),
            "sha256": base.sha256_file(Path(__file__)),
            "version": RUNNER_VERSION,
        },
        "candidate_count": len(items),
        "candidate_pair_ids_sha256": base.sha256_json(
            [item["canonical_pair_id"] for item in items]
        ),
        "stage_a_request_payload_set_sha256": base.sha256_json(
            [base.sha256_json(payload) for payload in stage_a_payloads]
        ),
        "stage_b_request_payload_set_sha256": None,
        "dry_run": args.dry_run,
        "started_at": started_at,
        "stage_a_completed_count": 0,
        "stage_a_positive_count": None,
        "stage_b_completed_count": 0,
        "stage_b_schema_repair_count": 0,
        "request_success": None,
        "json_parse_success": None,
        "prediction_schema_valid": None,
        "finish_reason": None,
        "latency_ms": None,
        "usage": None,
        "failure": None,
    }
    for item, payload in zip(items, stage_a_payloads):
        base.write_json(
            stage_dirs["stage_a"]["rendered"] / f"{item['canonical_pair_id']}.json",
            payload,
        )
    if args.dry_run:
        metadata["run_status"] = "dry_run_complete"
        base.write_json(run_metadata_path, metadata)
        print(
            f"Rendered {len(items)} Stage-A direct-edge requests to "
            f"{base.display_path(run_dir)}"
        )
        return 0

    base.load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        metadata["run_status"] = "request_failed"
        metadata["failure"] = {"stage": "stage_a", "message": "DEEPSEEK_API_KEY is unavailable"}
        base.write_json(run_metadata_path, metadata)
        print("Two-stage Connection run failed: DEEPSEEK_API_KEY is unavailable")
        return 1

    started_clock = time.monotonic()
    usages: list[dict[str, Any]] = []
    finish_reasons: list[str | None] = []
    gate_results: dict[str, dict[str, Any]] = {}

    for item, payload in zip(items, stage_a_payloads):
        pair_id = item["canonical_pair_id"]
        pair_started = time.monotonic()
        pair_metadata = _pair_metadata(pair_id, "direct_edge_gate")
        try:
            response = base.call_deepseek(api_key=api_key, payload=payload)
            pair_metadata["request_success"] = True
            base.write_json(stage_dirs["stage_a"]["raw"] / f"{pair_id}.json", response)
            parsed, finish_reason = base.extract_response(response)
            pair_metadata["json_parse_success"] = True
            result = validate_gate_prediction(parsed, item)
            pair_metadata["prediction_schema_valid"] = True
            pair_metadata["finish_reason"] = finish_reason
            pair_metadata["latency_ms"] = round((time.monotonic() - pair_started) * 1000)
            base.write_json(stage_dirs["stage_a"]["output"] / f"{pair_id}.json", result)
            base.write_json(stage_dirs["stage_a"]["metadata"] / f"{pair_id}.json", pair_metadata)
            gate_results[pair_id] = result
            finish_reasons.append(finish_reason)
            if isinstance(response.get("usage"), dict):
                usages.append(response["usage"])
        except (RuntimeError, base.ConnectionRunError) as exc:
            pair_metadata["failure"] = str(exc)
            pair_metadata["latency_ms"] = round((time.monotonic() - pair_started) * 1000)
            base.write_json(stage_dirs["stage_a"]["metadata"] / f"{pair_id}.json", pair_metadata)
            metadata.update({
                "run_status": "stage_a_failed",
                "stage_a_completed_count": len(gate_results),
                "request_success": pair_metadata["request_success"],
                "json_parse_success": pair_metadata["json_parse_success"],
                "prediction_schema_valid": pair_metadata["prediction_schema_valid"],
                "latency_ms": round((time.monotonic() - started_clock) * 1000),
                "failure": {"stage": "stage_a", "canonical_pair_id": pair_id, "message": str(exc)},
            })
            base.write_json(run_metadata_path, metadata)
            print(f"Two-stage Connection run failed at Stage A for {pair_id}: {exc}")
            return 1

    positive_items = [
        item
        for item in items
        if gate_results[item["canonical_pair_id"]]["decision"] == "DIRECT_CONNECTION"
    ]
    gate_prediction = {
        "artifact_type": "canonical_direct_edge_gate_predictions",
        "version": "v0.1",
        "results": [gate_results[item["canonical_pair_id"]] for item in items],
    }
    gate_prediction_path = run_dir / "stage_a" / "output" / "direct_gate_predictions.json"
    base.write_json(gate_prediction_path, gate_prediction)
    stage_b_payloads = [
        _payload(
            args,
            type_prompt,
            typing_model_input(item, gate_results[item["canonical_pair_id"]]),
            args.type_max_tokens,
        )
        for item in positive_items
    ]
    metadata["stage_a_completed_count"] = len(items)
    metadata["stage_a_positive_count"] = len(positive_items)
    metadata["stage_b_request_payload_set_sha256"] = base.sha256_json(
        [base.sha256_json(payload) for payload in stage_b_payloads]
    )
    for item, payload in zip(positive_items, stage_b_payloads):
        base.write_json(
            stage_dirs["stage_b"]["rendered"] / f"{item['canonical_pair_id']}.json",
            payload,
        )

    typed_results: dict[str, dict[str, Any]] = {}
    schema_repair_count = 0
    for item, payload in zip(positive_items, stage_b_payloads):
        pair_id = item["canonical_pair_id"]
        pair_started = time.monotonic()
        pair_metadata = _pair_metadata(pair_id, "relation_typing")
        pair_metadata["attempts"] = []
        current_payload = payload
        try:
            result: dict[str, Any] | None = None
            finish_reason: str | None = None
            for attempt_index in range(args.schema_repair_attempts + 1):
                attempt_number = attempt_index + 1
                attempt_started = time.monotonic()
                response = base.call_deepseek(api_key=api_key, payload=current_payload)
                pair_metadata["request_success"] = True
                finish_reasons.append(
                    response.get("choices", [{}])[0].get("finish_reason")
                    if isinstance(response.get("choices"), list) and response["choices"]
                    else None
                )
                if isinstance(response.get("usage"), dict):
                    usages.append(response["usage"])
                raw_name = (
                    f"{pair_id}.json"
                    if attempt_index == 0
                    else f"{pair_id}.repair_{attempt_index:02d}.json"
                )
                base.write_json(stage_dirs["stage_b"]["raw"] / raw_name, response)
                parsed, finish_reason = base.extract_response(response)
                pair_metadata["json_parse_success"] = True
                attempt_record = {
                    "attempt_number": attempt_number,
                    "request_success": True,
                    "json_parse_success": True,
                    "prediction_schema_valid": False,
                    "finish_reason": finish_reason,
                    "latency_ms": None,
                    "validation_error": None,
                }
                try:
                    result = validate_typed_prediction(parsed, item, gate_results[pair_id])
                    attempt_record["prediction_schema_valid"] = True
                    attempt_record["latency_ms"] = round(
                        (time.monotonic() - attempt_started) * 1000
                    )
                    pair_metadata["attempts"].append(attempt_record)
                    break
                except base.ConnectionRunError as exc:
                    attempt_record["validation_error"] = str(exc)
                    attempt_record["latency_ms"] = round(
                        (time.monotonic() - attempt_started) * 1000
                    )
                    pair_metadata["attempts"].append(attempt_record)
                    if attempt_index >= args.schema_repair_attempts:
                        raise
                    current_payload = repair_payload(current_payload, response, str(exc))
                    repair_dir = run_dir / "stage_b" / "rendered_inputs" / "repairs"
                    repair_dir.mkdir(parents=True, exist_ok=True)
                    base.write_json(
                        repair_dir / f"{pair_id}.repair_{attempt_index + 1:02d}.json",
                        current_payload,
                    )
                    schema_repair_count += 1
            if result is None:
                raise TwoStageRunError(f"{pair_id}: Stage-B result is unavailable")
            pair_metadata["prediction_schema_valid"] = True
            pair_metadata["finish_reason"] = finish_reason
            pair_metadata["attempt_count"] = len(pair_metadata["attempts"])
            pair_metadata["repair_count"] = len(pair_metadata["attempts"]) - 1
            pair_metadata["latency_ms"] = round((time.monotonic() - pair_started) * 1000)
            base.write_json(stage_dirs["stage_b"]["output"] / f"{pair_id}.json", result)
            base.write_json(stage_dirs["stage_b"]["metadata"] / f"{pair_id}.json", pair_metadata)
            typed_results[pair_id] = result
        except (RuntimeError, base.ConnectionRunError) as exc:
            pair_metadata["failure"] = str(exc)
            pair_metadata["latency_ms"] = round((time.monotonic() - pair_started) * 1000)
            base.write_json(stage_dirs["stage_b"]["metadata"] / f"{pair_id}.json", pair_metadata)
            metadata.update({
                "run_status": "stage_b_failed",
                "stage_b_completed_count": len(typed_results),
                "stage_b_schema_repair_count": schema_repair_count,
                "request_success": pair_metadata["request_success"],
                "json_parse_success": pair_metadata["json_parse_success"],
                "prediction_schema_valid": pair_metadata["prediction_schema_valid"],
                "latency_ms": round((time.monotonic() - started_clock) * 1000),
                "failure": {"stage": "stage_b", "canonical_pair_id": pair_id, "message": str(exc)},
            })
            base.write_json(run_metadata_path, metadata)
            print(f"Two-stage Connection run failed at Stage B for {pair_id}: {exc}")
            return 1

    typed_prediction = {
        "artifact_type": "evidence_constrained_connection_predictions",
        "version": "v0.1",
        "results": [typed_results[item["canonical_pair_id"]] for item in positive_items],
    }
    typed_prediction_path = run_dir / "stage_b" / "output" / "typed_connection_predictions.json"
    base.write_json(typed_prediction_path, typed_prediction)

    final_results: list[dict[str, Any]] = []
    for item in items:
        pair_id = item["canonical_pair_id"]
        gate = gate_results[pair_id]
        if gate["decision"] == "DIRECT_CONNECTION":
            final_results.append(typed_results[pair_id])
        else:
            final_results.append({
                "canonical_pair_id": pair_id,
                "source_canonical_ko_id": item["endpoint_ids"][0],
                "target_canonical_ko_id": item["endpoint_ids"][1],
                "relation_type": "NO_RELATION",
                "evidence_ids": [],
                "rationale": gate["rationale"],
            })
    prediction = {
        "artifact_type": "canonical_connection_predictions",
        "version": "v0.1",
        "results": final_results,
    }
    prediction_path = run_dir / "output" / "canonical_connection_predictions.json"
    base.write_json(prediction_path, prediction)
    metadata.update({
        "run_status": "completed_subset" if args.only else "completed",
        "stage_b_completed_count": len(positive_items),
        "stage_b_schema_repair_count": schema_repair_count,
        "request_success": True,
        "json_parse_success": True,
        "prediction_schema_valid": True,
        "finish_reason": "stop" if finish_reasons and all(value == "stop" for value in finish_reasons) else "mixed",
        "latency_ms": round((time.monotonic() - started_clock) * 1000),
        "usage": {"request_count": len(finish_reasons), **_usage_total(usages)},
        "stage_a_prediction": base.binding(gate_prediction_path),
        "stage_b_prediction": base.binding(typed_prediction_path),
        "prediction": base.binding(prediction_path),
    })
    base.write_json(run_metadata_path, metadata)
    print(
        f"Saved {len(final_results)} two-stage canonical Connection predictions "
        f"to {base.display_path(prediction_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
