#!/usr/bin/env python3
"""Prepare a repository-verified 002B-1 run without invoking an API."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_predicted_ko"
    / "runs"
)
DEFAULT_RELATION_GROUND_TRUTH = (
    ROOT / "benchmark" / "ground_truth" / "relations_development_v0_1.json"
)
DEFAULT_EXECUTION_SCOPE = "development_v0_1"
RELATION_SPLIT_BY_EXECUTION_SCOPE = {
    "development_v0_1": "development",
    "locked_reuse_v0_1": "holdout",
    "locked_reuse_v0_2": "holdout",
}
RELATION_REQUEST_PARTITIONING_BY_EXECUTION_SCOPE = {
    "development_v0_1": "single_deterministic_batch_v0_1",
    "locked_reuse_v0_1": "single_deterministic_batch_v0_1",
    "locked_reuse_v0_2": "one_candidate_pair_per_request_v0_1",
}
DEFAULT_RUN_DIR_BY_EXECUTION_SCOPE = {
    scope: DEFAULT_RUN_ROOT / scope / "run_01"
    for scope in RELATION_SPLIT_BY_EXECUTION_SCOPE
}
DEFAULT_ENTITY_PROMPT = (
    ROOT / "experiments" / "entity_extraction" / "002_prompt_refinement" / "prompt.md"
)
DEFAULT_RELATION_PROMPT = (
    ROOT / "experiments" / "relation_extraction" / "002_prompt_refinement" / "prompt.md"
)
DEFAULT_RELATION_SCHEMA = ROOT / "docs" / "decisions" / "004-relation-schema.md"
DEFAULT_ENTITY_SOURCE_RUNS = [
    ROOT / "experiments" / "entity_extraction" / "002_prompt_refinement",
    ROOT
    / "experiments"
    / "entity_extraction"
    / "002_prompt_refinement"
    / "runs"
    / "holdout_v0_1"
    / "run_01",
]
DEFAULT_IMPLEMENTATION_FILES = [
    ROOT / "scripts" / "prepare_predicted_ko_relation_run.py",
    ROOT / "scripts" / "run_entity_extraction.py",
    ROOT / "scripts" / "finalize_entity_prediction_bundle.py",
    ROOT / "scripts" / "knowledge_object_matching.py",
    ROOT / "scripts" / "normalize_predicted_kos.py",
    ROOT / "scripts" / "align_predicted_kos.py",
    ROOT / "scripts" / "project_recoverable_relation_pairs.py",
    ROOT / "scripts" / "run_relation_extraction.py",
    ROOT / "scripts" / "evaluate_relation_extraction.py",
    ROOT / "scripts" / "finalize_relation_evaluation_bundle.py",
    ROOT / "scripts" / "evaluate_predicted_ko_relation_pipeline.py",
]
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
ALLOWED_KO_TYPES = {"Concept", "Method", "Formula"}


class PreflightError(RuntimeError):
    """A fatal 002B-1 preflight error."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze a 002B-1 execution plan, compose its Oracle "
            "and lecture inventories, and audit reusable Entity predictions."
        )
    )
    parser.add_argument(
        "--method-commit",
        required=True,
        help="Forty-character commit hash for the frozen 002B-1 method.",
    )
    parser.add_argument(
        "--run-dir",
        help=(
            "Run-specific output directory. Defaults to runs/<execution-scope>/run_01."
        ),
    )
    parser.add_argument(
        "--execution-scope",
        choices=sorted(RELATION_SPLIT_BY_EXECUTION_SCOPE),
        default=DEFAULT_EXECUTION_SCOPE,
        help=(
            "Claim-preserving run scope. development_v0_1 consumes the Relation "
            "development split; locked_reuse_v0_1 preserves the original "
            "single-request holdout execution; locked_reuse_v0_2 consumes the "
            "same holdout with the candidate-scoped transport revision."
        ),
    )
    parser.add_argument(
        "--relation-ground-truth",
        default=str(DEFAULT_RELATION_GROUND_TRUTH),
    )
    parser.add_argument("--entity-prompt", default=str(DEFAULT_ENTITY_PROMPT))
    parser.add_argument("--relation-prompt", default=str(DEFAULT_RELATION_PROMPT))
    parser.add_argument("--relation-schema", default=str(DEFAULT_RELATION_SCHEMA))
    parser.add_argument(
        "--entity-source-run",
        action="append",
        dest="entity_source_runs",
        help=(
            "Prior Entity run root containing output/metadata and, when present, "
            "raw_responses/rendered_inputs. Repeat to audit multiple runs."
        ),
    )
    parser.add_argument("--entity-model", default="deepseek-v4-flash")
    parser.add_argument("--entity-temperature", type=float, default=0.0)
    parser.add_argument("--entity-top-p", type=float, default=1.0)
    parser.add_argument("--entity-max-tokens", type=int, default=4096)
    parser.add_argument("--relation-model", default="deepseek-v4-flash")
    parser.add_argument("--relation-temperature", type=float, default=0.0)
    parser.add_argument("--relation-top-p", type=float, default=1.0)
    parser.add_argument("--relation-max-tokens", type=int, default=8192)
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


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def run_git(args: list[str]) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise PreflightError(f"Unable to execute Git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise PreflightError(
            f"Git command failed ({' '.join(args)}): {detail or 'no error output'}"
        )
    return result.stdout


