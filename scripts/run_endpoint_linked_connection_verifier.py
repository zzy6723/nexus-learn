#!/usr/bin/env python3
"""Run candidate-scoped endpoint-linked Connection window verification."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .run_connection_discovery import (
        binding,
        build_payload,
        call_deepseek,
        display_path,
        extract_response,
        git_commit,
        git_dirty,
        load_dotenv,
        load_json,
        resolve_path,
        sha256_file,
        sha256_json,
        write_json,
    )
except ImportError:
    from run_connection_discovery import (
        binding,
        build_payload,
        call_deepseek,
        display_path,
        extract_response,
        git_commit,
        git_dirty,
        load_dotenv,
        load_json,
        resolve_path,
        sha256_file,
        sha256_json,
        write_json,
    )


ROOT = Path(__file__).resolve().parents[1]
METHOD_ROOT = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_2c_endpoint_linked_verifier"
)
DEFAULT_WINDOWS = METHOD_ROOT / "runs" / "development_v0_1" / "windows.json"
DEFAULT_PROMPT = METHOD_ROOT / "window_verifier_prompt.md"
DEFAULT_CANDIDATES = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_1_candidate_generation"
    / "runs"
    / "development_v0_1"
    / "overlap_bridge"
    / "run_01"
    / "generation"
    / "candidate_selection.json"
)
DEFAULT_EVIDENCE = (
    ROOT / "benchmark" / "connection_discovery" / "development_v0_1" / "evidence_catalogs.json"
)
DEFAULT_FREEZE = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_0_benchmark_preparation"
    / "benchmark_freeze_manifest_v0_1.json"
)
RUNNER_VERSION = "endpoint_linked_connection_verifier_runner_v0.1.1"
METHOD_ID = "endpoint_linked_window_verifier_v0.1.1"
SUPPORT_DECISIONS = {
    "DIRECT_IN_SCHEMA",
    "DIRECT_OUT_OF_SCHEMA",
    "MEDIATED_OR_CONTEXTUAL",
    "INSUFFICIENT",
}
RELATIONS = {
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
}
DECISION_KEYS = {
    "canonical_pair_id",
    "window_id",
    "support_decision",
    "source_canonical_ko_id",
    "target_canonical_ko_id",
    "relation_type",
    "evidence_ids",
    "rationale",
}


class EndpointVerifierError(ValueError):
    """Raised when endpoint-linked verification violates its run contract."""


def validate_window_bundle(bundle: dict[str, Any]) -> None:
    errors: list[str] = []
    if bundle.get("artifact_type") != "connection_evidence_window_bundle":
        errors.append("window bundle artifact_type is invalid")
    if bundle.get("version") != "v0.1":
        errors.append("window bundle version is invalid")
    if bundle.get("gold_fields_present") is not False:
        errors.append("window bundle must be gold-free")
    pairs = bundle.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        errors.append("window bundle pairs must be non-empty")
        pairs = []
    pair_ids = [pair.get("canonical_pair_id") for pair in pairs]
    if len(pair_ids) != len(set(pair_ids)):
        errors.append("window bundle contains duplicate pair IDs")
    window_ids: list[str] = []
    for pair in pairs:
        pair_id = pair.get("canonical_pair_id")
        endpoint_ids = pair.get("endpoint_ids")
        endpoint_objects = pair.get("endpoint_objects")
        windows = pair.get("windows")
        if not isinstance(endpoint_ids, list) or len(endpoint_ids) != 2 or len(set(endpoint_ids)) != 2:
            errors.append(f"{pair_id}: invalid endpoints")
            continue
        if not isinstance(endpoint_objects, list) or [
            item.get("canonical_ko_id") for item in endpoint_objects
        ] != endpoint_ids:
            errors.append(f"{pair_id}: endpoint object mismatch")
        if not isinstance(windows, list) or pair.get("window_count") != len(windows):
            errors.append(f"{pair_id}: window count mismatch")
            continue
        if pair.get("deterministic_no_window") is not (len(windows) == 0):
            errors.append(f"{pair_id}: deterministic_no_window mismatch")
        for window in windows:
            window_id = window.get("window_id")
            window_ids.append(window_id)
            evidence_ids = window.get("evidence_ids")
            blocks = window.get("evidence_blocks")
            if not isinstance(window_id, str) or not window_id:
                errors.append(f"{pair_id}: invalid window ID")
            if not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) > 3:
                errors.append(f"{pair_id}: invalid window Evidence IDs")
            if not isinstance(blocks, list) or [item.get("evidence_id") for item in blocks] != evidence_ids:
                errors.append(f"{pair_id}: window block mismatch")
            if len({item.get("lecture_id") for item in blocks or []}) != 1:
                errors.append(f"{pair_id}: window crosses lectures")
    if len(window_ids) != len(set(window_ids)):
        errors.append("window bundle contains duplicate window IDs")
    counts = bundle.get("counts", {})
    if counts.get("selected_pair_count") != len(pairs):
        errors.append("selected_pair_count mismatch")
    if counts.get("window_count") != len(window_ids):
        errors.append("window_count mismatch")
    if errors:
        raise EndpointVerifierError("; ".join(errors))


def build_execution_items(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    validate_window_bundle(bundle)
    items: list[dict[str, Any]] = []
    for pair in bundle["pairs"]:
        for window in pair["windows"]:
            items.append(
                {
                    "canonical_pair_id": pair["canonical_pair_id"],
                    "window_id": window["window_id"],
                    "endpoint_ids": pair["endpoint_ids"],
                    "endpoint_objects": pair["endpoint_objects"],
                    "allowed_evidence_ids": set(window["evidence_ids"]),
                    "model_input": {
                        "canonical_pair_id": pair["canonical_pair_id"],
                        "window_id": window["window_id"],
                        "endpoints": pair["endpoint_objects"],
                        "evidence_window": [
                            {
                                "evidence_id": block["evidence_id"],
                                "lecture_id": block["lecture_id"],
                                "span": block["span"],
                            }
                            for block in window["evidence_blocks"]
                        ],
                        "allowed_support_decisions": sorted(SUPPORT_DECISIONS),
                        "allowed_relation_types": sorted(RELATIONS),
                    },
                }
            )
    return items


def validate_window_decision(prediction: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    if set(prediction) != DECISION_KEYS:
        raise EndpointVerifierError(f"{item['window_id']}: prediction field set is invalid")
    if prediction["canonical_pair_id"] != item["canonical_pair_id"]:
        raise EndpointVerifierError(f"{item['window_id']}: canonical_pair_id changed")
    if prediction["window_id"] != item["window_id"]:
        raise EndpointVerifierError(f"{item['window_id']}: window_id changed")
    decision = prediction.get("support_decision")
    if decision not in SUPPORT_DECISIONS:
        raise EndpointVerifierError(f"{item['window_id']}: support decision is invalid")
    rationale = prediction.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise EndpointVerifierError(f"{item['window_id']}: rationale is empty")
    evidence_ids = prediction.get("evidence_ids")
    if not isinstance(evidence_ids, list) or any(not isinstance(value, str) for value in evidence_ids):
        raise EndpointVerifierError(f"{item['window_id']}: evidence_ids must be a string list")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise EndpointVerifierError(f"{item['window_id']}: duplicate Evidence IDs")
    if not set(evidence_ids) <= item["allowed_evidence_ids"]:
        raise EndpointVerifierError(f"{item['window_id']}: Evidence outside the window")

    if decision != "DIRECT_IN_SCHEMA":
        if any(
            prediction.get(key) is not None
            for key in (
                "source_canonical_ko_id",
                "target_canonical_ko_id",
                "relation_type",
            )
        ) or evidence_ids:
            raise EndpointVerifierError(
                f"{item['window_id']}: non-direct decision emitted a graph edge"
            )
        return prediction

    endpoints = {
        prediction.get("source_canonical_ko_id"),
        prediction.get("target_canonical_ko_id"),
    }
    if endpoints != set(item["endpoint_ids"]):
        raise EndpointVerifierError(f"{item['window_id']}: direct edge changed endpoints")
    if prediction.get("relation_type") not in RELATIONS:
        raise EndpointVerifierError(f"{item['window_id']}: Relation type is invalid")
    if not evidence_ids:
        raise EndpointVerifierError(f"{item['window_id']}: direct edge requires Evidence")
    if prediction["relation_type"] == "FORMALIZES":
        object_types = {
            obj["canonical_ko_id"]: obj["canonical_type"] for obj in item["endpoint_objects"]
        }
        if object_types[prediction["source_canonical_ko_id"]] != "Formula":
            raise EndpointVerifierError(f"{item['window_id']}: FORMALIZES source must be Formula")
    return prediction


def aggregate_predictions(
    bundle: dict[str, Any], decisions: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        by_pair.setdefault(decision["canonical_pair_id"], []).append(decision)
    results: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for pair in bundle["pairs"]:
        pair_id = pair["canonical_pair_id"]
        endpoints = pair["endpoint_ids"]
        direct = [
            item
            for item in by_pair.get(pair_id, [])
            if item["support_decision"] == "DIRECT_IN_SCHEMA"
        ]
        edge_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for item in direct:
            key = (
                item["source_canonical_ko_id"],
                item["target_canonical_ko_id"],
                item["relation_type"],
            )
            edge_groups.setdefault(key, []).append(item)
        if len(edge_groups) == 1:
            candidates = next(iter(edge_groups.values()))
            winner = min(candidates, key=lambda item: (len(item["evidence_ids"]), item["window_id"]))
            results.append(
                {
                    "canonical_pair_id": pair_id,
                    "source_canonical_ko_id": winner["source_canonical_ko_id"],
                    "target_canonical_ko_id": winner["target_canonical_ko_id"],
                    "relation_type": winner["relation_type"],
                    "evidence_ids": winner["evidence_ids"],
                    "rationale": winner["rationale"],
                }
            )
            outcome = "unique_direct_edge"
        else:
            results.append(
                {
                    "canonical_pair_id": pair_id,
                    "source_canonical_ko_id": endpoints[0],
                    "target_canonical_ko_id": endpoints[1],
                    "relation_type": "NO_RELATION",
                    "evidence_ids": [],
                    "rationale": (
                        "No endpoint-linked Evidence window established one unique direct "
                        "in-schema edge."
                    ),
                }
            )
            outcome = "conflicting_direct_edges" if len(edge_groups) > 1 else "no_direct_edge"
        diagnostics.append(
            {
                "canonical_pair_id": pair_id,
                "window_count": pair["window_count"],
                "direct_window_count": len(direct),
                "unique_direct_edge_count": len(edge_groups),
                "aggregation_outcome": outcome,
            }
        )
    return {
        "artifact_type": "canonical_connection_predictions",
        "version": "v0.1",
        "results": results,
    }, diagnostics


def call_with_retries(
    *,
    api_key: str,
    payload: dict[str, Any],
    retries: int,
    caller: Callable[..., dict[str, Any]] = call_deepseek,
) -> tuple[dict[str, Any], int]:
    failures = 0
    while True:
        try:
            return caller(api_key=api_key, payload=payload), failures
        except (TimeoutError, RuntimeError, OSError):
            if failures >= retries:
                raise
            failures += 1
            time.sleep(2)


def build_schema_repair_payload(
    original_payload: dict[str, Any],
    invalid_prediction: dict[str, Any],
    validator_error: str,
) -> dict[str, Any]:
    try:
        original_model_input = json.loads(original_payload["messages"][1]["content"])
        original_system_prompt = original_payload["messages"][0]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise EndpointVerifierError("Cannot construct schema repair payload") from exc
    repair_instruction = (
        "The previous response violated the deterministic output contract. "
        "Return one corrected JSON object for the unchanged candidate and Evidence "
        "window. Use only the supplied endpoint IDs and Evidence IDs. Do not add new "
        "facts. The validator error is structural and does not reveal a gold label."
    )
    repair_input = {
        "original_model_input": original_model_input,
        "invalid_response": invalid_prediction,
        "validator_error": validator_error,
    }
    repaired = dict(original_payload)
    repaired["messages"] = [
        {"role": "system", "content": f"{original_system_prompt}\n\n# Schema Repair\n{repair_instruction}"},
        {"role": "user", "content": json.dumps(repair_input, ensure_ascii=False, indent=2)},
    ]
    return repaired


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-bundle", default=str(DEFAULT_WINDOWS))
    parser.add_argument("--candidate-selection", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--evidence-catalogs", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--transport-retries", type=int, default=2)
    parser.add_argument("--schema-repair-attempts", type=int, choices=(0, 1), default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = resolve_path(args.run_dir)
    paths = {
        "window_bundle": resolve_path(args.window_bundle),
        "candidate_selection": resolve_path(args.candidate_selection),
        "evidence_catalogs": resolve_path(args.evidence_catalogs),
        "freeze_manifest": resolve_path(args.freeze_manifest),
        "prompt": resolve_path(args.prompt),
    }
    if run_dir.exists():
        print(f"Endpoint-linked verifier failed: run directory already exists: {display_path(run_dir)}")
        return 1
    try:
        commit = git_commit()
        dirty = git_dirty()
        if commit != args.method_commit:
            raise EndpointVerifierError("method_commit does not match current commit")
        if dirty:
            raise EndpointVerifierError("repository must be clean at method start")
        bundle = load_json(paths["window_bundle"])
        selection = load_json(paths["candidate_selection"])
        validate_window_bundle(bundle)
        if bundle["counts"]["selected_pair_count"] != selection.get("selected_pair_count"):
            raise EndpointVerifierError("window bundle candidate count mismatch")
        if [item["canonical_pair_id"] for item in bundle["pairs"]] != [
            item["canonical_pair_id"] for item in selection["selected_pairs"]
        ]:
            raise EndpointVerifierError("window bundle pair order mismatch")
        items = build_execution_items(bundle)
        prompt = paths["prompt"].read_text(encoding="utf-8")
        payloads = [
            build_payload(
                model=args.model,
                prompt=prompt,
                model_input=item["model_input"],
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
            )
            for item in items
        ]
    except (EndpointVerifierError, OSError, ValueError) as exc:
        print(f"Endpoint-linked verifier failed: {exc}")
        return 1

    started_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "artifact_type": "endpoint_linked_connection_verifier_run_metadata",
        "version": "v0.1",
        "run_id": args.run_id,
        "run_status": "prepared",
        "method_id": METHOD_ID,
        "method_commit": args.method_commit,
        "git_commit_at_start": commit,
        "git_dirty_at_start": dirty,
        "execution_scope": "full_selected_candidate_set",
        "request_partitioning": "one_endpoint_linked_window_per_request_v0.1",
        "request_parameters": {
            "model": args.model,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "transport_retries": args.transport_retries,
            "schema_repair_attempts": args.schema_repair_attempts,
        },
        "inputs": {
            "window_bundle": binding(paths["window_bundle"]),
            "candidate_selection": binding(paths["candidate_selection"]),
            "evidence_catalogs": binding(paths["evidence_catalogs"]),
            "freeze_manifest": binding(paths["freeze_manifest"]),
            "prompt": binding(paths["prompt"]),
        },
        "runner": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": RUNNER_VERSION,
        },
        "candidate_count": len(bundle["pairs"]),
        "window_request_count": len(items),
        "request_payload_set_sha256": sha256_json([sha256_json(item) for item in payloads]),
        "dry_run": args.dry_run,
        "started_at": started_at,
    }
    run_dir.mkdir(parents=True)
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    for item, payload in zip(items, payloads):
        write_json(run_dir / "rendered_inputs" / "windows" / f"{item['window_id']}.json", payload)
    if args.dry_run:
        metadata.update({"run_status": "dry_run_completed", "completed_window_count": 0})
        write_json(metadata_path, metadata)
        print(f"Rendered {len(items)} endpoint-linked window requests to {display_path(run_dir)}")
        return 0

    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        metadata.update({"run_status": "request_failed", "request_success": False, "api_error": "DEEPSEEK_API_KEY is unavailable"})
        write_json(metadata_path, metadata)
        print("Endpoint-linked verifier failed: DEEPSEEK_API_KEY is unavailable")
        return 1

    decisions: list[dict[str, Any]] = []
    retry_count = 0
    finish_reasons: list[str | None] = []
    usage: dict[str, int] = {}
    attempted_window_count = 0
    api_request_attempt_count = 0
    request_completed_count = 0
    parse_completed_count = 0
    schema_repair_count = 0
    try:
        for item, payload in zip(items, payloads):
            attempted_window_count += 1
            api_request_attempt_count += 1
            response, retries = call_with_retries(
                api_key=api_key,
                payload=payload,
                retries=args.transport_retries,
            )
            request_completed_count += 1
            retry_count += retries
            write_json(
                run_dir / "raw_responses" / "windows" / f"{item['window_id']}.json",
                response,
            )
            parsed, finish_reason = extract_response(response)
            parse_completed_count += 1
            write_json(
                run_dir / "parsed_responses" / "windows" / f"{item['window_id']}.json",
                parsed,
            )
            try:
                decision = validate_window_decision(parsed, item)
            except EndpointVerifierError as schema_error:
                if args.schema_repair_attempts != 1:
                    raise
                repair_payload = build_schema_repair_payload(
                    payload, parsed, str(schema_error)
                )
                repair_name = f"{item['window_id']}.repair_01.json"
                write_json(
                    run_dir / "rendered_inputs" / "repairs" / repair_name,
                    repair_payload,
                )
                api_request_attempt_count += 1
                repair_response, repair_retries = call_with_retries(
                    api_key=api_key,
                    payload=repair_payload,
                    retries=args.transport_retries,
                )
                request_completed_count += 1
                retry_count += repair_retries
                schema_repair_count += 1
                write_json(
                    run_dir / "raw_responses" / "repairs" / repair_name,
                    repair_response,
                )
                repair_parsed, repair_finish_reason = extract_response(repair_response)
                parse_completed_count += 1
                write_json(
                    run_dir / "parsed_responses" / "repairs" / repair_name,
                    repair_parsed,
                )
                decision = validate_window_decision(repair_parsed, item)
                finish_reasons.append(repair_finish_reason)
                for key, value in repair_response.get("usage", {}).items():
                    if isinstance(value, int):
                        usage[key] = usage.get(key, 0) + value
            decisions.append(decision)
            finish_reasons.append(finish_reason)
            write_json(
                run_dir / "window_decisions" / "windows" / f"{item['window_id']}.json",
                decision,
            )
            for key, value in response.get("usage", {}).items():
                if isinstance(value, int):
                    usage[key] = usage.get(key, 0) + value
        predictions, diagnostics = aggregate_predictions(bundle, decisions)
        prediction_path = run_dir / "output" / "canonical_connection_predictions.json"
        decision_path = run_dir / "window_decisions" / "window_verifications.json"
        diagnostics_path = run_dir / "output" / "aggregation_diagnostics.json"
        write_json(decision_path, {"artifact_type": "connection_window_verifications", "version": "v0.1", "decisions": decisions})
        write_json(diagnostics_path, {"artifact_type": "connection_window_aggregation_diagnostics", "version": "v0.1", "pairs": diagnostics})
        write_json(prediction_path, predictions)
        metadata.update(
            {
                "run_status": "completed",
                "request_success": True,
                "json_parse_success": True,
                "prediction_schema_valid": True,
                "finish_reason": "stop" if set(finish_reasons) == {"stop"} else "mixed",
                "completed_window_count": len(decisions),
                "attempted_window_count": attempted_window_count,
                "api_request_attempt_count": api_request_attempt_count,
                "request_completed_count": request_completed_count,
                "parse_completed_count": parse_completed_count,
                "completed_candidate_count": len(predictions["results"]),
                "transport_retry_count": retry_count,
                "schema_repair_count": schema_repair_count,
                "aggregation_conflict_count": sum(
                    item["aggregation_outcome"] == "conflicting_direct_edges"
                    for item in diagnostics
                ),
                "usage": usage,
                "window_verifications": binding(decision_path),
                "aggregation_diagnostics": binding(diagnostics_path),
                "prediction": binding(prediction_path),
            }
        )
        write_json(metadata_path, metadata)
    except Exception as exc:
        if request_completed_count < api_request_attempt_count:
            failure_status = "request_failed"
            request_success = False
            json_parse_success = False
        elif parse_completed_count < request_completed_count:
            failure_status = "json_parse_failed"
            request_success = True
            json_parse_success = False
        else:
            failure_status = "prediction_schema_failed"
            request_success = True
            json_parse_success = True
        metadata.update(
            {
                "run_status": failure_status,
                "request_success": request_success,
                "json_parse_success": json_parse_success,
                "prediction_schema_valid": False,
                "attempted_window_count": attempted_window_count,
                "api_request_attempt_count": api_request_attempt_count,
                "request_completed_count": request_completed_count,
                "parse_completed_count": parse_completed_count,
                "completed_window_count": len(decisions),
                "transport_retry_count": retry_count,
                "schema_repair_count": schema_repair_count,
                "failure": str(exc),
            }
        )
        write_json(metadata_path, metadata)
        print(f"Endpoint-linked verifier failed after {len(decisions)} windows: {exc}")
        return 1
    print(f"Saved {len(predictions['results'])} endpoint-linked Connection predictions to {display_path(prediction_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
