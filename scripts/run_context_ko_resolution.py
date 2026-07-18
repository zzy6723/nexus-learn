#!/usr/bin/env python3
"""Run candidate-scoped context-aware Knowledge Object identity resolution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_deterministic_ko_canonicalization import read_repository_state
from scripts.run_relation_extraction import (
    call_deepseek,
    extract_content,
    extract_finish_reason,
    load_dotenv,
    parse_model_content,
)


DEFAULT_PROMPT = (
    ROOT
    / "experiments"
    / "knowledge_object_resolution"
    / "002c_2_context_aware_resolution"
    / "prompt.md"
)
DEFAULT_MODEL = "deepseek-v4-flash"
RUNNER_VERSION = "context_ko_resolution_runner_v0.1"
DECISIONS = {"SAME_OBJECT", "DISTINCT_OBJECT", "UNRESOLVED"}


class ContextResolutionError(ValueError):
    """Raised when the context-resolution run violates its contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--lecture-inventory", required=True)
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--run-id", default="run_01")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextResolutionError(f"Unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextResolutionError(f"{label} must be a JSON object.")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ContextResolutionError(f"Missing artifact: {display_path(path)}")
    return {"path": display_path(path), "sha256": sha256_file(path)}


def validate_candidate_bundle(candidate_dir: Path) -> dict[str, Any]:
    candidate_path = candidate_dir / "candidate_pairs.json"
    metadata_path = candidate_dir / "metadata.json"
    audit_path = candidate_dir / "candidate_generation_audit.json"
    marker_path = candidate_dir / "candidate_generation_complete.json"
    marker = load_json(marker_path, label="candidate completion marker")
    if marker.get("status") != "final":
        raise ContextResolutionError("Candidate bundle is not final.")
    expected = {
        "candidates": binding(candidate_path),
        "audit": binding(audit_path),
        "metadata": binding(metadata_path),
    }
    if marker.get("artifacts") != expected:
        raise ContextResolutionError("Candidate completion marker is stale.")
    bundle = load_json(candidate_path, label="candidate bundle")
    candidates = bundle.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ContextResolutionError("Candidate bundle is empty.")
    ids = [item.get("candidate_id") for item in candidates]
    if len(ids) != len(set(ids)) or any(not isinstance(item, str) for item in ids):
        raise ContextResolutionError("Candidate IDs are invalid or duplicated.")
    return bundle


def build_model_input(
    candidate: dict[str, Any], lecture_by_id: dict[str, str]
) -> dict[str, Any]:
    endpoints = []
    relevant_lectures: dict[str, str] = {}
    for key in ("mention_a", "mention_b"):
        mention = candidate[key]
        lecture_id = mention["lecture_id"]
        if lecture_id not in lecture_by_id:
            raise ContextResolutionError(f"Unknown lecture: {lecture_id}")
        endpoints.append(
            {
                "mention_id": mention["mention_id"],
                "lecture_id": lecture_id,
                "name": mention["name"],
                "type": mention["type"],
                "source_spans": mention["source_spans"],
            }
        )
        relevant_lectures[lecture_id] = lecture_by_id[lecture_id]
    return {
        "candidate_id": candidate["candidate_id"],
        "unordered_mentions": endpoints,
        "lectures": [
            {"lecture_id": lecture_id, "text": text}
            for lecture_id, text in relevant_lectures.items()
        ],
    }


