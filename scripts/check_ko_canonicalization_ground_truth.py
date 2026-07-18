#!/usr/bin/env python3
"""Strictly validate KO mention and canonicalization Ground Truth artifacts."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.create_ko_mention_inventory import (  # noqa: E402
    DEFAULT_SCHEMA as MENTION_SCHEMA,
    GENERATOR_VERSION,
    MentionInventoryError,
    build_mention_inventory,
    load_json_object as load_mention_json,
)
from scripts.generate_candidate_pair_universe import (  # noqa: E402
    display_path,
    sha256_file,
)
from scripts.knowledge_object_matching import name_matching_key  # noqa: E402


DEFAULT_MENTION_INVENTORY = (
    ROOT / "benchmark" / "ko_mentions" / "development_v0_1" / "mention_inventory.json"
)
DEFAULT_GROUND_TRUTH = (
    ROOT
    / "benchmark"
    / "ground_truth"
    / "ko_canonicalization_development_v0_1.json"
)
DEFAULT_COMPLETION_MARKER = DEFAULT_GROUND_TRUTH.with_name(
    "ko_canonicalization_development_v0_1_complete.json"
)
MENTION_MARKER_NAME = "mention_inventory_complete.json"
ANNOTATION_GUIDELINES = ROOT / "benchmark" / "ko_canonicalization_annotation_guidelines.md"
EVALUATION_PROTOCOL = ROOT / "benchmark" / "ko_canonicalization_protocol.md"
GROUND_TRUTH_SCHEMA = (
    ROOT / "benchmark" / "schema" / "ko_canonicalization_ground_truth.schema.json"
)
CHECKER_VERSION = "ko_canonicalization_ground_truth_checker_v0.1"
ALLOWED_TYPES = ["Concept", "Method", "Formula"]
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

INVENTORY_KEYS = {
    "artifact_type",
    "version",
    "benchmark_split",
    "source_data_role",
    "mention_order",
    "source_inventory",
    "lecture_inventory",
    "counts",
    "mentions",
}
MENTION_KEYS = {
    "mention_id",
    "source_inventory_index",
    "lecture_id",
    "predicted_ko_id",
    "name",
    "type",
    "source_spans",
    "source_span_exact_flags",
    "provenance",
}
GROUND_TRUTH_KEYS = {
    "artifact_type",
    "version",
    "benchmark_split",
    "status",
    "mention_inventory",
    "annotation_guidelines",
    "evaluation_protocol",
    "schema_bindings",
    "identity_policy",
    "allowed_types",
    "clusters",
}
CLUSTER_KEYS = {
    "canonical_id",
    "canonical_name",
    "canonical_type",
    "mention_ids",
    "aliases",
    "annotation_status",
    "identity_rationale",
    "notes",
}
MENTION_MARKER_KEYS = {
    "artifact_type",
    "version",
    "status",
    "mention_inventory",
    "source_inventory",
    "lecture_inventory",
    "schema",
    "generator",
    "counts",
}
GROUND_TRUTH_MARKER_KEYS = {
    "artifact_type",
    "version",
    "status",
    "ground_truth",
    "mention_inventory",
    "annotation_guidelines",
    "evaluation_protocol",
    "schema_bindings",
    "checker",
    "counts",
}
SUMMARY_COUNT_KEYS = {
    "mentions",
    "canonical_clusters",
    "singleton_clusters",
    "multi_mention_clusters",
    "all_mention_pairs",
    "same_object_pairs",
    "distinct_object_pairs",
    "cross_lecture_pairs",
    "cross_lecture_same_object_pairs",
    "cross_lecture_distinct_object_pairs",
    "types",
}


class CanonicalizationGroundTruthError(ValueError):
    """Raised when a required artifact cannot be loaded."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", default=str(DEFAULT_MENTION_INVENTORY))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument("--completion-marker", default=str(DEFAULT_COMPLETION_MARKER))
    parser.add_argument(
        "--allow-draft",
        action="store_true",
        help="Allow draft Ground Truth and skip the completion marker requirement.",
    )
    parser.add_argument(
        "--write-completion-marker",
        action="store_true",
        help="Write the final marker after all strict checks pass.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalizationGroundTruthError(
            f"Unable to read {label} {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise CanonicalizationGroundTruthError(f"{label} must be a JSON object.")
    return value


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_exact_keys(
    value: Any,
    *,
    expected: set[str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: must be an object")
        return False
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"{label}: missing keys {missing}")
    if extra:
        errors.append(f"{label}: unexpected keys {extra}")
    return not missing and not extra


def validate_binding(
    value: Any,
    *,
    label: str,
    errors: list[str],
    require_version: bool = False,
    expected_path: Path | None = None,
) -> Path | None:
    keys = {"path", "sha256"} | ({"version"} if require_version else set())
    if not validate_exact_keys(value, expected=keys, label=label, errors=errors):
        return None
    path_text = value.get("path")
    expected_hash = value.get("sha256")
    if not nonempty_text(path_text):
        errors.append(f"{label}.path: must be non-empty")
        return None
    if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash):
        errors.append(f"{label}.sha256: must be lowercase SHA-256")
        return None
    if require_version and not nonempty_text(value.get("version")):
        errors.append(f"{label}.version: must be non-empty")
    path = resolve_path(path_text)
    if expected_path is not None and path.resolve() != expected_path.resolve():
        errors.append(f"{label}: unexpected bound path {path_text}")
    if not path.is_file():
        errors.append(f"{label}: bound file does not exist: {path_text}")
        return None
    if sha256_file(path) != expected_hash:
        errors.append(f"{label}: stale SHA-256 binding")
    return path


def validate_mention_marker(
    inventory_path: Path,
    inventory: dict[str, Any],
    *,
    errors: list[str],
) -> None:
    marker_path = inventory_path.with_name(MENTION_MARKER_NAME)
    if not marker_path.is_file():
        errors.append("mention inventory: completion marker is missing")
        return
    marker = load_json_object(marker_path, label="mention inventory completion marker")
    validate_exact_keys(
        marker,
        expected=MENTION_MARKER_KEYS,
        label="mention inventory completion marker",
        errors=errors,
    )
    if marker.get("artifact_type") != "ko_mention_inventory_complete":
        errors.append("mention inventory marker: invalid artifact_type")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        errors.append("mention inventory marker: version/status must be v0.1/final")
    for key, expected_path in (
        ("mention_inventory", inventory_path),
        ("source_inventory", resolve_path(inventory["source_inventory"]["path"])),
        ("lecture_inventory", resolve_path(inventory["lecture_inventory"]["path"])),
        ("schema", MENTION_SCHEMA),
    ):
        validate_binding(
            marker.get(key),
            label=f"mention inventory marker.{key}",
            errors=errors,
            expected_path=expected_path,
        )
    generator = marker.get("generator")
    if validate_exact_keys(
        generator,
        expected={"path", "sha256", "version"},
        label="mention inventory marker.generator",
        errors=errors,
    ):
        generator_path = resolve_path(generator["path"])
        if generator_path.resolve() != (
            ROOT / "scripts" / "create_ko_mention_inventory.py"
        ).resolve():
            errors.append("mention inventory marker.generator: unexpected path")
        if not generator_path.is_file() or sha256_file(generator_path) != generator["sha256"]:
            errors.append("mention inventory marker.generator: stale SHA-256 binding")
        if generator.get("version") != GENERATOR_VERSION:
            errors.append("mention inventory marker.generator: wrong version")
    if marker.get("counts") != inventory.get("counts"):
        errors.append("mention inventory marker: counts do not match inventory")


def validate_mention_inventory(
    inventory_path: Path,
    inventory: dict[str, Any],
    *,
    errors: list[str],
) -> None:
    validate_exact_keys(
        inventory,
        expected=INVENTORY_KEYS,
        label="mention inventory",
        errors=errors,
    )
    mentions = inventory.get("mentions")
    if not isinstance(mentions, list) or not mentions:
        errors.append("mention inventory.mentions: must be a non-empty list")
        return
    for index, mention in enumerate(mentions):
        validate_exact_keys(
            mention,
            expected=MENTION_KEYS,
            label=f"mention inventory.mentions[{index}]",
            errors=errors,
        )
        spans = mention.get("source_spans")
        flags = mention.get("source_span_exact_flags")
        if not isinstance(spans, list) or not spans:
            errors.append(f"mention inventory.mentions[{index}]: source_spans invalid")
        if not isinstance(flags, list) or len(flags) != len(spans or []):
            errors.append(
                f"mention inventory.mentions[{index}]: exact flags must align with spans"
            )

    source_binding = inventory.get("source_inventory")
    lecture_binding = inventory.get("lecture_inventory")
    if not isinstance(source_binding, dict) or not isinstance(lecture_binding, dict):
        errors.append("mention inventory: source/lecture bindings must be objects")
        return
    source_path = validate_binding(
        {key: source_binding.get(key) for key in ("path", "sha256")},
        label="mention inventory.source_inventory",
        errors=errors,
    )
    lecture_path = validate_binding(
        lecture_binding,
        label="mention inventory.lecture_inventory",
        errors=errors,
    )
    if source_path is not None and lecture_path is not None:
        try:
            source = load_mention_json(source_path, label="source inventory")
            lecture_inventory = load_mention_json(lecture_path, label="lecture inventory")
            expected = build_mention_inventory(
                source,
                source_path=source_path,
                lecture_inventory=lecture_inventory,
                lecture_inventory_path=lecture_path,
                benchmark_split=inventory.get("benchmark_split"),
                source_data_role=inventory.get("source_data_role"),
            )
            if inventory != expected:
                errors.append(
                    "mention inventory: content is not the deterministic rendering of its bound sources"
                )
        except MentionInventoryError as exc:
            errors.append(f"mention inventory: source validation failed: {exc}")
    validate_mention_marker(inventory_path, inventory, errors=errors)


def summarize_partition(
    mentions: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    mention_by_id = {item["mention_id"]: item for item in mentions}
    cluster_by_mention: dict[str, str] = {}
    for cluster in clusters:
        for mention_id in cluster.get("mention_ids", []):
            if mention_id in mention_by_id:
                cluster_by_mention[mention_id] = cluster.get("canonical_id", "")
    same_pairs = 0
    distinct_pairs = 0
    cross_pairs = 0
    cross_same_pairs = 0
    for left_index, left in enumerate(mentions):
        for right in mentions[left_index + 1 :]:
            same = cluster_by_mention.get(left["mention_id"]) == cluster_by_mention.get(
                right["mention_id"]
            )
            if same:
                same_pairs += 1
            else:
                distinct_pairs += 1
            if left["lecture_id"] != right["lecture_id"]:
                cross_pairs += 1
                if same:
                    cross_same_pairs += 1
    cluster_sizes = [len(item.get("mention_ids", [])) for item in clusters]
    type_counts = Counter(item.get("canonical_type") for item in clusters)
    return {
        "mentions": len(mentions),
        "canonical_clusters": len(clusters),
        "singleton_clusters": sum(size == 1 for size in cluster_sizes),
        "multi_mention_clusters": sum(size > 1 for size in cluster_sizes),
        "all_mention_pairs": math.comb(len(mentions), 2),
        "same_object_pairs": same_pairs,
        "distinct_object_pairs": distinct_pairs,
        "cross_lecture_pairs": cross_pairs,
        "cross_lecture_same_object_pairs": cross_same_pairs,
        "cross_lecture_distinct_object_pairs": cross_pairs - cross_same_pairs,
        "types": {name: type_counts[name] for name in ALLOWED_TYPES},
    }


def validate_ground_truth(
    ground_truth: dict[str, Any],
    inventory: dict[str, Any],
    *,
    inventory_path: Path,
    allow_draft: bool,
    errors: list[str],
) -> dict[str, Any]:
    validate_exact_keys(
        ground_truth,
        expected=GROUND_TRUTH_KEYS,
        label="ground truth",
        errors=errors,
    )
    if ground_truth.get("artifact_type") != "ko_canonicalization_ground_truth":
        errors.append("ground truth: invalid artifact_type")
    if ground_truth.get("version") != "v0.1":
        errors.append("ground truth: version must be v0.1")
    if ground_truth.get("benchmark_split") != inventory.get("benchmark_split"):
        errors.append("ground truth: benchmark split does not match mention inventory")
    expected_status = {"draft_annotation_required", "frozen"} if allow_draft else {"frozen"}
    if ground_truth.get("status") not in expected_status:
        errors.append(f"ground truth: status must be one of {sorted(expected_status)}")
    validate_binding(
        ground_truth.get("mention_inventory"),
        label="ground truth.mention_inventory",
        errors=errors,
        expected_path=inventory_path,
    )
    for key, expected_path, version in (
        (
            "annotation_guidelines",
            ANNOTATION_GUIDELINES,
            "ko_canonicalization_annotation_v0.1",
        ),
        ("evaluation_protocol", EVALUATION_PROTOCOL, "ko_canonicalization_protocol_v0.1"),
    ):
        binding = ground_truth.get(key)
        validate_binding(
            binding,
            label=f"ground truth.{key}",
            errors=errors,
            require_version=True,
            expected_path=expected_path,
        )
        if isinstance(binding, dict) and binding.get("version") != version:
            errors.append(f"ground truth.{key}: unexpected version")
    schema_bindings = ground_truth.get("schema_bindings")
    if validate_exact_keys(
        schema_bindings,
        expected={"mention_inventory", "ground_truth"},
        label="ground truth.schema_bindings",
        errors=errors,
    ):
        for key, expected_path in (
            ("mention_inventory", MENTION_SCHEMA),
            ("ground_truth", GROUND_TRUTH_SCHEMA),
        ):
            binding = schema_bindings.get(key)
            validate_binding(
                binding,
                label=f"ground truth.schema_bindings.{key}",
                errors=errors,
                require_version=True,
                expected_path=expected_path,
            )
            if isinstance(binding, dict) and binding.get("version") != "v0.1":
                errors.append(f"ground truth.schema_bindings.{key}: wrong version")
    expected_policy = {
        "cluster_annotation": "authoritative",
        "canonical_id_scheme": "opaque_sequential_in_first_mention_order",
        "cross_type_merge": "forbidden",
        "singleton_records": "required",
        "provenance_retention": "through_complete_mention_membership",
    }
    if ground_truth.get("identity_policy") != expected_policy:
        errors.append("ground truth: identity_policy differs from v0.1 protocol")
    if ground_truth.get("allowed_types") != ALLOWED_TYPES:
        errors.append("ground truth: allowed_types must preserve the frozen order")

    mentions = inventory["mentions"]
    mention_by_id = {item["mention_id"]: item for item in mentions}
    mention_order = {item["mention_id"]: index for index, item in enumerate(mentions)}
    clusters = ground_truth.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        errors.append("ground truth.clusters: must be a non-empty list")
        return summarize_partition(mentions, [])
    split_token = "dev" if inventory["benchmark_split"] == "development" else "holdout"
    assigned: list[str] = []
    first_positions: list[int] = []
    canonical_ids: list[str] = []
    for index, cluster in enumerate(clusters):
        label = f"ground truth.clusters[{index}]"
        if not validate_exact_keys(cluster, expected=CLUSTER_KEYS, label=label, errors=errors):
            continue
        expected_id = f"canonical_ko_{split_token}_{index + 1:03d}"
        canonical_id = cluster.get("canonical_id")
        canonical_ids.append(canonical_id)
        if canonical_id != expected_id:
            errors.append(f"{label}: expected canonical_id {expected_id}")
        members = cluster.get("mention_ids")
        if not isinstance(members, list) or not members:
            errors.append(f"{label}: mention_ids must be a non-empty list")
            continue
        if len(members) != len(set(members)):
            errors.append(f"{label}: duplicate mention membership")
        unknown = [mention_id for mention_id in members if mention_id not in mention_by_id]
        if unknown:
            errors.append(f"{label}: unknown mention IDs {unknown}")
            continue
        expected_member_order = sorted(members, key=mention_order.__getitem__)
        if members != expected_member_order:
            errors.append(f"{label}: mention_ids are not in mention-inventory order")
        first_positions.append(mention_order[members[0]])
        assigned.extend(members)
        member_types = {mention_by_id[mention_id]["type"] for mention_id in members}
        if len(member_types) != 1:
            errors.append(f"{label}: cross-type cluster is forbidden")
        elif cluster.get("canonical_type") != next(iter(member_types)):
            errors.append(f"{label}: canonical_type does not match member type")
        if cluster.get("canonical_type") not in ALLOWED_TYPES:
            errors.append(f"{label}: invalid canonical_type")
        if not nonempty_text(cluster.get("canonical_name")):
            errors.append(f"{label}: canonical_name must be non-empty")
        aliases = cluster.get("aliases")
        if not isinstance(aliases, list) or any(not nonempty_text(item) for item in aliases):
            errors.append(f"{label}: aliases must be a list of non-empty strings")
        else:
            keys = [name_matching_key(item) for item in aliases]
            if len(keys) != len(set(keys)):
                errors.append(f"{label}: aliases duplicate after conservative normalization")
            if nonempty_text(cluster.get("canonical_name")) and name_matching_key(
                cluster["canonical_name"]
            ) in keys:
                errors.append(f"{label}: aliases repeat canonical_name")
        allowed_statuses = {"draft", "pending_review", "final"} if allow_draft else {"final"}
        if cluster.get("annotation_status") not in allowed_statuses:
            errors.append(f"{label}: annotation_status must be one of {sorted(allowed_statuses)}")
        if not nonempty_text(cluster.get("identity_rationale")):
            errors.append(f"{label}: identity_rationale must be non-empty")
        if not isinstance(cluster.get("notes"), str):
            errors.append(f"{label}: notes must be a string")

    if len(canonical_ids) != len(set(canonical_ids)):
        errors.append("ground truth: duplicate canonical IDs")
    if first_positions != sorted(first_positions):
        errors.append("ground truth: clusters are not ordered by first mention")
    duplicates = sorted(
        mention_id for mention_id, count in Counter(assigned).items() if count > 1
    )
    if duplicates:
        errors.append(f"ground truth: mentions assigned more than once: {duplicates}")
    missing = sorted(set(mention_by_id) - set(assigned), key=mention_order.__getitem__)
    if missing:
        errors.append(f"ground truth: orphan mentions: {missing}")
    return summarize_partition(mentions, clusters)


def build_completion_marker(
    *,
    ground_truth_path: Path,
    inventory_path: Path,
    counts: dict[str, Any],
) -> dict[str, Any]:
    checker_path = Path(__file__).resolve()
    return {
        "artifact_type": "ko_canonicalization_ground_truth_complete",
        "version": "v0.1",
        "status": "final",
        "ground_truth": {
            "path": display_path(ground_truth_path),
            "sha256": sha256_file(ground_truth_path),
        },
        "mention_inventory": {
            "path": display_path(inventory_path),
            "sha256": sha256_file(inventory_path),
        },
        "annotation_guidelines": {
            "path": display_path(ANNOTATION_GUIDELINES),
            "sha256": sha256_file(ANNOTATION_GUIDELINES),
        },
        "evaluation_protocol": {
            "path": display_path(EVALUATION_PROTOCOL),
            "sha256": sha256_file(EVALUATION_PROTOCOL),
        },
        "schema_bindings": {
            "mention_inventory": {
                "path": display_path(MENTION_SCHEMA),
                "sha256": sha256_file(MENTION_SCHEMA),
            },
            "ground_truth": {
                "path": display_path(GROUND_TRUTH_SCHEMA),
                "sha256": sha256_file(GROUND_TRUTH_SCHEMA),
            },
        },
        "checker": {
            "path": display_path(checker_path),
            "sha256": sha256_file(checker_path),
            "version": CHECKER_VERSION,
        },
        "counts": counts,
    }


def validate_completion_marker(
    marker_path: Path,
    marker: dict[str, Any],
    *,
    ground_truth_path: Path,
    inventory_path: Path,
    counts: dict[str, Any],
    errors: list[str],
) -> None:
    validate_exact_keys(
        marker,
        expected=GROUND_TRUTH_MARKER_KEYS,
        label="ground truth completion marker",
        errors=errors,
    )
    if marker.get("artifact_type") != "ko_canonicalization_ground_truth_complete":
        errors.append("completion marker: invalid artifact_type")
    if marker.get("version") != "v0.1" or marker.get("status") != "final":
        errors.append("completion marker: version/status must be v0.1/final")
    for key, expected_path in (
        ("ground_truth", ground_truth_path),
        ("mention_inventory", inventory_path),
        ("annotation_guidelines", ANNOTATION_GUIDELINES),
        ("evaluation_protocol", EVALUATION_PROTOCOL),
    ):
        validate_binding(
            marker.get(key),
            label=f"completion marker.{key}",
            errors=errors,
            expected_path=expected_path,
        )
    schemas = marker.get("schema_bindings")
    if validate_exact_keys(
        schemas,
        expected={"mention_inventory", "ground_truth"},
        label="completion marker.schema_bindings",
        errors=errors,
    ):
        for key, expected_path in (
            ("mention_inventory", MENTION_SCHEMA),
            ("ground_truth", GROUND_TRUTH_SCHEMA),
        ):
            validate_binding(
                schemas.get(key),
                label=f"completion marker.schema_bindings.{key}",
                errors=errors,
                expected_path=expected_path,
            )
    checker = marker.get("checker")
    if validate_exact_keys(
        checker,
        expected={"path", "sha256", "version"},
        label="completion marker.checker",
        errors=errors,
    ):
        checker_path = resolve_path(checker["path"])
        if checker_path.resolve() != Path(__file__).resolve():
            errors.append("completion marker.checker: unexpected path")
        if not checker_path.is_file() or sha256_file(checker_path) != checker["sha256"]:
            errors.append("completion marker.checker: stale SHA-256 binding")
        if checker.get("version") != CHECKER_VERSION:
            errors.append("completion marker.checker: wrong version")
    marker_counts = marker.get("counts")
    if not isinstance(marker_counts, dict) or set(marker_counts) != SUMMARY_COUNT_KEYS:
        errors.append("completion marker.counts: invalid keys")
    elif marker_counts != counts:
        errors.append("completion marker.counts: do not match derived counts")


def validate_bundle(
    *,
    inventory_path: Path,
    ground_truth_path: Path,
    completion_marker_path: Path | None,
    allow_draft: bool,
    require_completion_marker: bool,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    inventory = load_json_object(inventory_path, label="mention inventory")
    ground_truth = load_json_object(ground_truth_path, label="canonicalization Ground Truth")
    validate_mention_inventory(inventory_path, inventory, errors=errors)
    counts = validate_ground_truth(
        ground_truth,
        inventory,
        inventory_path=inventory_path,
        allow_draft=allow_draft,
        errors=errors,
    )
    if require_completion_marker:
        if completion_marker_path is None or not completion_marker_path.is_file():
            errors.append("ground truth: final completion marker is missing")
        else:
            marker = load_json_object(
                completion_marker_path,
                label="canonicalization completion marker",
            )
            validate_completion_marker(
                completion_marker_path,
                marker,
                ground_truth_path=ground_truth_path,
                inventory_path=inventory_path,
                counts=counts,
                errors=errors,
            )
    summary = {
        "validation_status": "invalid" if errors else ("draft" if allow_draft else "final"),
        **counts,
    }
    return errors, summary


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_path = Path(args.mention_inventory).resolve()
    ground_truth_path = Path(args.ground_truth).resolve()
    marker_path = Path(args.completion_marker).resolve()
    try:
        errors, summary = validate_bundle(
            inventory_path=inventory_path,
            ground_truth_path=ground_truth_path,
            completion_marker_path=marker_path,
            allow_draft=args.allow_draft,
            require_completion_marker=not args.allow_draft and not args.write_completion_marker,
        )
    except CanonicalizationGroundTruthError as exc:
        print(f"Canonicalization Ground Truth validation failed: {exc}")
        return 1
    if errors:
        print(f"Canonicalization Ground Truth invalid ({len(errors)} errors):")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.write_completion_marker:
        if args.allow_draft:
            print("Cannot write a completion marker in draft mode.")
            return 1
        if marker_path.exists() and not args.overwrite:
            print(f"Refusing to overwrite: {display_path(marker_path)}")
            return 1
        marker = build_completion_marker(
            ground_truth_path=ground_truth_path,
            inventory_path=inventory_path,
            counts={key: summary[key] for key in SUMMARY_COUNT_KEYS},
        )
        atomic_write(marker_path, marker)
        print(f"Wrote completion marker: {display_path(marker_path)}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