def git_text(args: list[str]) -> str:
    return run_git(args).decode("utf-8", errors="strict").strip()


def verify_repository_state(
    *,
    method_commit: str,
    required_paths: list[Path],
) -> dict[str, Any]:
    repository_root = Path(git_text(["rev-parse", "--show-toplevel"])).resolve()
    if repository_root != ROOT.resolve():
        raise PreflightError(
            f"Git root mismatch: expected {ROOT.resolve()}, got {repository_root}."
        )

    head_commit = git_text(["rev-parse", "--verify", "HEAD"])
    if head_commit != method_commit:
        raise PreflightError(
            "--method-commit does not match the current HEAD: "
            f"provided {method_commit}, current {head_commit}."
        )

    branch = git_text(["rev-parse", "--abbrev-ref", "HEAD"])
    status = git_text(["status", "--porcelain=v1", "--untracked-files=all"])
    if status:
        entries = status.splitlines()
        preview = "; ".join(entries[:10])
        suffix = " ..." if len(entries) > 10 else ""
        raise PreflightError(
            "Formal preflight requires a clean tracked and non-ignored-untracked "
            f"working tree: {preview}{suffix}"
        )

    verified_artifacts: list[dict[str, str]] = []
    unique_paths = sorted(
        {path.resolve() for path in required_paths},
        key=lambda path: display_path(path),
    )
    for path in unique_paths:
        if not path.is_file():
            raise PreflightError(f"Required frozen artifact is missing: {path}")
        try:
            relative = path.relative_to(ROOT.resolve()).as_posix()
        except ValueError as exc:
            raise PreflightError(
                f"Required frozen artifact is outside the repository: {path}"
            ) from exc

        run_git(["ls-files", "--error-unmatch", "--", relative])
        committed_bytes = run_git(["show", f"{head_commit}:{relative}"])
        working_bytes = path.read_bytes()
        if committed_bytes != working_bytes:
            raise PreflightError(
                f"Frozen artifact does not match {head_commit}: {relative}"
            )
        verified_artifacts.append({
            "path": relative,
            "sha256": sha256_bytes(working_bytes),
        })

    return {
        "repository_root": ".",
        "head_commit": head_commit,
        "branch": branch,
        "worktree_clean": True,
        "status_scope": "tracked_and_non_ignored_untracked",
        "verified_artifacts": verified_artifacts,
    }


def read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"{label} must be a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def extract_lecture_body(markdown: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).strip() + "\n"
    return markdown.strip() + "\n"


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
    result = "\n".join(collected).strip()
    if not result:
        raise PreflightError(f"Missing '# {heading}' in Entity prompt.")
    return result + "\n"


