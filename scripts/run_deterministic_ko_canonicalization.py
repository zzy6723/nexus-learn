#!/usr/bin/env python3
"""Run deterministic KO canonicalization without API or Ground Truth access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ko_canonicalization_ground_truth import (  # noqa: E402
    validate_mention_inventory,
)
from scripts.generate_candidate_pair_universe import display_path, sha256_file  # noqa: E402
from scripts.knowledge_object_matching import (  # noqa: E402
    APOSTROPHE_TRANSLATION,
    DASH_TRANSLATION,
    name_matching_key,
)


DEFAULT_INVENTORY = (
    ROOT / "benchmark" / "ko_mentions" / "development_v0_1" / "mention_inventory.json"
)
DEFAULT_NORMALIZATION_CONFIG = ROOT / "benchmark" / "ko_name_normalization_v0_1.json"
DEFAULT_ALIAS_RESOURCE = ROOT / "benchmark" / "ko_aliases_v0_1.json"
METHOD_IDS = {
    "exact_name_same_type_v0_1": "exact_name_same_type_v0_1",
    "alias_aware_same_type_v0_1": "alias_aware_same_type_v0_1",
}
OUTPUT_FILES = {
    "clusters": "canonical_clusters.json",
    "assignments": "mention_assignments.json",
    "audit": "normalization_audit.json",
    "metadata": "metadata.json",
    "completion": "generation_complete.json",
}
RUNNER_VERSION = "deterministic_ko_canonicalizer_v0.1"
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
ALLOWED_TYPES = {"Concept", "Method", "Formula"}


class DeterministicCanonicalizationError(ValueError):
    """Raised when deterministic canonicalization cannot safely continue."""


def read_repository_state() -> tuple[str, bool]:
    """Read the launch commit and tracked/untracked worktree state."""

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
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeterministicCanonicalizationError(
            f"Unable to verify repository state: {exc}"
        ) from exc
    commit = commit_result.stdout.strip()
    if not COMMIT_PATTERN.fullmatch(commit):
        raise DeterministicCanonicalizationError("Repository returned an invalid commit hash.")
    return commit, bool(status_result.stdout.strip())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mention-inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument(
        "--method",
        choices=sorted(METHOD_IDS),
        required=True,
    )
    parser.add_argument(
        "--normalization-config",
        default=str(DEFAULT_NORMALIZATION_CONFIG),
    )
    parser.add_argument("--alias-resource", default=str(DEFAULT_ALIAS_RESOURCE))
    parser.add_argument("--method-commit", required=True)
    parser.add_argument("--run-id", default="run_01")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeterministicCanonicalizationError(
            f"Unable to read {label} {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise DeterministicCanonicalizationError(f"{label} must be a JSON object.")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


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
            handle.write(serialize_json(value))
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def validate_normalization_config(config: dict[str, Any]) -> list[dict[str, str]]:
    expected_keys = {
        "artifact_type",
        "version",
        "protocol_version",
        "unicode_form",
        "ordered_operations",
        "outer_wrappers",
        "prohibited_operations",
    }
    if set(config) != expected_keys:
        raise DeterministicCanonicalizationError(
            "Normalization config has an unexpected field set."
        )
    if config.get("artifact_type") != "ko_name_normalization_config":
        raise DeterministicCanonicalizationError("Invalid normalization artifact_type.")
    if config.get("version") != "v0.1" or config.get("unicode_form") != "NFKC":
        raise DeterministicCanonicalizationError("Unsupported normalization version.")
    expected_operations = [
        "unicode_normalization",
        "apostrophe_normalization",
        "dash_normalization",
        "trim_whitespace",
        "balanced_outer_wrapper_removal",
        "collapse_whitespace",
        "casefold",
    ]
    if config.get("ordered_operations") != expected_operations:
        raise DeterministicCanonicalizationError(
            "Normalization operation order differs from v0.1."
        )
    wrappers = config.get("outer_wrappers")
    if not isinstance(wrappers, list) or not wrappers:
        raise DeterministicCanonicalizationError("outer_wrappers must be non-empty.")
    seen_names: set[str] = set()
    for index, wrapper in enumerate(wrappers):
        if not isinstance(wrapper, dict) or set(wrapper) != {"name", "open", "close"}:
            raise DeterministicCanonicalizationError(
                f"outer_wrappers[{index}] has invalid fields."
            )
        if not all(isinstance(wrapper[key], str) and wrapper[key] for key in wrapper):
            raise DeterministicCanonicalizationError(
                f"outer_wrappers[{index}] contains an empty value."
            )
        if wrapper["name"] in seen_names:
            raise DeterministicCanonicalizationError("Duplicate wrapper name.")
        seen_names.add(wrapper["name"])
    return wrappers


def normalize_name(
    name: str,
    *,
    wrappers: list[dict[str, str]],
) -> tuple[str, list[str]]:
    if not isinstance(name, str) or not name.strip():
        raise DeterministicCanonicalizationError("KO name must be non-empty text.")
    operations: list[str] = []
    value = name

    updated = unicodedata.normalize("NFKC", value)
    if updated != value:
        operations.append("unicode_normalization")
    value = updated

    updated = value.translate(APOSTROPHE_TRANSLATION)
    if updated != value:
        operations.append("apostrophe_normalization")
    value = updated

    updated = value.translate(DASH_TRANSLATION)
    if updated != value:
        operations.append("dash_normalization")
    value = updated

    updated = value.strip()
    if updated != value:
        operations.append("trim_whitespace")
    value = updated

    for wrapper in wrappers:
        opening = wrapper["open"]
        closing = wrapper["close"]
        if value.startswith(opening) and value.endswith(closing):
            candidate = value[len(opening) : len(value) - len(closing)]
            if candidate.strip():
                value = candidate
                operations.append(f"outer_wrapper_removed:{wrapper['name']}")
                break

    updated = re.sub(r"\s+", " ", value)
    if updated != value:
        operations.append("collapse_whitespace")
    value = updated

    updated = value.casefold()
    if updated != value:
        operations.append("casefold")
    value = updated
    if not value:
        raise DeterministicCanonicalizationError("Normalized KO name is empty.")
    if value != name_matching_key(value):
        raise DeterministicCanonicalizationError(
            "Canonicalization normalization drifted from shared name matching."
        )
    return value, operations


def build_alias_index(
    alias_resource: dict[str, Any],
    *,
    wrappers: list[dict[str, str]],
) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    expected_keys = {
        "artifact_type",
        "version",
        "status",
        "scope",
        "ground_truth_independent",
        "entries",
    }
    if set(alias_resource) != expected_keys:
        raise DeterministicCanonicalizationError("Alias resource has invalid fields.")
    if alias_resource.get("artifact_type") != "ko_alias_equivalence_resource":
        raise DeterministicCanonicalizationError("Invalid alias resource artifact_type.")
    if alias_resource.get("version") != "v0.1":
        raise DeterministicCanonicalizationError("Unsupported alias resource version.")
    if alias_resource.get("status") != "frozen_pre_evaluation":
        raise DeterministicCanonicalizationError("Alias resource is not frozen.")
    if alias_resource.get("ground_truth_independent") is not True:
        raise DeterministicCanonicalizationError("Alias resource is not Ground Truth independent.")

    index: dict[tuple[str, str], str] = {}
    display_names: dict[tuple[str, str], str] = {}
    entries = alias_resource.get("entries")
    if not isinstance(entries, list):
        raise DeterministicCanonicalizationError("Alias entries must be a list.")
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {
            "type",
            "canonical_name",
            "aliases",
            "source_note",
        }:
            raise DeterministicCanonicalizationError(
                f"Alias entry {entry_index} has invalid fields."
            )
        ko_type = entry.get("type")
        if ko_type not in ALLOWED_TYPES:
            raise DeterministicCanonicalizationError(
                f"Alias entry {entry_index} has invalid type."
            )
        canonical_name = entry.get("canonical_name")
        aliases = entry.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            raise DeterministicCanonicalizationError(
                f"Alias entry {entry_index} requires aliases."
            )
        canonical_key, _ = normalize_name(canonical_name, wrappers=wrappers)
        group_names = [canonical_name, *aliases]
        for group_name in group_names:
            normalized, _ = normalize_name(group_name, wrappers=wrappers)
            key = (ko_type, normalized)
            existing = index.get(key)
            if existing is not None and existing != canonical_key:
                raise DeterministicCanonicalizationError(
                    f"Alias collision for {ko_type}: {group_name}."
                )
            index[key] = canonical_key
            display_names[(ko_type, canonical_key)] = canonical_name
    return index, display_names


def stable_cluster_id(
    *,
    ko_type: str,
    identity_key: str,
    mention_ids: list[str],
) -> str:
    digest = sha256_json(
        {
            "type": ko_type,
            "identity_key": identity_key,
            "mention_ids": sorted(mention_ids),
        }
    )
    return f"canonical_pred_{digest[:16]}"


def build_prediction(
    inventory: dict[str, Any],
    *,
    method_id: str,
    normalization_config: dict[str, Any],
    alias_resource: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    wrappers = validate_normalization_config(normalization_config)
    alias_index: dict[tuple[str, str], str] = {}
    alias_display: dict[tuple[str, str], str] = {}
    if method_id == "alias_aware_same_type_v0_1":
        if alias_resource is None:
            raise DeterministicCanonicalizationError("Alias-aware method requires a resource.")
        alias_index, alias_display = build_alias_index(
            alias_resource,
            wrappers=wrappers,
        )
    elif method_id != "exact_name_same_type_v0_1":
        raise DeterministicCanonicalizationError(f"Unsupported method: {method_id}.")

    mentions = inventory["mentions"]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    audit_records: list[dict[str, Any]] = []
    for mention in mentions:
        normalized_name, operations = normalize_name(
            mention["name"],
            wrappers=wrappers,
        )
        ko_type = mention["type"]
        identity_key = alias_index.get((ko_type, normalized_name), normalized_name)
        if identity_key != normalized_name:
            operations = [*operations, "frozen_alias_equivalence"]
        groups[(ko_type, identity_key)].append(mention)
        audit_records.append(
            {
                "mention_id": mention["mention_id"],
                "original_name": mention["name"],
                "normalized_name": normalized_name,
                "identity_key": identity_key,
                "type": ko_type,
                "normalization_operations": operations,
                "assigned_cluster_id": None,
            }
        )

    mention_order = {
        mention["mention_id"]: index for index, mention in enumerate(mentions)
    }
    ordered_groups = sorted(
        groups.items(),
        key=lambda item: min(mention_order[m["mention_id"]] for m in item[1]),
    )
    clusters: list[dict[str, Any]] = []
    assignments: list[dict[str, str]] = []
    assignment_by_mention: dict[str, str] = {}
    for (ko_type, identity_key), members in ordered_groups:
        members = sorted(members, key=lambda item: mention_order[item["mention_id"]])
        mention_ids = [item["mention_id"] for item in members]
        cluster_id = stable_cluster_id(
            ko_type=ko_type,
            identity_key=identity_key,
            mention_ids=mention_ids,
        )
        canonical_name = alias_display.get((ko_type, identity_key), members[0]["name"])
        clusters.append(
            {
                "canonical_id": cluster_id,
                "canonical_name": canonical_name,
                "canonical_type": ko_type,
                "normalized_identity_key": identity_key,
                "mention_ids": mention_ids,
                "mention_provenance": [dict(item) for item in members],
            }
        )
        for mention_id in mention_ids:
            assignment_by_mention[mention_id] = cluster_id
            assignments.append(
                {
                    "mention_id": mention_id,
                    "canonical_id": cluster_id,
                }
            )
    assignments.sort(key=lambda item: mention_order[item["mention_id"]])
    for record in audit_records:
        record["assigned_cluster_id"] = assignment_by_mention[record["mention_id"]]

    method = {
        "method_id": method_id,
        "version": "v0.1",
        "merge_rule": "same_identity_key_and_same_type",
        "uses_alias_resource": method_id == "alias_aware_same_type_v0_1",
    }
    counts = {
        "mentions": len(mentions),
        "clusters": len(clusters),
        "singleton_clusters": sum(len(item["mention_ids"]) == 1 for item in clusters),
        "multi_mention_clusters": sum(len(item["mention_ids"]) > 1 for item in clusters),
    }
    prediction = {
        "artifact_type": "ko_canonicalization_prediction",
        "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"],
        "cluster_order": "ascending_first_mention_inventory_index",
        "method": method,
        "counts": counts,
        "clusters": clusters,
    }
    assignment_artifact = {
        "artifact_type": "ko_canonicalization_assignments",
        "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"],
        "method_id": method_id,
        "assignments": assignments,
    }
    audit = {
        "artifact_type": "ko_name_normalization_audit",
        "version": "v0.1",
        "benchmark_split": inventory["benchmark_split"],
        "method_id": method_id,
        "records": audit_records,
    }
    return prediction, assignment_artifact, audit


def artifact_binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def write_run(
    *,
    output_dir: Path,
    inventory_path: Path,
    normalization_path: Path,
    alias_path: Path | None,
    method_id: str,
    method_commit: str,
    git_commit_at_start: str,
    git_dirty_at_start: bool,
    run_id: str,
    prediction: dict[str, Any],
    assignments: dict[str, Any],
    audit: dict[str, Any],
    overwrite: bool,
) -> None:
    paths = {name: output_dir / filename for name, filename in OUTPUT_FILES.items()}
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        raise DeterministicCanonicalizationError(
            "Refusing to overwrite: " + ", ".join(display_path(path) for path in existing)
        )
    if overwrite:
        for path in paths.values():
            if path.exists():
                path.unlink()

    atomic_write(paths["clusters"], prediction)
    atomic_write(paths["assignments"], assignments)
    atomic_write(paths["audit"], audit)
    metadata = {
        "artifact_type": "ko_canonicalization_run_metadata",
        "version": "v0.1",
        "run_id": run_id,
        "run_status": "completed",
        "method_id": method_id,
        "method_commit": method_commit,
        "git_commit_at_start": git_commit_at_start,
        "git_dirty_at_start": git_dirty_at_start,
        "mention_inventory": artifact_binding(inventory_path),
        "mention_inventory_completion_marker": artifact_binding(
            inventory_path.with_name("mention_inventory_complete.json")
        ),
        "normalization_config": artifact_binding(normalization_path),
        "alias_resource": artifact_binding(alias_path) if alias_path is not None else None,
        "runner": {
            **artifact_binding(Path(__file__).resolve()),
            "version": RUNNER_VERSION,
        },
        "outputs": {
            "canonical_clusters": artifact_binding(paths["clusters"]),
            "mention_assignments": artifact_binding(paths["assignments"]),
            "normalization_audit": artifact_binding(paths["audit"]),
        },
        "counts": prediction["counts"],
    }
    atomic_write(paths["metadata"], metadata)
    marker = {
        "artifact_type": "ko_canonicalization_generation_complete",
        "version": "v0.1",
        "status": "final",
        "method_id": method_id,
        "method_commit": method_commit,
        "artifacts": {
            "canonical_clusters": artifact_binding(paths["clusters"]),
            "mention_assignments": artifact_binding(paths["assignments"]),
            "normalization_audit": artifact_binding(paths["audit"]),
            "metadata": artifact_binding(paths["metadata"]),
        },
    }
    atomic_write(paths["completion"], marker)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not COMMIT_PATTERN.fullmatch(args.method_commit):
        print("Canonicalization failed: --method-commit must be a 40-character commit hash.")
        return 1
    inventory_path = Path(args.mention_inventory).resolve()
    normalization_path = Path(args.normalization_config).resolve()
    alias_path = (
        Path(args.alias_resource).resolve()
        if args.method == "alias_aware_same_type_v0_1"
        else None
    )
    output_dir = Path(args.output_dir).resolve()
    try:
        git_commit_at_start, git_dirty_at_start = read_repository_state()
        if git_commit_at_start != args.method_commit:
            raise DeterministicCanonicalizationError(
                "Current repository commit does not match --method-commit."
            )
        if git_dirty_at_start:
            raise DeterministicCanonicalizationError(
                "Formal deterministic run requires a clean working tree."
            )
        inventory = load_json_object(inventory_path, label="mention inventory")
        inventory_errors: list[str] = []
        validate_mention_inventory(inventory_path, inventory, errors=inventory_errors)
        if inventory_errors:
            raise DeterministicCanonicalizationError(
                "Mention inventory validation failed: " + "; ".join(inventory_errors)
            )
        normalization_config = load_json_object(
            normalization_path,
            label="normalization config",
        )
        alias_resource = (
            load_json_object(alias_path, label="alias resource")
            if alias_path is not None
            else None
        )
        prediction, assignments, audit = build_prediction(
            inventory,
            method_id=args.method,
            normalization_config=normalization_config,
            alias_resource=alias_resource,
        )
        if args.dry_run:
            print(json.dumps(prediction["counts"], indent=2))
            print("Dry run complete; no artifacts written.")
            return 0
        write_run(
            output_dir=output_dir,
            inventory_path=inventory_path,
            normalization_path=normalization_path,
            alias_path=alias_path,
            method_id=args.method,
            method_commit=args.method_commit,
            git_commit_at_start=git_commit_at_start,
            git_dirty_at_start=git_dirty_at_start,
            run_id=args.run_id,
            prediction=prediction,
            assignments=assignments,
            audit=audit,
            overwrite=args.overwrite,
        )
    except DeterministicCanonicalizationError as exc:
        print(f"Canonicalization failed: {exc}")
        return 1
    print(
        f"Wrote {prediction['counts']['clusters']} clusters to "
        f"{display_path(output_dir)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
