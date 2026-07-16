from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Callable

from scripts.check_candidate_pair_ground_truth import (
    build_completion_marker,
    validate_candidate_pair_ground_truth,
)
from scripts.create_candidate_pair_annotation_template import (
    DEFAULT_EVALUATION_PROTOCOL,
    DEFAULT_GROUND_TRUTH_SCHEMA,
    DEFAULT_GUIDELINES,
    DEFAULT_PAIR_UNIVERSE_SCHEMA,
    DEFAULT_RELATION_GUIDELINES,
    DEFAULT_SUCCESS_CRITERIA,
    build_annotation_template,
)
from scripts.generate_candidate_pair_universe import (
    build_pair_universe,
    serialize_json,
    sha256_file,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "candidate_pair_ground_truth"
INVENTORY_PATH = FIXTURE_DIR / "synthetic_inventory.json"
LECTURE_INVENTORY_PATH = FIXTURE_DIR / "synthetic_lecture_inventory.json"
ANNOTATIONS_PATH = FIXTURE_DIR / "valid_annotations.json"
REAL_UNIVERSE_PATH = (
    ROOT
    / "benchmark"
    / "candidate_pairs"
    / "development_v0_1"
    / "pair_universe.json"
)
REAL_GROUND_TRUTH_PATH = (
    ROOT / "benchmark" / "ground_truth" / "candidate_pairs_development_v0_1.json"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(serialize_json(value), encoding="utf-8")


def make_valid_bundle(root: Path) -> tuple[Path, Path]:
    inventory = load_json(INVENTORY_PATH)
    lecture_inventory = load_json(LECTURE_INVENTORY_PATH)
    universe = build_pair_universe(
        inventory,
        source_inventory_path=str(INVENTORY_PATH.relative_to(ROOT)),
        source_inventory_sha256=sha256_file(INVENTORY_PATH),
        lecture_inventory=lecture_inventory,
        lecture_inventory_path=str(LECTURE_INVENTORY_PATH.relative_to(ROOT)),
        lecture_inventory_sha256=sha256_file(LECTURE_INVENTORY_PATH),
        benchmark_split="development",
    )
    universe_path = root / "pair_universe.json"
    marker_path = root / "pair_universe_complete.json"
    ground_truth_path = root / "ground_truth.json"
    write_outputs(
        output_path=universe_path,
        marker_path=marker_path,
        pair_universe=universe,
        source_inventory_path=INVENTORY_PATH,
        source_inventory_sha256=sha256_file(INVENTORY_PATH),
        lecture_inventory_path=LECTURE_INVENTORY_PATH,
        lecture_inventory_sha256=sha256_file(LECTURE_INVENTORY_PATH),
        overwrite=False,
    )
    ground_truth = build_annotation_template(
        universe,
        pair_universe_path=universe_path,
        guidelines_path=DEFAULT_GUIDELINES,
        evaluation_protocol_path=DEFAULT_EVALUATION_PROTOCOL,
        success_criteria_path=DEFAULT_SUCCESS_CRITERIA,
        relation_guidelines_path=DEFAULT_RELATION_GUIDELINES,
        pair_universe_schema_path=DEFAULT_PAIR_UNIVERSE_SCHEMA,
        ground_truth_schema_path=DEFAULT_GROUND_TRUTH_SCHEMA,
    )
    ground_truth["status"] = "frozen"
    ground_truth["annotations"] = load_json(ANNOTATIONS_PATH)
    write_json(ground_truth_path, ground_truth)
    return universe_path, ground_truth_path


class CandidatePairGroundTruthCheckerTests(unittest.TestCase):
    def assert_ground_truth_mutation_fails(
        self,
        mutate: Callable[[dict], None],
        expected: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            universe_path, ground_truth_path = make_valid_bundle(Path(temp_dir))
            ground_truth = load_json(ground_truth_path)
            mutate(ground_truth)
            write_json(ground_truth_path, ground_truth)
            errors, _ = validate_candidate_pair_ground_truth(
                universe_path, ground_truth_path, allow_draft=False
            )
        self.assertTrue(any(expected in error for error in errors), errors)

    def assert_universe_mutation_fails(
        self,
        mutate: Callable[[dict], None],
        expected: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            universe_path, ground_truth_path = make_valid_bundle(Path(temp_dir))
            universe = load_json(universe_path)
            mutate(universe)
            write_json(universe_path, universe)
            ground_truth = load_json(ground_truth_path)
            ground_truth["pair_universe"]["sha256"] = sha256_file(universe_path)
            write_json(ground_truth_path, ground_truth)
            errors, _ = validate_candidate_pair_ground_truth(
                universe_path, ground_truth_path, allow_draft=False
            )
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_final_bundle_covers_diagnostic_and_multi_relation_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            universe_path, ground_truth_path = make_valid_bundle(Path(temp_dir))
            errors, summary = validate_candidate_pair_ground_truth(
                universe_path, ground_truth_path, allow_draft=False
            )

        self.assertEqual(errors, [])
        self.assertEqual(summary["evaluation_status"], "final")
        self.assertEqual(summary["pair_count"], 6)
        self.assertEqual(summary["primary_denominator"], 4)
        self.assertEqual(summary["diagnostic_denominator"], 2)
        self.assertEqual(
            summary["label_counts"],
            {
                "AMBIGUOUS": 1,
                "IN_SCHEMA_RELATION": 3,
                "NO_IN_SCHEMA_RELATION": 1,
                "OUT_OF_SCHEMA_RELATION": 1,
            },
        )

    def test_real_176_pair_final_passes_allow_draft(self) -> None:
        errors, summary = validate_candidate_pair_ground_truth(
            REAL_UNIVERSE_PATH, REAL_GROUND_TRUTH_PATH, allow_draft=True
        )

        self.assertEqual(errors, [])
        self.assertEqual(summary["pair_count"], 176)
        self.assertEqual(summary["pending_workflow_items"], 0)
        self.assertEqual(
            summary["label_counts"],
            {
                "IN_SCHEMA_RELATION": 80,
                "NO_IN_SCHEMA_RELATION": 91,
                "OUT_OF_SCHEMA_RELATION": 5,
            },
        )
        self.assertEqual(summary["evaluation_status"], "final")

    def test_real_final_passes_final_mode(self) -> None:
        errors, summary = validate_candidate_pair_ground_truth(
            REAL_UNIVERSE_PATH, REAL_GROUND_TRUTH_PATH, allow_draft=False
        )

        self.assertEqual(errors, [])
        self.assertEqual(summary["evaluation_status"], "final")
        self.assertEqual(summary["pending_workflow_items"], 0)

    def test_synthetic_draft_fails_final_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            universe_path, ground_truth_path = make_valid_bundle(Path(temp_dir))
            data = load_json(ground_truth_path)
            data["status"] = "draft_annotation_required"
            data["annotations"][0]["annotation_status"] = "draft"
            write_json(ground_truth_path, data)
            errors, summary = validate_candidate_pair_ground_truth(
                universe_path, ground_truth_path, allow_draft=False
            )

        self.assertEqual(summary["evaluation_status"], "invalid")
        self.assertTrue(any("final mode requires frozen" in error for error in errors))
        self.assertTrue(
            any("final mode requires annotation_status = final" in error for error in errors)
        )

    def test_missing_extra_and_duplicate_annotations_fail(self) -> None:
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"].pop(),
            "missing pair IDs",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"].append(
                {**copy.deepcopy(data["annotations"][-1]), "pair_id": "cand_dev_999"}
            ),
            "extra pair IDs",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"].__setitem__(
                1, copy.deepcopy(data["annotations"][0])
            ),
            "duplicate pair_id",
        )

    def test_reversed_duplicate_unknown_cross_lecture_and_self_pairs_fail(self) -> None:
        def reversed_duplicate(data: dict) -> None:
            first = data["pairs"][0]
            second = data["pairs"][1]
            second["ko_a"] = copy.deepcopy(first["ko_b"])
            second["ko_b"] = copy.deepcopy(first["ko_a"])

        self.assert_universe_mutation_fails(
            reversed_duplicate,
            "duplicate or reversed-duplicate pair",
        )
        self.assert_universe_mutation_fails(
            lambda data: data["pairs"][0]["ko_a"].__setitem__("ko_id", "unknown"),
            "unknown endpoint",
        )

        def cross_lecture(data: dict) -> None:
            data["pairs"][0]["ko_b"] = {
                "lecture_id": "synthetic_candidate_002",
                "ko_id": "concept_gamma",
            }

        self.assert_universe_mutation_fails(
            cross_lecture,
            "endpoints must belong to pair lecture",
        )
        self.assert_universe_mutation_fails(
            lambda data: data["pairs"][0].__setitem__(
                "ko_b", copy.deepcopy(data["pairs"][0]["ko_a"])
            ),
            "self pair is forbidden",
        )

    def test_relation_label_direction_and_payload_failures(self) -> None:
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][3]["gold_relations"][0].__setitem__(
                "relation_type", "INVALID"
            ),
            "invalid relation_type",
        )

        def wrong_formalizes_direction(data: dict) -> None:
            relation = data["annotations"][3]["gold_relations"][0]
            relation["source"], relation["target"] = relation["target"], relation["source"]

        self.assert_ground_truth_mutation_fails(
            wrong_formalizes_direction,
            "FORMALIZES source must be a Formula",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][3].__setitem__("gold_relations", []),
            "IN_SCHEMA_RELATION requires gold_relations",
        )

        def negative_with_relation(data: dict) -> None:
            data["annotations"][1]["gold_relations"] = copy.deepcopy(
                data["annotations"][3]["gold_relations"]
            )

        self.assert_ground_truth_mutation_fails(
            negative_with_relation,
            "negative annotation must not contain gold_relations",
        )

    def test_evidence_final_label_and_hash_failures(self) -> None:
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][3]["gold_relations"][0][
                "evidence_spans"
            ][0].__setitem__("span", "not in the lecture"),
            "span is not an exact lecture substring",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][1].__setitem__("candidate_label", None),
            "final annotation requires candidate_label",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["pair_universe"].__setitem__("sha256", "0" * 64),
            "stale SHA-256 binding",
        )

    def test_reused_annotation_requires_snapshot_bound_provenance(self) -> None:
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][1].__setitem__(
                "annotation_source", "reused_existing_relation_annotation"
            ),
            "source_annotation: must be an object",
        )

    def test_stale_pair_universe_completion_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            universe_path, ground_truth_path = make_valid_bundle(Path(temp_dir))
            marker_path = universe_path.with_name("pair_universe_complete.json")
            marker = load_json(marker_path)
            marker["generator"]["sha256"] = "0" * 64
            write_json(marker_path, marker)
            errors, _ = validate_candidate_pair_ground_truth(
                universe_path, ground_truth_path, allow_draft=False
            )

        self.assertTrue(any("generator: stale SHA-256 binding" in error for error in errors))

    def test_malformed_scalar_types_fail_closed_instead_of_crashing(self) -> None:
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][0].__setitem__("pair_id", ["bad"]),
            "invalid pair_id",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][0].__setitem__(
                "candidate_label", ["IN_SCHEMA_RELATION"]
            ),
            "invalid candidate_label",
        )
        self.assert_ground_truth_mutation_fails(
            lambda data: data["annotations"][3]["gold_relations"][0].__setitem__(
                "relation_type", ["FORMALIZES"]
            ),
            "invalid relation_type",
        )

    def test_completion_marker_binds_final_bundle_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            universe_path, ground_truth_path = make_valid_bundle(Path(temp_dir))
            errors, summary = validate_candidate_pair_ground_truth(
                universe_path, ground_truth_path, allow_draft=False
            )
            ground_truth = load_json(ground_truth_path)
            marker = build_completion_marker(
                pair_universe_path=universe_path,
                ground_truth_path=ground_truth_path,
                ground_truth=ground_truth,
                summary=summary,
            )
            expected_ground_truth_hash = sha256_file(ground_truth_path)

        self.assertEqual(errors, [])
        self.assertEqual(marker["completion_status"], "final")
        self.assertEqual(marker["counts"]["total_pairs"], 6)
        self.assertEqual(marker["counts"]["pending_workflow_items"], 0)
        self.assertEqual(
            marker["artifacts"]["ground_truth"]["sha256"],
            expected_ground_truth_hash,
        )


if __name__ == "__main__":
    unittest.main()