def build_payload(
    *, model: str, prompt: str, model_input: dict[str, Any], temperature: float,
    top_p: float, max_tokens: int
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


def validate_prediction(
    prediction: dict[str, Any], candidate: dict[str, Any], lecture_by_id: dict[str, str]
) -> None:
    required = {
        "candidate_id", "mention_a", "mention_b", "decision", "evidence_spans", "rationale"
    }
    if set(prediction) != required:
        raise ContextResolutionError("Prediction keys do not match the frozen schema.")
    if prediction["candidate_id"] != candidate["candidate_id"]:
        raise ContextResolutionError("Prediction changed candidate_id.")
    if prediction["mention_a"] != candidate["mention_a"]["mention_id"]:
        raise ContextResolutionError("Prediction changed mention_a.")
    if prediction["mention_b"] != candidate["mention_b"]["mention_id"]:
        raise ContextResolutionError("Prediction changed mention_b.")
    if prediction["decision"] not in DECISIONS:
        raise ContextResolutionError("Prediction decision is invalid.")
    if not isinstance(prediction["rationale"], str) or not prediction["rationale"].strip():
        raise ContextResolutionError("Prediction rationale is empty.")
    evidence = prediction["evidence_spans"]
    if not isinstance(evidence, list):
        raise ContextResolutionError("Prediction evidence_spans must be a list.")
    allowed_lectures = {
        candidate["mention_a"]["lecture_id"], candidate["mention_b"]["lecture_id"]
    }
    if prediction["decision"] != "UNRESOLVED" and not evidence:
        raise ContextResolutionError("Resolved decision requires evidence.")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"lecture_id", "span"}:
            raise ContextResolutionError("Prediction evidence item is malformed.")
        lecture_id, span = item["lecture_id"], item["span"]
        if lecture_id not in allowed_lectures or not isinstance(span, str) or not span:
            raise ContextResolutionError("Prediction evidence endpoint is invalid.")
        if span not in lecture_by_id[lecture_id]:
            raise ContextResolutionError("Prediction evidence span is not exact.")


def artifact_targets(run_dir: Path, candidate_id: str) -> dict[str, Path]:
    return {
        "rendered": run_dir / "rendered_inputs" / "pairs" / f"{candidate_id}.json",
        "raw": run_dir / "raw_responses" / "pairs" / f"{candidate_id}.json",
        "output": run_dir / "output" / "pairs" / f"{candidate_id}.json",
        "metadata": run_dir / "metadata" / "pairs" / f"{candidate_id}.json",
    }


