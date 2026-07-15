from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import align_predicted_kos as aligner
from scripts import normalize_predicted_kos as normalizer
from scripts import project_recoverable_relation_pairs as projector
from scripts.check_relation_ground_truth import validate_ground_truth
from tests.predicted_ko_fixture_support import FIXTURES, read_json


SHARED = FIXTURES / "shared"
ORACLE_PATH = SHARED / "synthetic_oracle_inventory.json"
PREDICTED_RAW_PATH = SHARED / "synthetic_predicted_inventory.json"
LECTURES_PATH = SHARED / "synthetic_lectures.json"
RELATION_PATH = SHARED / "synthetic_original_ground_truth.json"
MANIFEST_CASES_PATH = FIXTURES / "manifest_cases.json"


def build_base_context() -> dict[str, Any]:
    oracle = read_json(ORACLE_PATH)
    predicted = normalizer.normalize_prediction_files([PREDICTED_RAW_PATH])
    lectures = read_json(LECTURES_PATH)
    relation = read_json(RELATION_PATH)
    oracle_hash = projector.artifact_sha256(oracle)
    predicted_hash = projector.artifact_sha256(predicted)
    alignment = aligner.align_inventories(
        oracle,
        predicted,
        lectures,
        oracle_inventory_sha256=oracle_hash,
        predicted_inventory_sha256=predicted_hash,
    )["alignment"]
    return {
        "oracle": oracle,
        "predicted": predicted,
        "lectures": lectures,
        "relation": relation,
        "alignment": alignment,
        "oracle_hash": oracle_hash,
        "predicted_hash": predicted_hash,
    }


def mark_oracle_missing(alignment: dict[str, Any], oracle_refs: set[str]) -> None:
    predicted_to_release: set[tuple[str, str]] = set()
    for record in alignment["oracle_records"]:
        label = (
            f"{record['oracle_ref']['lecture_id']}::{record['oracle_ref']['ko_id']}"
        )
        if label not in oracle_refs:
            continue
        matched = record["matched_predicted_ref"]
        if matched is not None:
            predicted_to_release.add((matched["lecture_id"], matched["ko_id"]))
        record.update({
            "matched_predicted_ref": None,
            "linked_predicted_refs": [],
            "alignment_level": "unresolved",
            "identity_match": False,
            "type_match": None,
            "predicted_source_span_exact": None,
            "predicted_source_span_supports_identity": None,
            "primary_structural_status": "missing",
            "structural_flags": [],
            "recoverable": False,
            "adjudication_required": False,
            "notes": "Synthetic missing endpoint for projection testing.",
        })
    for record in alignment["predicted_records"]:
        ref = (record["predicted_ref"]["lecture_id"], record["predicted_ref"]["ko_id"])
        if ref not in predicted_to_release:
            continue
        record.update({
            "matched_oracle_ref": None,
            "linked_oracle_refs": [],
            "accounting_status": "unmatched_extra",
            "identity_match": False,
            "recoverable": False,
            "notes": "Synthetic unmatched prediction for projection testing.",
        })


def refresh_input_hashes(artifact: dict[str, Any]) -> None:
    artifact["ko_content_sha256"] = projector.sha256_json(
        artifact["model_input"]["knowledge_objects"]
    )
    artifact["model_input_sha256"] = projector.sha256_json(artifact["model_input"])


def refresh_lecture_hashes(artifact: dict[str, Any]) -> None:
    artifact["lecture_sha256"] = {
        lecture["lecture_id"]: projector.sha256_text(lecture["text"])
        for lecture in artifact["model_input"]["lectures"]
    }


class PredictedKOProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = build_base_context()
        cls.manifest_cases = read_json(MANIFEST_CASES_PATH)["cases"]

    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def project(
        self,
        *,
        relation: dict[str, Any] | None = None,
        alignment: dict[str, Any] | None = None,
        original_ground_truth_sha256: str | None = None,
    ) -> dict[str, Any]:
        relation = copy.deepcopy(relation or self.base["relation"])
        alignment = copy.deepcopy(alignment or self.base["alignment"])
        output_dir = self.temporary_root / "projection"
        return projector.project_artifacts(
            relation,
            copy.deepcopy(self.base["oracle"]),
            copy.deepcopy(self.base["predicted"]),
            alignment,
            copy.deepcopy(self.base["lectures"]),
            matched_ko_path=str(output_dir / "matched_knowledge_objects.json"),
            original_ground_truth_sha256=original_ground_truth_sha256,
            oracle_inventory_sha256=self.base["oracle_hash"],
            predicted_inventory_sha256=self.base["predicted_hash"],
            relation_prompt_sha256="a" * 64,
            relation_schema_sha256="b" * 64,
        )

    def test_all_ten_manifest_cases_are_executable(self) -> None:
        self.assertEqual(len(self.manifest_cases), 10)
        base_bundle = self.project()
        pair_manifest = base_bundle["recoverable_pair_manifest.json"]
        ko_manifest = base_bundle["recoverable_ko_manifest.json"]
        oracle_input = base_bundle["oracle_normalized_input.json"]
        predicted_input = base_bundle["predicted_normalized_input.json"]

        for case in self.manifest_cases:
            case_id = case["case_id"]
            expected = case["expected"]
            with self.subTest(case_id=case_id):
                if case_id == "manifest_reused_wrong_type_endpoint":
                    slot = next(
                        item
                        for item in ko_manifest["slots"]
                        if item["oracle_ref"]["ko_id"] == "gradient"
                    )
                    self.assertEqual(slot["slot_id"], expected["slot_id"])
                    a_obj = next(
                        item
                        for item in oracle_input["model_input"]["knowledge_objects"]
                        if item["ko_id"] == slot["slot_id"]
                    )
                    b_obj = next(
                        item
                        for item in predicted_input["model_input"]["knowledge_objects"]
                        if item["ko_id"] == slot["slot_id"]
                    )
                    self.assertEqual(a_obj["type"], expected["A_prime_type"])
                    self.assertEqual(b_obj["type"], expected["B_prime_type"])
                    self.assertEqual(len(slot["referenced_by_pair_ids"]), 3)
                elif case_id == "manifest_repeated_endpoint_one_slot":
                    matching = [
                        item
                        for item in ko_manifest["slots"]
                        if item["oracle_ref"] == {
                            "lecture_id": "calculus_fixture_001",
                            "ko_id": "gradient",
                        }
                    ]
                    self.assertEqual(len(matching), 1)
                    self.assertEqual(
                        matching[0]["referenced_by_pair_ids"],
                        expected["referenced_by_pair_ids"],
                    )
                elif case_id == "manifest_pair_input_order_deterministic":
                    reversed_relation = copy.deepcopy(self.base["relation"])
                    reversed_relation["pairs"].reverse()
                    frozen_hash = "c" * 64
                    forward = self.project(original_ground_truth_sha256=frozen_hash)
                    reverse = self.project(
                        relation=reversed_relation,
                        original_ground_truth_sha256=frozen_hash,
                    )
                    self.assertEqual(
                        forward["recoverable_pair_manifest.json"],
                        reverse["recoverable_pair_manifest.json"],
                    )
                    self.assertEqual(
                        forward["recoverable_ko_manifest.json"],
                        reverse["recoverable_ko_manifest.json"],
                    )
                elif case_id == "manifest_unreferenced_prediction_excluded":
                    all_predicted_refs = {
                        (
                            slot["predicted_ref"]["lecture_id"],
                            slot["predicted_ref"]["ko_id"],
                        )
                        for slot in ko_manifest["slots"]
                    }
                    self.assertNotIn(
                        ("optimisation_fixture_001", "unmatched_learning_rate"),
                        all_predicted_refs,
                    )
                elif case_id == "manifest_stale_after_pair_change":
                    mutated = copy.deepcopy(base_bundle)
                    mutated["recoverable_ko_manifest.json"][
                        "pair_manifest_sha256"
                    ] = "7" * 64
                    with self.assertRaises(projector.ProjectionError) as raised:
                        projector.validate_projection_artifacts(
                            mutated,
                            original_pair_ids={
                                pair["pair_id"] for pair in self.base["relation"]["pairs"]
                            },
                            alignment_sha256=projector.artifact_sha256(
                                self.base["alignment"]
                            ),
                        )
                    self.assertEqual(
                        raised.exception.code, "stale_pair_manifest_reference"
                    )
                elif case_id == "manifest_full_recoverability":
                    self.assertEqual(len(pair_manifest["primary_pairs"]), 4)
                    self.assertEqual(pair_manifest["unrecoverable_primary_pairs"], [])
                elif case_id == "manifest_zero_recoverability":
                    missing_alignment = copy.deepcopy(self.base["alignment"])
                    mark_oracle_missing(
                        missing_alignment,
                        {
                            "calculus_fixture_001::gradient",
                            "calculus_fixture_001::gradient_descent",
                            "calculus_fixture_001::taylor_remainder",
                            "optimisation_fixture_001::optimisation_problem",
                        },
                    )
                    zero = self.project(alignment=missing_alignment)
                    self.assertEqual(
                        zero["recoverable_pair_manifest.json"]["primary_pairs"], []
                    )
                    self.assertEqual(zero["recoverable_ko_manifest.json"]["slots"], [])
                    self.assertEqual(
                        zero["batch_plan.json"]["executable_batch_count"], 0
                    )
                elif case_id == "manifest_partial_recoverability":
                    partial_alignment = copy.deepcopy(self.base["alignment"])
                    mark_oracle_missing(
                        partial_alignment,
                        {"optimisation_fixture_001::optimisation_problem"},
                    )
                    partial = self.project(alignment=partial_alignment)
                    ids = [
                        pair["pair_id"]
                        for pair in partial["recoverable_pair_manifest.json"][
                            "primary_pairs"
                        ]
                    ]
                    self.assertEqual(ids, case["input"]["recoverable_pair_ids"])
                elif case_id == "manifest_collapsed_endpoints":
                    first = {
                        "recoverable": True,
                        "identity_match": True,
                        "primary_structural_status": "one_to_one",
                        "matched_predicted_ref": {"lecture_id": "lecture_a", "ko_id": "same"},
                        "linked_predicted_refs": [],
                    }
                    second = copy.deepcopy(first)
                    self.assertEqual(
                        projector.pair_unrecoverable_reasons(first, second),
                        expected["unrecoverable_reasons"],
                    )
                elif case_id == "manifest_diagnostics_separate":
                    self.assertEqual(
                        [pair["pair_id"] for pair in pair_manifest["primary_pairs"]],
                        expected["primary_pair_ids"],
                    )
                    self.assertEqual(
                        [pair["pair_id"] for pair in pair_manifest["diagnostic_pairs"]],
                        expected["diagnostic_pair_ids"],
                    )

    def test_generated_matched_ground_truth_passes_strict_checker(self) -> None:
        artifacts = self.project()
        output_dir = self.temporary_root / "projection"
        projector.write_projection_bundle(
            output_dir,
            artifacts,
            alignment_bundle_complete_sha256="c" * 64,
            overwrite=False,
        )
        matched_gt = read_json(output_dir / "matched_relation_ground_truth.json")
        errors, summary = validate_ground_truth(matched_gt)
        self.assertEqual(errors, [])
        self.assertEqual(summary["pair_count"], 4)

    def test_zero_recoverability_ground_truth_passes_strict_checker(self) -> None:
        alignment = copy.deepcopy(self.base["alignment"])
        mark_oracle_missing(
            alignment,
            {
                "calculus_fixture_001::gradient",
                "calculus_fixture_001::gradient_descent",
                "calculus_fixture_001::taylor_remainder",
                "optimisation_fixture_001::optimisation_problem",
            },
        )
        artifacts = self.project(alignment=alignment)
        output_dir = self.temporary_root / "projection"
        projector.write_projection_bundle(
            output_dir,
            artifacts,
            alignment_bundle_complete_sha256="c" * 64,
            overwrite=False,
        )
        matched_gt = read_json(output_dir / "matched_relation_ground_truth.json")
        errors, summary = validate_ground_truth(matched_gt)
        self.assertEqual(errors, [])
        self.assertEqual(summary["pair_count"], 0)
        self.assertEqual(
            artifacts["oracle_normalized_input.json"]["batch_count"], 0
        )
        self.assertIsNone(artifacts["oracle_normalized_input.json"]["batch_id"])

    def test_noncontiguous_derived_pair_ids_pass_checker(self) -> None:
        alignment = copy.deepcopy(self.base["alignment"])
        mark_oracle_missing(
            alignment,
            {
                "calculus_fixture_001::gradient",
                "calculus_fixture_001::taylor_remainder",
            },
        )
        artifacts = self.project(alignment=alignment)
        output_dir = self.temporary_root / "projection"
        projector.write_projection_bundle(
            output_dir,
            artifacts,
            alignment_bundle_complete_sha256="c" * 64,
            overwrite=False,
        )
        matched_gt = read_json(output_dir / "matched_relation_ground_truth.json")
        self.assertEqual([pair["pair_id"] for pair in matched_gt["pairs"]], ["rel_dev_004"])
        errors, _ = validate_ground_truth(matched_gt)
        self.assertEqual(errors, [])

    def test_A_prime_and_B_prime_differ_only_in_ko_content(self) -> None:
        artifacts = self.project()
        a_model = artifacts["oracle_normalized_input.json"]["model_input"]
        b_model = artifacts["predicted_normalized_input.json"]["model_input"]
        self.assertEqual(a_model["relation_schema"], b_model["relation_schema"])
        self.assertEqual(a_model["lectures"], b_model["lectures"])
        self.assertEqual(a_model["candidate_pairs"], b_model["candidate_pairs"])
        for a_obj, b_obj in zip(
            a_model["knowledge_objects"], b_model["knowledge_objects"], strict=True
        ):
            self.assertEqual(
                (a_obj["lecture_id"], a_obj["ko_id"]),
                (b_obj["lecture_id"], b_obj["ko_id"]),
            )
            self.assertEqual(set(a_obj), set(b_obj))

    def test_raw_ids_do_not_appear_in_structural_endpoint_fields(self) -> None:
        artifacts = self.project()
        for filename in ["oracle_normalized_input.json", "predicted_normalized_input.json"]:
            model_input = artifacts[filename]["model_input"]
            for obj in model_input["knowledge_objects"]:
                self.assertRegex(obj["ko_id"], r"^ko_slot_[0-9]{3}$")
            for pair in model_input["candidate_pairs"]:
                self.assertRegex(pair["ko_a"]["ko_id"], r"^ko_slot_[0-9]{3}$")
                self.assertRegex(pair["ko_b"]["ko_id"], r"^ko_slot_[0-9]{3}$")

    def test_projection_bundle_no_overwrite_and_completion_marker(self) -> None:
        artifacts = self.project()
        output_dir = self.temporary_root / "projection"
        projector.write_projection_bundle(
            output_dir,
            artifacts,
            alignment_bundle_complete_sha256="c" * 64,
            overwrite=False,
        )
        marker = read_json(output_dir / "projection_bundle_complete.json")
        self.assertEqual(marker["evaluation_status"], "final")
        self.assertEqual(
            marker["upstream"]["alignment_bundle_complete_sha256"], "c" * 64
        )
        for filename in projector.MANAGED_FILENAMES:
            self.assertEqual(
                marker["artifacts"][filename],
                projector.sha256_bytes((output_dir / filename).read_bytes()),
            )
        with self.assertRaises(projector.ProjectionError) as raised:
            projector.write_projection_bundle(
                output_dir,
                artifacts,
                alignment_bundle_complete_sha256="c" * 64,
                overwrite=False,
            )
        self.assertEqual(raised.exception.code, "output_exists")

    def test_projection_cli_requires_and_consumes_final_alignment_bundle(self) -> None:
        input_dir = self.temporary_root / "inputs"
        alignment_dir = self.temporary_root / "alignment"
        output_dir = self.temporary_root / "projection"
        input_dir.mkdir()
        paths = {
            "relation": input_dir / "relation.json",
            "oracle": input_dir / "oracle.json",
            "predicted": input_dir / "predicted.json",
            "lectures": input_dir / "lectures.json",
        }
        values = {
            "relation": self.base["relation"],
            "oracle": self.base["oracle"],
            "predicted": self.base["predicted"],
            "lectures": self.base["lectures"],
        }
        for name, path in paths.items():
            path.write_text(projector.serialize_json(values[name]), encoding="utf-8")

        oracle_hash = projector.sha256_bytes(paths["oracle"].read_bytes())
        predicted_hash = projector.sha256_bytes(paths["predicted"].read_bytes())
        alignment_result = aligner.align_inventories(
            values["oracle"],
            values["predicted"],
            values["lectures"],
            oracle_inventory_sha256=oracle_hash,
            predicted_inventory_sha256=predicted_hash,
        )
        aligner.write_artifacts(alignment_dir, alignment_result, overwrite=False)

        return_code = projector.main([
            "--relation-ground-truth",
            str(paths["relation"]),
            "--oracle-inventory",
            str(paths["oracle"]),
            "--predicted-inventory",
            str(paths["predicted"]),
            "--alignment",
            str(alignment_dir / "alignment.json"),
            "--lectures",
            str(paths["lectures"]),
            "--output-dir",
            str(output_dir),
        ])
        self.assertEqual(return_code, 0)
        marker = read_json(output_dir / "projection_bundle_complete.json")
        self.assertEqual(set(marker["artifacts"]), set(projector.MANAGED_FILENAMES))

    def test_projection_bundle_is_byte_deterministic(self) -> None:
        first = self.project()
        second = self.project()
        self.assertEqual(first, second)
        self.assertEqual(
            {name: projector.artifact_sha256(value) for name, value in first.items()},
            {name: projector.artifact_sha256(value) for name, value in second.items()},
        )

    def test_matched_condition_integrity_mutations_are_rejected(self) -> None:
        original_pair_ids = {
            pair["pair_id"] for pair in self.base["relation"]["pairs"]
        }
        alignment_hash = projector.artifact_sha256(self.base["alignment"])
        mutations = [
            (
                "pair_set",
                "matched_pair_id_set_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"]["model_input"]["candidate_pairs"].pop(),
            ),
            (
                "pair_order",
                "matched_pair_order_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"]["model_input"]["candidate_pairs"].reverse(),
            ),
            (
                "ko_order",
                "matched_ko_order_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"]["model_input"]["knowledge_objects"].reverse(),
            ),
            (
                "prompt_hash",
                "matched_relation_prompt_hash_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"].__setitem__("relation_prompt_sha256", "1" * 64),
            ),
            (
                "schema_hash",
                "matched_relation_schema_hash_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"].__setitem__("relation_schema_sha256", "2" * 64),
            ),
            (
                "lecture_hash",
                "matched_lecture_hash_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"]["lecture_sha256"].__setitem__("calculus_fixture_001", "3" * 64),
            ),
            (
                "pair_incidence",
                "matched_pair_slot_incidence_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"]["model_input"]["candidate_pairs"][3]["ko_b"].__setitem__("ko_id", "ko_slot_003"),
            ),
            (
                "extra_ko",
                "matched_inventory_extra_ko",
                lambda bundle: bundle["predicted_normalized_input.json"]["model_input"]["knowledge_objects"].append({
                    "lecture_id": "optimisation_fixture_001",
                    "ko_id": "ko_slot_005",
                    "name": "Extra",
                    "type": "Concept",
                    "source_spans": ["extra"],
                }),
            ),
            (
                "missing_ko",
                "matched_inventory_missing_ko",
                lambda bundle: bundle["predicted_normalized_input.json"]["model_input"]["knowledge_objects"].pop(),
            ),
            (
                "normalization_version",
                "normalization_version_mismatch",
                lambda bundle: bundle["predicted_normalized_input.json"].__setitem__(
                    "structural_normalization_version",
                    "predicted_ko_structural_normalization_v0_2",
                ),
            ),
            (
                "matched_ground_truth_hash",
                "stale_matched_ground_truth",
                lambda bundle: bundle["predicted_normalized_input.json"].__setitem__(
                    "matched_ground_truth_sha256", "4" * 64
                ),
            ),
        ]
        for name, expected_code, mutate in mutations:
            with self.subTest(name=name):
                bundle = self.project()
                mutate(bundle)
                refresh_input_hashes(bundle["predicted_normalized_input.json"])
                with self.assertRaises(projector.ProjectionError) as raised:
                    projector.validate_projection_artifacts(
                        bundle,
                        original_pair_ids=original_pair_ids,
                        alignment_sha256=alignment_hash,
                    )
                self.assertEqual(raised.exception.code, expected_code)

    def test_gold_leakage_and_unknown_lecture_are_rejected(self) -> None:
        original_pair_ids = {
            pair["pair_id"] for pair in self.base["relation"]["pairs"]
        }
        alignment_hash = projector.artifact_sha256(self.base["alignment"])

        leakage = self.project()
        for filename in ["oracle_normalized_input.json", "predicted_normalized_input.json"]:
            artifact = leakage[filename]
            artifact["model_input"]["candidate_pairs"][0]["relation_type"] = "REQUIRES"
            refresh_input_hashes(artifact)
        with self.assertRaises(projector.ProjectionError) as raised:
            projector.validate_projection_artifacts(
                leakage,
                original_pair_ids=original_pair_ids,
                alignment_sha256=alignment_hash,
            )
        self.assertEqual(raised.exception.code, "gold_relation_leakage")

        unknown_lecture = self.project()
        for filename in ["oracle_normalized_input.json", "predicted_normalized_input.json"]:
            artifact = unknown_lecture[filename]
            artifact["model_input"]["lectures"].append({
                "lecture_id": "unknown_fixture_001",
                "text": "Unrelated lecture text.",
            })
            refresh_lecture_hashes(artifact)
            refresh_input_hashes(artifact)
        with self.assertRaises(projector.ProjectionError) as raised:
            projector.validate_projection_artifacts(
                unknown_lecture,
                original_pair_ids=original_pair_ids,
                alignment_sha256=alignment_hash,
            )
        self.assertEqual(raised.exception.code, "unknown_lecture_reference")

    def test_matched_ground_truth_and_diagnostics_mutations_are_rejected(self) -> None:
        original_pair_ids = {
            pair["pair_id"] for pair in self.base["relation"]["pairs"]
        }
        alignment_hash = projector.artifact_sha256(self.base["alignment"])
        mutations = [
            (
                "ground_truth_set",
                "matched_ground_truth_pair_set_mismatch",
                lambda bundle: bundle["matched_relation_ground_truth.json"]["pairs"].pop(),
            ),
            (
                "ground_truth_order",
                "matched_ground_truth_pair_order_mismatch",
                lambda bundle: bundle["matched_relation_ground_truth.json"]["pairs"].reverse(),
            ),
            (
                "diagnostics",
                "projection_diagnostics_mismatch",
                lambda bundle: bundle["projection_errors.json"]["diagnostic_pairs"].pop(),
            ),
        ]
        for name, expected_code, mutate in mutations:
            with self.subTest(name=name):
                bundle = self.project()
                mutate(bundle)
                with self.assertRaises(projector.ProjectionError) as raised:
                    projector.validate_projection_artifacts(
                        bundle,
                        original_pair_ids=original_pair_ids,
                        alignment_sha256=alignment_hash,
                    )
                self.assertEqual(raised.exception.code, expected_code)


if __name__ == "__main__":
    unittest.main()
