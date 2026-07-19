#!/usr/bin/env python3
"""Run context-aware KO identity resolution with opaque evidence IDs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_context_ko_resolution import (
    ContextResolutionError,
    artifact_targets,
    binding,
    load_json,
    sha256_file,
    sha256_json,
    validate_candidate_bundle,
    write_json,
)
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
    / "002c_4_evidence_id_resolution"
    / "prompt.md"
)
DEFAULT_MODEL = "deepseek-v4-flash"
RUNNER_VERSION = "context_ko_resolution_runner_v0.2.1"
METHOD_ID = "candidate_scoped_context_resolution_evidence_ids_v0_2_1"
DECISIONS = {"SAME_OBJECT", "DISTINCT_OBJECT", "UNRESOLVED"}


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


def exact_text_blocks(text: str) -> list[str]:
    """Return non-empty paragraph blocks without changing their source bytes."""
    blocks = []
    start = 0
    separators = list(re.finditer(r"\n[ \t]*\n", text))
    for separator in [*separators, None]:
        end = separator.start() if separator is not None else len(text)
        raw_block = text[start:end]
        left = len(raw_block) - len(raw_block.lstrip())
        right = len(raw_block.rstrip())
        if left < right:
            span = raw_block[left:right]
            if span not in blocks:
                blocks.append(span)
        if separator is not None:
            start = separator.end()
    return blocks


def build_evidence_catalog(
    candidate: dict[str, Any], lecture_by_id: dict[str, str]
) -> list[dict[str, str]]:
    lecture_ids = []
    for key in ("mention_a", "mention_b"):
        lecture_id = candidate[key]["lecture_id"]
        if lecture_id not in lecture_by_id:
            raise ContextResolutionError(f"Unknown lecture: {lecture_id}")
        if lecture_id not in lecture_ids:
            lecture_ids.append(lecture_id)
    catalog = []
    for lecture_id in lecture_ids:
        blocks = exact_text_blocks(lecture_by_id[lecture_id])
        for span in blocks:
            catalog.append(
                {
                    "evidence_id": f"evidence_{len(catalog) + 1:03d}",
                    "lecture_id": lecture_id,
                    "span": span,
                }
            )
    if not catalog:
        raise ContextResolutionError("Relevant lectures contain no evidence blocks.")
    return catalog


def build_model_input(
    candidate: dict[str, Any], lecture_by_id: dict[str, str]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    endpoints = []
    for key in ("mention_a", "mention_b"):
        mention = candidate[key]
        endpoints.append(
            {
                "mention_id": mention["mention_id"],
                "lecture_id": mention["lecture_id"],
                "name": mention["name"],
                "type": mention["type"],
                "upstream_source_spans": mention["source_spans"],
            }
        )
    catalog = build_evidence_catalog(candidate, lecture_by_id)
    return (
        {
            "candidate_id": candidate["candidate_id"],
            "unordered_mentions": endpoints,
            "evidence_catalog": catalog,
        },
        catalog,
    )


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


def validate_and_materialize_prediction(
    prediction: dict[str, Any], candidate: dict[str, Any],
    evidence_catalog: list[dict[str, str]], lecture_by_id: dict[str, str]
) -> dict[str, Any]:
    required = {
        "candidate_id", "mention_a", "mention_b", "decision", "evidence_ids", "rationale"
    }
    if set(prediction) != required:
        raise ContextResolutionError("Prediction keys do not match the v0.2 schema.")
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
    evidence_ids = prediction["evidence_ids"]
    if not isinstance(evidence_ids, list) or any(not isinstance(item, str) for item in evidence_ids):
        raise ContextResolutionError("Prediction evidence_ids must be a list of strings.")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ContextResolutionError("Prediction evidence_ids contain duplicates.")
    if prediction["decision"] != "UNRESOLVED" and not evidence_ids:
        raise ContextResolutionError("Resolved decision requires evidence IDs.")
    catalog_by_id = {item["evidence_id"]: item for item in evidence_catalog}
    if any(item not in catalog_by_id for item in evidence_ids):
        raise ContextResolutionError("Prediction referenced an unknown evidence ID.")
    evidence_spans = []
    for evidence_id in evidence_ids:
        item = catalog_by_id[evidence_id]
        if item["span"] not in lecture_by_id[item["lecture_id"]]:
            raise ContextResolutionError("Evidence catalog is not exact to the lecture source.")
        evidence_spans.append(
            {"lecture_id": item["lecture_id"], "span": item["span"]}
        )
    return {**prediction, "evidence_spans": evidence_spans}


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
        catalogs = []
        for candidate, targets in zip(candidates, all_targets, strict=True):
            model_input, catalog = build_model_input(candidate, lecture_by_id)
            payload = build_payload(
                model=args.model, prompt=prompt, model_input=model_input,
                temperature=args.temperature, top_p=args.top_p, max_tokens=args.max_tokens,
            )
            payloads.append(payload)
            catalogs.append(catalog)
            write_json(targets["rendered"], payload)
            write_json(
                targets["metadata"],
                {
                    "candidate_id": candidate["candidate_id"],
                    "run_status": "rendered" if args.dry_run else "prepared",
                    "request_payload_sha256": sha256_json(payload),
                    "evidence_catalog_sha256": sha256_json(catalog),
                    "evidence_unit_count": len(catalog),
                },
            )
        aggregate_metadata = {
            "artifact_type": "ko_context_resolution_run_metadata",
            "version": "v0.2.1",
            "run_id": args.run_id,
            "run_status": "dry_run_complete" if args.dry_run else "running",
            "method_id": METHOD_ID,
            "method_commit": args.method_commit,
            "git_commit_at_start": commit,
            "git_dirty_at_start": dirty,
            "request_partitioning": "one_identity_candidate_per_request_v0_1",
            "evidence_transport": "candidate_scoped_opaque_ids_v0_2_1",
            "request_parameters": {
                "model": args.model, "temperature": args.temperature, "top_p": args.top_p,
                "max_tokens": args.max_tokens, "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            },
            "inputs": {
                "candidate_bundle": binding(candidate_dir / "candidate_pairs.json"),
                "candidate_completion_marker": binding(
                    candidate_dir / "candidate_generation_complete.json"
                ),
                "lecture_inventory": binding(lecture_path),
                "prompt": binding(prompt_path),
            },
            "runner": {**binding(Path(__file__).resolve()), "version": RUNNER_VERSION},
            "candidate_count": len(candidates),
            "request_payload_set_sha256": sha256_json([sha256_json(item) for item in payloads]),
            "evidence_catalog_set_sha256": sha256_json([sha256_json(item) for item in catalogs]),
        }
        if args.dry_run:
            write_json(aggregate_paths["metadata"], aggregate_metadata)
            print(f"Rendered {len(candidates)} KO identity requests with evidence IDs.")
            return 0
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            aggregate_metadata["run_status"] = "configuration_failed"
            aggregate_metadata["api_error"] = "DEEPSEEK_API_KEY is not set."
            write_json(aggregate_paths["metadata"], aggregate_metadata)
            return 2
        results = []
        total_latency = 0
        for candidate, payload, catalog, targets in zip(
            candidates, payloads, catalogs, all_targets, strict=True
        ):
            started = time.perf_counter()
            try:
                response = api_call(api_key=api_key, payload=payload)
                total_latency += int((time.perf_counter() - started) * 1000)
                write_json(targets["raw"], response)
                if extract_finish_reason(response) != "stop":
                    raise ContextResolutionError("API finish_reason was not stop.")
                parsed = parse_model_content(extract_content(response))
                # Preserve the model-level prediction even when ID validation fails.
                write_json(targets["output"], parsed)
                materialized = validate_and_materialize_prediction(
                    parsed, candidate, catalog, lecture_by_id
                )
                write_json(targets["output"], materialized)
            except (RuntimeError, ContextResolutionError) as exc:
                pair_metadata = load_json(targets["metadata"], label="pair metadata")
                pair_metadata.update({"run_status": "failed", "error": str(exc)})
                if targets["raw"].is_file():
                    pair_metadata["raw_response_sha256"] = sha256_file(targets["raw"])
                if targets["output"].is_file():
                    pair_metadata["prediction_sha256"] = sha256_file(targets["output"])
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
            results.append(materialized)
        output = {
            "artifact_type": "ko_context_identity_decisions", "version": "v0.2.1",
            "method_id": METHOD_ID, "results": results,
        }
        write_json(aggregate_paths["output"], output)
        aggregate_metadata.update(
            {
                "run_status": "completed", "request_success": True,
                "json_parse_success": True, "prediction_schema_valid": True,
                "finish_reason": "stop", "completed_candidate_count": len(results),
                "latency_ms": total_latency,
                "prediction_sha256": sha256_file(aggregate_paths["output"]),
            }
        )
        write_json(aggregate_paths["metadata"], aggregate_metadata)
        write_json(
            aggregate_paths["completion"],
            {
                "artifact_type": "ko_context_resolution_complete", "version": "v0.2.1",
                "status": "final", "method_id": METHOD_ID,
                "method_commit": args.method_commit,
                "artifacts": {
                    "identity_decisions": binding(aggregate_paths["output"]),
                    "metadata": binding(aggregate_paths["metadata"]),
                },
            },
        )
    except (OSError, ContextResolutionError) as exc:
        print(f"Context resolution failed: {exc}")
        return 1
    print(f"Saved {len(results)} context identity decisions with evidence IDs.")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