def run(
    args: argparse.Namespace,
    *,
    api_call: Callable[..., dict[str, Any]] = call_deepseek,
    repository_reader: Callable[[], tuple[str, bool]] = read_repository_state,
) -> int:
    candidate_dir = Path(args.candidate_dir).resolve()
    lecture_path = Path(args.lecture_inventory).resolve()
    prompt_path = Path(args.prompt).resolve()
    run_dir = Path(args.run_dir).resolve()
    aggregate_paths = {
        "output": run_dir / "output" / "identity_decisions.json",
        "metadata": run_dir / "metadata" / "run_metadata.json",
        "completion": run_dir / "resolution_complete.json",
    }
    try:
        bundle = validate_candidate_bundle(candidate_dir)
        lecture_inventory = load_json(lecture_path, label="lecture inventory")
        lecture_by_id = {
            item["lecture_id"]: item["text"] for item in lecture_inventory.get("lectures", [])
        }
        prompt = prompt_path.read_text(encoding="utf-8")
        commit, dirty = repository_reader()
        if not args.dry_run and (dirty or commit != args.method_commit):
            raise ContextResolutionError(
                "Formal run requires a clean worktree at the declared method commit."
            )
        candidates = bundle["candidates"]
        all_targets = [artifact_targets(run_dir, item["candidate_id"]) for item in candidates]
        existing = [
            path for targets in all_targets for path in targets.values() if path.exists()
        ] + [path for path in aggregate_paths.values() if path.exists()]
        if existing and not args.overwrite:
            raise ContextResolutionError("Refusing to overwrite existing run artifacts.")
        if args.overwrite:
            for path in existing:
                path.unlink()
        payloads = []
        for candidate, targets in zip(candidates, all_targets, strict=True):
            model_input = build_model_input(candidate, lecture_by_id)
            payload = build_payload(
                model=args.model, prompt=prompt, model_input=model_input,
                temperature=args.temperature, top_p=args.top_p, max_tokens=args.max_tokens,
            )
            payloads.append(payload)
            write_json(targets["rendered"], payload)
            write_json(
                targets["metadata"],
                {
                    "candidate_id": candidate["candidate_id"],
                    "run_status": "rendered" if args.dry_run else "prepared",
                    "request_payload_sha256": sha256_json(payload),
                },
            )
        aggregate_metadata = {
            "artifact_type": "ko_context_resolution_run_metadata",
            "version": "v0.1",
            "run_id": args.run_id,
            "run_status": "dry_run_complete" if args.dry_run else "running",
            "method_id": "candidate_scoped_context_resolution_v0_1",
            "method_commit": args.method_commit,
            "git_commit_at_start": commit,
            "git_dirty_at_start": dirty,
            "request_partitioning": "one_identity_candidate_per_request_v0_1",
            "request_parameters": {
                "model": args.model, "temperature": args.temperature, "top_p": args.top_p,
                "max_tokens": args.max_tokens, "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            },
            "inputs": {
                "candidate_bundle": binding(candidate_dir / "candidate_pairs.json"),
                "candidate_completion_marker": binding(candidate_dir / "candidate_generation_complete.json"),
                "lecture_inventory": binding(lecture_path),
                "prompt": binding(prompt_path),
            },
            "runner": {**binding(Path(__file__).resolve()), "version": RUNNER_VERSION},
            "candidate_count": len(candidates),
            "request_payload_set_sha256": sha256_json([sha256_json(item) for item in payloads]),
        }
        if args.dry_run:
            write_json(aggregate_paths["metadata"], aggregate_metadata)
            print(f"Rendered {len(candidates)} KO identity requests.")
            return 0
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            aggregate_metadata["run_status"] = "configuration_failed"
            aggregate_metadata["api_error"] = "DEEPSEEK_API_KEY is not set."
            write_json(aggregate_paths["metadata"], aggregate_metadata)
            return 2
        results = []
        total_latency = 0
        for candidate, payload, targets in zip(candidates, payloads, all_targets, strict=True):
            started = time.perf_counter()
            try:
                response = api_call(api_key=api_key, payload=payload)
                total_latency += int((time.perf_counter() - started) * 1000)
                write_json(targets["raw"], response)
                if extract_finish_reason(response) != "stop":
                    raise ContextResolutionError("API finish_reason was not stop.")
                parsed = parse_model_content(extract_content(response))
                write_json(targets["output"], parsed)
                validate_prediction(parsed, candidate, lecture_by_id)
            except (RuntimeError, ContextResolutionError) as exc:
                pair_metadata = load_json(targets["metadata"], label="pair metadata")
                pair_metadata.update({"run_status": "failed", "error": str(exc)})
                write_json(targets["metadata"], pair_metadata)
                aggregate_metadata.update(
                    {
                        "run_status": "candidate_failed",
                        "failed_candidate_id": candidate["candidate_id"],
                        "completed_candidate_count": len(results),
                        "error": str(exc),
                    }
                )
                write_json(aggregate_paths["metadata"], aggregate_metadata)
                print(f"Context resolution failed for {candidate['candidate_id']}: {exc}")
                return 1
            pair_metadata = load_json(targets["metadata"], label="pair metadata")
            pair_metadata.update(
                {
                    "run_status": "completed", "request_success": True,
                    "json_parse_success": True, "prediction_schema_valid": True,
                    "finish_reason": "stop", "raw_response_sha256": sha256_file(targets["raw"]),
                    "prediction_sha256": sha256_file(targets["output"]),
                }
            )
            write_json(targets["metadata"], pair_metadata)
            results.append(parsed)
        output = {
            "artifact_type": "ko_context_identity_decisions", "version": "v0.1",
            "method_id": "candidate_scoped_context_resolution_v0_1",
            "results": results,
        }
        write_json(aggregate_paths["output"], output)
        aggregate_metadata.update(
            {
                "run_status": "completed", "request_success": True,
                "json_parse_success": True, "prediction_schema_valid": True,
                "finish_reason": "stop", "completed_candidate_count": len(results),
                "latency_ms": total_latency, "prediction_sha256": sha256_file(aggregate_paths["output"]),
            }
        )
        write_json(aggregate_paths["metadata"], aggregate_metadata)
        write_json(
            aggregate_paths["completion"],
            {
                "artifact_type": "ko_context_resolution_complete", "version": "v0.1",
                "status": "final", "method_commit": args.method_commit,
                "artifacts": {
                    "identity_decisions": binding(aggregate_paths["output"]),
                    "metadata": binding(aggregate_paths["metadata"]),
                },
            },
        )
    except (OSError, ContextResolutionError) as exc:
        print(f"Context resolution failed: {exc}")
        return 1
    print(f"Saved {len(results)} context identity decisions.")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
