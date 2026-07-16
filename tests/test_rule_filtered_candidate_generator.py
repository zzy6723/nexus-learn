from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_candidate_pair_universe import (
    build_pair_universe,
    serialize_json,
    sha256_bytes,
    sha256_file,
    sha256_json,
    write_outputs,
)
from scripts.generate_candidate_pairs import canonical_json
from scripts.generate_rule_filtered_candidate_pairs import (
    DEFAULT_DECISIONS_SCHEMA,
    DEFAULT_RULES,
    DEFAULT_RULES_SCHEMA,
    NAME_MATCHING_DEPENDENCY,
    RuleFilteredGenerationError,
    build_decision_audit,
    build_selection,
    build_semantic_blocks,
    evaluate_pair_rules,
    load_feature_inputs,
    validate_decision_audit,
    validate_rules_artifact,
    write_rule_filtered_bundle,
)
from tests.test_candidate_pair_generator import OUTPUT_SCHEMA_PATH, load_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "candidate_pair_generation"
    / "rule_filtered"
    / "rule_cases.json"
)


def build_source_artifacts(root: Path, fixture: dict | None = None):
    fixture = copy.deepcopy(fixture or load_json(FIXTURE_PATH))
    objects = []
    lecture_texts = {}
    for lecture in fixture["lectures"]:
        lecture_id = lecture["lecture_id"]
        lecture_texts[lecture_id] = lecture["text"]
        for item in lecture["knowledge_objects"]:
            objects.append(
                {
                    "lecture_id": lecture_id,
                    "predicted_ko_id": item["predicted_ko_id"],
                    "name": item["name"],
                    "type": item["type"],
                    "source_spans": item["source_spans"],
                    "provenance": {"fixture": True},
                }
            )
    inventory = {
        "artifact_type": "predicted_ko_normalized_inventory",
        "version": "v0.1",
        "split": "development",
        "structural_normalization_version": "fixture_v0.1",
        "knowledge_objects": objects,
        "normalized_content_sha256": sha256_json(objects),
    }
    lecture_inventory = {
        "artifact_type": "predicted_ko_relation_lecture_inventory",
        "version": "v0.1",
        "split": "development",
        "sources": [
            {
                "lecture_id": lecture_id,
                "path": f"{lecture_id}.md",
                "markdown_sha256": "a" * 64,
                "model_text_sha256": sha256_bytes(text.encode("utf-8")),
            }
            for lecture_id, text in sorted(lecture_texts.items())
        ],
        "lectures": [
            {"lecture_id": lecture_id, "text": text}
            for lecture_id, text in sorted(lecture_texts.items())
        ],
    }
    inventory_path = root / "inventory.json"
    lecture_inventory_path = root / "lecture_inventory.json"
    inventory_path.write_text(serialize_json(inventory), encoding="utf-8")
    lecture_inventory_path.write_text(
        serialize_json(lecture_inventory), encoding="utf-8"
    )
    universe = build_pair_universe(
        inventory,
        source_inventory_path=str(inventory_path),
        source_inventory_sha256=sha256_file(inventory_path),
        lecture_inventory=lecture_inventory,
        lecture_inventory_path=str(lecture_inventory_path),
        lecture_inventory_sha256=sha256_file(lecture_inventory_path),
        benchmark_split="development",
    )
    universe_path = root / "pair_universe.json"
    marker_path = root / "pair_universe_complete.json"
    write_outputs(
        output_path=universe_path,
        marker_path=marker_path,
        pair_universe=universe,
        source_inventory_path=inventory_path,
        source_inventory_sha256=sha256_file(inventory_path),
        lecture_inventory_path=lecture_inventory_path,
        lecture_inventory_sha256=sha256_file(lecture_inventory_path),
        overwrite=False,
    )
    return universe, universe_path, marker_path, inventory_path, lecture_inventory_path


class RuleFilteredCandidateGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        (
            self.universe,
            self.universe_path,
            self.marker_path,
            self.inventory_path,
            self.lecture_inventory_path,
        ) = build_source_artifacts(self.root)
        self.rules = load_json(DEFAULT_RULES)
        (
            self.object_map,
            self.lecture_texts,
            _,
            _,
        ) = load_feature_inputs(self.universe)
        self.audit = build_decision_audit(
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            rules=self.rules,
            rules_path=DEFAULT_RULES,
            object_map=self.object_map,
            lecture_texts=self.lecture_texts,
            source_inventory_path=self.inventory_path,
            lecture_inventory_path=self.lecture_inventory_path,
        )

    def pair_by_id(self, pair_id: str):
        return next(item for item in self.universe["pairs"] if item["pair_id"] == pair_id)

    def evaluate_with_only(self, pair_id: str, enabled_rule: str):
        rules = copy.deepcopy(self.rules)
        for rule_name in (
            "source_proximity",
            "lexical_overlap",
            "symbol_overlap",
            "explicit_reference",
        ):
            rules["rules"][rule_name]["enabled"] = rule_name == enabled_rule
        pair = self.pair_by_id(pair_id)
        semantic_blocks = {
            lecture_id: build_semantic_blocks(text)
            for lecture_id, text in self.lecture_texts.items()
        }
        return evaluate_pair_rules(
            pair,
            object_map=self.object_map,
            semantic_blocks=semantic_blocks,
            rules=rules,
        )

    def test_frozen_rules_are_valid_and_pair_specific_ids_are_absent(self) -> None:
        self.assertEqual(validate_rules_artifact(self.rules), [])
        self.assertNotIn("cand_dev_", canonical_json(self.rules))
        self.assertEqual(
            self.rules["normalization"]["name_matching"]["sha256"],
            sha256_file(NAME_MATCHING_DEPENDENCY),
        )

    def test_five_pair_fixture_selects_two_and_audits_all_five(self) -> None:
        expected = load_json(FIXTURE_PATH)["expected"]
        selected_ids = [
            item["pair_id"] for item in self.audit["decisions"] if item["selected"]
        ]

        self.assertEqual(self.universe["total_pair_count"], 5)
        self.assertEqual(self.audit["decision_count"], 5)
        self.assertEqual(self.audit["selected_pair_count"], 2)
        self.assertEqual(selected_ids, expected["selected_pair_ids"])
        self.assertEqual(validate_decision_audit(
            self.audit, pair_universe=self.universe, rules=self.rules
        ), [])

    def test_proximity_lexical_and_symbol_rules_trigger_independently(self) -> None:
        proximity = self.evaluate_with_only("cand_dev_004", "source_proximity")
        lexical = self.evaluate_with_only("cand_dev_004", "lexical_overlap")
        symbol = self.evaluate_with_only("cand_dev_005", "symbol_overlap")

        self.assertEqual([item["rule"] for item in proximity], ["source_proximity"])
        self.assertEqual([item["rule"] for item in lexical], ["lexical_overlap"])
        self.assertEqual([item["rule"] for item in symbol], ["symbol_overlap"])
        self.assertEqual(symbol[0]["details"]["shared_symbols"], ["theta"])

    def test_explicit_reference_rule_triggers_independently(self) -> None:
        pair = {
            "pair_id": "cand_dev_999",
            "lecture_id": "explicit_test",
            "ko_a": {"lecture_id": "explicit_test", "ko_id": "base"},
            "ko_b": {"lecture_id": "explicit_test", "ko_id": "advanced"},
        }
        objects = {
            ("explicit_test", "base"): {
                "lecture_id": "explicit_test",
                "predicted_ko_id": "base",
                "name": "Base Technique",
                "type": "Method",
                "source_spans": ["Base Technique"],
            },
            ("explicit_test", "advanced"): {
                "lecture_id": "explicit_test",
                "predicted_ko_id": "advanced",
                "name": "Advanced Procedure",
                "type": "Method",
                "source_spans": ["Advanced Procedure"],
            },
        }
        rules = copy.deepcopy(self.rules)
        rules["rules"]["source_proximity"]["enabled"] = False
        rules["rules"]["lexical_overlap"]["enabled"] = False
        rules["rules"]["symbol_overlap"]["enabled"] = False
        result = evaluate_pair_rules(
            pair,
            object_map=objects,
            semantic_blocks={
                "explicit_test": [
                    "Advanced Procedure extends Base Technique with a correction."
                ]
            },
            rules=rules,
        )
        self.assertEqual([item["rule"] for item in result], ["explicit_reference"])

    def test_multiple_rules_select_once_in_frozen_reason_order(self) -> None:
        decision = next(
            item for item in self.audit["decisions"] if item["pair_id"] == "cand_dev_004"
        )
        reason_names = [item["rule"] for item in decision["triggered_rules"]]
        self.assertTrue(decision["selected"])
        self.assertEqual(
            reason_names,
            [name for name in self.rules["reason_order"] if name in reason_names],
        )
        self.assertEqual(len(reason_names), len(set(reason_names)))

    def test_no_rule_pair_is_rejected_with_original_endpoints(self) -> None:
        decision = self.audit["decisions"][0]
        expected_pair = self.universe["pairs"][0]
        self.assertFalse(decision["selected"])
        self.assertEqual(decision["triggered_rules"], [])
        self.assertEqual(decision["exclusion_reason"], "no_rule_triggered")
        for field in ("pair_id", "lecture_id", "ko_a", "ko_b"):
            self.assertEqual(decision[field], expected_pair[field])

    def test_invalid_rule_name_threshold_hash_and_gold_field_fail(self) -> None:
        invalid_name = copy.deepcopy(self.rules)
        invalid_name["rules"]["pair_specific_override"] = {"enabled": True}
        self.assertTrue(
            any("forbidden fields" in item for item in validate_rules_artifact(invalid_name))
        )

        invalid_threshold = copy.deepcopy(self.rules)
        invalid_threshold["rules"]["source_proximity"][
            "maximum_semantic_block_distance"
        ] = -1
        self.assertTrue(
            any("invalid threshold" in item for item in validate_rules_artifact(invalid_threshold))
        )

        stale_hash = copy.deepcopy(self.rules)
        stale_hash["normalization"]["name_matching"]["sha256"] = "0" * 64
        self.assertTrue(
            any("stale binding" in item for item in validate_rules_artifact(stale_hash))
        )

        leaked = copy.deepcopy(self.rules)
        leaked["ground_truth"] = "forbidden.json"
        errors = validate_rules_artifact(leaked)
        self.assertTrue(any("forbidden fields" in item for item in errors), errors)

    def test_source_inventory_gold_field_is_rejected(self) -> None:
        inventory = load_json(self.inventory_path)
        inventory["knowledge_objects"][0]["candidate_label"] = "IN_SCHEMA_RELATION"
        inventory["normalized_content_sha256"] = sha256_json(
            inventory["knowledge_objects"]
        )
        self.inventory_path.write_text(serialize_json(inventory), encoding="utf-8")
        self.universe["source_inventory"]["sha256"] = sha256_file(self.inventory_path)
        self.universe["source_inventory"]["normalized_content_sha256"] = inventory[
            "normalized_content_sha256"
        ]

        with self.assertRaisesRegex(RuleFilteredGenerationError, "forbidden fields"):
            load_feature_inputs(self.universe)

    def test_empty_inventory_fails_and_single_ko_lecture_is_valid(self) -> None:
        inventory = load_json(self.inventory_path)
        inventory["knowledge_objects"] = []
        inventory["normalized_content_sha256"] = sha256_json([])
        self.inventory_path.write_text(serialize_json(inventory), encoding="utf-8")
        self.universe["source_inventory"]["sha256"] = sha256_file(self.inventory_path)
        self.universe["source_inventory"]["normalized_content_sha256"] = inventory[
            "normalized_content_sha256"
        ]
        with self.assertRaisesRegex(RuleFilteredGenerationError, "non-empty"):
            load_feature_inputs(self.universe)

        one_fixture = {
            "lectures": [
                {
                    "lecture_id": "single_001",
                    "text": "A single concept is introduced.",
                    "knowledge_objects": [
                        {
                            "predicted_ko_id": "single_concept",
                            "name": "Single Concept",
                            "type": "Concept",
                            "source_spans": ["A single concept is introduced."],
                        }
                    ],
                }
            ]
        }
        single_root = self.root / "single"
        single_root.mkdir()
        universe, universe_path, _, inventory_path, lecture_path = build_source_artifacts(
            single_root, one_fixture
        )
        objects, texts, _, _ = load_feature_inputs(universe)
        audit = build_decision_audit(
            pair_universe=universe,
            pair_universe_path=universe_path,
            rules=self.rules,
            rules_path=DEFAULT_RULES,
            object_map=objects,
            lecture_texts=texts,
            source_inventory_path=inventory_path,
            lecture_inventory_path=lecture_path,
        )
        self.assertEqual(universe["total_pair_count"], 0)
        self.assertEqual(audit["decisions"], [])
        self.assertEqual(audit["selected_pair_count"], 0)

    def test_decision_and_selection_builds_are_byte_deterministic(self) -> None:
        repeated_audit = build_decision_audit(
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            rules=self.rules,
            rules_path=DEFAULT_RULES,
            object_map=self.object_map,
            lecture_texts=self.lecture_texts,
            source_inventory_path=self.inventory_path,
            lecture_inventory_path=self.lecture_inventory_path,
        )
        self.assertEqual(serialize_json(self.audit), serialize_json(repeated_audit))

        decisions_path = self.root / "same" / "selection_decisions.json"
        decisions_path.parent.mkdir()
        decisions_path.write_text(serialize_json(self.audit), encoding="utf-8")
        first = build_selection(
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            rules=self.rules,
            rules_path=DEFAULT_RULES,
            rules_schema_path=DEFAULT_RULES_SCHEMA,
            decisions_path=decisions_path,
            decisions_schema_path=DEFAULT_DECISIONS_SCHEMA,
            audit=self.audit,
        )
        second = build_selection(
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            rules=self.rules,
            rules_path=DEFAULT_RULES,
            rules_schema_path=DEFAULT_RULES_SCHEMA,
            decisions_path=decisions_path,
            decisions_schema_path=DEFAULT_DECISIONS_SCHEMA,
            audit=repeated_audit,
        )
        self.assertEqual(serialize_json(first), serialize_json(second))

    def test_bundle_has_two_candidates_five_decisions_and_no_overwrite(self) -> None:
        output_dir = self.root / "run_01"
        paths = write_rule_filtered_bundle(
            output_dir=output_dir,
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            pair_universe_marker_path=self.marker_path,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            rules_path=DEFAULT_RULES,
            rules_schema_path=DEFAULT_RULES_SCHEMA,
            decisions_schema_path=DEFAULT_DECISIONS_SCHEMA,
            source_inventory_path=self.inventory_path,
            lecture_inventory_path=self.lecture_inventory_path,
            audit=self.audit,
        )
        selection = load_json(paths[0])
        decisions = load_json(paths[1])
        metadata = load_json(paths[2])
        marker = load_json(paths[3])
        self.assertEqual(selection["selected_pair_count"], 2)
        self.assertEqual(decisions["decision_count"], 5)
        self.assertEqual(marker["counts"]["selected_pairs"], 2)
        self.assertEqual(marker["counts"]["missing_universe_pairs"], 3)
        self.assertEqual(
            selection["generator"]["config"]["decision_audit"]["sha256"],
            sha256_file(paths[1]),
        )
        self.assertFalse(metadata["integrity"]["gold_artifacts_read"])

        with self.assertRaisesRegex(RuleFilteredGenerationError, "Refusing to overwrite"):
            write_rule_filtered_bundle(
                output_dir=output_dir,
                pair_universe=self.universe,
                pair_universe_path=self.universe_path,
                pair_universe_marker_path=self.marker_path,
                output_schema_path=OUTPUT_SCHEMA_PATH,
                rules_path=DEFAULT_RULES,
                rules_schema_path=DEFAULT_RULES_SCHEMA,
                decisions_schema_path=DEFAULT_DECISIONS_SCHEMA,
                source_inventory_path=self.inventory_path,
                lecture_inventory_path=self.lecture_inventory_path,
                audit=self.audit,
            )


if __name__ == "__main__":
    unittest.main()
