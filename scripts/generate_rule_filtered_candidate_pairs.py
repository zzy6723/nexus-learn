#!/usr/bin/env python3
"""Generate deterministic Rule-Filtered candidate pairs with a full audit."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_candidate_pairs import (  # noqa: E402
    COMPLETION_FILENAME,
    DEFAULT_OUTPUT_SCHEMA,
    DEFAULT_PAIR_UNIVERSE,
    DEFAULT_PAIR_UNIVERSE_MARKER,
    METADATA_FILENAME,
    SELECTION_FILENAME,
    CandidatePairGenerationError,
    _atomic_write_text,
    canonical_json,
    display_path,
    load_json_object,
    resolve_path,
    serialize_json,
    sha256_file,
    sha256_json,
    validate_candidate_selection,
    validate_pair_universe,
    validate_pair_universe_marker,
)
from scripts.knowledge_object_matching import (  # noqa: E402
    NAME_MATCHING_NORMALIZATION_VERSION,
    name_matching_key,
)


ROOT = PROJECT_ROOT
DEFAULT_RULES = ROOT / "benchmark" / "candidate_pair_generation_rules_v0_1.json"
DEFAULT_RULES_SCHEMA = (
    ROOT / "benchmark" / "schema" / "candidate_pair_generation_rules.schema.json"
)
DEFAULT_DECISIONS_SCHEMA = (
    ROOT / "benchmark" / "schema" / "candidate_pair_selection_decisions.schema.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments"
    / "relation_extraction"
    / "002b_candidate_discovery"
    / "runs"
    / "development_v0_1"
    / "rule_filtered_v0_1"
    / "run_01"
)
DECISIONS_FILENAME = "selection_decisions.json"
GENERATOR_NAME = "rule_filtered"
GENERATOR_VERSION = "v0.1"
GENERATOR_DEPENDENCY = ROOT / "scripts" / "generate_candidate_pairs.py"
NAME_MATCHING_DEPENDENCY = ROOT / "scripts" / "knowledge_object_matching.py"
DISPLAY_MATH_RE = re.compile(r"^\\\[[\s\S]*\\\][.,;:]?$", re.MULTILINE)
BLANK_LINE_RE = re.compile(r"\n\s*\n+")
LATEX_DELIMITER_RE = re.compile(r"\\[\[\]()]")
WHITESPACE_RE = re.compile(r"\s+")
ALLOWED_KO_TYPES = {"Concept", "Method", "Formula"}
EXPECTED_REASON_ORDER = [
    "source_proximity",
    "lexical_overlap",
    "symbol_overlap",
    "explicit_reference",
    "type_compatibility",
]
FORBIDDEN_RUNTIME_FIELDS = {
    "candidate_label",
    "gold_relations",
    "relation_type",
    "gold_evidence",
    "gold_rationale",
    "evaluation_errors",
    "oracle_alignment",
    "pair_id_allowlist",
}


class RuleFilteredGenerationError(CandidatePairGenerationError):
    """Raised when the Rule-Filtered method contract is violated."""


def _exact_keys(
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
        errors.append(f"{label}: missing fields {missing}")
    if extra:
        errors.append(f"{label}: forbidden fields {extra}")
    return not missing and not extra


def _binding(path: Path) -> dict[str, str]:
    return {"path": display_path(path), "sha256": sha256_file(path)}


def _validate_binding(
    value: Any,
    *,
    label: str,
    errors: list[str],
    expected_path: Path | None = None,
) -> None:
    if not _exact_keys(value, expected={"path", "sha256"}, label=label, errors=errors):
        return
    path_text = value.get("path")
    if not isinstance(path_text, str) or not path_text:
        errors.append(f"{label}.path: invalid")
        return
    path = resolve_path(path_text)
    if expected_path is not None and path.resolve() != expected_path.resolve():
        errors.append(f"{label}.path: unexpected path")
    if not path.is_file():
        errors.append(f"{label}: bound file does not exist")
    elif value.get("sha256") != sha256_file(path):
        errors.append(f"{label}.sha256: stale binding")


def _collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_collect_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_collect_keys(item))
        return keys
    return set()


def validate_rules_artifact(rules: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    top_keys = {
        "artifact_type",
        "version",
        "status",
        "method_id",
        "scope",
        "strategy",
        "input_contract",
        "normalization",
        "rules",
        "selection_policy",
        "reason_order",
        "failure_policy",
    }
    _exact_keys(rules, expected=top_keys, label="rules", errors=errors)
    expected_scalars = {
        "artifact_type": "candidate_pair_generation_rules",
        "version": "v0.1",
        "status": "frozen_for_development_baseline",
        "method_id": "rule_filtered_v0_1",
        "scope": "lecture_local_unordered_nonself",
        "strategy": "deterministic_union_filter",
        "selection_policy": "select_if_any_enabled_rule_matches",
    }
    for field, expected in expected_scalars.items():
        if rules.get(field) != expected:
            errors.append(f"rules.{field}: expected {expected!r}")
    if rules.get("reason_order") != EXPECTED_REASON_ORDER:
        errors.append("rules.reason_order: frozen order mismatch")

    input_contract = rules.get("input_contract")
    if _exact_keys(
        input_contract,
        expected={"allowed_ko_fields", "allowed_lecture_fields", "forbidden_fields"},
        label="rules.input_contract",
        errors=errors,
    ):
        if input_contract["allowed_ko_fields"] != [
            "lecture_id",
            "predicted_ko_id",
            "name",
            "type",
            "source_spans",
        ]:
            errors.append("rules.input_contract.allowed_ko_fields: mismatch")
        if input_contract["allowed_lecture_fields"] != ["lecture_id", "text"]:
            errors.append("rules.input_contract.allowed_lecture_fields: mismatch")
        if set(input_contract["forbidden_fields"]) != FORBIDDEN_RUNTIME_FIELDS:
            errors.append("rules.input_contract.forbidden_fields: mismatch")

    normalization = rules.get("normalization")
    if _exact_keys(
        normalization,
        expected={"name_matching", "lexical", "semantic_blocks", "symbols"},
        label="rules.normalization",
        errors=errors,
    ):
        name_matching = normalization["name_matching"]
        if _exact_keys(
            name_matching,
            expected={"path", "sha256", "version"},
            label="rules.normalization.name_matching",
            errors=errors,
        ):
            if name_matching.get("version") != NAME_MATCHING_NORMALIZATION_VERSION:
                errors.append("rules.normalization.name_matching.version: mismatch")
            comparable = {
                "path": name_matching.get("path"),
                "sha256": name_matching.get("sha256"),
            }
            _validate_binding(
                comparable,
                label="rules.normalization.name_matching",
                errors=errors,
                expected_path=NAME_MATCHING_DEPENDENCY,
            )
        lexical = normalization["lexical"]
        if _exact_keys(
            lexical,
            expected={"token_pattern", "stop_tokens"},
            label="rules.normalization.lexical",
            errors=errors,
        ):
            if lexical.get("token_pattern") != "[a-z0-9]+":
                errors.append("rules.normalization.lexical.token_pattern: mismatch")
            stop_tokens = lexical.get("stop_tokens")
            if not isinstance(stop_tokens, list) or stop_tokens != sorted(
                set(stop_tokens)
            ):
                errors.append("rules.normalization.lexical.stop_tokens: must be sorted unique")
        blocks = normalization["semantic_blocks"]
        expected_blocks = {
            "paragraph_split": "one_or_more_blank_lines",
            "display_math_policy": "attach_to_immediately_preceding_prose_block",
            "text_normalization": (
                "nfkc_casefold_remove_latex_delimiters_collapse_whitespace"
            ),
        }
        if blocks != expected_blocks:
            errors.append("rules.normalization.semantic_blocks: frozen policy mismatch")
        symbols = normalization["symbols"]
        symbol_keys = {
            "latex_command_pattern",
            "subscript_or_call_identifier_pattern",
            "uppercase_identifier_pattern",
            "stop_symbols",
        }
        if _exact_keys(
            symbols,
            expected=symbol_keys,
            label="rules.normalization.symbols",
            errors=errors,
        ):
            for field in (
                "latex_command_pattern",
                "subscript_or_call_identifier_pattern",
                "uppercase_identifier_pattern",
            ):
                try:
                    re.compile(symbols[field])
                except (TypeError, re.error) as exc:
                    errors.append(f"rules.normalization.symbols.{field}: {exc}")
            stop_symbols = symbols.get("stop_symbols")
            if not isinstance(stop_symbols, list) or stop_symbols != sorted(
                set(stop_symbols)
            ):
                errors.append("rules.normalization.symbols.stop_symbols: must be sorted unique")

    configured_rules = rules.get("rules")
    if _exact_keys(
        configured_rules,
        expected=set(EXPECTED_REASON_ORDER),
        label="rules.rules",
        errors=errors,
    ):
        for rule_name, threshold_name in (
            ("source_proximity", "maximum_semantic_block_distance"),
            ("lexical_overlap", "minimum_shared_normalized_tokens"),
            ("symbol_overlap", "minimum_shared_symbols"),
        ):
            config = configured_rules[rule_name]
            if not isinstance(config, dict) or set(config) != {"enabled", threshold_name}:
                errors.append(f"rules.rules.{rule_name}: invalid fields")
                continue
            threshold = config.get(threshold_name)
            minimum = 0 if rule_name == "source_proximity" else 1
            if config.get("enabled") is not True:
                errors.append(f"rules.rules.{rule_name}.enabled: must be true")
            if not isinstance(threshold, int) or isinstance(threshold, bool) or not (
                minimum <= threshold <= 5
            ):
                errors.append(f"rules.rules.{rule_name}.{threshold_name}: invalid threshold")
        explicit = configured_rules["explicit_reference"]
        if not isinstance(explicit, dict) or set(explicit) != {
            "enabled",
            "cue_phrases",
        }:
            errors.append("rules.rules.explicit_reference: invalid fields")
        else:
            cues = explicit.get("cue_phrases")
            if explicit.get("enabled") is not True:
                errors.append("rules.rules.explicit_reference.enabled: must be true")
            if not isinstance(cues, list) or not cues or cues != sorted(set(cues)):
                errors.append("rules.rules.explicit_reference.cue_phrases: sorted unique required")
        type_rule = configured_rules["type_compatibility"]
        if not isinstance(type_rule, dict) or set(type_rule) != {"enabled", "rationale"}:
            errors.append("rules.rules.type_compatibility: invalid fields")
        elif type_rule.get("enabled") is not False:
            errors.append("rules.rules.type_compatibility.enabled: v0.1 must be false")

    failure_policy = rules.get("failure_policy")
    expected_failure_policy = {
        "missing_source_artifact": "fatal",
        "unknown_endpoint": "fatal",
        "unlocatable_source_span": "do_not_trigger_source_proximity",
    }
    if failure_policy != expected_failure_policy:
        errors.append("rules.failure_policy: frozen policy mismatch")

    serialized = canonical_json(rules)
    if re.search(r"cand_(dev|holdout)_\d+", serialized):
        errors.append("rules: pair-specific IDs are forbidden")
    return errors


def normalize_feature_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = LATEX_DELIMITER_RE.sub(" ", normalized)
    normalized = WHITESPACE_RE.sub(" ", normalized).strip()
    return name_matching_key(normalized)


def build_semantic_blocks(text: str) -> list[str]:
    raw_blocks = [item.strip() for item in BLANK_LINE_RE.split(text) if item.strip()]
    semantic_blocks: list[str] = []
    for block in raw_blocks:
        if DISPLAY_MATH_RE.fullmatch(block) and semantic_blocks:
            semantic_blocks[-1] = f"{semantic_blocks[-1]}\n\n{block}"
        else:
            semantic_blocks.append(block)
    return semantic_blocks


def lexical_tokens(value: str, rules: dict[str, Any]) -> set[str]:
    lexical = rules["normalization"]["lexical"]
    tokens = set(re.findall(lexical["token_pattern"], name_matching_key(value)))
    filtered = tokens - set(lexical["stop_tokens"])
    return filtered or tokens


def symbol_tokens(source_spans: list[str], rules: dict[str, Any]) -> set[str]:
    symbols = rules["normalization"]["symbols"]
    found: set[str] = set()
    for span in source_spans:
        found.update(
            item.casefold()
            for item in re.findall(symbols["latex_command_pattern"], span)
        )
        found.update(
            item.casefold()
            for item in re.findall(
                symbols["subscript_or_call_identifier_pattern"], span
            )
        )
        found.update(
            item.casefold()
            for item in re.findall(symbols["uppercase_identifier_pattern"], span)
        )
    return found - set(symbols["stop_symbols"])


def locate_knowledge_object(
    knowledge_object: dict[str, Any],
    *,
    normalized_blocks: list[str],
) -> tuple[list[int], str]:
    located: set[int] = set()
    for span in knowledge_object["source_spans"]:
        normalized_span = normalize_feature_text(span)
        if not normalized_span:
            continue
        for index, block in enumerate(normalized_blocks):
            if normalized_span in block:
                located.add(index)
    if located:
        return sorted(located), "source_span"
    normalized_name = normalize_feature_text(knowledge_object["name"])
    for index, block in enumerate(normalized_blocks):
        if normalized_name and normalized_name in block:
            located.add(index)
    return sorted(located), "name_fallback" if located else "unlocated"


def load_feature_inputs(
    pair_universe: dict[str, Any],
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[str, str],
    Path,
    Path,
]:
    source_inventory_path = resolve_path(pair_universe["source_inventory"]["path"])
    lecture_inventory_path = resolve_path(pair_universe["lecture_inventory"]["path"])
    for path, binding, label in (
        (source_inventory_path, pair_universe["source_inventory"], "source inventory"),
        (lecture_inventory_path, pair_universe["lecture_inventory"], "lecture inventory"),
    ):
        if not path.is_file():
            raise RuleFilteredGenerationError(f"Missing {label}: {display_path(path)}")
        if sha256_file(path) != binding["sha256"]:
            raise RuleFilteredGenerationError(f"{label} has a stale universe binding.")

    source_inventory = load_json_object(source_inventory_path, label="source inventory")
    lecture_inventory = load_json_object(
        lecture_inventory_path, label="lecture inventory"
    )
    if source_inventory.get("artifact_type") != "predicted_ko_normalized_inventory":
        raise RuleFilteredGenerationError("Invalid predicted-KO inventory artifact_type.")
    objects = source_inventory.get("knowledge_objects")
    if not isinstance(objects, list) or not objects:
        raise RuleFilteredGenerationError(
            "Predicted-KO inventory requires a non-empty list."
        )
    if sha256_json(objects) != source_inventory.get("normalized_content_sha256"):
        raise RuleFilteredGenerationError("Predicted-KO content hash is stale.")
    forbidden_object_fields = _collect_keys(objects) & FORBIDDEN_RUNTIME_FIELDS
    if forbidden_object_fields:
        raise RuleFilteredGenerationError(
            "Predicted-KO inventory contains forbidden fields: "
            f"{sorted(forbidden_object_fields)}"
        )

    object_map: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_fields = {"lecture_id", "predicted_ko_id", "name", "type", "source_spans"}
    for index, raw_object in enumerate(objects):
        if not isinstance(raw_object, dict):
            raise RuleFilteredGenerationError(f"knowledge_objects[{index}] is invalid.")
        projected = {field: raw_object.get(field) for field in allowed_fields}
        lecture_id = projected["lecture_id"]
        ko_id = projected["predicted_ko_id"]
        if not isinstance(lecture_id, str) or not isinstance(ko_id, str):
            raise RuleFilteredGenerationError(f"knowledge_objects[{index}] has invalid IDs.")
        if not isinstance(projected["name"], str) or not projected["name"]:
            raise RuleFilteredGenerationError(f"knowledge_objects[{index}] has invalid name.")
        if projected["type"] not in ALLOWED_KO_TYPES:
            raise RuleFilteredGenerationError(f"knowledge_objects[{index}] has invalid type.")
        spans = projected["source_spans"]
        if not isinstance(spans, list) or not spans or not all(
            isinstance(span, str) and span for span in spans
        ):
            raise RuleFilteredGenerationError(
                f"knowledge_objects[{index}] has invalid source_spans."
            )
        ref = (lecture_id, ko_id)
        if ref in object_map:
            raise RuleFilteredGenerationError(f"Duplicate predicted KO {ref}.")
        object_map[ref] = projected

    lectures = lecture_inventory.get("lectures")
    if not isinstance(lectures, list):
        raise RuleFilteredGenerationError("Lecture inventory requires lectures.")
    forbidden_lecture_fields = _collect_keys(lectures) & FORBIDDEN_RUNTIME_FIELDS
    if forbidden_lecture_fields:
        raise RuleFilteredGenerationError(
            "Lecture inventory contains forbidden fields: "
            f"{sorted(forbidden_lecture_fields)}"
        )
    lecture_texts: dict[str, str] = {}
    for index, raw_lecture in enumerate(lectures):
        if not isinstance(raw_lecture, dict):
            raise RuleFilteredGenerationError(f"lectures[{index}] is invalid.")
        lecture_id = raw_lecture.get("lecture_id")
        text = raw_lecture.get("text")
        if not isinstance(lecture_id, str) or not isinstance(text, str) or not text:
            raise RuleFilteredGenerationError(f"lectures[{index}] has invalid fields.")
        if lecture_id in lecture_texts:
            raise RuleFilteredGenerationError(f"Duplicate lecture {lecture_id}.")
        lecture_texts[lecture_id] = text

    endpoint_refs = {
        (endpoint["lecture_id"], endpoint["ko_id"])
        for pair in pair_universe["pairs"]
        for endpoint in (pair["ko_a"], pair["ko_b"])
    }
    missing_refs = sorted(endpoint_refs - set(object_map))
    if missing_refs:
        raise RuleFilteredGenerationError(f"Unknown pair endpoints: {missing_refs}")
    if len(object_map) != pair_universe.get("total_ko_count"):
        raise RuleFilteredGenerationError(
            "Predicted-KO count differs from the frozen pair universe."
        )
    expected_lectures = {item["lecture_id"] for item in pair_universe["lectures"]}
    if expected_lectures != set(lecture_texts):
        raise RuleFilteredGenerationError("Lecture inventory IDs differ from universe.")
    return object_map, lecture_texts, source_inventory_path, lecture_inventory_path


def evaluate_pair_rules(
    pair: dict[str, Any],
    *,
    object_map: dict[tuple[str, str], dict[str, Any]],
    semantic_blocks: dict[str, list[str]],
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    refs = [
        (pair["ko_a"]["lecture_id"], pair["ko_a"]["ko_id"]),
        (pair["ko_b"]["lecture_id"], pair["ko_b"]["ko_id"]),
    ]
    ko_a, ko_b = (object_map[ref] for ref in refs)
    blocks = semantic_blocks[pair["lecture_id"]]
    normalized_blocks = [normalize_feature_text(block) for block in blocks]
    a_locations, a_location_method = locate_knowledge_object(
        ko_a, normalized_blocks=normalized_blocks
    )
    b_locations, b_location_method = locate_knowledge_object(
        ko_b, normalized_blocks=normalized_blocks
    )

    details_by_rule: dict[str, dict[str, Any]] = {}
    proximity = rules["rules"]["source_proximity"]
    if proximity["enabled"] and a_locations and b_locations:
        minimum_distance = min(
            abs(a_index - b_index)
            for a_index in a_locations
            for b_index in b_locations
        )
        if minimum_distance <= proximity["maximum_semantic_block_distance"]:
            details_by_rule["source_proximity"] = {
                "ko_a_block_indices": a_locations,
                "ko_b_block_indices": b_locations,
                "ko_a_location_method": a_location_method,
                "ko_b_location_method": b_location_method,
                "minimum_semantic_block_distance": minimum_distance,
            }

    lexical = rules["rules"]["lexical_overlap"]
    a_name_tokens = lexical_tokens(ko_a["name"], rules)
    b_name_tokens = lexical_tokens(ko_b["name"], rules)
    shared_tokens = sorted(a_name_tokens & b_name_tokens)
    if lexical["enabled"] and len(shared_tokens) >= lexical[
        "minimum_shared_normalized_tokens"
    ]:
        details_by_rule["lexical_overlap"] = {"shared_tokens": shared_tokens}

    symbol = rules["rules"]["symbol_overlap"]
    shared_symbols = sorted(
        symbol_tokens(ko_a["source_spans"], rules)
        & symbol_tokens(ko_b["source_spans"], rules)
    )
    if symbol["enabled"] and len(shared_symbols) >= symbol["minimum_shared_symbols"]:
        details_by_rule["symbol_overlap"] = {"shared_symbols": shared_symbols}

    explicit = rules["rules"]["explicit_reference"]
    explicit_blocks: list[dict[str, Any]] = []
    if explicit["enabled"]:
        for index, normalized_block in enumerate(normalized_blocks):
            block_tokens = set(
                re.findall(
                    rules["normalization"]["lexical"]["token_pattern"],
                    normalized_block,
                )
            )
            a_identified = a_name_tokens.issubset(block_tokens) or index in a_locations
            b_identified = b_name_tokens.issubset(block_tokens) or index in b_locations
            matched_cues = [
                cue
                for cue in explicit["cue_phrases"]
                if normalize_feature_text(cue) in normalized_block
            ]
            if a_identified and b_identified and matched_cues:
                explicit_blocks.append(
                    {"semantic_block_index": index, "cue_phrases": matched_cues}
                )
    if explicit_blocks:
        details_by_rule["explicit_reference"] = {"matches": explicit_blocks}

    return [
        {"rule": rule_name, "details": details_by_rule[rule_name]}
        for rule_name in rules["reason_order"]
        if rule_name in details_by_rule
    ]


def build_decision_audit(
    *,
    pair_universe: dict[str, Any],
    pair_universe_path: Path,
    rules: dict[str, Any],
    rules_path: Path,
    object_map: dict[tuple[str, str], dict[str, Any]],
    lecture_texts: dict[str, str],
    source_inventory_path: Path,
    lecture_inventory_path: Path,
) -> dict[str, Any]:
    semantic_blocks = {
        lecture_id: build_semantic_blocks(text)
        for lecture_id, text in lecture_texts.items()
    }
    decisions: list[dict[str, Any]] = []
    selected_count = 0
    for pair in pair_universe["pairs"]:
        triggered_rules = evaluate_pair_rules(
            pair,
            object_map=object_map,
            semantic_blocks=semantic_blocks,
            rules=rules,
        )
        selected = bool(triggered_rules)
        selected_count += int(selected)
        decisions.append(
            {
                "pair_id": pair["pair_id"],
                "lecture_id": pair["lecture_id"],
                "ko_a": dict(pair["ko_a"]),
                "ko_b": dict(pair["ko_b"]),
                "selected": selected,
                "triggered_rules": triggered_rules,
                "exclusion_reason": None if selected else "no_rule_triggered",
            }
        )
    return {
        "artifact_type": "candidate_pair_selection_decisions",
        "version": "v0.1",
        "benchmark_split": pair_universe["benchmark_split"],
        "generator": {
            "id": rules["method_id"],
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
        },
        "pair_universe": _binding(pair_universe_path),
        "rules": _binding(rules_path),
        "source_inventory": _binding(source_inventory_path),
        "lecture_inventory": _binding(lecture_inventory_path),
        "decision_count": len(decisions),
        "selected_pair_count": selected_count,
        "decisions": decisions,
    }


def validate_decision_audit(
    audit: dict[str, Any],
    *,
    pair_universe: dict[str, Any],
    rules: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    expected_top = {
        "artifact_type",
        "version",
        "benchmark_split",
        "generator",
        "pair_universe",
        "rules",
        "source_inventory",
        "lecture_inventory",
        "decision_count",
        "selected_pair_count",
        "decisions",
    }
    _exact_keys(audit, expected=expected_top, label="decision_audit", errors=errors)
    if audit.get("artifact_type") != "candidate_pair_selection_decisions":
        errors.append("decision_audit.artifact_type: invalid")
    if audit.get("version") != "v0.1":
        errors.append("decision_audit.version: invalid")
    decisions = audit.get("decisions")
    if not isinstance(decisions, list):
        errors.append("decision_audit.decisions: must be a list")
        return errors
    if audit.get("decision_count") != len(decisions):
        errors.append("decision_audit.decision_count: mismatch")
    universe_pairs = pair_universe["pairs"]
    if len(decisions) != len(universe_pairs):
        errors.append("decision_audit: must contain every universe pair")
    selected_count = 0
    for index, (decision, expected_pair) in enumerate(zip(decisions, universe_pairs)):
        label = f"decision_audit.decisions[{index}]"
        expected_keys = {
            "pair_id",
            "lecture_id",
            "ko_a",
            "ko_b",
            "selected",
            "triggered_rules",
            "exclusion_reason",
        }
        if not _exact_keys(decision, expected=expected_keys, label=label, errors=errors):
            continue
        for field in ("pair_id", "lecture_id", "ko_a", "ko_b"):
            if decision.get(field) != expected_pair.get(field):
                errors.append(f"{label}.{field}: universe mismatch")
        triggered = decision.get("triggered_rules")
        if not isinstance(triggered, list):
            errors.append(f"{label}.triggered_rules: must be a list")
            continue
        rule_names = [item.get("rule") for item in triggered if isinstance(item, dict)]
        expected_order = [name for name in rules["reason_order"] if name in rule_names]
        if rule_names != expected_order or len(rule_names) != len(set(rule_names)):
            errors.append(f"{label}.triggered_rules: invalid order or duplicate")
        selected = decision.get("selected")
        if not isinstance(selected, bool):
            errors.append(f"{label}.selected: must be boolean")
        elif selected != bool(triggered):
            errors.append(f"{label}.selected: inconsistent with triggered rules")
        if selected:
            selected_count += 1
            if decision.get("exclusion_reason") is not None:
                errors.append(f"{label}.exclusion_reason: selected pair must use null")
        elif decision.get("exclusion_reason") != "no_rule_triggered":
            errors.append(f"{label}.exclusion_reason: invalid")
    if audit.get("selected_pair_count") != selected_count:
        errors.append("decision_audit.selected_pair_count: mismatch")
    forbidden = _collect_keys(audit) & FORBIDDEN_RUNTIME_FIELDS
    if forbidden:
        errors.append(f"decision_audit: forbidden gold fields {sorted(forbidden)}")
    return errors


def build_selection(
    *,
    pair_universe: dict[str, Any],
    pair_universe_path: Path,
    rules: dict[str, Any],
    rules_path: Path,
    rules_schema_path: Path,
    decisions_path: Path,
    decisions_schema_path: Path,
    audit: dict[str, Any],
) -> dict[str, Any]:
    implementation_path = Path(__file__).resolve()
    config = {
        "strategy": "rule_filtered",
        "selection_policy": rules["selection_policy"],
        "rules_artifact": _binding(rules_path),
        "rules_schema": _binding(rules_schema_path),
        "decision_audit": _binding(decisions_path),
        "decision_schema": _binding(decisions_schema_path),
        "implementation_dependencies": [
            _binding(GENERATOR_DEPENDENCY),
            _binding(NAME_MATCHING_DEPENDENCY),
        ],
    }
    selected_by_id = {
        decision["pair_id"]: decision
        for decision in audit["decisions"]
        if decision["selected"]
    }
    selected_pairs = []
    for pair in pair_universe["pairs"]:
        decision = selected_by_id.get(pair["pair_id"])
        if decision is None:
            continue
        selected_pairs.append(
            {
                "pair_id": pair["pair_id"],
                "lecture_id": pair["lecture_id"],
                "ko_a": dict(pair["ko_a"]),
                "ko_b": dict(pair["ko_b"]),
                "candidate_reasons": [
                    item["rule"] for item in decision["triggered_rules"]
                ],
            }
        )
    source_inventory = pair_universe["source_inventory"]
    return {
        "artifact_type": "candidate_pair_selection",
        "version": "v0.1",
        "benchmark_split": pair_universe["benchmark_split"],
        "scope": pair_universe["scope"],
        "selection_order": "pair_universe_order",
        "generator": {
            "id": rules["method_id"],
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
            "implementation": _binding(implementation_path),
            "config": config,
            "config_sha256": sha256_json(config),
        },
        "pair_universe": _binding(pair_universe_path),
        "source_inventory": {
            "path": source_inventory["path"],
            "sha256": source_inventory["sha256"],
            "normalized_content_sha256": source_inventory[
                "normalized_content_sha256"
            ],
        },
        "selected_pair_count": len(selected_pairs),
        "selected_pairs": selected_pairs,
    }


def write_rule_filtered_bundle(
    *,
    output_dir: Path,
    pair_universe: dict[str, Any],
    pair_universe_path: Path,
    pair_universe_marker_path: Path,
    output_schema_path: Path,
    rules_path: Path,
    rules_schema_path: Path,
    decisions_schema_path: Path,
    source_inventory_path: Path,
    lecture_inventory_path: Path,
    audit: dict[str, Any],
) -> tuple[Path, Path, Path, Path]:
    decisions_path = output_dir / DECISIONS_FILENAME
    selection_path = output_dir / SELECTION_FILENAME
    metadata_path = output_dir / METADATA_FILENAME
    marker_path = output_dir / COMPLETION_FILENAME
    targets = (decisions_path, selection_path, metadata_path, marker_path)
    existing = [display_path(path) for path in targets if path.exists()]
    if existing:
        raise RuleFilteredGenerationError(
            f"Refusing to overwrite existing artifact(s): {', '.join(existing)}."
        )

    _atomic_write_text(decisions_path, serialize_json(audit))
    selection = build_selection(
        pair_universe=pair_universe,
        pair_universe_path=pair_universe_path,
        rules=load_json_object(rules_path, label="rules"),
        rules_path=rules_path,
        rules_schema_path=rules_schema_path,
        decisions_path=decisions_path,
        decisions_schema_path=decisions_schema_path,
        audit=audit,
    )
    selection_errors = validate_candidate_selection(
        selection,
        pair_universe=pair_universe,
        pair_universe_path=pair_universe_path,
        require_all_pairs_contract=False,
    )
    if selection_errors:
        raise RuleFilteredGenerationError("; ".join(selection_errors))
    _atomic_write_text(selection_path, serialize_json(selection))

    trigger_counts = Counter(
        item["rule"]
        for decision in audit["decisions"]
        for item in decision["triggered_rules"]
    )
    metadata = {
        "artifact_type": "candidate_pair_generation_metadata",
        "version": "v0.1",
        "status": "final",
        "generator": selection["generator"],
        "inputs": {
            "pair_universe": _binding(pair_universe_path),
            "pair_universe_completion_marker": _binding(
                pair_universe_marker_path
            ),
            "source_inventory": _binding(source_inventory_path),
            "lecture_inventory": _binding(lecture_inventory_path),
            "rules": _binding(rules_path),
            "rules_schema": _binding(rules_schema_path),
            "output_schema": _binding(output_schema_path),
            "decisions_schema": _binding(decisions_schema_path),
        },
        "decision_audit": _binding(decisions_path),
        "rule_trigger_counts": {
            rule_name: trigger_counts.get(rule_name, 0)
            for rule_name in EXPECTED_REASON_ORDER
        },
        "output": {
            "path": display_path(selection_path),
            "sha256": sha256_file(selection_path),
            "selected_pair_count": selection["selected_pair_count"],
        },
        "integrity": {
            "duplicate_pair_count": 0,
            "unknown_pair_count": 0,
            "endpoint_mismatch_count": 0,
            "order_matches_universe": True,
            "gold_artifacts_read": False,
        },
    }
    _atomic_write_text(metadata_path, serialize_json(metadata))

    marker = {
        "artifact_type": "candidate_pair_generation_complete",
        "version": "v0.1",
        "status": "final",
        "artifacts": {
            "candidate_selection": _binding(selection_path),
            "metadata": _binding(metadata_path),
            "pair_universe": _binding(pair_universe_path),
            "pair_universe_completion_marker": _binding(
                pair_universe_marker_path
            ),
            "output_schema": _binding(output_schema_path),
        },
        "generator": {
            "id": selection["generator"]["id"],
            "version": selection["generator"]["version"],
            "implementation": selection["generator"]["implementation"],
            "config_sha256": selection["generator"]["config_sha256"],
        },
        "counts": {
            "universe_pairs": pair_universe["total_pair_count"],
            "selected_pairs": selection["selected_pair_count"],
            "missing_universe_pairs": (
                pair_universe["total_pair_count"]
                - selection["selected_pair_count"]
            ),
            "extra_pairs": 0,
            "duplicate_pairs": 0,
            "endpoint_mismatches": 0,
        },
    }
    _atomic_write_text(marker_path, serialize_json(marker))
    return selection_path, decisions_path, metadata_path, marker_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic Rule-Filtered candidate pairs."
    )
    parser.add_argument("--pair-universe", default=str(DEFAULT_PAIR_UNIVERSE))
    parser.add_argument(
        "--pair-universe-completion-marker",
        default=str(DEFAULT_PAIR_UNIVERSE_MARKER),
    )
    parser.add_argument("--rules", default=str(DEFAULT_RULES))
    parser.add_argument("--rules-schema", default=str(DEFAULT_RULES_SCHEMA))
    parser.add_argument("--output-schema", default=str(DEFAULT_OUTPUT_SCHEMA))
    parser.add_argument(
        "--decisions-schema", default=str(DEFAULT_DECISIONS_SCHEMA)
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pair_universe_path = resolve_path(args.pair_universe)
    pair_universe_marker_path = resolve_path(args.pair_universe_completion_marker)
    rules_path = resolve_path(args.rules)
    rules_schema_path = resolve_path(args.rules_schema)
    output_schema_path = resolve_path(args.output_schema)
    decisions_schema_path = resolve_path(args.decisions_schema)
    output_dir = resolve_path(args.output_dir)
    try:
        required_paths = {
            "pair universe": pair_universe_path,
            "pair-universe completion marker": pair_universe_marker_path,
            "rules": rules_path,
            "rules schema": rules_schema_path,
            "output schema": output_schema_path,
            "decisions schema": decisions_schema_path,
        }
        for label, path in required_paths.items():
            if not path.is_file():
                raise RuleFilteredGenerationError(
                    f"Missing {label}: {display_path(path)}"
                )
        pair_universe = load_json_object(pair_universe_path, label="pair universe")
        pair_universe_marker = load_json_object(
            pair_universe_marker_path,
            label="pair-universe completion marker",
        )
        _, universe_errors = validate_pair_universe(pair_universe)
        universe_errors.extend(
            validate_pair_universe_marker(
                pair_universe_marker,
                marker_path=pair_universe_marker_path,
                pair_universe_path=pair_universe_path,
                pair_universe=pair_universe,
            )
        )
        if universe_errors:
            raise RuleFilteredGenerationError("; ".join(universe_errors))

        rules = load_json_object(rules_path, label="rules")
        rules_errors = validate_rules_artifact(rules)
        if rules_errors:
            raise RuleFilteredGenerationError("; ".join(rules_errors))
        object_map, lecture_texts, source_inventory_path, lecture_inventory_path = (
            load_feature_inputs(pair_universe)
        )
        audit = build_decision_audit(
            pair_universe=pair_universe,
            pair_universe_path=pair_universe_path,
            rules=rules,
            rules_path=rules_path,
            object_map=object_map,
            lecture_texts=lecture_texts,
            source_inventory_path=source_inventory_path,
            lecture_inventory_path=lecture_inventory_path,
        )
        audit_errors = validate_decision_audit(
            audit,
            pair_universe=pair_universe,
            rules=rules,
        )
        if audit_errors:
            raise RuleFilteredGenerationError("; ".join(audit_errors))
        selection_path, decisions_path, metadata_path, marker_path = (
            write_rule_filtered_bundle(
                output_dir=output_dir,
                pair_universe=pair_universe,
                pair_universe_path=pair_universe_path,
                pair_universe_marker_path=pair_universe_marker_path,
                output_schema_path=output_schema_path,
                rules_path=rules_path,
                rules_schema_path=rules_schema_path,
                decisions_schema_path=decisions_schema_path,
                source_inventory_path=source_inventory_path,
                lecture_inventory_path=lecture_inventory_path,
                audit=audit,
            )
        )
    except (OSError, json.JSONDecodeError, RuleFilteredGenerationError) as exc:
        print(f"Rule-Filtered candidate generation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Selected {audit['selected_pair_count']} of {audit['decision_count']} pairs "
        f"with {rules['method_id']}."
    )
    print(f"Candidates {display_path(selection_path)}")
    print(f"Decision audit {display_path(decisions_path)}")
    print(f"Metadata {display_path(metadata_path)}")
    print(f"Completion marker {display_path(marker_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
