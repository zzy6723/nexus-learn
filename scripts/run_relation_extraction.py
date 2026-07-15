#!/usr/bin/env python3
"""Render and run Oracle or frozen matched Typed Relation experiments."""

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
RELATION_EXTRACTION_DIR = ROOT / "experiments" / "relation_extraction"

PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_EXPERIMENT = "001_baseline"
DEFAULT_SPLIT = "development"
DEFAULT_RUN_ID = "run_01"
DEFAULT_MAX_TOKENS = 8192
BASE_URL = "https://api.deepseek.com/chat/completions"

MODEL_INPUT_TOP_LEVEL_KEYS = {
    "relation_schema",
    "lectures",
    "knowledge_objects",
    "candidate_pairs",
}
FORBIDDEN_MODEL_INPUT_KEYS = {
    "source",
    "target",
    "relation_type",
    "category",
    "symmetric",
    "acceptable_alternatives",
    "evidence_spans",
    "rationale",
    "primary_scoring_categories",
    "primary_scored",
}
PAIR_ID_PATTERN = re.compile(r"rel_[a-z0-9]+_\d{3}")
SAFE_COMPONENT_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
SLOT_ID_PATTERN = re.compile(r"ko_slot_\d{3}")
MATCHED_CONDITIONS = {"A_prime", "B_prime"}
SINGLE_REQUEST_PARTITIONING = "single_deterministic_batch_v0_1"
CANDIDATE_SCOPED_PARTITIONING = "one_candidate_pair_per_request_v0_1"
EXECUTION_PARTITIONINGS = {
    SINGLE_REQUEST_PARTITIONING,
    CANDIDATE_SCOPED_PARTITIONING,
}
MATCHED_INPUT_REQUIRED_KEYS = {
    "artifact_type",
    "version",
    "condition",
    "structural_normalization_version",
    "pair_manifest_sha256",
    "ko_manifest_sha256",
    "matched_ground_truth_sha256",
    "relation_prompt_sha256",
    "relation_schema_sha256",
    "batch_plan_sha256",
    "ko_content_sha256",
    "model_input_sha256",
    "lecture_sha256",
    "batch_id",
    "batch_index",
    "batch_count",
    "model_input",
}