def expected_entity_payload(
    *,
    prompt_path: Path,
    lecture_id: str,
    lecture_text: str,
    model: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> dict[str, Any]:
    prompt_markdown = prompt_path.read_text(encoding="utf-8")
    system_prompt = extract_markdown_section(prompt_markdown, "System Prompt")
    user_template = extract_markdown_section(prompt_markdown, "User Prompt Template")
    user_prompt = (
        user_template.replace("<lecture_id>", lecture_id).replace(
            "<lecture_text>", lecture_text.strip()
        )
    )
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


def validate_entity_prediction(value: Any, *, lecture_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"lecture_id", "knowledge_objects"}:
        return False
    if value.get("lecture_id") != lecture_id:
        return False
    objects = value.get("knowledge_objects")
    if not isinstance(objects, list):
        return False
    seen_ids: set[str] = set()
    required_keys = {
        "id",
        "name",
        "type",
        "aliases",
        "short_definition",
        "source_span",
    }
    for obj in objects:
        if not isinstance(obj, dict) or set(obj) != required_keys:
            return False
        ko_id = obj.get("id")
        if not isinstance(ko_id, str) or not ko_id.strip() or ko_id in seen_ids:
            return False
        seen_ids.add(ko_id)
        if obj.get("type") not in ALLOWED_KO_TYPES:
            return False
        if not isinstance(obj.get("aliases"), list) or not all(
            isinstance(alias, str) for alias in obj["aliases"]
        ):
            return False
        for field in ["name", "short_definition", "source_span"]:
            if not isinstance(obj.get(field), str) or not obj[field].strip():
                return False
    return True


def compose_inventories(
    relation_ground_truth_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    relation = read_json(relation_ground_truth_path, label="Relation ground truth")
    split = relation.get("split")
    lecture_ids = relation.get("lectures")
    source_paths = relation.get("knowledge_object_ground_truths")
    if not isinstance(split, str) or not split:
        raise PreflightError("Relation ground truth has no split.")
    if not isinstance(lecture_ids, list) or not all(
        isinstance(value, str) and value for value in lecture_ids
    ):
        raise PreflightError("Relation ground truth has an invalid lectures list.")
    if len(lecture_ids) != len(set(lecture_ids)):
        raise PreflightError("Relation ground truth repeats lecture IDs.")
    if not isinstance(source_paths, list) or not source_paths:
        raise PreflightError("Relation ground truth has no KO inventory sources.")

    lectures_by_id: dict[str, dict[str, Any]] = {}
    source_records: list[dict[str, Any]] = []
    allowed_types: set[str] | None = None
    for source_text in source_paths:
        if not isinstance(source_text, str) or not source_text:
            raise PreflightError("Invalid KO inventory path in Relation ground truth.")
        source_path = resolve_path(source_text)
        source = read_json(source_path, label="KO inventory")
        source_records.append({
            "path": display_path(source_path),
            "sha256": sha256_file(source_path),
        })
        current_types = source.get("allowed_object_types")
        if not isinstance(current_types, list) or not all(
            isinstance(value, str) for value in current_types
        ):
            raise PreflightError(f"Invalid allowed_object_types in {source_path}.")
        if allowed_types is None:
            allowed_types = set(current_types)
        elif allowed_types != set(current_types):
            raise PreflightError("KO source inventories use different object schemas.")
        for lecture in source.get("lectures", []):
            if not isinstance(lecture, dict):
                raise PreflightError(f"Invalid lecture in {source_path}.")
            lecture_id = lecture.get("lecture_id")
            if lecture_id in lectures_by_id:
                raise PreflightError(f"Duplicate composed lecture {lecture_id}.")
            if isinstance(lecture_id, str):
                lectures_by_id[lecture_id] = copy.deepcopy(lecture)

    missing = set(lecture_ids) - set(lectures_by_id)
    if missing:
        raise PreflightError(f"KO sources omit Relation lectures: {sorted(missing)}")
    selected_lectures = [lectures_by_id[lecture_id] for lecture_id in lecture_ids]
    extra = set(lectures_by_id) - set(lecture_ids)
    if extra:
        raise PreflightError(
            "KO source composition includes undeclared Relation lectures: "
            f"{sorted(extra)}"
        )

    relation_source = {
        "path": display_path(relation_ground_truth_path),
        "sha256": sha256_file(relation_ground_truth_path),
    }
    oracle_inventory = {
        "artifact_type": "composed_oracle_ko_inventory",
        "version": "v0.1",
        "split": split,
        "status": "derived",
        "description": (
            "Relation Oracle KO inventory composed without changing "
            "source Knowledge Object annotations."
        ),
        "allowed_object_types": sorted(allowed_types or ALLOWED_KO_TYPES),
        "derivation": {
            "relation_ground_truth": relation_source,
            "source_inventories": source_records,
            "lecture_order": lecture_ids,
        },
        "lectures": selected_lectures,
    }

    lecture_records: list[dict[str, Any]] = []
    lecture_sources: list[dict[str, Any]] = []
    for lecture in selected_lectures:
        lecture_id = lecture["lecture_id"]
        lecture_path_text = lecture.get("path")
        if not isinstance(lecture_path_text, str) or not lecture_path_text:
            raise PreflightError(f"{lecture_id} has no source lecture path.")
        lecture_path = resolve_path(lecture_path_text)
        try:
            markdown = lecture_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PreflightError(f"Unable to read lecture {lecture_path}: {exc}") from exc
        text = extract_lecture_body(markdown)
        lecture_records.append({"lecture_id": lecture_id, "text": text})
        lecture_sources.append({
            "lecture_id": lecture_id,
            "path": display_path(lecture_path),
            "markdown_sha256": sha256_file(lecture_path),
            "model_text_sha256": sha256_text(text),
        })
    lecture_inventory = {
        "artifact_type": "predicted_ko_relation_lecture_inventory",
        "version": "v0.1",
        "split": split,
        "relation_ground_truth": relation_source,
        "sources": lecture_sources,
        "lectures": lecture_records,
    }
    return oracle_inventory, lecture_inventory, source_records


def discover_entity_sources(source_roots: list[Path]) -> dict[str, list[Path]]:
    discovered: dict[str, list[Path]] = {}
    for root in source_roots:
        output_dir = root / "output"
        if not output_dir.is_dir():
            continue
        for output_path in sorted(output_dir.glob("*.json")):
            try:
                value = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            lecture_id = value.get("lecture_id") if isinstance(value, dict) else None
            if isinstance(lecture_id, str) and lecture_id:
                discovered.setdefault(lecture_id, []).append(root)
    return discovered


def raw_prediction_from_response(value: dict[str, Any]) -> Any:
    try:
        content = value["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PreflightError("Raw Entity response has an unexpected shape.") from exc
    if not isinstance(content, str):
        raise PreflightError("Raw Entity response content is not a string.")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise PreflightError("Raw Entity response content is not JSON.") from exc


def audit_entity_source(
    *,
    lecture_id: str,
    lecture_text: str,
    source_root: Path | None,
    prompt_path: Path,
    model: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> dict[str, Any]:
    expected_payload = expected_entity_payload(
        prompt_path=prompt_path,
        lecture_id=lecture_id,
        lecture_text=lecture_text,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    paths: dict[str, str | None] = {}
    hashes: dict[str, str | None] = {}
    if source_root is None:
        return {
            "lecture_id": lecture_id,
            "decision": "rerun_required",
            "source_run": None,
            "checks": {"source_candidate_unique": False},
            "reasons": ["missing_source_candidate"],
            "source_paths": {},
            "source_sha256": {},
        }

    artifact_paths = {
        "output": source_root / "output" / f"{lecture_id}.json",
        "metadata": source_root / "metadata" / f"{lecture_id}.json",
        "raw_response": source_root / "raw_responses" / f"{lecture_id}.json",
        "rendered_input": source_root / "rendered_inputs" / f"{lecture_id}.json",
    }
    values: dict[str, dict[str, Any] | None] = {}
    for name, path in artifact_paths.items():
        exists = path.is_file()
        checks[f"{name}_present"] = exists
        paths[name] = display_path(path) if exists else None
        hashes[name] = sha256_file(path) if exists else None
        if not exists:
            reasons.append(f"{name}_missing")
            values[name] = None
            continue
        try:
            values[name] = read_json(path, label=f"Entity {name}")
        except PreflightError:
            values[name] = None
            checks[f"{name}_valid_json"] = False
            reasons.append(f"{name}_invalid_json")
        else:
            checks[f"{name}_valid_json"] = True

    output = values.get("output")
    metadata = values.get("metadata")
    raw_response = values.get("raw_response")
    rendered_input = values.get("rendered_input")
    checks["output_schema_valid"] = validate_entity_prediction(
        output, lecture_id=lecture_id
    )
    if not checks["output_schema_valid"]:
        reasons.append("output_schema_invalid")

    expected_prompt_hash = sha256_file(prompt_path)
    metadata_checks = {
        "metadata_lecture_id_match": (
            isinstance(metadata, dict) and metadata.get("lecture_id") == lecture_id
        ),
        "metadata_prompt_hash_match": (
            isinstance(metadata, dict)
            and metadata.get("prompt_sha256") == expected_prompt_hash
        ),
        "metadata_input_hash_match": (
            isinstance(metadata, dict)
            and metadata.get("input_sha256") == sha256_text(lecture_text)
        ),
        "metadata_provider_match": (
            isinstance(metadata, dict) and metadata.get("provider") == "deepseek"
        ),
        "metadata_model_match": (
            isinstance(metadata, dict) and metadata.get("model_requested") == model
        ),
        "metadata_temperature_match": (
            isinstance(metadata, dict) and metadata.get("temperature") == temperature
        ),
        "metadata_top_p_match": (
            isinstance(metadata, dict) and metadata.get("top_p") == top_p
        ),
        "metadata_max_tokens_match": (
            isinstance(metadata, dict) and metadata.get("max_tokens") == max_tokens
        ),
        "metadata_request_success": (
            isinstance(metadata, dict) and metadata.get("request_success") is True
        ),
        "metadata_json_parse_success": (
            isinstance(metadata, dict) and metadata.get("json_parse_success") is True
        ),
        "metadata_finish_reason_stop": (
            isinstance(metadata, dict) and metadata.get("finish_reason") == "stop"
        ),
    }
    checks.update(metadata_checks)
    for name, passed in metadata_checks.items():
        if not passed:
            reasons.append(name.replace("metadata_", ""))

    checks["rendered_payload_exact_match"] = rendered_input == expected_payload
    if not checks["rendered_payload_exact_match"]:
        reasons.append("rendered_payload_mismatch")
    try:
        raw_prediction = (
            raw_prediction_from_response(raw_response)
            if isinstance(raw_response, dict)
            else None
        )
    except PreflightError:
        raw_prediction = None
    checks["parsed_output_matches_raw_response"] = (
        raw_prediction is not None and raw_prediction == output
    )
    if not checks["parsed_output_matches_raw_response"]:
        reasons.append("parsed_output_not_traceable_to_raw_response")

    decision = "reuse" if all(checks.values()) else "rerun_required"
    return {
        "lecture_id": lecture_id,
        "decision": decision,
        "source_run": display_path(source_root),
        "checks": checks,
        "reasons": sorted(set(reasons)),
        "source_paths": paths,
        "source_sha256": hashes,
        "audit_note": (
            "git_dirty_at_start is recorded but is not a reuse criterion; content "
            "and request traceability are checked directly."
        ),
    }


def copy_reusable_artifacts(
    audit: dict[str, Any],
    *,
    entity_dir: Path,
) -> None:
    if audit["decision"] != "reuse":
        return
    destinations = {
        "output": entity_dir / "output" / f"{audit['lecture_id']}.json",
        "metadata": entity_dir / "metadata" / f"{audit['lecture_id']}.json",
        "raw_response": entity_dir / "raw_responses" / f"{audit['lecture_id']}.json",
        "rendered_input": entity_dir / "rendered_inputs" / f"{audit['lecture_id']}.json",
    }
    for name, destination in destinations.items():
        source_text = audit["source_paths"].get(name)
        if not isinstance(source_text, str):
            raise PreflightError(f"Reusable {audit['lecture_id']} is missing {name}.")
        source = resolve_path(source_text)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256_file(destination) != audit["source_sha256"][name]:
            raise PreflightError(f"Copy verification failed for {destination}.")


def prepare_run(args: argparse.Namespace) -> dict[str, Any]:
    if not COMMIT_PATTERN.fullmatch(args.method_commit):
        raise PreflightError("--method-commit must be a 40-character lowercase hash.")
    if args.entity_max_tokens <= 0 or args.relation_max_tokens <= 0:
        raise PreflightError("Token limits must be positive.")

    run_dir = resolve_path(
        args.run_dir or DEFAULT_RUN_DIR_BY_EXECUTION_SCOPE[args.execution_scope]
    )
    if run_dir.exists() and any(run_dir.iterdir()):
        raise PreflightError(
            f"Run directory is not empty: {run_dir}. Use a new run ID."
        )
    relation_path = resolve_path(args.relation_ground_truth)
    entity_prompt_path = resolve_path(args.entity_prompt)
    relation_prompt_path = resolve_path(args.relation_prompt)
    relation_schema_path = resolve_path(args.relation_schema)
    for path in [
        relation_path,
        entity_prompt_path,
        relation_prompt_path,
        relation_schema_path,
    ]:
        if not path.is_file():
            raise PreflightError(f"Missing frozen input: {path}")

    oracle_inventory, lecture_inventory, ko_sources = compose_inventories(
        relation_path
    )
    relation_split = oracle_inventory["split"]
    expected_relation_split = RELATION_SPLIT_BY_EXECUTION_SCOPE[
        args.execution_scope
    ]
    if relation_split != expected_relation_split:
        raise PreflightError(
            "Execution scope and Relation benchmark split disagree: "
            f"{args.execution_scope!r} requires {expected_relation_split!r}, "
            f"but {display_path(relation_path)} declares {relation_split!r}."
        )
    repository_state = verify_repository_state(
        method_commit=args.method_commit,
        required_paths=[
            relation_path,
            entity_prompt_path,
            relation_prompt_path,
            relation_schema_path,
            *DEFAULT_IMPLEMENTATION_FILES,
            *[resolve_path(item["path"]) for item in ko_sources],
            *[
                resolve_path(item["path"])
                for item in lecture_inventory["sources"]
            ],
        ],
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    oracle_path = run_dir / "oracle_knowledge_objects.json"
    lectures_path = run_dir / "lecture_inventory.json"
    write_json(oracle_path, oracle_inventory)
    write_json(lectures_path, lecture_inventory)

    source_roots = [
        resolve_path(path)
        for path in (args.entity_source_runs or DEFAULT_ENTITY_SOURCE_RUNS)
    ]
    discovered = discover_entity_sources(source_roots)
    lecture_text_by_id = {
        item["lecture_id"]: item["text"] for item in lecture_inventory["lectures"]
    }
    audits: list[dict[str, Any]] = []
    for lecture_id in relation_lecture_ids(relation_path):
        candidates = discovered.get(lecture_id, [])
        if len(candidates) > 1:
            raise PreflightError(
                f"Multiple Entity source candidates found for {lecture_id}: "
                f"{[display_path(path) for path in candidates]}"
            )
        audit = audit_entity_source(
            lecture_id=lecture_id,
            lecture_text=lecture_text_by_id[lecture_id],
            source_root=candidates[0] if candidates else None,
            prompt_path=entity_prompt_path,
            model=args.entity_model,
            temperature=args.entity_temperature,
            top_p=args.entity_top_p,
            max_tokens=args.entity_max_tokens,
        )
        audits.append(audit)

    entity_dir = run_dir / "entity_predictions"
    for directory in ["output", "metadata", "raw_responses", "rendered_inputs"]:
        (entity_dir / directory).mkdir(parents=True, exist_ok=True)
    for audit in audits:
        copy_reusable_artifacts(audit, entity_dir=entity_dir)

    reuse_count = sum(item["decision"] == "reuse" for item in audits)
    rerun_ids = [
        item["lecture_id"] for item in audits if item["decision"] == "rerun_required"
    ]
    source_manifest = {
        "artifact_type": "entity_prediction_source_manifest",
        "version": "v0.1",
        "status": "prepared_pending_entity_reruns" if rerun_ids else "prepared_all_reused",
        "method_commit": args.method_commit,
        "execution_scope": args.execution_scope,
        "input_split": relation_split,
        "entity_prompt": {
            "path": display_path(entity_prompt_path),
            "sha256": sha256_file(entity_prompt_path),
        },
        "reuse_policy": {
            "requires_exact_lecture_and_prompt_hashes": True,
            "requires_identical_model_and_request_parameters": True,
            "requires_traceable_raw_rendered_parsed_artifacts": True,
            "requires_raw_parsed_content_equivalence": True,
            "does_not_require_historical_git_dirty_false": True,
        },
        "source_runs_audited": [display_path(path) for path in source_roots],
        "counts": {
            "lectures": len(audits),
            "reused": reuse_count,
            "rerun_required": len(rerun_ids),
        },
        "rerun_required_lecture_ids": rerun_ids,
        "lectures": audits,
    }
    source_manifest_path = entity_dir / "source_manifest.json"
    write_json(source_manifest_path, source_manifest)

    lecture_sources = lecture_inventory["sources"]
    execution_status = (
        "prepared_pending_entity_reruns" if rerun_ids else "prepared_entity_sources_complete"
    )
    manifest = {
        "artifact_type": "predicted_ko_relation_execution_manifest",
        "version": "v0.1",
        "status": execution_status,
        "experiment": "002B-1",
        "split": args.execution_scope,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "method_commit": args.method_commit,
        "repository_state": repository_state,
        "claim_boundary": {
            "development_v0_1": "single-run controlled paired diagnostic",
            "locked_reuse_v0_1": (
                "locked reuse of the previously evaluated 002A holdout"
            ),
            "locked_reuse_v0_2": (
                "execution-method revision on the previously evaluated 002A "
                "holdout; not an unseen-holdout claim"
            ),
        }[args.execution_scope],
        "frozen_methods": {
            "entity_prompt": {
                "path": display_path(entity_prompt_path),
                "sha256": sha256_file(entity_prompt_path),
            },
            "relation_prompt": {
                "path": display_path(relation_prompt_path),
                "sha256": sha256_file(relation_prompt_path),
            },
            "relation_schema": {
                "path": display_path(relation_schema_path),
                "sha256": sha256_file(relation_schema_path),
            },
            "implementation": [
                {
                    "path": display_path(path),
                    "sha256": sha256_file(path),
                }
                for path in DEFAULT_IMPLEMENTATION_FILES
            ],
        },
        "entity_execution": {
            "provider": "deepseek",
            "model": args.entity_model,
            "input_split": relation_split,
            "request_parameters": {
                "temperature": args.entity_temperature,
                "top_p": args.entity_top_p,
                "max_tokens": args.entity_max_tokens,
                "stream": False,
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            },
            "source_manifest": display_path(source_manifest_path),
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "rerun_required_lecture_ids": rerun_ids,
        },
        "relation_execution": {
            "provider": "deepseek",
            "model": args.relation_model,
            "request_partitioning": (
                RELATION_REQUEST_PARTITIONING_BY_EXECUTION_SCOPE[
                    args.execution_scope
                ]
            ),
            "request_parameters": {
                "temperature": args.relation_temperature,
                "top_p": args.relation_top_p,
                "max_tokens": args.relation_max_tokens,
                "stream": False,
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            },
            "matched_execution_order": ["A_prime", "B_prime"],
        },
        "benchmark": {
            "relation_split": relation_split,
            "original_relation_ground_truth": {
                "path": display_path(relation_path),
                "sha256": sha256_file(relation_path),
            },
            "source_ko_inventories": ko_sources,
            "oracle_inventory": {
                "path": display_path(oracle_path),
                "sha256": sha256_file(oracle_path),
            },
            "lecture_inventory": {
                "path": display_path(lectures_path),
                "sha256": sha256_file(lectures_path),
            },
            "lecture_ids": [item["lecture_id"] for item in lecture_sources],
            "lecture_markdown_sha256": {
                item["lecture_id"]: item["markdown_sha256"]
                for item in lecture_sources
            },
            "lecture_model_text_sha256": {
                item["lecture_id"]: item["model_text_sha256"]
                for item in lecture_sources
            },
        },
        "downstream_gate_order": [
            "entity_predictions_complete",
            "normalization_complete",
            "alignment_final",
            "projection_complete",
            "A_prime_dry_run",
            "B_prime_dry_run",
            "A_prime_formal_run",
            "B_prime_formal_run",
            "A_prime_relation_evaluation_final",
            "B_prime_relation_evaluation_final",
            "pipeline_evaluation_final",
        ],
    }
    execution_path = run_dir / "execution_manifest.json"
    write_json(execution_path, manifest)
    return manifest


def relation_lecture_ids(relation_path: Path) -> list[str]:
    relation = read_json(relation_path, label="Relation ground truth")
    lecture_ids = relation.get("lectures")
    if not isinstance(lecture_ids, list) or not all(
        isinstance(value, str) for value in lecture_ids
    ):
        raise PreflightError("Relation ground truth has an invalid lectures list.")
    return lecture_ids


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = prepare_run(args)
    except PreflightError as exc:
        print(f"002B-1 preflight failed: {exc}", file=sys.stderr)
        return 1
    run_dir = resolve_path(
        args.run_dir or DEFAULT_RUN_DIR_BY_EXECUTION_SCOPE[args.execution_scope]
    )
    reruns = manifest["entity_execution"]["rerun_required_lecture_ids"]
    print(
        f"Wrote 002B-1 {manifest['split']} preflight to "
        f"{display_path(run_dir)}"
    )
    print(f"Entity reruns required: {len(reruns)} ({', '.join(reruns) or 'none'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
