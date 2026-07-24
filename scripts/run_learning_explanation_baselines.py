#!/usr/bin/env python3
"""Render and execute Experiment 004 Learning Explanation baselines."""

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
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_learning_explanation_benchmark import validate_benchmark


EXPERIMENT_ROOT = ROOT / "experiments" / "learning_explanation"
STAGE_ROOT = EXPERIMENT_ROOT / "004_1_baselines"
DEFAULT_BENCHMARK = (
    ROOT
    / "benchmark"
    / "learning_explanation"
    / "development_v0_1"
    / "connection_instances.json"
)
DEFAULT_FREEZE_MANIFEST = (
    EXPERIMENT_ROOT
    / "004_0_benchmark_preparation"
    / "freeze_manifest.json"
)
DEFAULT_TEMPLATES = (
    STAGE_ROOT / "relation_paraphrase" / "templates_v0_1.json"
)
DEFAULT_PROMPT = STAGE_ROOT / "relation_only_llm" / "prompt.md"
DEFAULT_SCHEMA = (
    ROOT / "benchmark" / "schema" / "learning_explanation_output.schema.json"
)
BASE_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
RUNNER_VERSION = "learning_explanation_baseline_runner_v0.1"
METHODS = {
    "001a_deterministic_paraphrase",
    "001b_relation_only_llm",
}
RELATIONS = {
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "FORMALIZES",
    "CONTRASTS_WITH",
}
FIELD_NAMES = {
    "connection_summary",
    "why_connected",
    "learning_value",
}
OUTPUT_KEYS = {
    "explanation_instance_id",
    "source_ko_id",
    "relation_type",
    "target_ko_id",
    *FIELD_NAMES,
}
FORBIDDEN_MODEL_KEYS = {
    "source_connection_pair_id",
    "source_annotation_rationale",
    "provenance_stratum",
    "scope_flags",
    "data_role",
    "required_points",
    "forbidden_or_unsupported_points",
    "risk_tags",
    "gold_edge",
    "score",
    "success_criteria",
}
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
INSTANCE_ID_RE = re.compile(r"^le_(dev|ind)_[0-9]{3}$")

ApiCall = Callable[..., dict[str, Any]]
RepositoryReader = Callable[[], tuple[str | None, bool | None]]


