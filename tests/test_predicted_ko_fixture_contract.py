from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import project_recoverable_relation_pairs as projector
from scripts.check_relation_ground_truth import validate_ground_truth
from tests.predicted_ko_fixture_support import (
    FIXTURES,
    materialize_runtime_bundle,
    read_json,
    sha256_file,
)


class PredictedKOFixtureContractTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def test_every_matrix_case_has_a_unique_predeclared_expectation(self) -> None:
        matrix_names = [
            "normalization_cases.json",
            "alignment_cases.json",
            "manifest_cases.json",
            "scoring_cases.json",
            "integrity_cases.json",
        ]
        all_case_ids: list[str] = []
        for matrix_name in matrix_names:
            matrix = read_json(FIXTURES / matrix_name)
            cases = matrix["cases"]
            self.assertGreater(len(cases), 0, matrix_name)
            case_ids = [case["case_id"] for case in cases]
            self.assertEqual(len(case_ids), len(set(case_ids)), matrix_name)
            self.assertTrue(all("expected" in case for case in cases), matrix_name)
            all_case_ids.extend(case_ids)
        self.assertEqual(len(all_case_ids), len(set(all_case_ids)))

    def test_canonical_template_contains_lower_level_inputs(self) -> None:
        bundle = FIXTURES / "valid_bundle"
        for filename in [
            "batch_plan.json",
            "projection_errors.json",
            "alignment_bundle_complete.json",
            "projection_bundle_complete.json",
            "pipeline_evaluation_complete.json",
        ]:
            self.assertTrue((bundle / filename).is_file())
        for condition in ["A0", "A_prime", "B_prime"]:
            evaluation_dir = bundle / f"{condition}_evaluation"
            for filename in [
                "predictions.json",
                "metrics.json",
                "matches.json",
                "errors.json",
                "run_metadata.json",
                "evaluation_snapshot.json",
            ]:
                self.assertTrue((evaluation_dir / filename).is_file())

    def test_runtime_bundle_replaces_symbolic_dependency_hashes(self) -> None:
        bundle, provenance = materialize_runtime_bundle(self.temporary_root)

        pair_manifest = read_json(bundle / "recoverable_pair_manifest.json")
        ko_manifest = read_json(bundle / "recoverable_ko_manifest.json")
        matched_kos = read_json(bundle / "matched_knowledge_objects.json")
        matched_ground_truth = read_json(bundle / "matched_relation_ground_truth.json")

        self.assertEqual(
            pair_manifest["alignment_sha256"],
            sha256_file(bundle / "alignment.json"),
        )
        self.assertEqual(
            ko_manifest["pair_manifest_sha256"],
            sha256_file(bundle / "recoverable_pair_manifest.json"),
        )
        self.assertEqual(
            matched_kos["derivation"]["ko_manifest_sha256"],
            sha256_file(bundle / "recoverable_ko_manifest.json"),
        )
        self.assertEqual(
            matched_ground_truth["derivation"][
                "matched_knowledge_objects_sha256"
            ],
            sha256_file(bundle / "matched_knowledge_objects.json"),
        )
        ground_truth_errors, _ = validate_ground_truth(matched_ground_truth)
        self.assertEqual(ground_truth_errors, [])
        self.assertEqual(
            provenance["A_prime_evaluation_sha256"],
            sha256_file(bundle / "A_prime_evaluation" / "evaluation_snapshot.json"),
        )
        self.assertEqual(
            provenance["B_prime_evaluation_sha256"],
            sha256_file(bundle / "B_prime_evaluation" / "evaluation_snapshot.json"),
        )
        for filename in [
            "pipeline_metrics.json",
            "pipeline_errors.json",
            "pair_transitions.json",
        ]:
            self.assertEqual(read_json(bundle / filename)["provenance"], provenance)

        for marker_name in [
            "alignment_bundle_complete.json",
            "projection_bundle_complete.json",
        ]:
            marker = read_json(bundle / marker_name)
            self.assertEqual(marker["evaluation_status"], "final")
            for filename, digest in marker["artifacts"].items():
                self.assertEqual(digest, sha256_file(bundle / filename))
        projection_marker = read_json(bundle / "projection_bundle_complete.json")
        self.assertEqual(
            projection_marker["upstream"][
                "alignment_bundle_complete_sha256"
            ],
            sha256_file(bundle / "alignment_bundle_complete.json"),
        )
        pipeline_marker = read_json(bundle / "pipeline_evaluation_complete.json")
        self.assertEqual(pipeline_marker["evaluation_status"], "final")
        self.assertEqual(
            pipeline_marker["upstream"]["projection_bundle_complete_sha256"],
            sha256_file(bundle / "projection_bundle_complete.json"),
        )
        for filename, digest in pipeline_marker["artifacts"].items():
            self.assertEqual(digest, sha256_file(bundle / filename))

        artifacts = {
            filename: read_json(bundle / filename)
            for filename in projector.MANAGED_FILENAMES
        }
        original_ground_truth = read_json(
            FIXTURES / "shared" / "synthetic_original_ground_truth.json"
        )
        projector.validate_projection_artifacts(
            artifacts,
            original_pair_ids={
                pair["pair_id"] for pair in original_ground_truth["pairs"]
            },
            alignment_sha256=sha256_file(bundle / "alignment.json"),
        )

    def test_matched_run_metadata_freezes_execution_conditions(self) -> None:
        bundle, _ = materialize_runtime_bundle(self.temporary_root)
        a_metadata = read_json(bundle / "A_prime_evaluation" / "run_metadata.json")
        b_metadata = read_json(bundle / "B_prime_evaluation" / "run_metadata.json")

        for field in ["provider", "model_requested", "request_parameters"]:
            self.assertEqual(a_metadata[field], b_metadata[field])
        self.assertEqual(
            a_metadata["git_commit_at_start"], b_metadata["git_commit_at_start"]
        )
        self.assertFalse(a_metadata["git_dirty_at_start"])
        self.assertFalse(b_metadata["git_dirty_at_start"])
        self.assertNotEqual(
            a_metadata["input_artifact_sha256"],
            b_metadata["input_artifact_sha256"],
        )
        self.assertEqual(
            a_metadata["batch_plan_sha256"], b_metadata["batch_plan_sha256"]
        )

    def test_golden_pipeline_math_is_independent_of_pipeline_code(self) -> None:
        bundle = FIXTURES / "valid_bundle"
        b_matches = read_json(bundle / "B_prime_evaluation" / "matches.json")
        primary_matches = [item for item in b_matches if item["primary_scored"]]
        strict_correct = sum(item["strict_edge_correct"] for item in primary_matches)
        original_ground_truth = read_json(
            FIXTURES / "shared" / "synthetic_original_ground_truth.json"
        )
        primary_categories = set(
            original_ground_truth["primary_scoring_categories"]
        )
        primary_denominator = sum(
            pair["category"] in primary_categories
            for pair in original_ground_truth["pairs"]
        )
        golden = read_json(bundle / "pipeline_metrics.json")

        self.assertEqual((strict_correct, primary_denominator), (3, 4))
        self.assertEqual(
            golden["pipeline_metrics"]["strict_success"],
            {"numerator": 3, "denominator": 4, "value": 0.75},
        )

    def test_fixture_tree_has_no_macos_metadata(self) -> None:
        metadata_files = [
            path
            for path in FIXTURES.rglob("*")
            if path.name == ".DS_Store" or path.name.startswith("._")
        ]
        self.assertEqual(metadata_files, [])


if __name__ == "__main__":
    unittest.main()
