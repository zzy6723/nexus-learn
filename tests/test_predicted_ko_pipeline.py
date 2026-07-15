from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import align_predicted_kos as aligner
from scripts import evaluate_predicted_ko_relation_pipeline as pipeline
from scripts import project_recoverable_relation_pairs as projector
from tests.predicted_ko_fixture_support import (
    FIXTURES,
    materialize_runtime_bundle,
    read_json,
    sha256_file,
    update_json,
)
from tests.test_predicted_ko_projection import build_base_context, mark_oracle_missing


SCORING_CASES = FIXTURES / "scoring_cases.json"


def clone_bundle(bundle: pipeline.EvaluationBundle) -> pipeline.EvaluationBundle:
    return copy.deepcopy(bundle)


class PredictedKORelationPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)
        self.bundle, _ = materialize_runtime_bundle(self.temporary_root)

    def cli_args(self, output_dir: Path, *, overwrite: bool = False) -> list[str]:
        args = [
            "--original-ground-truth",
            str(FIXTURES / "shared" / "synthetic_original_ground_truth.json"),
            "--alignment",
            str(self.bundle / "alignment.json"),
            "--projection-dir",
            str(self.bundle),
            "--a0-evaluation-dir",
            str(self.bundle / "A0_evaluation"),
            "--a-prime-evaluation-dir",
            str(self.bundle / "A_prime_evaluation"),
            "--b-prime-evaluation-dir",
            str(self.bundle / "B_prime_evaluation"),
            "--output-dir",
            str(output_dir),
        ]
        if overwrite:
            args.append("--overwrite")
        return args

    def load_evaluation(
        self,
        condition: str,
        expected: set[str],
        extras: set[str] | None = None,
    ) -> pipeline.EvaluationBundle:
        return pipeline.load_evaluation_bundle(
            self.bundle / f"{condition}_evaluation",
            condition=condition,
            expected_pair_ids=expected,
            allowed_extra_pair_ids=extras,
        )

    def canonical_compute_inputs(self) -> dict[str, Any]:
        original = read_json(
            FIXTURES / "shared" / "synthetic_original_ground_truth.json"
        )
        primary, diagnostic = pipeline.primary_pair_maps(original)
        return {
            "original": original,
            "primary": primary,
            "alignment": read_json(self.bundle / "alignment.json"),
            "pair_manifest": read_json(
                self.bundle / "recoverable_pair_manifest.json"
            ),
            "ko_manifest": read_json(self.bundle / "recoverable_ko_manifest.json"),
            "projection_errors": read_json(self.bundle / "projection_errors.json"),
            "a_input": read_json(self.bundle / "oracle_normalized_input.json"),
            "b_input": read_json(self.bundle / "predicted_normalized_input.json"),
            "a0": self.load_evaluation("A0", set(primary), set(diagnostic)),
            "a": self.load_evaluation("A_prime", set(primary)),
            "b": self.load_evaluation("B_prime", set(primary)),
        }

    def test_canonical_runtime_bundle_produces_final_outputs(self) -> None:
        output_dir = self.temporary_root / "pipeline"

        return_code = pipeline.main(self.cli_args(output_dir))

        self.assertEqual(return_code, 0)
        metrics = read_json(output_dir / "pipeline_metrics.json")
        transitions = read_json(output_dir / "pair_transitions.json")["transitions"]
        marker = read_json(output_dir / "pipeline_evaluation_complete.json")
        self.assertEqual(metrics["pipeline_metrics"]["strict_success"], {
            "numerator": 3,
            "denominator": 4,
            "value": 0.75,
        })
        self.assertEqual(metrics["pair_recoverability"]["overall"]["value"], 1.0)
        self.assertEqual(metrics["denominators"]["diagnostic_pairs"], 2)
        self.assertEqual(len(transitions), 4)
        rel_003 = next(item for item in transitions if item["pair_id"] == "rel_dev_003")
        self.assertEqual(rel_003["primary_failure_locus"], "B_prime_relation_type_error")
        self.assertIn("ko_type_mismatch", rel_003["secondary_quality_flags"])
        self.assertEqual(marker["evaluation_status"], "final")
        for filename, digest in marker["artifacts"].items():
            self.assertEqual(digest, sha256_file(output_dir / filename))

    def scoring_inputs(self, case: dict[str, Any]) -> dict[str, Any]:
        values = self.canonical_compute_inputs()
        primary_ids = sorted(values["primary"])
        case_input = case["input"]
        if "unrecoverable_pair_ids" in case_input:
            recoverable_ids = set(primary_ids) - set(case_input["unrecoverable_pair_ids"])
        elif "recoverable_pair_ids" in case_input:
            recoverable_ids = set(case_input["recoverable_pair_ids"])
        elif "recoverable_pair_count" in case_input:
            recoverable_ids = set(primary_ids[: case_input["recoverable_pair_count"]])
        else:
            recoverable_ids = set(primary_ids)

        base_pairs = {
            item["pair_id"]: item for item in values["pair_manifest"]["primary_pairs"]
        }
        values["pair_manifest"]["primary_pairs"] = [
            base_pairs[pair_id] for pair_id in primary_ids if pair_id in recoverable_ids
        ]
        reasons = case_input.get("unrecoverable_reasons", {})
        values["pair_manifest"]["unrecoverable_primary_pairs"] = [
            {
                "pair_id": pair_id,
                "category": values["primary"][pair_id]["category"],
                "pair_status": "unrecoverable",
                "unrecoverable_reasons": reasons.get(pair_id, ["missing_endpoint"]),
            }
            for pair_id in primary_ids
            if pair_id not in recoverable_ids
        ]
        values["projection_errors"]["unrecoverable_primary_pairs"] = copy.deepcopy(
            values["pair_manifest"]["unrecoverable_primary_pairs"]
        )
        if case_input.get("invalid_source_span_count"):
            quality_flags = values["projection_errors"][
                "recoverable_slot_quality_flags"
            ]
            if quality_flags:
                quality_flags[0]["flags"] = sorted(
                    set(quality_flags[0]["flags"])
                    | {"predicted_source_span_invalid"}
                )

        values["a"].matches = [
            item for item in values["a"].matches if item["pair_id"] in recoverable_ids
        ]
        values["a"].errors = []
        values["b"].matches = [
            item for item in values["b"].matches if item["pair_id"] in recoverable_ids
        ]
        requested_correct = case_input.get(
            "B_prime_strict_correct", len(recoverable_ids)
        )
        values["b"].errors = []
        for index, match in enumerate(values["b"].matches):
            should_be_correct = index < requested_correct
            match["strict_edge_correct"] = should_be_correct
            match["relation_type_correct"] = should_be_correct
            match["direction_correct"] = True
            if not should_be_correct:
                match["predicted_edge"]["relation_type"] = "RELATED_TO"
                values["b"].errors.append({
                    "pair_id": match["pair_id"],
                    "error_type": "wrong_relation_type",
                })
        if not recoverable_ids:
            pair_hash = pipeline.artifact_sha256(values["pair_manifest"])
            ko_hash = pipeline.artifact_sha256(values["ko_manifest"])
            values["a"] = pipeline.noop_bundle(
                "A_prime",
                pipeline.make_noop_evaluation(
                    "A_prime",
                    pair_manifest_sha256=pair_hash,
                    ko_manifest_sha256=ko_hash,
                ),
            )
            values["b"] = pipeline.noop_bundle(
                "B_prime",
                pipeline.make_noop_evaluation(
                    "B_prime",
                    pair_manifest_sha256=pair_hash,
                    ko_manifest_sha256=ko_hash,
                ),
            )
        return values

    def test_all_eight_scoring_cases_are_executable(self) -> None:
        cases = read_json(SCORING_CASES)["cases"]
        self.assertEqual(len(cases), 8)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                values = self.scoring_inputs(case)
                outputs = pipeline.build_pipeline_outputs(
                    original_ground_truth=values["original"],
                    alignment=values["alignment"],
                    pair_manifest=values["pair_manifest"],
                    ko_manifest=values["ko_manifest"],
                    projection_errors=values["projection_errors"],
                    a_input=values["a_input"],
                    b_input=values["b_input"],
                    a0_bundle=values["a0"],
                    a_bundle=values["a"],
                    b_bundle=values["b"],
                    provenance={},
                )
                metrics = outputs["pipeline_metrics.json"]
                expected = case["expected"]
                self.assertEqual(metrics["evaluation_status"], "final")
                if "pair_recoverability" in expected:
                    self.assertEqual(
                        metrics["pair_recoverability"]["overall"],
                        expected["pair_recoverability"],
                    )
                if "positive_pair_recoverability" in expected:
                    self.assertEqual(
                        metrics["pair_recoverability"]["positive"],
                        expected["positive_pair_recoverability"],
                    )
                if "hard_negative_pair_recoverability" in expected:
                    self.assertEqual(
                        metrics["pair_recoverability"]["hard_negative"],
                        expected["hard_negative_pair_recoverability"],
                    )
                if "conditional_B_prime_strict" in expected:
                    self.assertEqual(
                        metrics["conditional_B_prime"]["strict_edge_accuracy"],
                        expected["conditional_B_prime_strict"],
                    )
                if "conditional_A_prime_strict" in expected:
                    self.assertEqual(
                        metrics["conditional_A_prime"]["strict_edge_accuracy"],
                        expected["conditional_A_prime_strict"],
                    )
                if "conditional_B_prime_no_relation_accuracy" in expected:
                    self.assertEqual(
                        metrics["conditional_B_prime"]["no_relation_accuracy"],
                        expected["conditional_B_prime_no_relation_accuracy"],
                    )
                if "pipeline_strict_success" in expected:
                    self.assertEqual(
                        metrics["pipeline_metrics"]["strict_success"],
                        expected["pipeline_strict_success"],
                    )
                if "pipeline_hard_negative_strict_success" in expected:
                    self.assertEqual(
                        metrics["pipeline_metrics"]["hard_negative_strict_success"],
                        expected["pipeline_hard_negative_strict_success"],
                    )
                if "primary_pair_denominator" in expected:
                    self.assertEqual(
                        metrics["denominators"]["all_primary_pairs"],
                        expected["primary_pair_denominator"],
                    )
                    self.assertEqual(
                        metrics["denominators"]["diagnostic_pairs"],
                        expected["diagnostic_pairs_excluded"],
                    )
                if "primary_failure_locus" in expected:
                    transitions = outputs["pair_transitions.json"]["transitions"]
                    by_id = {item["pair_id"]: item for item in transitions}
                    for pair_id, locus in expected["primary_failure_locus"].items():
                        self.assertEqual(by_id[pair_id]["primary_failure_locus"], locus)
                if "A_prime_execution_status" in expected:
                    self.assertEqual(
                        metrics["conditional_A_prime"]["execution_status"],
                        expected["A_prime_execution_status"],
                    )
                    self.assertEqual(
                        metrics["conditional_B_prime"]["execution_status"],
                        expected["B_prime_execution_status"],
                    )
                if "nonfatal_error_codes" in expected:
                    actual_codes = {
                        item["error_code"]
                        for item in outputs["pipeline_errors.json"]["nonfatal_errors"]
                    }
                    self.assertTrue(set(expected["nonfatal_error_codes"]) <= actual_codes)

    def mutate_snapshot_dependency(
        self,
        condition: str,
        dependency: str,
        update: Any,
    ) -> None:
        evaluation_dir = self.bundle / f"{condition}_evaluation"
        path = evaluation_dir / f"{dependency}.json"
        update_json(path, update)
        snapshot_field = {
            "metrics": "metrics_sha256",
            "matches": "matches_sha256",
            "errors": "errors_sha256",
            "run_metadata": "run_metadata_sha256",
        }[dependency]
        update_json(
            evaluation_dir / "evaluation_snapshot.json",
            lambda value: value.__setitem__(snapshot_field, sha256_file(path)),
        )

    def assert_invalid(self, output_dir: Path, expected_code: str) -> None:
        errors = read_json(output_dir / "pipeline_errors.json")
        marker = read_json(output_dir / "pipeline_evaluation_complete.json")
        self.assertEqual(errors["evaluation_status"], "invalid")
        self.assertEqual(errors["fatal_errors"][0]["error_code"], expected_code)
        self.assertEqual(marker["evaluation_status"], "invalid")
        self.assertFalse((output_dir / "pipeline_metrics.json").exists())
        self.assertFalse((output_dir / "pair_transitions.json").exists())

    def test_matched_metadata_integrity_failures(self) -> None:
        cases = [
            (
                "model",
                "matched_model_mismatch",
                lambda value: value.__setitem__("model_requested", "different-model"),
            ),
            (
                "provider",
                "matched_provider_mismatch",
                lambda value: value.__setitem__("provider", "different-provider"),
            ),
            (
                "dirty",
                "formal_run_started_dirty",
                lambda value: value.__setitem__("git_dirty_at_start", True),
            ),
            (
                "parameters",
                "matched_request_parameter_mismatch",
                lambda value: value["request_parameters"].__setitem__(
                    "temperature", 0.2
                ),
            ),
            (
                "commit",
                "matched_git_commit_mismatch",
                lambda value: value.__setitem__(
                    "git_commit_at_start",
                    "fedcba9876543210fedcba9876543210fedcba98",
                ),
            ),
            (
                "input_hash",
                "run_metadata_input_hash_mismatch",
                lambda value: value.__setitem__("input_artifact_sha256", "5" * 64),
            ),
            (
                "batch_hash",
                "matched_batching_mismatch",
                lambda value: value.__setitem__("batch_plan_sha256", "6" * 64),
            ),
        ]
        for name, expected_code, mutate in cases:
            with self.subTest(name=name):
                case_root = self.temporary_root / name
                bundle, _ = materialize_runtime_bundle(case_root)
                original_bundle = self.bundle
                self.bundle = bundle
                self.mutate_snapshot_dependency("B_prime", "run_metadata", mutate)
                output_dir = case_root / "pipeline"
                self.assertEqual(pipeline.main(self.cli_args(output_dir)), 1)
                self.assert_invalid(output_dir, expected_code)
                self.bundle = original_bundle

    def test_evaluation_integrity_failures(self) -> None:
        cases = [
            (
                "stale_prediction",
                "evaluation_prediction_hash_mismatch",
                lambda bundle: update_json(
                    bundle / "B_prime_evaluation" / "predictions.json",
                    lambda value: value["results"][0].__setitem__("rationale", "changed"),
                ),
            ),
            (
                "duplicate_outcome",
                "duplicate_pair_outcome",
                lambda bundle: self._duplicate_match(bundle),
            ),
            (
                "nonfinal",
                "base_relation_evaluation_not_final",
                lambda bundle: self._make_metrics_nonfinal(bundle),
            ),
            (
                "invalid_evaluation",
                "base_relation_evaluation_invalid",
                lambda bundle: self._make_metrics_invalid(bundle),
            ),
            (
                "stale_projection_marker",
                "stale_completion_marker",
                lambda bundle: update_json(
                    bundle / "recoverable_pair_manifest.json",
                    lambda value: value.__setitem__("original_primary_pair_count", 999),
                ),
            ),
        ]
        for name, expected_code, mutate in cases:
            with self.subTest(name=name):
                case_root = self.temporary_root / name
                bundle, _ = materialize_runtime_bundle(case_root)
                original_bundle = self.bundle
                self.bundle = bundle
                mutate(bundle)
                output_dir = case_root / "pipeline"
                self.assertEqual(pipeline.main(self.cli_args(output_dir)), 1)
                self.assert_invalid(output_dir, expected_code)
                self.bundle = original_bundle

    def _duplicate_match(self, bundle: Path) -> None:
        path = bundle / "B_prime_evaluation" / "matches.json"
        update_json(path, lambda value: value.append(copy.deepcopy(value[0])))
        update_json(
            bundle / "B_prime_evaluation" / "evaluation_snapshot.json",
            lambda value: value.__setitem__("matches_sha256", sha256_file(path)),
        )

    def _make_metrics_nonfinal(self, bundle: Path) -> None:
        path = bundle / "B_prime_evaluation" / "metrics.json"
        update_json(
            path,
            lambda value: value.__setitem__(
                "evaluation_status", "draft_pending_adjudication"
            ),
        )
        update_json(
            bundle / "B_prime_evaluation" / "evaluation_snapshot.json",
            lambda value: value.__setitem__("metrics_sha256", sha256_file(path)),
        )

    def _make_metrics_invalid(self, bundle: Path) -> None:
        path = bundle / "B_prime_evaluation" / "metrics.json"
        update_json(
            path,
            lambda value: value.__setitem__("evaluation_status", "invalid"),
        )
        snapshot_path = bundle / "B_prime_evaluation" / "evaluation_snapshot.json"
        update_json(
            snapshot_path,
            lambda value: value.update({
                "evaluation_status": "invalid",
                "metrics_sha256": sha256_file(path),
            }),
        )

    def test_no_overwrite_and_invalid_overwrite_remove_stale_aggregates(self) -> None:
        output_dir = self.temporary_root / "pipeline"
        self.assertEqual(pipeline.main(self.cli_args(output_dir)), 0)
        self.assertEqual(pipeline.main(self.cli_args(output_dir)), 2)
        update_json(
            self.bundle / "B_prime_evaluation" / "predictions.json",
            lambda value: value["results"][0].__setitem__("rationale", "changed"),
        )

        self.assertEqual(pipeline.main(self.cli_args(output_dir, overwrite=True)), 1)

        self.assert_invalid(output_dir, "evaluation_prediction_hash_mismatch")

    def test_zero_recoverability_cli_writes_final_noop_evaluations(self) -> None:
        context = build_base_context()
        alignment = copy.deepcopy(context["alignment"])
        mark_oracle_missing(
            alignment,
            {
                "calculus_fixture_001::gradient",
                "calculus_fixture_001::gradient_descent",
                "calculus_fixture_001::taylor_remainder",
                "optimisation_fixture_001::optimisation_problem",
            },
        )
        alignment_dir = self.temporary_root / "zero_alignment"
        pending = {
            "artifact_type": "predicted_ko_alignment_pending",
            "version": "v0.1",
            "alignment_snapshot_sha256": projector.artifact_sha256(alignment),
            "name_matching_normalization_version": (
                alignment["name_matching_normalization_version"]
            ),
            "items": [],
        }
        aligner.write_artifacts(
            alignment_dir,
            {"alignment": alignment, "pending": pending, "resolved": None},
            overwrite=False,
        )
        projection_dir = self.temporary_root / "zero_projection"
        artifacts = projector.project_artifacts(
            context["relation"],
            context["oracle"],
            context["predicted"],
            alignment,
            context["lectures"],
            matched_ko_path=str(projection_dir / "matched_knowledge_objects.json"),
            original_ground_truth_sha256=sha256_file(
                FIXTURES / "shared" / "synthetic_original_ground_truth.json"
            ),
            oracle_inventory_sha256=context["oracle_hash"],
            predicted_inventory_sha256=context["predicted_hash"],
            alignment_sha256=sha256_file(alignment_dir / "alignment.json"),
            relation_prompt_sha256="a" * 64,
            relation_schema_sha256="b" * 64,
        )
        projector.write_projection_bundle(
            projection_dir,
            artifacts,
            alignment_bundle_complete_sha256=sha256_file(
                alignment_dir / "alignment_bundle_complete.json"
            ),
            overwrite=False,
        )
        output_dir = self.temporary_root / "zero_pipeline"
        args = [
            "--original-ground-truth",
            str(FIXTURES / "shared" / "synthetic_original_ground_truth.json"),
            "--alignment",
            str(alignment_dir / "alignment.json"),
            "--projection-dir",
            str(projection_dir),
            "--a0-evaluation-dir",
            str(self.bundle / "A0_evaluation"),
            "--output-dir",
            str(output_dir),
        ]

        self.assertEqual(pipeline.main(args), 0)

        metrics = read_json(output_dir / "pipeline_metrics.json")
        self.assertEqual(
            metrics["conditional_A_prime"]["strict_edge_accuracy"],
            {"numerator": 0, "denominator": 0, "value": None},
        )
        self.assertEqual(
            metrics["pipeline_metrics"]["strict_success"],
            {"numerator": 0, "denominator": 4, "value": 0.0},
        )
        for filename in [
            "A_prime_noop_evaluation.json",
            "B_prime_noop_evaluation.json",
        ]:
            noop = read_json(output_dir / filename)
            self.assertEqual(
                noop["execution_status"], "not_run_no_recoverable_pairs"
            )

    def test_noop_evaluation_is_invalid_when_pairs_are_recoverable(self) -> None:
        evaluation_dir = self.temporary_root / "invalid_noop"
        evaluation_dir.mkdir()
        noop = pipeline.make_noop_evaluation(
            "B_prime",
            pair_manifest_sha256="a" * 64,
            ko_manifest_sha256="b" * 64,
        )
        (evaluation_dir / "empty_matched_relation_evaluation.json").write_text(
            pipeline.serialize_json(noop), encoding="utf-8"
        )

        with self.assertRaises(pipeline.PipelineError) as raised:
            pipeline.load_evaluation_bundle(
                evaluation_dir,
                condition="B_prime",
                expected_pair_ids={"rel_dev_001"},
            )

        self.assertEqual(raised.exception.code, "invalid_noop_evaluation")

    def test_failure_locus_precedence_is_descriptive_and_mutually_exclusive(self) -> None:
        values = self.canonical_compute_inputs()
        a_matches = pipeline.evaluation_match_map(values["a"])
        b_matches = pipeline.evaluation_match_map(values["b"])

        for match in [a_matches["rel_dev_001"], b_matches["rel_dev_001"]]:
            match["strict_edge_correct"] = False
            match["relation_type_correct"] = False
            match["predicted_edge"]["relation_type"] = "RELATED_TO"

        b_matches["rel_dev_002"]["strict_edge_correct"] = False
        b_matches["rel_dev_002"]["relation_type_correct"] = False
        b_matches["rel_dev_002"]["predicted_edge"]["relation_type"] = "RELATED_TO"

        b_matches["rel_dev_003"]["strict_edge_correct"] = False
        b_matches["rel_dev_003"]["relation_type_correct"] = False
        b_matches["rel_dev_003"]["predicted_edge"]["relation_type"] = "NO_RELATION"

        b_matches["rel_dev_004"]["strict_edge_correct"] = False
        b_matches["rel_dev_004"]["relation_type_correct"] = True
        b_matches["rel_dev_004"]["direction_correct"] = False

        outputs = pipeline.build_pipeline_outputs(
            original_ground_truth=values["original"],
            alignment=values["alignment"],
            pair_manifest=values["pair_manifest"],
            ko_manifest=values["ko_manifest"],
            projection_errors=values["projection_errors"],
            a_input=values["a_input"],
            b_input=values["b_input"],
            a0_bundle=values["a0"],
            a_bundle=values["a"],
            b_bundle=values["b"],
            provenance={},
        )
        transitions = {
            item["pair_id"]: item
            for item in outputs["pair_transitions.json"]["transitions"]
        }
        self.assertEqual(
            transitions["rel_dev_001"]["primary_failure_locus"],
            "pre_existing_A_prime_strict_error",
        )
        self.assertEqual(
            transitions["rel_dev_002"]["primary_failure_locus"],
            "B_prime_relation_false_positive",
        )
        self.assertEqual(
            transitions["rel_dev_003"]["primary_failure_locus"],
            "B_prime_relation_false_negative",
        )
        self.assertEqual(
            transitions["rel_dev_004"]["primary_failure_locus"],
            "B_prime_relation_direction_error",
        )

    def test_grounding_failure_does_not_change_strict_pipeline_success(self) -> None:
        values = self.canonical_compute_inputs()
        b_matches = pipeline.evaluation_match_map(values["b"])
        b_matches["rel_dev_001"]["evidence_support_status"] = "not_supported"
        values["b"].errors.append({
            "pair_id": "rel_dev_001",
            "error_type": "evidence_does_not_support_relation",
        })

        outputs = pipeline.build_pipeline_outputs(
            original_ground_truth=values["original"],
            alignment=values["alignment"],
            pair_manifest=values["pair_manifest"],
            ko_manifest=values["ko_manifest"],
            projection_errors=values["projection_errors"],
            a_input=values["a_input"],
            b_input=values["b_input"],
            a0_bundle=values["a0"],
            a_bundle=values["a"],
            b_bundle=values["b"],
            provenance={},
        )
        transitions = {
            item["pair_id"]: item
            for item in outputs["pair_transitions.json"]["transitions"]
        }
        self.assertEqual(
            outputs["pipeline_metrics.json"]["pipeline_metrics"]["strict_success"],
            {"numerator": 3, "denominator": 4, "value": 0.75},
        )
        self.assertEqual(
            transitions["rel_dev_001"]["primary_failure_locus"], "none"
        )
        self.assertIn(
            "relation_grounding_unsupported",
            transitions["rel_dev_001"]["secondary_quality_flags"],
        )


if __name__ == "__main__":
    unittest.main()