Ref = tuple[str, str]


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
        description="Render or run Oracle-KO Typed Relation Extraction."
    )
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT,
        help=(
            "Experiment directory under experiments/relation_extraction/. "
            f"Default: {DEFAULT_EXPERIMENT}"
        ),
    )
    parser.add_argument(
        "--split",
        choices=["development", "holdout"],
        default=DEFAULT_SPLIT,
        help=f"Relation benchmark split. Default: {DEFAULT_SPLIT}",
    )
    parser.add_argument(
        "--ground-truth",
        help=(
            "Relation ground-truth JSON. Default: "
            "benchmark/ground_truth/relations_<split>_v0_1.json"
        ),
    )
    parser.add_argument(
        "--input-artifact",
        help=(
            "Frozen matched_relation_input artifact produced by the 002B-1 "
            "projection step. When supplied, its model_input is rendered "
            "instead of rebuilding KO content from ground truth."
        ),
    )
    parser.add_argument(
        "--batch-plan",
        help="Frozen matched Relation batch plan; required with --input-artifact.",
    )
    parser.add_argument(
        "--execution-manifest",
        help=(
            "Repository-frozen 002B-1 execution manifest. The locked_reuse_v0_2 "
            "manifest activates candidate-scoped request partitioning."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=DEFAULT_RUN_ID,
        help=f"Run directory name. Default: {DEFAULT_RUN_ID}",
    )
    parser.add_argument(
        "--run-dir",
        help=(
            "Run root containing rendered_inputs/raw_responses/output/metadata. "
            "Overrides the default run-specific root."
        ),
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
        default=DEFAULT_MAX_TOKENS,
        help=f"Maximum output tokens. Default: {DEFAULT_MAX_TOKENS}",
    )
    parser.add_argument("--output-dir", help="Parsed prediction JSON directory.")
    parser.add_argument(
        "--rendered-inputs-dir", help="Rendered request payload directory."
    )
    parser.add_argument("--raw-responses-dir", help="Raw API response directory.")
    parser.add_argument("--metadata-dir", help="Run metadata directory.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render inputs and metadata without calling the API.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete stale artifacts for this run before writing new artifacts.",
    )
    return parser.parse_args(argv)


def resolve_path(path_text: str | None, default: Path) -> Path:
    if not path_text:
        return default
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def require_safe_component(value: str, field: str) -> None:
    if not SAFE_COMPONENT_PATTERN.fullmatch(value):
        raise RuntimeError(
            f"{field} must contain only letters, numbers, dot, underscore, or hyphen."
        )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(data: Any) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(data: Any) -> str:
    return sha256_text(canonical_json(data))


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read JSON file {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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


def parse_ref(value: Any, context: str) -> Ref:
    if not isinstance(value, dict):
        raise RuntimeError(f"{context} must be an object.")
    lecture_id = value.get("lecture_id")
    ko_id = value.get("ko_id")
    if not isinstance(lecture_id, str) or not lecture_id.strip():
        raise RuntimeError(f"{context}.lecture_id must be a non-empty string.")
    if not isinstance(ko_id, str) or not ko_id.strip():
        raise RuntimeError(f"{context}.ko_id must be a non-empty string.")
    return lecture_id, ko_id


def ref_json(ref: Ref) -> dict[str, str]:
    return {"lecture_id": ref[0], "ko_id": ref[1]}


def extract_lecture_body(markdown: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).strip() + "\n"
    return markdown.strip() + "\n"


def load_relation_ground_truth(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise RuntimeError("Relation ground truth must be a JSON object.")

    for field in [
        "version",
        "split",
        "knowledge_object_ground_truths",
        "allowed_relation_types",
        "pairs",
    ]:
        if field not in data:
            raise RuntimeError(f"Relation ground truth is missing {field!r}.")

    if not isinstance(data["version"], str) or not data["version"].strip():
        raise RuntimeError("Relation ground-truth version must be non-empty.")
    if not isinstance(data["split"], str) or not data["split"].strip():
        raise RuntimeError("Relation ground-truth split must be non-empty.")
    if not isinstance(data["knowledge_object_ground_truths"], list):
        raise RuntimeError("knowledge_object_ground_truths must be a list.")
    if not isinstance(data["allowed_relation_types"], list):
        raise RuntimeError("allowed_relation_types must be a list.")
    if not isinstance(data["pairs"], list) or not data["pairs"]:
        raise RuntimeError("Relation ground truth must contain candidate pairs.")
    return data


def load_knowledge_object_registry(
    path_texts: list[str],
) -> tuple[
    dict[Ref, dict[str, Any]],
    dict[str, Path],
    dict[str, str],
]:
    registry: dict[Ref, dict[str, Any]] = {}
    lecture_paths: dict[str, Path] = {}
    ground_truth_hashes: dict[str, str] = {}

    for path_text in path_texts:
        if not isinstance(path_text, str) or not path_text.strip():
            raise RuntimeError("Knowledge Object ground-truth path must be a string.")
        path = resolve_path(path_text, ROOT / path_text)
        data = load_json(path)
        if not isinstance(data, dict) or not isinstance(data.get("lectures"), list):
            raise RuntimeError(f"Invalid Knowledge Object ground truth: {path}")
        ground_truth_hashes[display_path(path)] = sha256_text(
            path.read_text(encoding="utf-8")
        )

        for lecture in data["lectures"]:
            if not isinstance(lecture, dict):
                raise RuntimeError(f"Invalid lecture entry in {path}.")
            lecture_id = lecture.get("lecture_id")
            lecture_path_text = lecture.get("path")
            if not isinstance(lecture_id, str) or not isinstance(
                lecture_path_text, str
            ):
                raise RuntimeError(f"Invalid lecture reference in {path}.")
            lecture_path = resolve_path(lecture_path_text, ROOT / lecture_path_text)
            previous_path = lecture_paths.get(lecture_id)
            if previous_path is not None and previous_path != lecture_path:
                raise RuntimeError(f"Conflicting paths for lecture {lecture_id}.")
            lecture_paths[lecture_id] = lecture_path

            objects = lecture.get("objects")
            if not isinstance(objects, list):
                raise RuntimeError(f"Lecture {lecture_id} has no objects list.")
            for obj in objects:
                if not isinstance(obj, dict):
                    raise RuntimeError(f"Invalid Knowledge Object in {lecture_id}.")
                ko_id = obj.get("id")
                name = obj.get("name")
                ko_type = obj.get("type")
                source_spans = obj.get("source_spans")
                if (
                    not isinstance(ko_id, str)
                    or not isinstance(name, str)
                    or not isinstance(ko_type, str)
                    or not isinstance(source_spans, list)
                    or not all(isinstance(span, str) for span in source_spans)
                ):
                    raise RuntimeError(
                        f"Knowledge Object {lecture_id}/{ko_id} has invalid fields."
                    )
                ref = (lecture_id, ko_id)
                if ref in registry:
                    raise RuntimeError(f"Duplicate Knowledge Object reference: {ref}")
                registry[ref] = {
                    "lecture_id": lecture_id,
                    "ko_id": ko_id,
                    "name": name,
                    "type": ko_type,
                    "source_spans": source_spans,
                }

    return registry, lecture_paths, ground_truth_hashes


def build_model_input(
    relation_ground_truth: dict[str, Any],
    ko_registry: dict[Ref, dict[str, Any]],
    lecture_paths: dict[str, Path],
) -> tuple[dict[str, Any], dict[str, set[Ref]], dict[str, str]]:
    candidate_members: dict[str, set[Ref]] = {}
    referenced_objects: set[Ref] = set()
    candidate_pairs: list[dict[str, Any]] = []

    for index, pair in enumerate(relation_ground_truth["pairs"]):
        if not isinstance(pair, dict):
            raise RuntimeError(f"Relation pair {index} must be an object.")
        pair_id = pair.get("pair_id")
        if not isinstance(pair_id, str) or not PAIR_ID_PATTERN.fullmatch(pair_id):
            raise RuntimeError(
                f"Relation pair {index} must use an opaque rel_<scope>_NNN pair_id."
            )
        if pair_id in candidate_members:
            raise RuntimeError(f"Duplicate relation pair_id: {pair_id}")

        source = parse_ref(pair.get("source"), f"{pair_id}.source")
        target = parse_ref(pair.get("target"), f"{pair_id}.target")
        if source == target:
            raise RuntimeError(f"{pair_id} must reference two different objects.")
        if source not in ko_registry or target not in ko_registry:
            raise RuntimeError(f"{pair_id} references an unknown Knowledge Object.")
        if (
            source[0] in pair_id
            or source[1] in pair_id
            or target[0] in pair_id
            or target[1] in pair_id
        ):
            raise RuntimeError(f"{pair_id} is not opaque with respect to its objects.")

        ordered = sorted([source, target])
        candidate_members[pair_id] = {source, target}
        referenced_objects.update({source, target})
        candidate_pairs.append({
            "pair_id": pair_id,
            "ko_a": ref_json(ordered[0]),
            "ko_b": ref_json(ordered[1]),
        })

    referenced_lectures = sorted({ref[0] for ref in referenced_objects})
    lectures: list[dict[str, str]] = []
    lecture_hashes: dict[str, str] = {}
    for lecture_id in referenced_lectures:
        lecture_path = lecture_paths.get(lecture_id)
        if lecture_path is None or not lecture_path.is_file():
            raise RuntimeError(f"Missing source lecture for {lecture_id}.")
        lecture_markdown = lecture_path.read_text(encoding="utf-8")
        lecture_text = extract_lecture_body(lecture_markdown)
        lectures.append({"lecture_id": lecture_id, "text": lecture_text})
        lecture_hashes[lecture_id] = sha256_text(lecture_markdown)

    knowledge_objects = [
        ko_registry[ref]
        for ref in sorted(referenced_objects)
    ]
    allowed_relation_types = relation_ground_truth["allowed_relation_types"]
    if not all(isinstance(value, str) for value in allowed_relation_types):
        raise RuntimeError("Relation schema labels must be strings.")
    graph_relation_types = [
        value for value in allowed_relation_types if value != "NO_RELATION"
    ]

    model_input = {
        "relation_schema": {
            "graph_relation_types": graph_relation_types,
            "benchmark_only_relation_types": ["NO_RELATION"],
        },
        "lectures": lectures,
        "knowledge_objects": knowledge_objects,
        "candidate_pairs": candidate_pairs,
    }
    return model_input, candidate_members, lecture_hashes


def collect_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(collect_keys(child))
    return keys


def validate_model_input(
    model_input: dict[str, Any],
    candidate_members: dict[str, set[Ref]],
) -> dict[str, Any]:
    if set(model_input) != MODEL_INPUT_TOP_LEVEL_KEYS:
        raise RuntimeError("Model input has unexpected top-level fields.")

    forbidden_present = sorted(
        collect_keys(model_input).intersection(FORBIDDEN_MODEL_INPUT_KEYS)
    )
    if forbidden_present:
        raise RuntimeError(
            "Gold leakage detected through forbidden fields: "
            + ", ".join(forbidden_present)
        )

    if set(model_input["relation_schema"]) != {
        "graph_relation_types",
        "benchmark_only_relation_types",
    }:
        raise RuntimeError("Model-facing Relation schema has unexpected fields.")

    lecture_ids: set[str] = set()
    for lecture in model_input["lectures"]:
        if not isinstance(lecture, dict) or set(lecture) != {"lecture_id", "text"}:
            raise RuntimeError("Model-facing lecture has unexpected fields.")
        lecture_id = lecture.get("lecture_id")
        text = lecture.get("text")
        if (
            not isinstance(lecture_id, str)
            or not lecture_id.strip()
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise RuntimeError("Model-facing lecture has invalid values.")
        if lecture_id in lecture_ids:
            raise RuntimeError("Model input contains duplicate lecture IDs.")
        lecture_ids.add(lecture_id)

    object_refs: set[Ref] = set()
    for obj in model_input["knowledge_objects"]:
        if not isinstance(obj, dict) or set(obj) != {
            "lecture_id",
            "ko_id",
            "name",
            "type",
            "source_spans",
        }:
            raise RuntimeError("Model-facing Knowledge Object has unexpected fields.")
        lecture_id = obj.get("lecture_id")
        ko_id = obj.get("ko_id")
        name = obj.get("name")
        ko_type = obj.get("type")
        source_spans = obj.get("source_spans")
        if (
            not isinstance(lecture_id, str)
            or not lecture_id.strip()
            or not isinstance(ko_id, str)
            or not ko_id.strip()
            or not isinstance(name, str)
            or not name.strip()
            or ko_type not in {"Concept", "Method", "Formula"}
            or not isinstance(source_spans, list)
            or not source_spans
            or not all(isinstance(span, str) and span.strip() for span in source_spans)
        ):
            raise RuntimeError("Model-facing Knowledge Object has invalid values.")
        ref = (lecture_id, ko_id)
        if ref in object_refs:
            raise RuntimeError("Model input contains duplicate Knowledge Object references.")
        object_refs.add(ref)

    rendered_pair_ids: set[str] = set()
    rendered_refs: set[Ref] = set()
    for pair in model_input["candidate_pairs"]:
        if not isinstance(pair, dict) or set(pair) != {"pair_id", "ko_a", "ko_b"}:
            raise RuntimeError("Model-facing candidate pair has unexpected fields.")
        pair_id = pair["pair_id"]
        ko_a = parse_ref(pair["ko_a"], f"{pair_id}.ko_a")
        ko_b = parse_ref(pair["ko_b"], f"{pair_id}.ko_b")
        if [ko_a, ko_b] != sorted([ko_a, ko_b]):
            raise RuntimeError(f"{pair_id} candidate order is not deterministic.")
        if {ko_a, ko_b} != candidate_members.get(pair_id):
            raise RuntimeError(f"{pair_id} model-facing members do not match candidate.")
        if pair_id in rendered_pair_ids:
            raise RuntimeError(f"Model input repeats candidate pair {pair_id}.")
        rendered_pair_ids.add(pair_id)
        rendered_refs.update({ko_a, ko_b})

    if rendered_pair_ids != set(candidate_members):
        raise RuntimeError("Model input omitted or created candidate pair IDs.")
    if rendered_refs != object_refs:
        raise RuntimeError("Model input contains unrelated or missing Knowledge Objects.")
    if {ref[0] for ref in rendered_refs} != lecture_ids:
        raise RuntimeError("Model input contains unrelated or missing lectures.")

    return {
        "passed": True,
        "candidate_serialization": "sorted_fully_qualified_references",
        "forbidden_keys_checked": sorted(FORBIDDEN_MODEL_INPUT_KEYS),
        "rendered_pair_count": len(rendered_pair_ids),
        "rendered_knowledge_object_count": len(object_refs),
        "rendered_lecture_count": len(lecture_ids),
    }


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object.")
    return value


def validate_execution_manifest(
    *,
    manifest_path: Path,
    relation_split: str,
    prompt_path: Path,
    schema_path: Path,
    input_artifact_path: Path,
    batch_plan_path: Path,
    ground_truth_path: Path,
    model: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    git_commit_at_start: str | None,
    git_dirty_at_start: bool | None,
) -> dict[str, Any]:
    manifest = load_json_object(manifest_path, label="002B-1 execution manifest")
    if (
        manifest.get("artifact_type")
        != "predicted_ko_relation_execution_manifest"
        or manifest.get("version") != "v0.1"
        or manifest.get("experiment") != "002B-1"
    ):
        raise RuntimeError("Unexpected 002B-1 execution manifest contract.")
    if manifest.get("split") != "locked_reuse_v0_2":
        raise RuntimeError(
            "Candidate-scoped execution requires split locked_reuse_v0_2."
        )

    method_commit = manifest.get("method_commit")
    repository_state = manifest.get("repository_state")
    if (
        not isinstance(method_commit, str)
        or not isinstance(repository_state, dict)
        or repository_state.get("head_commit") != method_commit
        or repository_state.get("worktree_clean") is not True
    ):
        raise RuntimeError("Execution manifest repository state is not frozen.")
    if git_commit_at_start != method_commit or git_dirty_at_start is not False:
        raise RuntimeError(
            "Candidate-scoped execution must start clean at the frozen method commit."
        )

    benchmark = manifest.get("benchmark")
    if (
        not isinstance(benchmark, dict)
        or benchmark.get("relation_split") != relation_split
    ):
        raise RuntimeError("Execution manifest Relation split does not match the run.")

    frozen_methods = manifest.get("frozen_methods")
    if not isinstance(frozen_methods, dict):
        raise RuntimeError("Execution manifest is missing frozen methods.")
    expected_method_hashes = {
        "relation_prompt": (prompt_path, sha256_file(prompt_path)),
        "relation_schema": (schema_path, sha256_file(schema_path)),
    }
    for field, (path, expected_hash) in expected_method_hashes.items():
        record = frozen_methods.get(field)
        if (
            not isinstance(record, dict)
            or record.get("path") != display_path(path)
            or record.get("sha256") != expected_hash
        ):
            raise RuntimeError(f"Execution manifest has stale {field}.")

    implementation = frozen_methods.get("implementation")
    runner_path = Path(__file__).resolve()
    runner_records = [
        record
        for record in implementation
        if isinstance(record, dict)
        and isinstance(record.get("path"), str)
        and resolve_path(record["path"], ROOT).resolve() == runner_path
    ] if isinstance(implementation, list) else []
    if (
        len(runner_records) != 1
        or runner_records[0].get("sha256") != sha256_file(runner_path)
    ):
        raise RuntimeError("Relation runner differs from the frozen method.")

    execution = manifest.get("relation_execution")
    expected_parameters = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    if (
        not isinstance(execution, dict)
        or execution.get("provider") != PROVIDER
        or execution.get("model") != model
        or execution.get("request_parameters") != expected_parameters
        or execution.get("request_partitioning")
        != CANDIDATE_SCOPED_PARTITIONING
        or execution.get("matched_execution_order") != ["A_prime", "B_prime"]
    ):
        raise RuntimeError("Relation execution differs from the frozen manifest.")

    run_root = manifest_path.parent.resolve()
    projection_dir = input_artifact_path.parent.resolve()
    if (
        projection_dir.parent != run_root
        or batch_plan_path.parent.resolve() != projection_dir
        or ground_truth_path.parent.resolve() != projection_dir
    ):
        raise RuntimeError(
            "Candidate-scoped execution inputs must come from the manifest's "
            "run-local projection directory."
        )
    projection_marker_path = input_artifact_path.parent / "projection_bundle_complete.json"
    projection_marker = load_json_object(
        projection_marker_path, label="projection completion marker"
    )
    projection_hashes = projection_marker.get("artifacts")
    required_projection_hashes = {
        input_artifact_path.name: sha256_file(input_artifact_path),
        batch_plan_path.name: sha256_file(batch_plan_path),
        ground_truth_path.name: sha256_file(ground_truth_path),
    }
    if (
        projection_marker.get("artifact_type")
        != "predicted_ko_projection_bundle_complete"
        or projection_marker.get("evaluation_status") != "final"
        or not isinstance(projection_hashes, dict)
        or any(
            projection_hashes.get(filename) != digest
            for filename, digest in required_projection_hashes.items()
        )
    ):
        raise RuntimeError("Projection bundle is missing, stale, or incomplete.")

    entity_marker_path = manifest_path.parent / "entity_predictions" / (
        "entity_predictions_complete.json"
    )
    entity_marker = load_json_object(
        entity_marker_path, label="Entity completion marker"
    )
    if (
        entity_marker.get("artifact_type") != "entity_predictions_completion_marker"
        or entity_marker.get("status") != "final"
        or entity_marker.get("method_commit") != method_commit
        or entity_marker.get("execution_manifest_sha256")
        != sha256_file(manifest_path)
    ):
        raise RuntimeError("Entity source bundle is not final for this method.")

    return {
        "execution_manifest": display_path(manifest_path),
        "execution_manifest_sha256": sha256_file(manifest_path),
        "method_commit": method_commit,
        "request_partitioning": CANDIDATE_SCOPED_PARTITIONING,
        "projection_completion_marker": display_path(projection_marker_path),
        "projection_completion_marker_sha256": sha256_file(projection_marker_path),
        "entity_completion_marker": display_path(entity_marker_path),
        "entity_completion_marker_sha256": sha256_file(entity_marker_path),
    }


def matched_object_refs(model_input: dict[str, Any]) -> list[Ref]:
    return [
        (obj["lecture_id"], obj["ko_id"])
        for obj in model_input["knowledge_objects"]
    ]


def validate_matched_input_artifact(
    *,
    input_artifact_path: Path,
    batch_plan_path: Path,
    ground_truth_path: Path,
    prompt_path: Path,
    schema_path: Path,
    expected_model_input: dict[str, Any],
    candidate_members: dict[str, set[Ref]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = load_json_object(input_artifact_path, label="matched input artifact")
    missing = MATCHED_INPUT_REQUIRED_KEYS - set(artifact)
    unknown = set(artifact) - MATCHED_INPUT_REQUIRED_KEYS
    if missing or unknown:
        raise RuntimeError(
            "Matched input artifact fields differ from the frozen contract: "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}."
        )
    if artifact.get("artifact_type") != "matched_relation_input":
        raise RuntimeError("Unexpected matched input artifact_type.")
    if artifact.get("version") != "v0.1":
        raise RuntimeError("Unexpected matched input version.")
    condition = artifact.get("condition")
    if condition not in MATCHED_CONDITIONS:
        raise RuntimeError("Matched input condition must be A_prime or B_prime.")

    expected_hashes = {
        "matched_ground_truth_sha256": sha256_file(ground_truth_path),
        "relation_prompt_sha256": sha256_file(prompt_path),
        "relation_schema_sha256": sha256_file(schema_path),
        "batch_plan_sha256": sha256_file(batch_plan_path),
    }
    for field, expected in expected_hashes.items():
        if artifact.get(field) != expected:
            raise RuntimeError(f"Matched input has stale {field}.")

    model_input = artifact.get("model_input")
    if not isinstance(model_input, dict):
        raise RuntimeError("Matched input model_input must be an object.")
    leakage_audit = validate_model_input(model_input, candidate_members)
    if artifact.get("model_input_sha256") != sha256_json(model_input):
        raise RuntimeError("Matched input has stale model_input_sha256.")
    if artifact.get("ko_content_sha256") != sha256_json(
        model_input["knowledge_objects"]
    ):
        raise RuntimeError("Matched input has stale ko_content_sha256.")
    lecture_hashes = {
        lecture["lecture_id"]: sha256_text(lecture["text"])
        for lecture in model_input["lectures"]
    }
    if artifact.get("lecture_sha256") != lecture_hashes:
        raise RuntimeError("Matched input has stale lecture_sha256.")

    for field in ["relation_schema", "lectures", "candidate_pairs"]:
        if model_input[field] != expected_model_input[field]:
            raise RuntimeError(
                f"Matched input {field} differs from matched ground truth rendering."
            )
    expected_refs = matched_object_refs(expected_model_input)
    actual_refs = matched_object_refs(model_input)
    if actual_refs != expected_refs:
        raise RuntimeError("Matched input KO slot identities or order changed.")
    if not all(SLOT_ID_PATTERN.fullmatch(ref[1]) for ref in actual_refs):
        raise RuntimeError("Matched input contains a non-neutral KO slot ID.")
    if condition == "A_prime" and (
        model_input["knowledge_objects"] != expected_model_input["knowledge_objects"]
    ):
        raise RuntimeError("A_prime input does not preserve Oracle KO content.")

    batch_plan = load_json_object(batch_plan_path, label="matched batch plan")
    if batch_plan.get("artifact_type") != "matched_relation_batch_plan":
        raise RuntimeError("Unexpected matched batch-plan artifact_type.")
    if batch_plan.get("version") != "v0.1":
        raise RuntimeError("Unexpected matched batch-plan version.")
    if batch_plan.get("pair_manifest_sha256") != artifact.get(
        "pair_manifest_sha256"
    ) or batch_plan.get("ko_manifest_sha256") != artifact.get(
        "ko_manifest_sha256"
    ):
        raise RuntimeError("Matched input and batch plan reference different manifests.")
    batches = batch_plan.get("batches")
    if (
        batch_plan.get("executable_batch_count") != 1
        or not isinstance(batches, list)
        or len(batches) != 1
        or not isinstance(batches[0], dict)
    ):
        raise RuntimeError("v0.1 matched execution requires one deterministic batch.")
    batch = batches[0]
    pair_ids = [pair["pair_id"] for pair in model_input["candidate_pairs"]]
    slot_ids = [ref[1] for ref in actual_refs]
    if batch.get("pair_ids") != pair_ids or batch.get("ko_slot_ids") != slot_ids:
        raise RuntimeError("Matched input differs from the frozen batch contents.")
    if (
        artifact.get("batch_id") != batch.get("batch_id")
        or artifact.get("batch_index") != batch.get("batch_index")
        or artifact.get("batch_count") != batch_plan.get("executable_batch_count")
    ):
        raise RuntimeError("Matched input batch identity differs from the batch plan.")

    return model_input, {
        "condition": condition,
        "input_artifact": display_path(input_artifact_path),
        "input_artifact_sha256": sha256_file(input_artifact_path),
        "batch_plan": display_path(batch_plan_path),
        "batch_plan_sha256": sha256_file(batch_plan_path),
        "lecture_sha256": lecture_hashes,
        "leakage_audit": leakage_audit,
    }


def build_request_payload(
    *,
    model: str,
    system_prompt: str,
    model_input: dict[str, Any],
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(model_input, indent=2, ensure_ascii=False),
            },
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
        value = api_response["choices"][0]["finish_reason"]
    except (KeyError, IndexError, TypeError):
        return None
    return value if isinstance(value, str) else None


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
    candidate_members: dict[str, set[Ref]],
    allowed_relation_types: set[str],
) -> None:
    results = prediction.get("results")
    if not isinstance(results, list):
        raise RuntimeError("Prediction JSON must contain a results list.")
    predicted_ids: list[str] = []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise RuntimeError(f"Prediction result {index} must be an object.")
        pair_id = result.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise RuntimeError(f"Prediction result {index} has invalid pair_id.")
        if pair_id not in candidate_members:
            raise RuntimeError(f"Prediction result {index} has unknown pair_id.")
        source = parse_ref(result.get("source"), f"prediction[{index}].source")
        target = parse_ref(result.get("target"), f"prediction[{index}].target")
        if {source, target} != candidate_members[pair_id]:
            raise RuntimeError(
                f"Prediction result {index} changed the candidate endpoints."
            )
        relation_type = result.get("relation_type")
        if relation_type not in allowed_relation_types:
            raise RuntimeError(
                f"Prediction result {index} has invalid Relation type."
            )
        evidence_spans = result.get("evidence_spans")
        if not isinstance(evidence_spans, list):
            raise RuntimeError(
                f"Prediction result {index} evidence_spans must be a list."
            )
        for evidence_index, evidence in enumerate(evidence_spans):
            if (
                not isinstance(evidence, dict)
                or not isinstance(evidence.get("lecture_id"), str)
                or not evidence["lecture_id"].strip()
                or not isinstance(evidence.get("span"), str)
                or not evidence["span"].strip()
            ):
                raise RuntimeError(
                    f"Prediction result {index} evidence {evidence_index} is invalid."
                )
        if not isinstance(result.get("rationale"), str):
            raise RuntimeError(f"Prediction result {index} rationale must be a string.")
        predicted_ids.append(pair_id)
    if len(predicted_ids) != len(set(predicted_ids)):
        raise RuntimeError("Prediction contains duplicate pair IDs.")
    if set(predicted_ids) != set(candidate_members):
        raise RuntimeError("Prediction pair IDs do not match rendered candidates.")


def artifact_paths(
    *,
    artifact_name: str,
    output_dir: Path,
    rendered_inputs_dir: Path,
    raw_responses_dir: Path,
    metadata_dir: Path,
) -> dict[str, Path]:
    return {
        "rendered_input": rendered_inputs_dir / f"{artifact_name}.json",
        "raw_response": raw_responses_dir / f"{artifact_name}.json",
        "prediction": output_dir / f"{artifact_name}.json",
        "unparsed_output": output_dir / f"{artifact_name}.raw.txt",
        "metadata": metadata_dir / f"{artifact_name}.json",
    }


def prepare_artifacts(paths: dict[str, Path], *, overwrite: bool) -> None:
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        lines = "\n".join(f"- {display_path(path)}" for path in existing)
        raise RuntimeError(
            "Target artifacts already exist. Use --overwrite or a new run ID.\n"
            + lines
        )
    if overwrite:
        for path in existing:
            path.unlink()


def make_run_scope(split: str, version: str) -> str:
    normalized_version = version.replace(".", "_")
    require_safe_component(normalized_version, "ground-truth version")
    return f"{split}_{normalized_version}"


def build_metadata(
    *,
    experiment: str,
    run_id: str,
    split: str,
    version: str,
    ground_truth_path: Path,
    prompt_path: Path,
    schema_path: Path,
    request_payload: dict[str, Any],
    model_input: dict[str, Any],
    leakage_audit: dict[str, Any],
    ko_ground_truth_hashes: dict[str, str],
    lecture_hashes: dict[str, str],
    artifact_map: dict[str, Path],
    git_commit_at_start: str | None,
    git_dirty_at_start: bool | None,
    started_at: str,
    dry_run: bool,
    matched_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "provider": PROVIDER,
        "experiment": experiment,
        "run_id": run_id,
        "split": split,
        "benchmark_version": version,
        "ground_truth": display_path(ground_truth_path),
        "prompt_path": display_path(prompt_path),
        "relation_schema_path": display_path(schema_path),
        "model_requested": request_payload["model"],
        "model_returned": None,
        "system_fingerprint": None,
        "finish_reason": None,
        "request_parameters": {
            "temperature": request_payload["temperature"],
            "top_p": request_payload["top_p"],
            "max_tokens": request_payload["max_tokens"],
            "stream": request_payload["stream"],
            "response_format": request_payload["response_format"],
            "thinking": request_payload["thinking"],
        },
        "run_timestamp": started_at,
        "latency_ms": None,
        "git_commit_at_start": git_commit_at_start,
        "git_dirty_at_start": git_dirty_at_start,
        "hashes": {
            "ground_truth_sha256": sha256_text(
                ground_truth_path.read_text(encoding="utf-8")
            ),
            "prompt_sha256": sha256_text(prompt_path.read_text(encoding="utf-8")),
            "relation_schema_sha256": sha256_text(
                schema_path.read_text(encoding="utf-8")
            ),
            "knowledge_object_ground_truth_sha256": ko_ground_truth_hashes,
            "lecture_sha256": lecture_hashes,
            "model_input_sha256": sha256_json(model_input),
            "request_payload_sha256": sha256_json(request_payload),
        },
        "input_counts": {
            "candidate_pairs": len(model_input["candidate_pairs"]),
            "knowledge_objects": len(model_input["knowledge_objects"]),
            "lectures": len(model_input["lectures"]),
        },
        "gold_leakage_audit": leakage_audit,
        "artifacts": {
            name: display_path(path) for name, path in artifact_map.items()
        },
        "usage": None,
        "request_success": None,
        "api_error": None,
        "json_parse_success": None,
        "json_parse_error": None,
        "prediction_schema_valid": None,
        "prediction_schema_error": None,
        "retry_count": 0,
        "dry_run": dry_run,
        "run_status": "prepared",
    }
    if matched_context is not None:
        metadata.update({
            "condition": matched_context["condition"],
            "input_artifact": matched_context["input_artifact"],
            "input_artifact_sha256": matched_context["input_artifact_sha256"],
            "batch_plan": matched_context["batch_plan"],
            "batch_plan_sha256": matched_context["batch_plan_sha256"],
        })
    return metadata


def build_candidate_scoped_batches(
    model_input: dict[str, Any],
    candidate_members: dict[str, set[Ref]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    object_by_ref = {
        (obj["lecture_id"], obj["ko_id"]): obj
        for obj in model_input["knowledge_objects"]
    }
    lecture_by_id = {
        lecture["lecture_id"]: lecture for lecture in model_input["lectures"]
    }
    batches: list[dict[str, Any]] = []
    plan_batches: list[dict[str, Any]] = []
    for index, pair in enumerate(model_input["candidate_pairs"], start=1):
        pair_id = pair["pair_id"]
        refs = [
            parse_ref(pair["ko_a"], f"{pair_id}.ko_a"),
            parse_ref(pair["ko_b"], f"{pair_id}.ko_b"),
        ]
        if set(refs) != candidate_members[pair_id]:
            raise RuntimeError(f"{pair_id} candidate-scoped endpoints are stale.")
        missing_refs = [ref for ref in refs if ref not in object_by_ref]
        if missing_refs:
            raise RuntimeError(
                f"{pair_id} candidate-scoped KOs are missing: {missing_refs}."
            )
        lecture_ids = sorted({ref[0] for ref in refs})
        missing_lectures = [
            lecture_id
            for lecture_id in lecture_ids
            if lecture_id not in lecture_by_id
        ]
        if missing_lectures:
            raise RuntimeError(
                f"{pair_id} candidate-scoped lectures are missing: "
                f"{missing_lectures}."
            )
        scoped_input = {
            "relation_schema": model_input["relation_schema"],
            "lectures": [lecture_by_id[lecture_id] for lecture_id in lecture_ids],
            "knowledge_objects": [object_by_ref[ref] for ref in refs],
            "candidate_pairs": [pair],
        }
        scoped_members = {pair_id: set(refs)}
        leakage_audit = validate_model_input(scoped_input, scoped_members)
        batch_id = f"candidate_{index:03d}"
        artifact_name = f"{index:03d}_{pair_id}"
        plan_batches.append({
            "batch_id": batch_id,
            "batch_index": index,
            "pair_id": pair_id,
            "endpoint_refs": [
                {"lecture_id": ref[0], "ko_id": ref[1]} for ref in refs
            ],
            "lecture_ids": lecture_ids,
        })
        batches.append({
            "batch_id": batch_id,
            "batch_index": index,
            "pair_id": pair_id,
            "artifact_name": artifact_name,
            "model_input": scoped_input,
            "candidate_members": scoped_members,
            "lecture_hashes": {
                lecture_id: sha256_text(lecture_by_id[lecture_id]["text"])
                for lecture_id in lecture_ids
            },
            "leakage_audit": leakage_audit,
        })
    execution_plan = {
        "artifact_type": "candidate_scoped_relation_execution_plan",
        "version": "v0.1",
        "request_partitioning": CANDIDATE_SCOPED_PARTITIONING,
        "batch_count": len(plan_batches),
        "pair_ids": [batch["pair_id"] for batch in plan_batches],
        "batches": plan_batches,
    }
    return execution_plan, batches


def aggregate_usage(usages: list[dict[str, Any]]) -> dict[str, Any]:
    integer_fields = sorted({
        key
        for usage in usages
        for key, value in usage.items()
        if isinstance(value, int) and not isinstance(value, bool)
    })
    return {
        "request_count": len(usages),
        **{
            field: sum(
                usage.get(field, 0)
                for usage in usages
                if isinstance(usage.get(field, 0), int)
            )
            for field in integer_fields
        },
    }


def candidate_scoped_aggregate_metadata(
    *,
    args: argparse.Namespace,
    relation_ground_truth: dict[str, Any],
    ground_truth_path: Path,
    prompt_path: Path,
    schema_path: Path,
    model_input: dict[str, Any],
    leakage_audit: dict[str, Any],
    ko_ground_truth_hashes: dict[str, str],
    lecture_hashes: dict[str, str],
    matched_context: dict[str, Any],
    execution_context: dict[str, Any],
    execution_plan_path: Path,
    execution_plan_sha256: str,
    prediction_path: Path,
    metadata_path: Path,
    payload_hashes: list[str],
    git_commit_at_start: str | None,
    git_dirty_at_start: bool | None,
    started_at: str,
) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "experiment": args.experiment,
        "run_id": args.run_id,
        "split": relation_ground_truth["split"],
        "benchmark_version": relation_ground_truth["version"],
        "ground_truth": display_path(ground_truth_path),
        "prompt_path": display_path(prompt_path),
        "relation_schema_path": display_path(schema_path),
        "model_requested": args.model,
        "model_returned": None,
        "system_fingerprint": None,
        "finish_reason": None,
        "request_partitioning": CANDIDATE_SCOPED_PARTITIONING,
        "request_parameters": {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        },
        "run_timestamp": started_at,
        "latency_ms": None,
        "git_commit_at_start": git_commit_at_start,
        "git_dirty_at_start": git_dirty_at_start,
        "hashes": {
            "ground_truth_sha256": sha256_file(ground_truth_path),
            "prompt_sha256": sha256_file(prompt_path),
            "relation_schema_sha256": sha256_file(schema_path),
            "knowledge_object_ground_truth_sha256": ko_ground_truth_hashes,
            "lecture_sha256": lecture_hashes,
            "model_input_sha256": sha256_json(model_input),
            "request_payload_set_sha256": sha256_json(payload_hashes),
        },
        "input_counts": {
            "candidate_pairs": len(model_input["candidate_pairs"]),
            "knowledge_objects": len(model_input["knowledge_objects"]),
            "lectures": len(model_input["lectures"]),
            "request_batches": len(payload_hashes),
        },
        "gold_leakage_audit": leakage_audit,
        "artifacts": {
            "execution_batch_plan": display_path(execution_plan_path),
            "prediction": display_path(prediction_path),
            "metadata": display_path(metadata_path),
        },
        "condition": matched_context["condition"],
        "input_artifact": matched_context["input_artifact"],
        "input_artifact_sha256": matched_context["input_artifact_sha256"],
        "batch_plan": matched_context["batch_plan"],
        "batch_plan_sha256": matched_context["batch_plan_sha256"],
        "execution_batch_plan": display_path(execution_plan_path),
        "execution_batch_plan_sha256": execution_plan_sha256,
        **execution_context,
        "batch_count": len(payload_hashes),
        "completed_batch_count": 0,
        "batch_results": [],
        "usage": None,
        "request_success": None,
        "api_error": None,
        "json_parse_success": None,
        "json_parse_error": None,
        "prediction_schema_valid": None,
        "prediction_schema_error": None,
        "retry_count": 0,
        "dry_run": args.dry_run,
        "run_status": "prepared",
    }


def run_candidate_scoped_execution(
    *,
    args: argparse.Namespace,
    relation_ground_truth: dict[str, Any],
    ground_truth_path: Path,
    prompt_path: Path,
    schema_path: Path,
    prompt_text: str,
    run_dir: Path,
    output_dir: Path,
    rendered_inputs_dir: Path,
    raw_responses_dir: Path,
    metadata_dir: Path,
    model_input: dict[str, Any],
    candidate_members: dict[str, set[Ref]],
    leakage_audit: dict[str, Any],
    ko_ground_truth_hashes: dict[str, str],
    lecture_hashes: dict[str, str],
    matched_context: dict[str, Any],
    execution_context: dict[str, Any],
    git_commit_at_start: str | None,
    git_dirty_at_start: bool | None,
) -> int:
    if args.overwrite:
        raise RuntimeError(
            "Candidate-scoped frozen execution does not permit --overwrite."
        )
    execution_plan, batches = build_candidate_scoped_batches(
        model_input, candidate_members
    )
    if not batches:
        raise RuntimeError("Candidate-scoped execution requires at least one pair.")
    input_artifact = load_json_object(
        resolve_path(args.input_artifact, ROOT), label="matched input artifact"
    )
    execution_plan.update({
        "source_batch_plan_sha256": matched_context["batch_plan_sha256"],
        "pair_manifest_sha256": input_artifact["pair_manifest_sha256"],
        "ko_manifest_sha256": input_artifact["ko_manifest_sha256"],
        "matched_ground_truth_sha256": input_artifact[
            "matched_ground_truth_sha256"
        ],
        "relation_prompt_sha256": input_artifact["relation_prompt_sha256"],
        "relation_schema_sha256": input_artifact["relation_schema_sha256"],
    })
    execution_plan_path = run_dir / "execution_batch_plan.json"
    artifact_name = ground_truth_path.stem
    aggregate_prediction_path = output_dir / f"{artifact_name}.json"
    aggregate_metadata_path = metadata_dir / f"{artifact_name}.json"

    prompt_payloads: list[dict[str, Any]] = []
    batch_targets: list[dict[str, Path]] = []
    all_target_paths: dict[str, Path] = {
        "execution_plan": execution_plan_path,
        "aggregate_prediction": aggregate_prediction_path,
        "aggregate_metadata": aggregate_metadata_path,
    }
    for batch in batches:
        payload = build_request_payload(
            model=args.model,
            system_prompt=prompt_text,
            model_input=batch["model_input"],
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )
        targets = artifact_paths(
            artifact_name=batch["artifact_name"],
            output_dir=output_dir / "pairs",
            rendered_inputs_dir=rendered_inputs_dir / "pairs",
            raw_responses_dir=raw_responses_dir / "pairs",
            metadata_dir=metadata_dir / "pairs",
        )
        prompt_payloads.append(payload)
        batch_targets.append(targets)
        for name, path in targets.items():
            all_target_paths[f"{batch['batch_id']}.{name}"] = path
    prepare_artifacts(all_target_paths, overwrite=False)
    for directory in [
        run_dir,
        output_dir,
        rendered_inputs_dir,
        raw_responses_dir,
        metadata_dir,
        output_dir / "pairs",
        rendered_inputs_dir / "pairs",
        raw_responses_dir / "pairs",
        metadata_dir / "pairs",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    write_json(execution_plan_path, execution_plan)
    execution_plan_sha256 = sha256_file(execution_plan_path)
    started_at = datetime.now(timezone.utc).isoformat()
    payload_hashes = [sha256_json(payload) for payload in prompt_payloads]
    aggregate_metadata = candidate_scoped_aggregate_metadata(
        args=args,
        relation_ground_truth=relation_ground_truth,
        ground_truth_path=ground_truth_path,
        prompt_path=prompt_path,
        schema_path=schema_path,
        model_input=model_input,
        leakage_audit=leakage_audit,
        ko_ground_truth_hashes=ko_ground_truth_hashes,
        lecture_hashes=lecture_hashes,
        matched_context=matched_context,
        execution_context=execution_context,
        execution_plan_path=execution_plan_path,
        execution_plan_sha256=execution_plan_sha256,
        prediction_path=aggregate_prediction_path,
        metadata_path=aggregate_metadata_path,
        payload_hashes=payload_hashes,
        git_commit_at_start=git_commit_at_start,
        git_dirty_at_start=git_dirty_at_start,
        started_at=started_at,
    )

    for batch, payload, targets in zip(
        batches, prompt_payloads, batch_targets, strict=True
    ):
        batch_context = {
            **matched_context,
            "execution_batch_id": batch["batch_id"],
            "execution_batch_index": batch["batch_index"],
            "execution_batch_count": len(batches),
        }
        metadata = build_metadata(
            experiment=args.experiment,
            run_id=args.run_id,
            split=relation_ground_truth["split"],
            version=relation_ground_truth["version"],
            ground_truth_path=ground_truth_path,
            prompt_path=prompt_path,
            schema_path=schema_path,
            request_payload=payload,
            model_input=batch["model_input"],
            leakage_audit=batch["leakage_audit"],
            ko_ground_truth_hashes=ko_ground_truth_hashes,
            lecture_hashes=batch["lecture_hashes"],
            artifact_map=targets,
            git_commit_at_start=git_commit_at_start,
            git_dirty_at_start=git_dirty_at_start,
            started_at=started_at,
            dry_run=args.dry_run,
            matched_context=batch_context,
        )
        metadata.update({
            "request_partitioning": CANDIDATE_SCOPED_PARTITIONING,
            "execution_batch_plan": display_path(execution_plan_path),
            "execution_batch_plan_sha256": execution_plan_sha256,
            "execution_batch_id": batch["batch_id"],
            "execution_batch_index": batch["batch_index"],
            "execution_batch_count": len(batches),
            "pair_id": batch["pair_id"],
            **execution_context,
        })
        write_json(targets["rendered_input"], payload)
        if args.dry_run:
            metadata["run_status"] = "dry_run_complete"
            write_json(targets["metadata"], metadata)
        batch["metadata"] = metadata

    if args.dry_run:
        aggregate_metadata["run_status"] = "dry_run_complete"
        write_json(aggregate_metadata_path, aggregate_metadata)
        print(
            f"Rendered {len(batches)} candidate-scoped requests under "
            f"{display_path(rendered_inputs_dir / 'pairs')}"
        )
        print(f"Metadata {display_path(aggregate_metadata_path)}")
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        aggregate_metadata["run_status"] = "configuration_failed"
        aggregate_metadata["api_error"] = "DEEPSEEK_API_KEY is not set."
        write_json(aggregate_metadata_path, aggregate_metadata)
        print(aggregate_metadata["api_error"], file=sys.stderr)
        return 2

    allowed_relation_types = set(relation_ground_truth["allowed_relation_types"])
    results: list[dict[str, Any]] = []
    usages: list[dict[str, Any]] = []
    request_ids: list[str] = []
    model_returned_values: list[str] = []
    fingerprints: list[str] = []
    total_latency_ms = 0
    for batch, payload, targets in zip(
        batches, prompt_payloads, batch_targets, strict=True
    ):
        metadata = batch["metadata"]
        api_response: dict[str, Any] | None = None
        request_started = time.perf_counter()
        try:
            api_response = call_deepseek(api_key=api_key, payload=payload)
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            total_latency_ms += latency_ms
            metadata["latency_ms"] = latency_ms
            metadata["request_success"] = True
            metadata["model_returned"] = api_response.get("model")
            metadata["system_fingerprint"] = api_response.get("system_fingerprint")
            metadata["request_id"] = api_response.get("id")
            metadata["finish_reason"] = extract_finish_reason(api_response)
            metadata["usage"] = api_response.get("usage")
            write_json(targets["raw_response"], api_response)
            metadata["raw_response_sha256"] = sha256_file(targets["raw_response"])
        except RuntimeError as exc:
            metadata["latency_ms"] = int(
                (time.perf_counter() - request_started) * 1000
            )
            metadata["request_success"] = False
            metadata["api_error"] = str(exc)
            metadata["run_status"] = "request_failed"
            write_json(targets["metadata"], metadata)
            aggregate_metadata.update({
                "latency_ms": total_latency_ms + metadata["latency_ms"],
                "request_success": False,
                "api_error": str(exc),
                "failed_batch_id": batch["batch_id"],
                "failed_pair_id": batch["pair_id"],
                "completed_batch_count": len(results),
                "run_status": "candidate_request_failed",
            })
            write_json(aggregate_metadata_path, aggregate_metadata)
            print(
                f"Relation candidate request failed for {batch['pair_id']}: {exc}",
                file=sys.stderr,
            )
            return 1

        if metadata["finish_reason"] != "stop":
            metadata["run_status"] = "finish_reason_failed"
            write_json(targets["metadata"], metadata)
            aggregate_metadata.update({
                "latency_ms": total_latency_ms,
                "request_success": True,
                "finish_reason": metadata["finish_reason"],
                "failed_batch_id": batch["batch_id"],
                "failed_pair_id": batch["pair_id"],
                "completed_batch_count": len(results),
                "run_status": "candidate_finish_reason_failed",
            })
            write_json(aggregate_metadata_path, aggregate_metadata)
            print(
                f"Relation candidate request did not stop cleanly for "
                f"{batch['pair_id']}.",
                file=sys.stderr,
            )
            return 1

        try:
            content = extract_content(api_response)
            parsed = parse_model_content(content)
            metadata["json_parse_success"] = True
            write_json(targets["prediction"], parsed)
            metadata["prediction_sha256"] = sha256_file(targets["prediction"])
        except RuntimeError as exc:
            metadata["json_parse_success"] = False
            metadata["json_parse_error"] = str(exc)
            metadata["run_status"] = "parse_failed"
            content = ""
            try:
                content = extract_content(api_response)
            except RuntimeError:
                pass
            targets["unparsed_output"].write_text(content, encoding="utf-8")
            write_json(targets["metadata"], metadata)
            aggregate_metadata.update({
                "latency_ms": total_latency_ms,
                "request_success": True,
                "json_parse_success": False,
                "json_parse_error": str(exc),
                "failed_batch_id": batch["batch_id"],
                "failed_pair_id": batch["pair_id"],
                "completed_batch_count": len(results),
                "run_status": "candidate_parse_failed",
            })
            write_json(aggregate_metadata_path, aggregate_metadata)
            print(
                f"Relation candidate output parsing failed for "
                f"{batch['pair_id']}: {exc}",
                file=sys.stderr,
            )
            return 1

        try:
            validate_prediction_envelope(
                parsed, batch["candidate_members"], allowed_relation_types
            )
            metadata["prediction_schema_valid"] = True
        except RuntimeError as exc:
            metadata["prediction_schema_valid"] = False
            metadata["prediction_schema_error"] = str(exc)
            metadata["run_status"] = "prediction_schema_failed"
            write_json(targets["metadata"], metadata)
            aggregate_metadata.update({
                "latency_ms": total_latency_ms,
                "request_success": True,
                "json_parse_success": True,
                "prediction_schema_valid": False,
                "prediction_schema_error": str(exc),
                "failed_batch_id": batch["batch_id"],
                "failed_pair_id": batch["pair_id"],
                "completed_batch_count": len(results),
                "run_status": "candidate_prediction_schema_failed",
            })
            write_json(aggregate_metadata_path, aggregate_metadata)
            print(
                f"Relation candidate schema failed for {batch['pair_id']}: {exc}",
                file=sys.stderr,
            )
            return 1

        metadata["run_status"] = "completed"
        write_json(targets["metadata"], metadata)
        results.append(parsed["results"][0])
        usage = api_response.get("usage")
        if isinstance(usage, dict):
            usages.append(usage)
        for value, collection in [
            (api_response.get("id"), request_ids),
            (api_response.get("model"), model_returned_values),
            (api_response.get("system_fingerprint"), fingerprints),
        ]:
            if isinstance(value, str):
                collection.append(value)
        aggregate_metadata["batch_results"].append({
            "batch_id": batch["batch_id"],
            "pair_id": batch["pair_id"],
            "request_id": api_response.get("id"),
            "prediction_sha256": metadata["prediction_sha256"],
            "metadata": display_path(targets["metadata"]),
            "metadata_sha256": sha256_file(targets["metadata"]),
        })

    aggregate_prediction = {"results": results}
    validate_prediction_envelope(
        aggregate_prediction, candidate_members, allowed_relation_types
    )
    write_json(aggregate_prediction_path, aggregate_prediction)
    aggregate_metadata.update({
        "model_returned": (
            model_returned_values[0]
            if len(set(model_returned_values)) == 1
            else sorted(set(model_returned_values))
        ),
        "system_fingerprint": (
            fingerprints[0]
            if len(set(fingerprints)) == 1
            else sorted(set(fingerprints))
        ),
        "finish_reason": "stop",
        "latency_ms": total_latency_ms,
        "request_ids": request_ids,
        "usage": aggregate_usage(usages),
        "request_success": True,
        "json_parse_success": True,
        "prediction_schema_valid": True,
        "completed_batch_count": len(results),
        "prediction_sha256": sha256_file(aggregate_prediction_path),
        "run_status": "completed",
    })
    write_json(aggregate_metadata_path, aggregate_metadata)
    print(
        f"Saved {len(results)} candidate-scoped predictions to "
        f"{display_path(aggregate_prediction_path)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    try:
        require_safe_component(args.experiment, "--experiment")
        require_safe_component(args.run_id, "--run-id")
        if args.max_tokens <= 0:
            raise RuntimeError("--max-tokens must be positive.")

        experiment_dir = RELATION_EXTRACTION_DIR / args.experiment
        prompt_path = experiment_dir / "prompt.md"
        schema_path = ROOT / "docs" / "decisions" / "004-relation-schema.md"
        default_ground_truth = (
            ROOT
            / "benchmark"
            / "ground_truth"
            / f"relations_{args.split}_v0_1.json"
        )
        ground_truth_path = resolve_path(args.ground_truth, default_ground_truth)

        if bool(args.input_artifact) != bool(args.batch_plan):
            raise RuntimeError(
                "--input-artifact and --batch-plan must be supplied together."
            )
        if args.execution_manifest and not args.input_artifact:
            raise RuntimeError(
                "--execution-manifest requires --input-artifact and --batch-plan."
            )

        for required_path in [prompt_path, schema_path, ground_truth_path]:
            if not required_path.is_file():
                raise RuntimeError(f"Missing required file: {required_path}")

        relation_ground_truth = load_relation_ground_truth(ground_truth_path)
        if relation_ground_truth["split"] != args.split:
            raise RuntimeError(
                f"Ground-truth split is {relation_ground_truth['split']!r}, "
                f"but --split is {args.split!r}."
            )

        run_scope = make_run_scope(
            relation_ground_truth["split"], relation_ground_truth["version"]
        )
        default_run_dir = (
            experiment_dir / "runs" / run_scope / args.run_id
        )
        run_dir = resolve_path(args.run_dir, default_run_dir)
        output_dir = resolve_path(args.output_dir, run_dir / "output")
        rendered_inputs_dir = resolve_path(
            args.rendered_inputs_dir, run_dir / "rendered_inputs"
        )
        raw_responses_dir = resolve_path(
            args.raw_responses_dir, run_dir / "raw_responses"
        )
        metadata_dir = resolve_path(args.metadata_dir, run_dir / "metadata")

        git_commit_at_start = git_commit()
        git_dirty_at_start = git_dirty()

        ko_registry, lecture_paths, ko_ground_truth_hashes = (
            load_knowledge_object_registry(
                relation_ground_truth["knowledge_object_ground_truths"]
            )
        )
        expected_model_input, candidate_members, lecture_hashes = build_model_input(
            relation_ground_truth,
            ko_registry,
            lecture_paths,
        )
        matched_context: dict[str, Any] | None = None
        execution_context: dict[str, Any] | None = None
        if args.input_artifact:
            input_artifact_path = resolve_path(args.input_artifact, ROOT)
            batch_plan_path = resolve_path(args.batch_plan, ROOT)
            for required_path in [input_artifact_path, batch_plan_path]:
                if not required_path.is_file():
                    raise RuntimeError(f"Missing required file: {required_path}")
            model_input, matched_context = validate_matched_input_artifact(
                input_artifact_path=input_artifact_path,
                batch_plan_path=batch_plan_path,
                ground_truth_path=ground_truth_path,
                prompt_path=prompt_path,
                schema_path=schema_path,
                expected_model_input=expected_model_input,
                candidate_members=candidate_members,
            )
            lecture_hashes = matched_context["lecture_sha256"]
            leakage_audit = matched_context["leakage_audit"]
            if args.execution_manifest:
                execution_manifest_path = resolve_path(
                    args.execution_manifest, ROOT
                )
                if not execution_manifest_path.is_file():
                    raise RuntimeError(
                        f"Missing required file: {execution_manifest_path}"
                    )
                execution_context = validate_execution_manifest(
                    manifest_path=execution_manifest_path,
                    relation_split=relation_ground_truth["split"],
                    prompt_path=prompt_path,
                    schema_path=schema_path,
                    input_artifact_path=input_artifact_path,
                    batch_plan_path=batch_plan_path,
                    ground_truth_path=ground_truth_path,
                    model=args.model,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    max_tokens=args.max_tokens,
                    git_commit_at_start=git_commit_at_start,
                    git_dirty_at_start=git_dirty_at_start,
                )
        else:
            model_input = expected_model_input
            leakage_audit = validate_model_input(model_input, candidate_members)

        prompt_text = prompt_path.read_text(encoding="utf-8")
        if execution_context is not None:
            if matched_context is None:
                raise RuntimeError("Candidate-scoped execution requires matched input.")
            return run_candidate_scoped_execution(
                args=args,
                relation_ground_truth=relation_ground_truth,
                ground_truth_path=ground_truth_path,
                prompt_path=prompt_path,
                schema_path=schema_path,
                prompt_text=prompt_text,
                run_dir=run_dir,
                output_dir=output_dir,
                rendered_inputs_dir=rendered_inputs_dir,
                raw_responses_dir=raw_responses_dir,
                metadata_dir=metadata_dir,
                model_input=model_input,
                candidate_members=candidate_members,
                leakage_audit=leakage_audit,
                ko_ground_truth_hashes=ko_ground_truth_hashes,
                lecture_hashes=lecture_hashes,
                matched_context=matched_context,
                execution_context=execution_context,
                git_commit_at_start=git_commit_at_start,
                git_dirty_at_start=git_dirty_at_start,
            )
        request_payload = build_request_payload(
            model=args.model,
            system_prompt=prompt_text,
            model_input=model_input,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
        )

        artifact_name = ground_truth_path.stem
        targets = artifact_paths(
            artifact_name=artifact_name,
            output_dir=output_dir,
            rendered_inputs_dir=rendered_inputs_dir,
            raw_responses_dir=raw_responses_dir,
            metadata_dir=metadata_dir,
        )
        prepare_artifacts(targets, overwrite=args.overwrite)
        for directory in [
            output_dir,
            rendered_inputs_dir,
            raw_responses_dir,
            metadata_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc).isoformat()
        metadata = build_metadata(
            experiment=args.experiment,
            run_id=args.run_id,
            split=relation_ground_truth["split"],
            version=relation_ground_truth["version"],
            ground_truth_path=ground_truth_path,
            prompt_path=prompt_path,
            schema_path=schema_path,
            request_payload=request_payload,
            model_input=model_input,
            leakage_audit=leakage_audit,
            ko_ground_truth_hashes=ko_ground_truth_hashes,
            lecture_hashes=lecture_hashes,
            artifact_map=targets,
            git_commit_at_start=git_commit_at_start,
            git_dirty_at_start=git_dirty_at_start,
            started_at=started_at,
            dry_run=args.dry_run,
            matched_context=matched_context,
        )
        write_json(targets["rendered_input"], request_payload)

        if args.dry_run:
            metadata["run_status"] = "dry_run_complete"
            write_json(targets["metadata"], metadata)
            print(f"Rendered {display_path(targets['rendered_input'])}")
            print(f"Metadata {display_path(targets['metadata'])}")
            return 0

        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            metadata["run_status"] = "configuration_failed"
            metadata["api_error"] = "DEEPSEEK_API_KEY is not set."
            write_json(targets["metadata"], metadata)
            print(metadata["api_error"], file=sys.stderr)
            return 2

        api_response: dict[str, Any] | None = None
        try:
            request_started = time.perf_counter()
            api_response = call_deepseek(api_key=api_key, payload=request_payload)
            metadata["latency_ms"] = int(
                (time.perf_counter() - request_started) * 1000
            )
            metadata["request_success"] = True
            metadata["model_returned"] = api_response.get("model")
            metadata["system_fingerprint"] = api_response.get("system_fingerprint")
            metadata["request_id"] = api_response.get("id")
            metadata["finish_reason"] = extract_finish_reason(api_response)
            metadata["usage"] = api_response.get("usage")
            write_json(targets["raw_response"], api_response)
            metadata["raw_response_sha256"] = sha256_file(targets["raw_response"])
        except RuntimeError as exc:
            metadata["latency_ms"] = int(
                (time.perf_counter() - request_started) * 1000
            )
            metadata["request_success"] = False
            metadata["api_error"] = str(exc)
            metadata["run_status"] = "request_failed"
            write_json(targets["metadata"], metadata)
            print(f"Relation request failed: {exc}", file=sys.stderr)
            return 1

        try:
            content = extract_content(api_response)
            parsed = parse_model_content(content)
            metadata["json_parse_success"] = True
            write_json(targets["prediction"], parsed)
            metadata["prediction_sha256"] = sha256_file(targets["prediction"])
        except RuntimeError as exc:
            metadata["json_parse_success"] = False
            metadata["json_parse_error"] = str(exc)
            metadata["run_status"] = "parse_failed"
            content = ""
            try:
                content = extract_content(api_response)
            except RuntimeError:
                pass
            targets["unparsed_output"].write_text(content, encoding="utf-8")
            write_json(targets["metadata"], metadata)
            print(f"Relation output parsing failed: {exc}", file=sys.stderr)
            return 1

        try:
            validate_prediction_envelope(
                parsed,
                candidate_members,
                set(relation_ground_truth["allowed_relation_types"]),
            )
            metadata["prediction_schema_valid"] = True
        except RuntimeError as exc:
            metadata["prediction_schema_valid"] = False
            metadata["prediction_schema_error"] = str(exc)
            metadata["run_status"] = "prediction_schema_failed"
            write_json(targets["metadata"], metadata)
            print(f"Relation prediction schema failed: {exc}", file=sys.stderr)
            return 1

        metadata["run_status"] = "completed"
        write_json(targets["metadata"], metadata)
        print(f"Saved {display_path(targets['prediction'])}")
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
