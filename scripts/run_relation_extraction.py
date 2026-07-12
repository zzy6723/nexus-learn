#!/usr/bin/env python3
"""Render and run Oracle-KO Typed Relation Extraction experiments."""

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
        lecture_ids.add(lecture["lecture_id"])

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
        object_refs.add((obj["lecture_id"], obj["ko_id"]))

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
) -> dict[str, Any]:
    return {
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
        model_input, candidate_members, lecture_hashes = build_model_input(
            relation_ground_truth,
            ko_registry,
            lecture_paths,
        )
        leakage_audit = validate_model_input(model_input, candidate_members)

        prompt_text = prompt_path.read_text(encoding="utf-8")
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
            metadata["finish_reason"] = extract_finish_reason(api_response)
            metadata["usage"] = api_response.get("usage")
            write_json(targets["raw_response"], api_response)
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