class BaselineRunError(ValueError):
    """Raised when a baseline run cannot satisfy its execution contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
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
        raise BaselineRunError(
            f"Missing required file: {display_path(path)}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BaselineRunError(
            f"Invalid JSON in {display_path(path)}: {exc}"
        ) from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_json(value), encoding="utf-8")


def binding(path: Path) -> dict[str, str]:
    return {
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def read_repository_state() -> tuple[str | None, bool | None]:
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit_result.stdout.strip(), bool(status_result.stdout.strip())


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


def collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(collect_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(collect_keys(item))
        return keys
    return set()


def validate_freeze_chain(
    *,
    freeze_manifest_path: Path,
    benchmark_path: Path,
) -> dict[str, Any]:
    freeze = load_json(freeze_manifest_path)
    if freeze.get("artifact_type") != "learning_explanation_004_0_freeze_manifest":
        raise BaselineRunError("004-0 freeze manifest artifact_type is invalid.")
    if freeze.get("status") != "frozen_content_binding":
        raise BaselineRunError("004-0 freeze manifest is not final.")
    if SHA1_RE.fullmatch(str(freeze.get("freeze_commit", ""))) is None:
        raise BaselineRunError("004-0 freeze commit is invalid.")

    preflight_record = freeze.get("preflight")
    if not isinstance(preflight_record, dict):
        raise BaselineRunError("004-0 freeze manifest has no preflight binding.")
    preflight_path = resolve_path(str(preflight_record.get("path", "")))
    if (
        not preflight_path.is_file()
        or preflight_record.get("sha256") != sha256_file(preflight_path)
    ):
        raise BaselineRunError("004-0 preflight binding is stale.")
    preflight = load_json(preflight_path)
    benchmark_record = preflight.get("bindings", {}).get(
        "benchmark_completion"
    )
    if not isinstance(benchmark_record, dict):
        raise BaselineRunError("004-0 preflight has no benchmark binding.")
    benchmark_complete_path = resolve_path(
        str(benchmark_record.get("path", ""))
    )
    if (
        not benchmark_complete_path.is_file()
        or benchmark_record.get("sha256")
        != sha256_file(benchmark_complete_path)
    ):
        raise BaselineRunError("004-0 benchmark completion binding is stale.")
    complete = load_json(benchmark_complete_path)
    instance_record = complete.get("artifacts", {}).get(
        "connection_instances"
    )
    if not isinstance(instance_record, dict):
        raise BaselineRunError(
            "Benchmark completion has no Connection instance binding."
        )
    if resolve_path(instance_record["path"]).resolve() != benchmark_path.resolve():
        raise BaselineRunError(
            "Requested benchmark differs from the frozen Connection instances."
        )
    if instance_record.get("sha256") != sha256_file(benchmark_path):
        raise BaselineRunError("Frozen benchmark Connection instances changed.")
    validate_benchmark(ROOT, benchmark_path.parent)
    return freeze


def build_model_input(instance: dict[str, Any]) -> dict[str, Any]:
    model_input = {
        "explanation_instance_id": instance["explanation_instance_id"],
        "source_ko": {
            "canonical_ko_id": instance["source_ko"]["canonical_ko_id"],
            "canonical_name": instance["source_ko"]["canonical_name"],
            "canonical_type": instance["source_ko"]["canonical_type"],
        },
        "relation_type": instance["relation_type"],
        "symmetric": instance["symmetric"],
        "target_ko": {
            "canonical_ko_id": instance["target_ko"]["canonical_ko_id"],
            "canonical_name": instance["target_ko"]["canonical_name"],
            "canonical_type": instance["target_ko"]["canonical_type"],
        },
        "evidence_catalog": [],
    }
    leaked = collect_keys(model_input) & FORBIDDEN_MODEL_KEYS
    if leaked:
        raise BaselineRunError(
            f"Forbidden fields leaked into model input: {sorted(leaked)}"
        )
    if set(model_input) != {
        "explanation_instance_id",
        "source_ko",
        "relation_type",
        "symmetric",
        "target_ko",
        "evidence_catalog",
    }:
        raise BaselineRunError("Model input whitelist changed.")
    if model_input["evidence_catalog"]:
        raise BaselineRunError("Baseline model input must not contain Evidence.")
    return model_input


def build_payload(
    *,
    model: str,
    prompt: str,
    model_input: dict[str, Any],
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    model_input,
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def call_deepseek(
    *,
    api_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"DeepSeek API returned HTTP {exc.code}: {body}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Failed to reach DeepSeek API: {exc}") from exc


def extract_response(
    api_response: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    try:
        content = api_response["choices"][0]["message"]["content"]
        finish_reason = api_response["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError) as exc:
        raise BaselineRunError("Unexpected DeepSeek response shape.") from exc
    if not isinstance(content, str) or not content.strip():
        raise BaselineRunError("DeepSeek response content is empty.")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise BaselineRunError(
            f"Model output is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise BaselineRunError("Model output must be a JSON object.")
    return parsed, finish_reason if isinstance(finish_reason, str) else None


def validate_output(
    output: Any,
    instance: dict[str, Any],
) -> dict[str, Any]:
    instance_id = instance["explanation_instance_id"]
    if not isinstance(output, dict) or set(output) != OUTPUT_KEYS:
        raise BaselineRunError(
            f"{instance_id}: output field set is invalid."
        )
    expected = {
        "explanation_instance_id": instance_id,
        "source_ko_id": instance["source_ko"]["canonical_ko_id"],
        "relation_type": instance["relation_type"],
        "target_ko_id": instance["target_ko"]["canonical_ko_id"],
    }
    for field, value in expected.items():
        if output.get(field) != value:
            raise BaselineRunError(
                f"{instance_id}: immutable field {field} changed."
            )
    for field in FIELD_NAMES:
        value = output[field]
        if not isinstance(value, dict) or set(value) != {
            "text",
            "evidence_refs",
        }:
            raise BaselineRunError(
                f"{instance_id}: {field} structure is invalid."
            )
        if not isinstance(value["text"], str) or not value["text"].strip():
            raise BaselineRunError(
                f"{instance_id}: {field}.text must be non-empty."
            )
        if value["evidence_refs"] != []:
            raise BaselineRunError(
                f"{instance_id}: baseline Evidence references must be empty."
            )
    return output


def deterministic_output(
    instance: dict[str, Any],
    templates: dict[str, Any],
) -> dict[str, Any]:
    relation = instance["relation_type"]
    relation_template = templates["templates"].get(relation)
    if not isinstance(relation_template, dict):
        raise BaselineRunError(f"No deterministic template for {relation}.")
    values = {
        "source": instance["source_ko"]["canonical_name"],
        "target": instance["target_ko"]["canonical_name"],
    }
    output = {
        "explanation_instance_id": instance["explanation_instance_id"],
        "source_ko_id": instance["source_ko"]["canonical_ko_id"],
        "relation_type": relation,
        "target_ko_id": instance["target_ko"]["canonical_ko_id"],
    }
    for field in FIELD_NAMES:
        template = relation_template.get(field)
        if not isinstance(template, str) or not template:
            raise BaselineRunError(
                f"Deterministic template {relation}.{field} is missing."
            )
        output[field] = {
            "text": template.format(**values),
            "evidence_refs": [],
        }
    return validate_output(output, instance)


def aggregate_predictions(
    *,
    method_id: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "artifact_type": "learning_explanation_predictions",
        "artifact_schema_version": "v0.1",
        "method_id": method_id,
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True, choices=sorted(METHODS))
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument(
        "--freeze-manifest",
        default=str(DEFAULT_FREEZE_MANIFEST),
    )
    parser.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--prediction-schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--run-id", default="run_01")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--only")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--model",
        default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=900)
    return parser.parse_args(argv)


def run(
    args: argparse.Namespace,
    *,
    api_call: ApiCall = call_deepseek,
    repository_reader: RepositoryReader = read_repository_state,
) -> int:
    run_dir = resolve_path(args.run_dir)
    if run_dir.exists():
        print(
            "Learning Explanation baseline failed: run directory already "
            f"exists: {display_path(run_dir)}"
        )
        return 1
    if SHA1_RE.fullmatch(args.method_commit) is None:
        print(
            "Learning Explanation baseline failed: method_commit must be a "
            "40-character SHA-1."
        )
        return 1
    commit, dirty = repository_reader()
    if commit != args.method_commit or dirty is not False:
        print(
            "Learning Explanation baseline failed: repository must be clean "
            "at the supplied method commit."
        )
        return 1

    benchmark_path = resolve_path(args.benchmark)
    freeze_manifest_path = resolve_path(args.freeze_manifest)
    templates_path = resolve_path(args.templates)
    prompt_path = resolve_path(args.prompt)
    schema_path = resolve_path(args.prediction_schema)
    try:
        freeze = validate_freeze_chain(
            freeze_manifest_path=freeze_manifest_path,
            benchmark_path=benchmark_path,
        )
        benchmark = load_json(benchmark_path)
        instances = benchmark.get("instances")
        if not isinstance(instances, list) or not instances:
            raise BaselineRunError("Benchmark contains no explanation instances.")
        if args.only:
            if INSTANCE_ID_RE.fullmatch(args.only) is None:
                raise BaselineRunError("--only has an invalid instance ID.")
            instances = [
                item
                for item in instances
                if item["explanation_instance_id"] == args.only
            ]
            if not instances:
                raise BaselineRunError(
                    "--only instance is not in the benchmark."
                )
        model_inputs = [build_model_input(item) for item in instances]
        templates = load_json(templates_path)
        prompt = prompt_path.read_text(encoding="utf-8")
        if templates.get("method_id") != "001a_deterministic_paraphrase":
            raise BaselineRunError("Deterministic template method is invalid.")
        if not schema_path.is_file():
            raise BaselineRunError("Prediction schema is missing.")
        payloads = [
            build_payload(
                model=args.model,
                prompt=prompt,
                model_input=model_input,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
            )
            for model_input in model_inputs
        ]
    except (BaselineRunError, KeyError, OSError, ValueError) as exc:
        print(f"Learning Explanation baseline failed: {exc}")
        return 1

    rendered_dir = run_dir / "rendered_inputs" / "instances"
    raw_dir = run_dir / "raw_responses" / "instances"
    parsed_dir = run_dir / "parsed_responses" / "instances"
    output_dir = run_dir / "output" / "instances"
    metadata_dir = run_dir / "metadata" / "instances"
    for directory in (
        rendered_dir,
        raw_dir,
        parsed_dir,
        output_dir,
        metadata_dir,
    ):
        directory.mkdir(parents=True, exist_ok=False)

    method_asset_path = (
        templates_path
        if args.method == "001a_deterministic_paraphrase"
        else prompt_path
    )
    started_at = datetime.now(timezone.utc).isoformat()
    rendered_values: list[dict[str, Any]] = []
    for instance, model_input, payload in zip(
        instances,
        model_inputs,
        payloads,
    ):
        rendered = (
            {
                "method_id": args.method,
                "model_input": model_input,
                "template_binding": binding(templates_path),
            }
            if args.method == "001a_deterministic_paraphrase"
            else payload
        )
        rendered_values.append(rendered)
        write_json(
            rendered_dir / f"{instance['explanation_instance_id']}.json",
            rendered,
        )

    metadata = {
        "artifact_type": "learning_explanation_baseline_run_metadata",
        "artifact_schema_version": "v0.1",
        "run_id": args.run_id,
        "run_status": "prepared",
        "method_id": args.method,
        "method_commit": args.method_commit,
        "git_commit_at_start": commit,
        "git_dirty_at_start": dirty,
        "004_0_freeze_commit": freeze["freeze_commit"],
        "request_partitioning": "one_explanation_instance_per_request_v0.1",
        "execution_scope": "subset" if args.only else "full_development",
        "request_parameters": (
            None
            if args.method == "001a_deterministic_paraphrase"
            else {
                "model": args.model,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_tokens": args.max_tokens,
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            }
        ),
        "inputs": {
            "benchmark": binding(benchmark_path),
            "freeze_manifest": binding(freeze_manifest_path),
            "prediction_schema": binding(schema_path),
        },
        "method_asset": binding(method_asset_path),
        "runner": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "version": RUNNER_VERSION,
        },
        "instance_count": len(instances),
        "instance_ids_sha256": sha256_json(
            [item["explanation_instance_id"] for item in instances]
        ),
        "rendered_input_set_sha256": sha256_json(rendered_values),
        "started_at": started_at,
        "dry_run": args.dry_run,
        "api_call_count": 0,
        "request_success": None,
        "json_parse_success": None,
        "prediction_schema_valid": None,
        "finish_reason": None,
        "completed_instance_count": 0,
        "latency_ms": None,
        "usage": None,
        "failure": None,
    }
    run_metadata_path = run_dir / "metadata" / "run_metadata.json"
    if args.dry_run:
        metadata["run_status"] = "dry_run_complete"
        write_json(run_metadata_path, metadata)
        print(
            f"Rendered {len(instances)} {args.method} inputs to "
            f"{display_path(run_dir)}"
        )
        return 0

    results: list[dict[str, Any]] = []
    if args.method == "001a_deterministic_paraphrase":
        started_clock = time.monotonic()
        try:
            for instance in instances:
                result = deterministic_output(instance, templates)
                instance_id = instance["explanation_instance_id"]
                write_json(output_dir / f"{instance_id}.json", result)
                write_json(
                    metadata_dir / f"{instance_id}.json",
                    {
                        "explanation_instance_id": instance_id,
                        "generation_mode": "deterministic_template",
                        "prediction_schema_valid": True,
                    },
                )
                results.append(result)
            aggregate = aggregate_predictions(
                method_id=args.method,
                results=results,
            )
            prediction_path = run_dir / "output" / "predictions.json"
            write_json(prediction_path, aggregate)
            metadata.update(
                {
                    "run_status": (
                        "completed_subset" if args.only else "completed"
                    ),
                    "prediction_schema_valid": True,
                    "completed_instance_count": len(results),
                    "latency_ms": round(
                        (time.monotonic() - started_clock) * 1000
                    ),
                    "prediction": binding(prediction_path),
                }
            )
            write_json(run_metadata_path, metadata)
        except (BaselineRunError, KeyError, OSError) as exc:
            metadata["run_status"] = "prediction_schema_failed"
            metadata["failure"] = str(exc)
            metadata["completed_instance_count"] = len(results)
            write_json(run_metadata_path, metadata)
            print(f"Learning Explanation baseline failed: {exc}")
            return 1
        print(
            f"Saved {len(results)} deterministic explanations to "
            f"{display_path(prediction_path)}"
        )
        return 0

    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        metadata["run_status"] = "request_failed"
        metadata["request_success"] = False
        metadata["failure"] = "DEEPSEEK_API_KEY is unavailable"
        write_json(run_metadata_path, metadata)
        print(
            "Learning Explanation baseline failed: DEEPSEEK_API_KEY is "
            "unavailable."
        )
        return 1

    started_clock = time.monotonic()
    finish_reasons: list[str | None] = []
    usages: list[dict[str, Any]] = []
    for instance, payload in zip(instances, payloads):
        instance_id = instance["explanation_instance_id"]
        instance_started = time.monotonic()
        item_metadata = {
            "explanation_instance_id": instance_id,
            "request_success": False,
            "json_parse_success": False,
            "prediction_schema_valid": False,
        }
        try:
            response = api_call(api_key=api_key, payload=payload)
            metadata["api_call_count"] += 1
            item_metadata["request_success"] = True
            write_json(raw_dir / f"{instance_id}.json", response)
            parsed, finish_reason = extract_response(response)
            item_metadata["json_parse_success"] = True
            write_json(parsed_dir / f"{instance_id}.json", parsed)
            result = validate_output(parsed, instance)
            item_metadata["prediction_schema_valid"] = True
            item_metadata["finish_reason"] = finish_reason
            item_metadata["latency_ms"] = round(
                (time.monotonic() - instance_started) * 1000
            )
            write_json(output_dir / f"{instance_id}.json", result)
            write_json(metadata_dir / f"{instance_id}.json", item_metadata)
            results.append(result)
            finish_reasons.append(finish_reason)
            if isinstance(response.get("usage"), dict):
                usages.append(response["usage"])
        except (BaselineRunError, RuntimeError, OSError) as exc:
            item_metadata["failure"] = str(exc)
            item_metadata["latency_ms"] = round(
                (time.monotonic() - instance_started) * 1000
            )
            write_json(metadata_dir / f"{instance_id}.json", item_metadata)
            metadata.update(
                {
                    "run_status": (
                        "prediction_schema_failed"
                        if item_metadata["json_parse_success"]
                        else "json_parse_failed"
                        if item_metadata["request_success"]
                        else "request_failed"
                    ),
                    "request_success": item_metadata["request_success"],
                    "json_parse_success": item_metadata[
                        "json_parse_success"
                    ],
                    "prediction_schema_valid": item_metadata[
                        "prediction_schema_valid"
                    ],
                    "completed_instance_count": len(results),
                    "latency_ms": round(
                        (time.monotonic() - started_clock) * 1000
                    ),
                    "failure": {
                        "explanation_instance_id": instance_id,
                        "message": str(exc),
                    },
                }
            )
            write_json(run_metadata_path, metadata)
            print(
                f"Learning Explanation baseline failed for {instance_id}: "
                f"{exc}"
            )
            return 1

    aggregate = aggregate_predictions(
        method_id=args.method,
        results=results,
    )
    prediction_path = run_dir / "output" / "predictions.json"
    write_json(prediction_path, aggregate)
    usage_totals = {
        key: sum(
            item.get(key, 0)
            for item in usages
            if isinstance(item.get(key), int)
        )
        for key in sorted({key for item in usages for key in item})
    }
    metadata.update(
        {
            "run_status": "completed_subset" if args.only else "completed",
            "request_success": True,
            "json_parse_success": True,
            "prediction_schema_valid": True,
            "finish_reason": (
                "stop"
                if finish_reasons
                and all(value == "stop" for value in finish_reasons)
                else "mixed"
            ),
            "completed_instance_count": len(results),
            "latency_ms": round(
                (time.monotonic() - started_clock) * 1000
            ),
            "usage": {
                "request_count": len(instances),
                **usage_totals,
            },
            "prediction": binding(prediction_path),
        }
    )
    write_json(run_metadata_path, metadata)
    print(
        f"Saved {len(results)} Relation-only explanations to "
        f"{display_path(prediction_path)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
