#!/usr/bin/env python3
"""Render and execute candidate-scoped canonical Connection classification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = (
    ROOT / "experiments" / "connection_discovery" / "003_2_oracle_connection_discovery"
)
BENCHMARK_ROOT = ROOT / "benchmark" / "connection_discovery" / "development_v0_1"
DEFAULT_SELECTION = (
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
DEFAULT_CANDIDATE_COMPLETION = DEFAULT_SELECTION.with_name("generation_complete.json")
DEFAULT_CANDIDATE_VALIDATION = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_1_candidate_generation"
    / "development_validation_complete.json"
)
DEFAULT_INVENTORY = BENCHMARK_ROOT / "oracle_canonical_inventory.json"
DEFAULT_CATALOGS = BENCHMARK_ROOT / "evidence_catalogs.json"
DEFAULT_FREEZE_MANIFEST = (
    ROOT
    / "experiments"
    / "connection_discovery"
    / "003_0_benchmark_preparation"
    / "benchmark_freeze_manifest_v0_1.json"
)
DEFAULT_PROMPT = EXPERIMENT_ROOT / "prompt.md"
DEFAULT_SCHEMA = ROOT / "benchmark" / "schema" / "connection_prediction.schema.json"
DEFAULT_MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com/chat/completions"
RUNNER_VERSION = "canonical_connection_runner_v0.1"
ALLOWED_RELATIONS = {
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
    "NO_RELATION",
}
FORBIDDEN_MODEL_KEYS = {
    "score",
    "features",
    "rank",
    "provenance_stratum",
    "scope_flags",
    "category",
    "primary_scoring_eligible",
    "gold_edge",
    "acceptable_alternatives",
    "evidence_support_scope",
    "annotation_origin",
    "schema_gap_relation",
}
RESULT_KEYS = {
    "canonical_pair_id",
    "source_canonical_ko_id",
    "target_canonical_ko_id",
    "relation_type",
    "evidence_ids",
    "rationale",
}
SHA1_RE = re.compile(r"[0-9a-f]{40}")
PAIR_ID_RE = re.compile(r"conn_(dev|holdout)_pair_[0-9a-f]{16}")


class ConnectionRunError(ValueError):
    """Raised when a run cannot satisfy its frozen execution contract."""


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConnectionRunError(f"Missing required file: {display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ConnectionRunError(f"Invalid JSON in {display_path(path)}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_json(value), encoding="utf-8")


def binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(result.stdout.strip())


def _collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_collect_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_collect_keys(item))
        return result
    return set()


def validate_input_chain(
    *,
    selection: dict[str, Any],
    selection_path: Path,
    candidate_completion: dict[str, Any],
    candidate_validation: dict[str, Any],
    inventory: dict[str, Any],
    catalogs: dict[str, Any],
    freeze_manifest: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    errors: list[str] = []
    if selection.get("artifact_type") != "connection_candidate_selection":
        errors.append("candidate selection artifact_type is invalid")
    if selection.get("method", {}).get("id") != "overlap_bridge_v0.1":
        errors.append("candidate selection is not overlap_bridge_v0.1")
    if selection.get("selected_pair_count") != 125:
        errors.append("candidate selection count must be 125")
    if candidate_completion.get("status") != "final":
        errors.append("candidate generation completion is not final")
    if candidate_completion.get("artifacts", {}).get("selection") != binding(
        selection_path
    ):
        errors.append("candidate completion does not bind the selected artifact")
    if candidate_validation.get("status") != "complete_with_scope_limitation":
        errors.append("candidate validation completion status is invalid")
    if candidate_validation.get("selected_method") != "overlap_bridge_v0.1":
        errors.append("candidate validation selected method mismatch")
    selected_evaluation = candidate_validation.get("method_evaluations", {}).get(
        "overlap_bridge", {}
    )
    if selected_evaluation.get("generation_complete") != binding(
        paths["candidate_completion"]
    ):
        errors.append("candidate validation does not bind the selected generation")
    if candidate_completion.get("method", {}).get("id") != "overlap_bridge_v0.1":
        errors.append("candidate completion method mismatch")
    if inventory.get("artifact_type") != "connection_discovery_oracle_canonical_inventory":
        errors.append("canonical inventory artifact_type is invalid")
    if catalogs.get("artifact_type") != "connection_evidence_catalog_bundle":
        errors.append("Evidence catalog artifact_type is invalid")
    if freeze_manifest.get("status") != "frozen_content_binding":
        errors.append("benchmark freeze manifest status is invalid")
    frozen = freeze_manifest.get("frozen_artifacts", {})
    expected_frozen = {
        "oracle_canonical_inventory": paths["canonical_inventory"],
        "evidence_catalogs": paths["evidence_catalogs"],
    }
    for name, path in expected_frozen.items():
        if frozen.get(name) != binding(path):
            errors.append(f"frozen {name} binding mismatch")
    leaked = (
        _collect_keys(selection)
        | _collect_keys(inventory)
        | _collect_keys(catalogs)
    ) & {"gold_edge", "category", "primary_scoring_eligible", "acceptable_alternatives"}
    if leaked:
        errors.append(f"gold fields found in runner inputs: {sorted(leaked)}")
    if errors:
        raise ConnectionRunError("; ".join(errors))


def build_execution_items(
    selection: dict[str, Any],
    inventory: dict[str, Any],
    catalogs: dict[str, Any],
) -> list[dict[str, Any]]:
    object_map = {
        item["canonical_ko_id"]: item for item in inventory["canonical_objects"]
    }
    catalog_map = {
        item["canonical_pair_id"]: item for item in catalogs["catalogs"]
    }
    items: list[dict[str, Any]] = []
    for selected in selection["selected_pairs"]:
        pair_id = selected["canonical_pair_id"]
        endpoint_ids = [
            selected["ko_a"]["canonical_ko_id"],
            selected["ko_b"]["canonical_ko_id"],
        ]
        if len(set(endpoint_ids)) != 2:
            raise ConnectionRunError(f"{pair_id}: invalid candidate endpoints")
        if any(endpoint not in object_map for endpoint in endpoint_ids):
            raise ConnectionRunError(f"{pair_id}: missing canonical endpoint")
        catalog = catalog_map.get(pair_id)
        if catalog is None or set(catalog["endpoint_ids"]) != set(endpoint_ids):
            raise ConnectionRunError(f"{pair_id}: Evidence catalog endpoint mismatch")

        def visible_object(object_id: str) -> dict[str, Any]:
            obj = object_map[object_id]
            return {
                "canonical_ko_id": obj["canonical_ko_id"],
                "canonical_name": obj["canonical_name"],
                "canonical_type": obj["canonical_type"],
                "aliases": obj["aliases"],
                "groundings": [
                    {
                        "lecture_id": mention["lecture_id"],
                        "source_spans": mention["source_spans"],
                    }
                    for mention in obj["mentions"]
                ],
            }

        model_input = {
            "candidate_pair": {
                "canonical_pair_id": pair_id,
                "ko_a": visible_object(endpoint_ids[0]),
                "ko_b": visible_object(endpoint_ids[1]),
            },
            "evidence_catalog": [
                {
                    "evidence_id": evidence["evidence_id"],
                    "lecture_id": evidence["lecture_id"],
                    "span": evidence["span"],
                }
                for evidence in catalog["evidence_items"]
            ],
        }
        leaked = _collect_keys(model_input) & FORBIDDEN_MODEL_KEYS
        if leaked:
            raise ConnectionRunError(f"{pair_id}: model input leaked {sorted(leaked)}")
        items.append({
            "canonical_pair_id": pair_id,
            "endpoint_ids": endpoint_ids,
            "allowed_evidence_ids": {
                item["evidence_id"] for item in catalog["evidence_items"]
            },
            "model_input": model_input,
        })
    ids = [item["canonical_pair_id"] for item in items]
    if len(ids) != len(set(ids)) or len(ids) != selection["selected_pair_count"]:
        raise ConnectionRunError("execution item pair set is invalid")
    return items


def build_payload(
    *, model: str, prompt: str, model_input: dict[str, Any],
    temperature: float, top_p: float, max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(model_input, ensure_ascii=False, indent=2)},
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def call_deepseek(*, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach DeepSeek API: {exc}") from exc


def extract_response(api_response: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    try:
        content = api_response["choices"][0]["message"]["content"]
        finish_reason = api_response["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError) as exc:
        raise ConnectionRunError("Unexpected DeepSeek response shape") from exc
    if not isinstance(content, str) or not content.strip():
        raise ConnectionRunError("DeepSeek response content is empty")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ConnectionRunError(f"Model output is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ConnectionRunError("Model output must be a JSON object")
    return parsed, finish_reason if isinstance(finish_reason, str) else None


def validate_prediction(prediction: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    if set(prediction) != {"result"} or not isinstance(prediction["result"], dict):
        raise ConnectionRunError("Prediction must contain exactly one result object")
    result = prediction["result"]
    if set(result) != RESULT_KEYS:
        raise ConnectionRunError("Prediction result field set is invalid")
    pair_id = item["canonical_pair_id"]
    if result["canonical_pair_id"] != pair_id:
        raise ConnectionRunError(f"{pair_id}: prediction changed canonical_pair_id")
    endpoints = {
        result.get("source_canonical_ko_id"), result.get("target_canonical_ko_id")
    }
    if endpoints != set(item["endpoint_ids"]):
        raise ConnectionRunError(f"{pair_id}: prediction changed candidate endpoints")
    if result.get("relation_type") not in ALLOWED_RELATIONS:
        raise ConnectionRunError(f"{pair_id}: prediction Relation type is invalid")
    evidence_ids = result.get("evidence_ids")
    if not isinstance(evidence_ids, list) or any(
        not isinstance(value, str) for value in evidence_ids
    ):
        raise ConnectionRunError(f"{pair_id}: evidence_ids must be a string list")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ConnectionRunError(f"{pair_id}: duplicate Evidence IDs")
    unknown = set(evidence_ids) - item["allowed_evidence_ids"]
    if unknown:
        raise ConnectionRunError(f"{pair_id}: unknown Evidence IDs {sorted(unknown)}")
    if not isinstance(result.get("rationale"), str):
        raise ConnectionRunError(f"{pair_id}: rationale must be a string")
    return result


def run_metadata_base(
    *, args: argparse.Namespace, paths: dict[str, Path], prompt_path: Path,
    schema_path: Path, commit: str, dirty: bool, items: list[dict[str, Any]],
    payload_hashes: list[str], started_at: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "canonical_connection_run_metadata",
        "version": "v0.1",
        "run_id": args.run_id,
        "run_status": "prepared",
        "provider": "deepseek",
        "method_commit": args.method_commit,
        "git_commit_at_start": commit,
        "git_dirty_at_start": dirty,
        "request_partitioning": "one_canonical_pair_per_request_v0.1",
        "execution_scope": "subset" if args.only else "full_selected_candidate_set",
        "request_parameters": {
            "model": args.model,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        },
        "inputs": {name: binding(path) for name, path in paths.items()},
        "prompt": binding(prompt_path),
        "prediction_schema": binding(schema_path),
        "runner": {"path": display_path(Path(__file__)), "sha256": sha256_file(Path(__file__)), "version": RUNNER_VERSION},
        "candidate_count": len(items),
        "candidate_pair_ids_sha256": sha256_json([item["canonical_pair_id"] for item in items]),
        "request_payload_set_sha256": sha256_json(payload_hashes),
        "started_at": started_at,
        "dry_run": args.dry_run,
        "request_success": None,
        "json_parse_success": None,
        "prediction_schema_valid": None,
        "finish_reason": None,
        "completed_candidate_count": 0,
        "latency_ms": None,
        "usage": None,
        "retry_count": 0,
        "failure": None,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-selection", default=str(DEFAULT_SELECTION))
    parser.add_argument("--candidate-completion", default=str(DEFAULT_CANDIDATE_COMPLETION))
    parser.add_argument("--candidate-validation", default=str(DEFAULT_CANDIDATE_VALIDATION))
    parser.add_argument("--canonical-inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--evidence-catalogs", default=str(DEFAULT_CATALOGS))
    parser.add_argument("--freeze-manifest", default=str(DEFAULT_FREEZE_MANIFEST))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--prediction-schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--run-id", default="run_01")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--only", help="Run one candidate pair for a non-final subset smoke test.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = resolve_path(args.run_dir)
    if run_dir.exists():
        print(f"Connection run failed: run directory already exists: {display_path(run_dir)}")
        return 1
    if SHA1_RE.fullmatch(args.method_commit) is None:
        print("Connection run failed: method_commit must be a 40-character SHA-1")
        return 1
    commit = git_commit()
    dirty = git_dirty()
    if commit != args.method_commit or dirty is not False:
        print("Connection run failed: repository must be clean at the supplied method commit")
        return 1
    paths = {
        "candidate_selection": resolve_path(args.candidate_selection),
        "candidate_completion": resolve_path(args.candidate_completion),
        "candidate_validation": resolve_path(args.candidate_validation),
        "canonical_inventory": resolve_path(args.canonical_inventory),
        "evidence_catalogs": resolve_path(args.evidence_catalogs),
        "freeze_manifest": resolve_path(args.freeze_manifest),
    }
    prompt_path = resolve_path(args.prompt)
    schema_path = resolve_path(args.prediction_schema)
    try:
        selection = load_json(paths["candidate_selection"])
        candidate_completion = load_json(paths["candidate_completion"])
        candidate_validation = load_json(paths["candidate_validation"])
        inventory = load_json(paths["canonical_inventory"])
        catalogs = load_json(paths["evidence_catalogs"])
        freeze_manifest = load_json(paths["freeze_manifest"])
        validate_input_chain(
            selection=selection, selection_path=paths["candidate_selection"],
            candidate_completion=candidate_completion,
            candidate_validation=candidate_validation, inventory=inventory,
            catalogs=catalogs, freeze_manifest=freeze_manifest, paths=paths,
        )
        items = build_execution_items(selection, inventory, catalogs)
        if args.only:
            if PAIR_ID_RE.fullmatch(args.only) is None:
                raise ConnectionRunError("--only has an invalid canonical pair ID")
            items = [item for item in items if item["canonical_pair_id"] == args.only]
            if not items:
                raise ConnectionRunError("--only pair is not in the selected candidate set")
        prompt = prompt_path.read_text(encoding="utf-8")
        payloads = [
            build_payload(
                model=args.model, prompt=prompt, model_input=item["model_input"],
                temperature=args.temperature, top_p=args.top_p, max_tokens=args.max_tokens,
            )
            for item in items
        ]
    except (ConnectionRunError, OSError) as exc:
        print(f"Connection run failed: {exc}")
        return 1

    rendered_dir = run_dir / "rendered_inputs" / "pairs"
    raw_dir = run_dir / "raw_responses" / "pairs"
    pair_output_dir = run_dir / "output" / "pairs"
    pair_metadata_dir = run_dir / "metadata" / "pairs"
    run_metadata_path = run_dir / "metadata" / "run_metadata.json"
    for directory in (rendered_dir, raw_dir, pair_output_dir, pair_metadata_dir):
        directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    metadata = run_metadata_base(
        args=args, paths=paths, prompt_path=prompt_path, schema_path=schema_path,
        commit=commit, dirty=dirty, items=items,
        payload_hashes=[sha256_json(payload) for payload in payloads], started_at=started_at,
    )
    for item, payload in zip(items, payloads):
        write_json(rendered_dir / f"{item['canonical_pair_id']}.json", payload)
    if args.dry_run:
        metadata["run_status"] = "dry_run_complete"
        write_json(run_metadata_path, metadata)
        print(f"Rendered {len(items)} candidate-scoped Connection requests to {display_path(run_dir)}")
        return 0

    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        metadata["run_status"] = "request_failed"
        metadata["failure"] = "DEEPSEEK_API_KEY is unavailable"
        write_json(run_metadata_path, metadata)
        print("Connection run failed: DEEPSEEK_API_KEY is unavailable")
        return 1

    results: list[dict[str, Any]] = []
    usages: list[dict[str, Any]] = []
    finish_reasons: list[str | None] = []
    started_clock = time.monotonic()
    for item, payload in zip(items, payloads):
        pair_id = item["canonical_pair_id"]
        pair_started = time.monotonic()
        pair_metadata = {"canonical_pair_id": pair_id, "request_success": False, "json_parse_success": False, "prediction_schema_valid": False}
        try:
            response = call_deepseek(api_key=api_key, payload=payload)
            pair_metadata["request_success"] = True
            write_json(raw_dir / f"{pair_id}.json", response)
            parsed, finish_reason = extract_response(response)
            pair_metadata["json_parse_success"] = True
            result = validate_prediction(parsed, item)
            pair_metadata["prediction_schema_valid"] = True
            pair_metadata["finish_reason"] = finish_reason
            pair_metadata["latency_ms"] = round((time.monotonic() - pair_started) * 1000)
            write_json(pair_output_dir / f"{pair_id}.json", result)
            write_json(pair_metadata_dir / f"{pair_id}.json", pair_metadata)
            results.append(result)
            finish_reasons.append(finish_reason)
            if isinstance(response.get("usage"), dict):
                usages.append(response["usage"])
        except (RuntimeError, ConnectionRunError) as exc:
            pair_metadata["failure"] = str(exc)
            pair_metadata["latency_ms"] = round((time.monotonic() - pair_started) * 1000)
            write_json(pair_metadata_dir / f"{pair_id}.json", pair_metadata)
            metadata.update({
                "run_status": (
                    "prediction_schema_failed" if pair_metadata["json_parse_success"]
                    else "json_parse_failed" if pair_metadata["request_success"]
                    else "request_failed"
                ),
                "request_success": pair_metadata["request_success"],
                "json_parse_success": pair_metadata["json_parse_success"],
                "prediction_schema_valid": pair_metadata["prediction_schema_valid"],
                "completed_candidate_count": len(results),
                "latency_ms": round((time.monotonic() - started_clock) * 1000),
                "failure": {"canonical_pair_id": pair_id, "message": str(exc)},
            })
            write_json(run_metadata_path, metadata)
            print(f"Connection run failed for {pair_id}: {exc}")
            return 1

    prediction = {
        "artifact_type": "canonical_connection_predictions",
        "version": "v0.1",
        "results": results,
    }
    prediction_path = run_dir / "output" / "canonical_connection_predictions.json"
    write_json(prediction_path, prediction)
    usage_totals = {
        key: sum(item.get(key, 0) for item in usages if isinstance(item.get(key), int))
        for key in sorted({key for item in usages for key in item})
    }
    metadata.update({
        "run_status": "completed_subset" if args.only else "completed",
        "request_success": True,
        "json_parse_success": True,
        "prediction_schema_valid": True,
        "finish_reason": "stop" if finish_reasons and all(value == "stop" for value in finish_reasons) else "mixed",
        "completed_candidate_count": len(results),
        "latency_ms": round((time.monotonic() - started_clock) * 1000),
        "usage": {"request_count": len(items), **usage_totals},
        "prediction": binding(prediction_path),
    })
    write_json(run_metadata_path, metadata)
    print(f"Saved {len(results)} canonical Connection predictions to {display_path(prediction_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
