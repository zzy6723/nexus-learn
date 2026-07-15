#!/usr/bin/env python3
"""Run entity extraction experiments against the DeepSeek Chat Completions API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENTITY_EXTRACTION_DIR = ROOT / "experiments" / "entity_extraction"

PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_SPLIT = "development"
BASE_URL = "https://api.deepseek.com/chat/completions"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Knowledge Object extraction using DeepSeek."
    )
    parser.add_argument(
        "--experiment",
        default="001_baseline",
        help="Experiment directory under experiments/entity_extraction/. Default: 001_baseline",
    )
    parser.add_argument(
        "--split",
        choices=["development", "holdout"],
        default=DEFAULT_SPLIT,
        help="Benchmark split to run. Default: development",
    )
    parser.add_argument(
        "--ground-truth",
        help="Ground-truth JSON path. Default: benchmark/ground_truth/<split>_v0_1.json",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
        help=f"DeepSeek model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature. Default: 0.0",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=1.0,
        help="Nucleus sampling value. Default: 1.0",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum output tokens per request. Default: 4096",
    )
    parser.add_argument(
        "--only",
        help="Run only one lecture_id from the selected ground truth.",
    )
    parser.add_argument(
        "--execution-manifest",
        help=(
            "Optional 002B-1 execution manifest. When supplied, --only is "
            "required, the lecture/configuration must match the frozen rerun "
            "plan, and artifact directories are fixed by the manifest run."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory for parsed prediction JSON. Default: <experiment>/output "
            "for development, or <experiment>/runs/holdout_v0_1/run_01/output for holdout."
        ),
    )
    parser.add_argument(
        "--rendered-inputs-dir",
        help=(
            "Directory for rendered request payloads. Default: <experiment>/rendered_inputs "
            "for development, or <experiment>/runs/holdout_v0_1/run_01/rendered_inputs for holdout."
        ),
    )
    parser.add_argument(
        "--raw-responses-dir",
        help=(
            "Directory for raw API responses. Default: <experiment>/raw_responses "
            "for development, or <experiment>/runs/holdout_v0_1/run_01/raw_responses for holdout."
        ),
    )
    parser.add_argument(
        "--metadata-dir",
        help=(
            "Directory for run metadata. Default: <experiment>/metadata "
            "for development, or <experiment>/runs/holdout_v0_1/run_01/metadata for holdout."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render request payloads and metadata without calling the API.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing per-lecture artifacts after deleting stale files first.",
    )
    return parser.parse_args(argv)


def resolve_path(path_text: str | None, default: Path) -> Path:
    if not path_text:
        return default
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def default_artifact_dirs(experiment_dir: Path, split: str) -> dict[str, Path]:
    if split == "holdout":
        run_dir = experiment_dir / "runs" / "holdout_v0_1" / "run_01"
        return {
            "output": run_dir / "output",
            "rendered_inputs": run_dir / "rendered_inputs",
            "raw_responses": run_dir / "raw_responses",
            "metadata": run_dir / "metadata",
        }
    return {
        "output": experiment_dir / "output",
        "rendered_inputs": experiment_dir / "rendered_inputs",
        "raw_responses": experiment_dir / "raw_responses",
        "metadata": experiment_dir / "metadata",
    }


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object: {path}")
    return value


def manifest_artifact_dirs(manifest_path: Path) -> dict[str, Path]:
    entity_dir = manifest_path.parent / "entity_predictions"
    return {
        "output": entity_dir / "output",
        "rendered_inputs": entity_dir / "rendered_inputs",
        "raw_responses": entity_dir / "raw_responses",
        "metadata": entity_dir / "metadata",
    }


def validate_execution_manifest_binding(
    *,
    manifest_path: Path,
    args: argparse.Namespace,
    prompt_path: Path,
    git_commit_at_start: str | None,
    git_dirty_at_start: bool | None,
) -> dict[str, Any]:
    manifest = read_json_object(manifest_path, label="002B-1 execution manifest")
    if manifest.get("artifact_type") != "predicted_ko_relation_execution_manifest":
        raise RuntimeError("Execution manifest has an invalid artifact_type.")
    if manifest.get("version") != "v0.1" or manifest.get("experiment") != "002B-1":
        raise RuntimeError("Execution manifest is not a 002B-1 v0.1 manifest.")
    if manifest.get("status") != "prepared_pending_entity_reruns":
        raise RuntimeError(
            "Execution manifest is not awaiting Entity reruns: "
            f"{manifest.get('status')!r}."
        )
    if args.split != "development":
        raise RuntimeError("002B-1 manifest-bound Entity reruns require --split development.")
    if not args.only:
        raise RuntimeError("--only is required with --execution-manifest.")
    if args.overwrite:
        raise RuntimeError("--overwrite is prohibited for a manifest-bound formal run.")
    if args.dry_run:
        raise RuntimeError(
            "Use an unbound directory for Entity dry-runs; a manifest-bound run "
            "is reserved for formal artifacts."
        )

    method_commit = manifest.get("method_commit")
    repository_state = manifest.get("repository_state")
    if not isinstance(method_commit, str):
        raise RuntimeError("Execution manifest has no method_commit.")
    if not isinstance(repository_state, dict):
        raise RuntimeError("Execution manifest has no verified repository_state.")
    if (
        repository_state.get("head_commit") != method_commit
        or repository_state.get("worktree_clean") is not True
    ):
        raise RuntimeError("Execution manifest repository verification is invalid.")
    if git_commit_at_start != method_commit:
        raise RuntimeError(
            "Current Entity run commit does not match the execution manifest: "
            f"{git_commit_at_start!r} != {method_commit!r}."
        )
    if git_dirty_at_start is not False:
        raise RuntimeError("Manifest-bound Entity run must start from a clean worktree.")

    frozen_methods = manifest.get("frozen_methods")
    if not isinstance(frozen_methods, dict):
        raise RuntimeError("Execution manifest has no frozen_methods object.")
    prompt_record = frozen_methods.get("entity_prompt")
    if not isinstance(prompt_record, dict):
        raise RuntimeError("Execution manifest has no frozen Entity prompt.")
    expected_prompt_path = resolve_path(prompt_record.get("path"), prompt_path)
    if expected_prompt_path.resolve() != prompt_path.resolve():
        raise RuntimeError("Entity experiment prompt path differs from the manifest.")
    if prompt_record.get("sha256") != sha256_file(prompt_path):
        raise RuntimeError("Entity prompt hash differs from the execution manifest.")

    implementation = frozen_methods.get("implementation")
    if not isinstance(implementation, list):
        raise RuntimeError("Execution manifest has no frozen implementation hashes.")
    runner_path = Path(__file__).resolve()
    runner_records = [
        item
        for item in implementation
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and resolve_path(item["path"], runner_path).resolve() == runner_path
    ]
    if len(runner_records) != 1 or runner_records[0].get("sha256") != sha256_file(
        runner_path
    ):
        raise RuntimeError("Entity runner hash differs from the execution manifest.")

    entity_execution = manifest.get("entity_execution")
    if not isinstance(entity_execution, dict):
        raise RuntimeError("Execution manifest has no entity_execution object.")
    rerun_ids = entity_execution.get("rerun_required_lecture_ids")
    if not isinstance(rerun_ids, list) or args.only not in rerun_ids:
        raise RuntimeError(
            f"Lecture {args.only!r} is not declared as an Entity rerun."
        )
    expected_parameters = {
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    if entity_execution.get("provider") != PROVIDER:
        raise RuntimeError("Entity provider differs from the execution manifest.")
    if entity_execution.get("model") != args.model:
        raise RuntimeError("Entity model differs from the execution manifest.")
    if entity_execution.get("request_parameters") != expected_parameters:
        raise RuntimeError("Entity request parameters differ from the execution manifest.")

    source_manifest_text = entity_execution.get("source_manifest")
    if not isinstance(source_manifest_text, str):
        raise RuntimeError("Execution manifest has no Entity source manifest path.")
    source_manifest_path = resolve_path(source_manifest_text, manifest_path.parent)
    if not source_manifest_path.is_file():
        raise RuntimeError(f"Missing Entity source manifest: {source_manifest_path}")
    source_manifest_hash = sha256_file(source_manifest_path)
    if entity_execution.get("source_manifest_sha256") != source_manifest_hash:
        raise RuntimeError("Entity source manifest hash is stale.")
    source_manifest = read_json_object(
        source_manifest_path, label="Entity source manifest"
    )
    if (
        source_manifest.get("status") != "prepared_pending_entity_reruns"
        or source_manifest.get("method_commit") != method_commit
        or source_manifest.get("rerun_required_lecture_ids") != rerun_ids
    ):
        raise RuntimeError("Entity source manifest does not match the execution plan.")

    benchmark = manifest.get("benchmark")
    lecture_hashes = (
        benchmark.get("lecture_model_text_sha256")
        if isinstance(benchmark, dict)
        else None
    )
    if not isinstance(lecture_hashes, dict) or args.only not in lecture_hashes:
        raise RuntimeError("Execution manifest has no frozen input hash for the lecture.")

    return {
        "execution_manifest": display_path(manifest_path),
        "execution_manifest_sha256": sha256_file(manifest_path),
        "method_commit": method_commit,
        "source_manifest": display_path(source_manifest_path),
        "source_manifest_sha256": source_manifest_hash,
        "expected_input_sha256": lecture_hashes[args.only],
    }


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(result.stdout.strip())


def load_ground_truth(path: Path) -> tuple[str, list[dict[str, str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    split = data.get("split")
    if not isinstance(split, str) or not split.strip():
        raise RuntimeError(f"{path}: missing non-empty split.")
    lectures = data.get("lectures")
    if not isinstance(lectures, list):
        raise RuntimeError(f"{path}: missing lectures list.")

    records = []
    for index, lecture in enumerate(lectures):
        if not isinstance(lecture, dict):
            raise RuntimeError(f"{path}: lecture {index} must be an object.")
        lecture_id = lecture.get("lecture_id")
        lecture_path = lecture.get("path")
        if not isinstance(lecture_id, str) or not isinstance(lecture_path, str):
            raise RuntimeError(f"{path}: lecture {index} has invalid lecture_id/path.")
        records.append({"lecture_id": lecture_id, "path": lecture_path})
    return split, records


def extract_markdown_section(markdown: str, heading: str) -> str:
    marker = f"# {heading}"
    lines = markdown.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == marker:
            in_section = True
            continue
        if in_section and (line.startswith("# ") or line.strip() == "---"):
            break
        if in_section:
            collected.append(line)

    section = "\n".join(collected).strip()
    if not section:
        raise RuntimeError(f"Missing section '# {heading}' in prompt.md.")
    return section + "\n"


def extract_lecture_body(markdown: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[index + 1:]).strip() + "\n"
    return markdown.strip() + "\n"


def render_user_prompt(template: str, lecture_id: str, lecture_text: str) -> str:
    return (
        template
        .replace("<lecture_id>", lecture_id)
        .replace("<lecture_text>", lecture_text.strip())
    )


def build_request_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
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


def extract_content(api_response: dict[str, Any]) -> str:
    try:
        content = api_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected DeepSeek response shape.") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("DeepSeek response content was empty or not a string.")
    return content


def extract_finish_reason(api_response: dict[str, Any] | None) -> str | None:
    if not api_response:
        return None
    try:
        finish_reason = api_response["choices"][0]["finish_reason"]
    except (KeyError, IndexError, TypeError):
        return None
    return finish_reason if isinstance(finish_reason, str) else None


def parse_model_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model output was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Model output JSON must be an object.")
    return parsed


def validate_prediction_envelope(
    prediction: dict[str, Any],
    *,
    lecture_id: str,
) -> None:
    if set(prediction) != {"lecture_id", "knowledge_objects"}:
        raise RuntimeError("Entity prediction has unexpected top-level fields.")
    if prediction.get("lecture_id") != lecture_id:
        raise RuntimeError("Entity prediction changed the lecture_id.")
    objects = prediction.get("knowledge_objects")
    if not isinstance(objects, list):
        raise RuntimeError("Entity prediction knowledge_objects must be a list.")
    required_keys = {
        "id",
        "name",
        "type",
        "aliases",
        "short_definition",
        "source_span",
    }
    seen_ids: set[str] = set()
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict) or set(obj) != required_keys:
            raise RuntimeError(
                f"Entity prediction object {index} has unexpected fields."
            )
        ko_id = obj.get("id")
        if not isinstance(ko_id, str) or not ko_id.strip():
            raise RuntimeError(f"Entity prediction object {index} has invalid id.")
        if ko_id in seen_ids:
            raise RuntimeError(f"Entity prediction repeats id {ko_id!r}.")
        seen_ids.add(ko_id)
        if obj.get("type") not in {"Concept", "Method", "Formula"}:
            raise RuntimeError(f"Entity prediction object {index} has invalid type.")
        aliases = obj.get("aliases")
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) for alias in aliases
        ):
            raise RuntimeError(
                f"Entity prediction object {index} has invalid aliases."
            )
        for field in ["name", "short_definition", "source_span"]:
            if not isinstance(obj.get(field), str) or not obj[field].strip():
                raise RuntimeError(
                    f"Entity prediction object {index} has invalid {field}."
                )


def write_json(path: Path, data: Any) -> None:
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def target_artifact_paths(
    *,
    lecture_id: str,
    output_dir: Path,
    rendered_inputs_dir: Path,
    raw_responses_dir: Path,
    metadata_dir: Path,
) -> list[Path]:
    return [
        rendered_inputs_dir / f"{lecture_id}.json",
        raw_responses_dir / f"{lecture_id}.json",
        output_dir / f"{lecture_id}.json",
        output_dir / f"{lecture_id}.raw.txt",
        metadata_dir / f"{lecture_id}.json",
    ]


def ensure_no_stale_artifacts(paths: list[Path], *, overwrite: bool) -> bool:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return True
    if not overwrite:
        print("Target artifacts already exist. Use --overwrite or choose a new run directory.", file=sys.stderr)
        for path in existing:
            print(f"- {display_path(path)}", file=sys.stderr)
        return False
    for path in existing:
        path.unlink()
    return True


def build_metadata(
    *,
    lecture_id: str,
    split: str,
    ground_truth_path: Path,
    lecture_path: Path,
    prompt_path: Path,
    request_payload: dict[str, Any],
    lecture_text: str,
    user_prompt: str,
    git_commit_at_start: str | None,
    git_dirty_at_start: bool | None,
    started_at: str,
    latency_ms: int | None,
    api_response: dict[str, Any] | None,
    request_success: bool | None,
    api_error: str | None,
    json_parse_success: bool | None,
    json_parse_error: str | None,
    dry_run: bool,
    retry_count: int,
    execution_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = {
        "provider": PROVIDER,
        "lecture_id": lecture_id,
        "split": split,
        "ground_truth": display_path(ground_truth_path),
        "lecture_path": display_path(lecture_path),
        "prompt_path": display_path(prompt_path),
        "model_requested": request_payload["model"],
        "model_returned": api_response.get("model") if api_response else None,
        "system_fingerprint": api_response.get("system_fingerprint") if api_response else None,
        "finish_reason": extract_finish_reason(api_response),
        "temperature": request_payload["temperature"],
        "top_p": request_payload["top_p"],
        "max_tokens": request_payload["max_tokens"],
        "run_timestamp": started_at,
        "latency_ms": latency_ms,
        "prompt_sha256": sha256_text(prompt_path.read_text(encoding="utf-8")),
        "input_sha256": sha256_text(lecture_text),
        "rendered_input_sha256": sha256_text(user_prompt),
        "request_payload_sha256": sha256_text(
            json.dumps(
                request_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
        "git_commit_at_start": git_commit_at_start,
        "git_dirty_at_start": git_dirty_at_start,
        "usage": api_response.get("usage") if api_response else None,
        "request_success": request_success,
        "api_error": api_error,
        "json_parse_success": json_parse_success,
        "json_parse_error": json_parse_error,
        "prediction_schema_valid": None,
        "prediction_schema_error": None,
        "repair_status": "not_attempted",
        "retry_count": retry_count,
        "dry_run": dry_run,
        "run_status": "prepared",
    }
    if execution_binding is not None:
        metadata["execution_binding"] = execution_binding
    return metadata


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    experiment_dir = ENTITY_EXTRACTION_DIR / args.experiment
    prompt_path = experiment_dir / "prompt.md"
    ground_truth_default = ROOT / "benchmark" / "ground_truth" / f"{args.split}_v0_1.json"
    execution_manifest_path = (
        resolve_path(args.execution_manifest, ROOT)
        if args.execution_manifest
        else None
    )
    artifact_defaults = (
        manifest_artifact_dirs(execution_manifest_path)
        if execution_manifest_path is not None
        else default_artifact_dirs(experiment_dir, args.split)
    )
    ground_truth_path = resolve_path(args.ground_truth, ground_truth_default)
    output_dir = resolve_path(args.output_dir, artifact_defaults["output"])
    rendered_inputs_dir = resolve_path(args.rendered_inputs_dir, artifact_defaults["rendered_inputs"])
    raw_responses_dir = resolve_path(args.raw_responses_dir, artifact_defaults["raw_responses"])
    metadata_dir = resolve_path(args.metadata_dir, artifact_defaults["metadata"])
    git_commit_at_start = git_commit()
    git_dirty_at_start = git_dirty()

    if not prompt_path.is_file():
        print(f"Missing prompt file: {prompt_path}", file=sys.stderr)
        return 2
    if not ground_truth_path.is_file():
        print(f"Missing ground-truth file: {ground_truth_path}", file=sys.stderr)
        return 2
    if execution_manifest_path is not None:
        if not execution_manifest_path.is_file():
            print(
                f"Missing execution manifest: {execution_manifest_path}",
                file=sys.stderr,
            )
            return 2
        actual_dirs = {
            "output": output_dir,
            "rendered_inputs": rendered_inputs_dir,
            "raw_responses": raw_responses_dir,
            "metadata": metadata_dir,
        }
        mismatched_dirs = [
            name
            for name, expected in artifact_defaults.items()
            if actual_dirs[name].resolve() != expected.resolve()
        ]
        if mismatched_dirs:
            print(
                "Manifest-bound artifact directories cannot be overridden: "
                + ", ".join(mismatched_dirs),
                file=sys.stderr,
            )
            return 2

    execution_binding: dict[str, Any] | None = None
    if execution_manifest_path is not None:
        try:
            execution_binding = validate_execution_manifest_binding(
                manifest_path=execution_manifest_path,
                args=args,
                prompt_path=prompt_path,
                git_commit_at_start=git_commit_at_start,
                git_dirty_at_start=git_dirty_at_start,
            )
        except RuntimeError as exc:
            print(f"Execution manifest validation failed: {exc}", file=sys.stderr)
            return 2

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and not args.dry_run:
        print(
            "DEEPSEEK_API_KEY is not set. Set it in your shell or in a local .env file.",
            file=sys.stderr,
        )
        return 2

    prompt_markdown = prompt_path.read_text(encoding="utf-8")
    system_prompt = extract_markdown_section(prompt_markdown, "System Prompt")
    user_template = extract_markdown_section(prompt_markdown, "User Prompt Template")

    ground_truth_split, lectures = load_ground_truth(ground_truth_path)
    if ground_truth_split != args.split:
        print(
            f"Ground-truth split mismatch: --split is {args.split!r}, "
            f"but {display_path(ground_truth_path)} declares {ground_truth_split!r}.",
            file=sys.stderr,
        )
        return 2
    if args.only:
        lectures = [lecture for lecture in lectures if lecture["lecture_id"] == args.only]
        if not lectures:
            print(
                f"lecture_id {args.only!r} not found in {display_path(ground_truth_path)}",
                file=sys.stderr,
            )
            return 2

    for directory in [output_dir, rendered_inputs_dir, raw_responses_dir, metadata_dir]:
        os.makedirs(directory, exist_ok=True)

    for lecture in lectures:
        lecture_id = lecture["lecture_id"]
        lecture_path = ROOT / lecture["path"]
        if not lecture_path.is_file():
            print(f"Missing lecture file: {lecture_path}", file=sys.stderr)
            return 2

        artifact_paths = target_artifact_paths(
            lecture_id=lecture_id,
            output_dir=output_dir,
            rendered_inputs_dir=rendered_inputs_dir,
            raw_responses_dir=raw_responses_dir,
            metadata_dir=metadata_dir,
        )
        if not ensure_no_stale_artifacts(artifact_paths, overwrite=args.overwrite):
            return 2

        lecture_markdown = lecture_path.read_text(encoding="utf-8")
        lecture_text = extract_lecture_body(lecture_markdown)
        if (
            execution_binding is not None
            and sha256_text(lecture_text)
            != execution_binding["expected_input_sha256"]
        ):
            print(
                f"Frozen lecture input hash mismatch for {lecture_id}.",
                file=sys.stderr,
            )
            return 2
        user_prompt = render_user_prompt(user_template, lecture_id, lecture_text)
        request_payload = build_request_payload(
            model=args.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )

        rendered_input_path = rendered_inputs_dir / f"{lecture_id}.json"
        write_json(rendered_input_path, request_payload)

        started_at = datetime.now(timezone.utc).isoformat()
        latency_ms: int | None = None
        api_response: dict[str, Any] | None = None
        request_success: bool | None = None
        api_error: str | None = None
        json_parse_success: bool | None = None
        json_parse_error: str | None = None
        retry_count = 0

        print(f"Prepared {lecture_id} ({args.split})")
        if not args.dry_run:
            print(f"Running {lecture_id} with {args.model}...")
            try:
                start = time.perf_counter()
                api_response = call_deepseek(api_key=api_key or "", payload=request_payload)
                latency_ms = int((time.perf_counter() - start) * 1000)
                request_success = True
                write_json(raw_responses_dir / f"{lecture_id}.json", api_response)

                content = extract_content(api_response)
                parsed = parse_model_content(content)
                json_parse_success = True
                write_json(output_dir / f"{lecture_id}.json", parsed)
            except RuntimeError as exc:
                if api_response is None:
                    request_success = False
                    api_error = str(exc)
                else:
                    json_parse_success = False
                    json_parse_error = str(exc)
                    try:
                        content = extract_content(api_response)
                    except RuntimeError:
                        content = ""
                    (output_dir / f"{lecture_id}.raw.txt").write_text(content, encoding="utf-8")
                metadata = build_metadata(
                    lecture_id=lecture_id,
                    split=args.split,
                    ground_truth_path=ground_truth_path,
                    lecture_path=lecture_path,
                    prompt_path=prompt_path,
                    request_payload=request_payload,
                    lecture_text=lecture_text,
                    user_prompt=user_prompt,
                    git_commit_at_start=git_commit_at_start,
                    git_dirty_at_start=git_dirty_at_start,
                    started_at=started_at,
                    latency_ms=latency_ms,
                    api_response=api_response,
                    request_success=request_success,
                    api_error=api_error,
                    json_parse_success=json_parse_success,
                    json_parse_error=json_parse_error,
                    dry_run=args.dry_run,
                    retry_count=retry_count,
                    execution_binding=execution_binding,
                )
                metadata["run_status"] = (
                    "request_failed" if api_response is None else "parse_failed"
                )
                if api_response is not None:
                    metadata["request_id"] = api_response.get("id")
                    raw_path = raw_responses_dir / f"{lecture_id}.json"
                    if raw_path.is_file():
                        metadata["raw_response_sha256"] = sha256_file(raw_path)
                write_json(metadata_dir / f"{lecture_id}.json", metadata)
                print(f"Run failed for {lecture_id}: {exc}", file=sys.stderr)
                return 1

            try:
                validate_prediction_envelope(parsed, lecture_id=lecture_id)
            except RuntimeError as exc:
                metadata = build_metadata(
                    lecture_id=lecture_id,
                    split=args.split,
                    ground_truth_path=ground_truth_path,
                    lecture_path=lecture_path,
                    prompt_path=prompt_path,
                    request_payload=request_payload,
                    lecture_text=lecture_text,
                    user_prompt=user_prompt,
                    git_commit_at_start=git_commit_at_start,
                    git_dirty_at_start=git_dirty_at_start,
                    started_at=started_at,
                    latency_ms=latency_ms,
                    api_response=api_response,
                    request_success=request_success,
                    api_error=api_error,
                    json_parse_success=json_parse_success,
                    json_parse_error=json_parse_error,
                    dry_run=args.dry_run,
                    retry_count=retry_count,
                    execution_binding=execution_binding,
                )
                metadata["request_id"] = api_response.get("id")
                metadata["prediction_schema_valid"] = False
                metadata["prediction_schema_error"] = str(exc)
                metadata["run_status"] = "prediction_schema_failed"
                metadata["raw_response_sha256"] = sha256_file(
                    raw_responses_dir / f"{lecture_id}.json"
                )
                metadata["prediction_sha256"] = sha256_file(
                    output_dir / f"{lecture_id}.json"
                )
                write_json(metadata_dir / f"{lecture_id}.json", metadata)
                print(f"Entity prediction schema failed: {exc}", file=sys.stderr)
                return 1

        metadata = build_metadata(
            lecture_id=lecture_id,
            split=args.split,
            ground_truth_path=ground_truth_path,
            lecture_path=lecture_path,
            prompt_path=prompt_path,
            request_payload=request_payload,
            lecture_text=lecture_text,
            user_prompt=user_prompt,
            git_commit_at_start=git_commit_at_start,
            git_dirty_at_start=git_dirty_at_start,
            started_at=started_at,
            latency_ms=latency_ms,
            api_response=api_response,
            request_success=request_success,
            api_error=api_error,
            json_parse_success=json_parse_success,
            json_parse_error=json_parse_error,
            dry_run=args.dry_run,
            retry_count=retry_count,
            execution_binding=execution_binding,
        )
        if args.dry_run:
            metadata["run_status"] = "dry_run_complete"
        else:
            metadata["request_id"] = api_response.get("id") if api_response else None
            metadata["prediction_schema_valid"] = True
            metadata["run_status"] = "completed"
            metadata["raw_response_sha256"] = sha256_file(
                raw_responses_dir / f"{lecture_id}.json"
            )
            metadata["prediction_sha256"] = sha256_file(
                output_dir / f"{lecture_id}.json"
            )
        write_json(metadata_dir / f"{lecture_id}.json", metadata)

        if args.dry_run:
            print(f"Rendered {display_path(rendered_input_path)}")
        else:
            print(f"Saved {display_path(output_dir / f'{lecture_id}.json')}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
