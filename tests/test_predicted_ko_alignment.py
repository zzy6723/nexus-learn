from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import align_predicted_kos as aligner
from tests.predicted_ko_fixture_support import FIXTURES, read_json


MATRIX_PATH = FIXTURES / "alignment_cases.json"


def build_protocol_inputs(case_input: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    lectures = case_input["lectures"]
    oracle_by_lecture: dict[str, list[dict[str, Any]]] = {
        lecture_id: [] for lecture_id in lectures
    }
    for obj in case_input["oracle_objects"]:
        oracle_by_lecture[obj["lecture_id"]].append({
            "id": obj["ko_id"],
            "name": obj["name"],
            "type": obj["type"],
            "category": "required",
            "aliases": obj["aliases"],
            "source_spans": obj["source_spans"],
        })
    oracle = {
        "version": "v0.1",
        "split": "synthetic",
        "lectures": [
            {
                "lecture_id": lecture_id,
                "objects": sorted(
                    oracle_by_lecture[lecture_id], key=lambda item: item["id"]
                ),
            }
            for lecture_id in sorted(lectures)
        ],
    }
    predicted = {
        "artifact_type": "predicted_ko_normalized_inventory",
        "version": "v0.1",
        "split": "synthetic",
        "structural_normalization_version": aligner.STRUCTURAL_NORMALIZATION_VERSION,
        "input_files": [],
        "input_set_sha256": aligner.sha256_json([]),
        "normalized_content_sha256": aligner.sha256_json(
            case_input["predicted_objects"]
        ),
        "knowledge_objects": [
            {
                "lecture_id": obj["lecture_id"],
                "predicted_ko_id": obj["ko_id"],
                "name": obj["name"],
                "type": obj["type"],
                "source_spans": obj["source_spans"],
                "provenance": {
                    "source_prediction_id": obj["ko_id"],
                    "source_file": "alignment_fixture.json",
                    "source_object_index": index,
                },
            }
            for index, obj in enumerate(case_input["predicted_objects"])
        ],
    }
    lecture_data = {
        "artifact_type": "synthetic_lecture_inventory",
        "version": "v0.1",
        "split": "synthetic",
        "lectures": [
            {"lecture_id": lecture_id, "text": lectures[lecture_id]}
            for lecture_id in sorted(lectures)
        ],
    }
    review_data = {
        "artifact_type": "predicted_ko_alignment_review_items",
        "version": "v0.1",
        "items": case_input.get("review_items", []),
    }
    return oracle, predicted, lecture_data, review_data


def bind_adjudication(
    pending: dict[str, Any], specification: dict[str, Any]
) -> dict[str, Any]:
    pending_by_id = {item["item_id"]: item for item in pending["items"]}
    decisions: list[dict[str, Any]] = []
    for decision_spec in specification["decisions"]:
        item = pending_by_id[decision_spec["item_id"]]
        decisions.append({
            **decision_spec,
            "item_snapshot_sha256": item["item_snapshot_sha256"],
            "oracle_snapshots": item["oracle_snapshots"],
            "candidate_predicted_snapshots": item[
                "candidate_predicted_snapshots"
            ],
            "lecture_snapshot": item["lecture_snapshot"],
        })
    return {
        "artifact_type": "predicted_ko_alignment_resolved",
        "version": "v0.1",
        "alignment_snapshot_sha256": pending["alignment_snapshot_sha256"],
        "oracle_inventory_sha256": pending["oracle_inventory_sha256"],
        "predicted_inventory_sha256": pending["predicted_inventory_sha256"],
        "lecture_sha256": pending["lecture_sha256"],
        "name_matching_normalization_version": (
            pending["name_matching_normalization_version"]
        ),
        "decisions": decisions,
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    oracle, predicted, lectures, review = build_protocol_inputs(case["input"])
    initial = aligner.align_inventories(
        oracle,
        predicted,
        lectures,
        review_data=review,
    )
    adjudication_spec = case["input"].get("adjudication")
    if adjudication_spec is None:
        return initial
    adjudication = bind_adjudication(initial["pending"], adjudication_spec)
    return aligner.align_inventories(
        oracle,
        predicted,
        lectures,
        review_data=review,
        adjudication_data=adjudication,
    )


class PredictedKOAlignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = read_json(MATRIX_PATH)

    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def test_all_predeclared_alignment_cases(self) -> None:
        cases = self.matrix["cases"]
        self.assertEqual(len(cases), 14)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                result = run_case(case)
                alignment = result["alignment"]
                expected = case["expected"]
                self.assertEqual(
                    alignment["evaluation_status"],
                    expected["evaluation_status"],
                )
                self.assertEqual(
                    sorted(error["error_code"] for error in alignment["errors"]),
                    sorted(expected["error_codes"]),
                )
                if "pending_item_count" in expected:
                    self.assertEqual(
                        len(result["pending"]["items"]),
                        expected["pending_item_count"],
                    )
                oracle_records = {
                    f"{item['oracle_ref']['lecture_id']}::{item['oracle_ref']['ko_id']}": item
                    for item in alignment["oracle_records"]
                }
                predicted_records = {
                    f"{item['predicted_ref']['lecture_id']}::{item['predicted_ref']['ko_id']}": item
                    for item in alignment["predicted_records"]
                }
                self.assertEqual(
                    set(oracle_records), set(expected["oracle_records"])
                )
                self.assertEqual(
                    set(predicted_records), set(expected["predicted_records"])
                )
                for ref, expected_fields in expected["oracle_records"].items():
                    for field, value in expected_fields.items():
                        self.assertEqual(oracle_records[ref][field], value)
                for ref, expected_fields in expected["predicted_records"].items():
                    for field, value in expected_fields.items():
                        self.assertEqual(predicted_records[ref][field], value)
                aligner.validate_bidirectional_accounting(alignment)

    def test_fixture_inputs_are_complete_and_relation_blind(self) -> None:
        for case in self.matrix["cases"]:
            with self.subTest(case_id=case["case_id"]):
                case_input = case["input"]
                for field in [
                    "lectures",
                    "oracle_objects",
                    "predicted_objects",
                    "review_items",
                ]:
                    self.assertIn(field, case_input)
                aligner.reject_relation_leakage(
                    case_input, location=case["case_id"]
                )

    def test_order_changes_do_not_change_semantic_alignment_records(self) -> None:
        case = next(
            item
            for item in self.matrix["cases"]
            if item["case_id"] == "alignment_duplicate_predictions"
        )
        oracle, predicted, lectures, review = build_protocol_inputs(case["input"])
        forward = aligner.align_inventories(
            oracle, predicted, lectures, review_data=review
        )["alignment"]
        oracle_reversed = copy.deepcopy(oracle)
        predicted_reversed = copy.deepcopy(predicted)
        oracle_reversed["lectures"].reverse()
        for lecture in oracle_reversed["lectures"]:
            lecture["objects"].reverse()
        predicted_reversed["knowledge_objects"].reverse()
        reverse = aligner.align_inventories(
            oracle_reversed,
            predicted_reversed,
            lectures,
            review_data=review,
        )["alignment"]
        # Exact input hashes intentionally change when source bytes or array order
        # change. The deterministic invariant applies to semantic accounting.
        for field in [
            "evaluation_status",
            "oracle_records",
            "predicted_records",
            "errors",
        ]:
            self.assertEqual(forward[field], reverse[field])

    def test_same_local_ids_in_different_lectures_are_legal(self) -> None:
        case_input = {
            "lectures": {"lecture_a": "Gradient A.", "lecture_b": "Gradient B."},
            "oracle_objects": [
                {"lecture_id": "lecture_a", "ko_id": "gradient", "name": "Gradient", "type": "Concept", "aliases": [], "source_spans": ["Gradient A."]},
                {"lecture_id": "lecture_b", "ko_id": "gradient", "name": "Gradient", "type": "Concept", "aliases": [], "source_spans": ["Gradient B."]},
            ],
            "predicted_objects": [
                {"lecture_id": "lecture_a", "ko_id": "gradient", "name": "Gradient", "type": "Concept", "source_spans": ["Gradient A."]},
                {"lecture_id": "lecture_b", "ko_id": "gradient", "name": "Gradient", "type": "Concept", "source_spans": ["Gradient B."]},
            ],
            "review_items": [],
        }
        oracle, predicted, lectures, review = build_protocol_inputs(case_input)
        result = aligner.align_inventories(
            oracle, predicted, lectures, review_data=review
        )
        self.assertEqual(result["alignment"]["evaluation_status"], "final")
        self.assertEqual(
            sum(record["recoverable"] for record in result["alignment"]["oracle_records"]),
            2,
        )

    def test_stale_adjudication_is_fatal(self) -> None:
        case = next(
            item
            for item in self.matrix["cases"]
            if item["case_id"] == "alignment_manual_resolved_match"
        )
        oracle, predicted, lectures, review = build_protocol_inputs(case["input"])
        initial = aligner.align_inventories(
            oracle, predicted, lectures, review_data=review
        )
        adjudication = bind_adjudication(
            initial["pending"], case["input"]["adjudication"]
        )
        adjudication["decisions"][0]["candidate_predicted_snapshots"][0][
            "name"
        ] = "Changed after pending snapshot"
        with self.assertRaises(aligner.AlignmentError) as raised:
            aligner.align_inventories(
                oracle,
                predicted,
                lectures,
                review_data=review,
                adjudication_data=adjudication,
            )
        self.assertEqual(
            raised.exception.code, "changed_alignment_adjudication_snapshot"
        )

    def test_missing_and_unused_adjudications_are_fatal(self) -> None:
        case = next(
            item
            for item in self.matrix["cases"]
            if item["case_id"] == "alignment_manual_resolved_match"
        )
        oracle, predicted, lectures, review = build_protocol_inputs(case["input"])
        initial = aligner.align_inventories(
            oracle, predicted, lectures, review_data=review
        )
        adjudication = bind_adjudication(
            initial["pending"], case["input"]["adjudication"]
        )
        missing = {**adjudication, "decisions": []}
        with self.assertRaises(aligner.AlignmentError) as raised_missing:
            aligner.align_inventories(
                oracle,
                predicted,
                lectures,
                review_data=review,
                adjudication_data=missing,
            )
        self.assertEqual(
            raised_missing.exception.code, "missing_alignment_adjudication"
        )

        unused = copy.deepcopy(adjudication)
        unused["decisions"][0]["item_id"] = "unknown_review_item"
        with self.assertRaises(aligner.AlignmentError) as raised_unused:
            aligner.align_inventories(
                oracle,
                predicted,
                lectures,
                review_data=review,
                adjudication_data=unused,
            )
        self.assertEqual(
            raised_unused.exception.code, "unused_alignment_adjudication"
        )

    def test_non_greedy_many_to_one_component_requires_review(self) -> None:
        case_input = {
            "lectures": {"lecture_a": "Two uses of score are discussed."},
            "oracle_objects": [
                {"lecture_id": "lecture_a", "ko_id": "score_a", "name": "Score", "type": "Concept", "aliases": [], "source_spans": ["Two uses of score are discussed."]},
                {"lecture_id": "lecture_a", "ko_id": "score_b", "name": "Score", "type": "Concept", "aliases": [], "source_spans": ["Two uses of score are discussed."]},
            ],
            "predicted_objects": [
                {"lecture_id": "lecture_a", "ko_id": "score", "name": "Score", "type": "Concept", "source_spans": ["Two uses of score are discussed."]}
            ],
            "review_items": [],
        }
        oracle, predicted, lectures, review = build_protocol_inputs(case_input)
        result = aligner.align_inventories(
            oracle, predicted, lectures, review_data=review
        )
        self.assertEqual(
            result["alignment"]["evaluation_status"],
            "draft_pending_adjudication",
        )
        self.assertEqual(len(result["pending"]["items"]), 1)
        self.assertTrue(
            all(
                record["matched_predicted_ref"] is None
                for record in result["alignment"]["oracle_records"]
            )
        )

    def test_repeated_execution_is_byte_deterministic(self) -> None:
        case = self.matrix["cases"][0]
        first = run_case(case)
        second = run_case(case)
        self.assertEqual(aligner.serialize_json(first), aligner.serialize_json(second))

    def test_granularity_mismatch_is_final_but_unrecoverable(self) -> None:
        case_input = {
            "lectures": {"lecture_a": "A derivative includes several derivative notions."},
            "oracle_objects": [
                {"lecture_id": "lecture_a", "ko_id": "partial_derivative", "name": "Partial Derivative", "type": "Concept", "aliases": [], "source_spans": ["A derivative includes several derivative notions."]}
            ],
            "predicted_objects": [
                {"lecture_id": "lecture_a", "ko_id": "derivative", "name": "Derivative", "type": "Concept", "source_spans": ["A derivative includes several derivative notions."]}
            ],
            "review_items": [
                {"item_id": "review_granularity", "oracle_refs": [{"lecture_id": "lecture_a", "ko_id": "partial_derivative"}], "candidate_predicted_refs": [{"lecture_id": "lecture_a", "ko_id": "derivative"}], "proposed_alignment_level": "unresolved", "proposed_primary_structural_status": "granularity_mismatch", "reason_code": "granularity_mismatch"}
            ],
            "adjudication": {
                "decisions": [
                    {"item_id": "review_granularity", "decision": "structural_error", "resulting_alignment_level": "unresolved", "resulting_primary_structural_status": "granularity_mismatch", "matched_predicted_ref": None, "rationale": "Derivative is broader than the Oracle partial-derivative concept."}
                ]
            },
        }
        case = {"input": case_input}
        result = run_case(case)
        self.assertEqual(result["alignment"]["evaluation_status"], "final")
        self.assertEqual(
            result["alignment"]["oracle_records"][0]["primary_structural_status"],
            "granularity_mismatch",
        )
        self.assertFalse(result["alignment"]["oracle_records"][0]["recoverable"])

    def test_alignment_output_has_no_relation_fields(self) -> None:
        result = run_case(self.matrix["cases"][0])
        aligner.reject_relation_leakage(result, location="alignment_result")

    def test_cli_no_overwrite_preserves_existing_artifacts(self) -> None:
        case = self.matrix["cases"][0]
        oracle, predicted, lectures, review = build_protocol_inputs(case["input"])
        paths: dict[str, Path] = {}
        for name, value in [
            ("oracle.json", oracle),
            ("predicted.json", predicted),
            ("lectures.json", lectures),
            ("review.json", review),
        ]:
            path = self.temporary_root / name
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = path
        output_dir = self.temporary_root / "alignment"
        arguments = [
            "--oracle-inventory", str(paths["oracle.json"]),
            "--predicted-inventory", str(paths["predicted.json"]),
            "--lectures", str(paths["lectures.json"]),
            "--review-items", str(paths["review.json"]),
            "--output-dir", str(output_dir),
        ]
        self.assertEqual(aligner.main(arguments), 0)
        original = (output_dir / "alignment.json").read_bytes()
        self.assertEqual(aligner.main(arguments), 2)
        self.assertEqual((output_dir / "alignment.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
