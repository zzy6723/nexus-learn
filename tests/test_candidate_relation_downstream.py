from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import evaluate_candidate_relation_pipeline as pipeline
from scripts import evaluate_relation_extraction as base_evaluator
from scripts import finalize_candidate_relation_evaluation as finalizer
from scripts import prepare_candidate_relation_diagnostic as preparer
from scripts import project_candidate_pairs_to_relations as projector
from scripts import run_candidate_relation_diagnostic as diagnostic_runner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmark" / "candidate_relation_downstream_diagnostic_v0_1.json"
CANDIDATE_GT_PATH = ROOT / "benchmark" / "ground_truth" / "candidate_pairs_development_v0_1.json"
UNIVERSE_PATH = ROOT / "benchmark" / "candidate_pairs" / "development_v0_1" / "pair_universe.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def projected_values():
    candidate_gt = load_json(CANDIDATE_GT_PATH)
    universe = load_json(UNIVERSE_PATH)
    relation_gt, mapping, _, _ = projector.build_relation_projection(
        candidate_gt=candidate_gt,
        universe=universe,
        ko_output_path=Path("fixture_knowledge_objects.json"),
        created="2026-07-17",
    )
    return candidate_gt, universe, relation_gt, mapping


def selected_relation_ids(condition: str, mapping: dict) -> list[str]:
    contract = load_json(CONTRACT_PATH)
    record = next(
        item for item in contract["candidate_conditions"] if item["condition"] == condition
    )
    selection = load_json(ROOT / record["selection"]["path"])
    relation_by_candidate = {
        item["candidate_pair_id"]: item["relation_pair_id"]
        for item in mapping["mappings"]
    }
    return [relation_by_candidate[item["pair_id"]] for item in selection["selected_pairs"]]


def perfect_match(pair: dict) -> dict:
    category = pair["category"]
    direction_eligible = category == "positive" and not pair["symmetric"]
    return {
        "pair_id": pair["pair_id"],
        "category": category,
        "primary_scored": category in {"positive", "hard_negative"},
        "gold_edge": {
            "source": copy.deepcopy(pair["source"]),
            "target": copy.deepcopy(pair["target"]),
            "relation_type": pair["relation_type"],
        },
        "accepted_alternatives": [],
        "predicted_edge": {
            "source": copy.deepcopy(pair["source"]),
            "target": copy.deepcopy(pair["target"]),
            "relation_type": pair["relation_type"],
        },
        "unordered_candidate_pair_correct": True,
        "relation_type_correct": True,
        "direction_eligible": direction_eligible,
        "direction_type_conditioned_eligible": direction_eligible,
        "direction_correct": True if direction_eligible else None,
        "strict_edge_correct": True,
        "acceptable_alternative_match": True,
        "rationale_present": True,
        "evidence": [],
        "evidence_support_status": (
            "auto_supported_by_gold_evidence" if category == "positive" else None
        ),
    }


def base_metrics(matches: list[dict]) -> dict:
    primary = [item for item in matches if item["primary_scored"]]
    positive = [item for item in matches if item["category"] == "positive"]
    negative = [item for item in matches if item["category"] == "hard_negative"]
    direction = [item for item in matches if item["direction_eligible"]]
    conditioned = [
        item
        for item in direction
        if item["direction_type_conditioned_eligible"]
    ]
    return {
        "evaluation_status": "final",
        "total_pairs": len(matches),
        "primary_scored_pairs": len(primary),
        "positive_pairs": len(positive),
        "hard_negative_pairs": len(negative),
        "schema_gap_pairs": sum(item["category"] == "schema_gap" for item in matches),
        "strict_edge_correct_count": sum(item["strict_edge_correct"] for item in primary),
        "relation_type_correct_count": sum(item["relation_type_correct"] for item in primary),
        "positive_relation_correct_count": sum(
            item["strict_edge_correct"] for item in positive
        ),
        "no_relation_correct_count": sum(item["strict_edge_correct"] for item in negative),
        "endpoint_direction_correct_count": sum(
            item["direction_correct"] is True for item in direction
        ),
        "endpoint_direction_scored_count": len(direction),
        "direction_when_type_correct_count": sum(
            item["direction_correct"] is True for item in conditioned
        ),
        "direction_when_type_correct_scored_count": len(conditioned),
        "exact_evidence_span_count": len(positive),
        "evidence_span_count": len(positive),
        "manual_adjudication_count": 0,
        "pending_adjudication_count": 0,
        "related_to_overuse_count": 0,
    }


def metadata(pair_count: int) -> dict:
    return {
        "usage": {
            "request_count": pair_count,
            "prompt_tokens": pair_count * 10,
            "completion_tokens": pair_count * 2,
            "total_tokens": pair_count * 12,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": pair_count * 10,
        },
        "latency_ms": pair_count * 5,
    }


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def perfect_predictions(selected_gt: dict) -> dict:
    return {
        "results": [
            {
                "pair_id": pair["pair_id"],
                "source": copy.deepcopy(pair["source"]),
                "target": copy.deepcopy(pair["target"]),
                "relation_type": pair["relation_type"],
                "evidence_spans": copy.deepcopy(pair["evidence_spans"]),
                "rationale": pair["rationale"],
            }
            for pair in selected_gt["pairs"]
        ]
    }


class CandidateRelationProjectionTests(unittest.TestCase):
    def test_real_projection_has_frozen_denominators_and_one_to_one_ids(self) -> None:
        _, _, relation_gt, mapping = projected_values()
        counts = {
            category: sum(item["category"] == category for item in relation_gt["pairs"])
            for category in ("positive", "hard_negative", "schema_gap")
        }

        self.assertEqual(counts, {"positive": 80, "hard_negative": 91, "schema_gap": 5})
        self.assertEqual(len(mapping["mappings"]), 176)
        self.assertEqual(
            mapping["mappings"][0]["candidate_pair_id"], "cand_dev_001"
        )
        self.assertEqual(
            mapping["mappings"][0]["relation_pair_id"], "rel_dev_001"
        )

    def test_multi_relation_positive_fails_closed(self) -> None:
        candidate_gt, universe, _, _ = projected_values()
        candidate_gt = copy.deepcopy(candidate_gt)
        positive = next(
            item
            for item in candidate_gt["annotations"]
            if item["candidate_label"] == "IN_SCHEMA_RELATION"
        )
        positive["gold_relations"].append(copy.deepcopy(positive["gold_relations"][0]))

        with self.assertRaisesRegex(projector.ProjectionError, "exactly one"):
            projector.build_relation_projection(
                candidate_gt=candidate_gt,
                universe=universe,
                ko_output_path=Path("fixture.json"),
                created="2026-07-17",
            )

    def test_endpoint_mismatch_fails_closed(self) -> None:
        candidate_gt, universe, _, _ = projected_values()
        candidate_gt = copy.deepcopy(candidate_gt)
        positive = next(
            item
            for item in candidate_gt["annotations"]
            if item["candidate_label"] == "IN_SCHEMA_RELATION"
        )
        positive["gold_relations"][0]["target"] = {
            "lecture_id": "unknown",
            "ko_id": "unknown",
        }

        with self.assertRaisesRegex(projector.ProjectionError, "changed endpoints"):
            projector.build_relation_projection(
                candidate_gt=candidate_gt,
                universe=universe,
                ko_output_path=Path("fixture.json"),
                created="2026-07-17",
            )


class CandidateRelationPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_real_preparation_is_gold_free_and_has_expected_counts(self) -> None:
        ko_path = self.root / "knowledge_objects.json"
        relation_path = self.root / "relations.json"
        mapping_path = self.root / "mapping.json"
        marker_path = self.root / "projection_complete.json"
        projector.build_projection_bundle(
            contract_path=CONTRACT_PATH,
            ko_output_path=ko_path,
            relation_output_path=relation_path,
            mapping_output_path=mapping_path,
            marker_output_path=marker_path,
        )
        expected = {
            "all_pairs": (176, 80),
            "rule_filtered_v0_1": (127, 70),
        }
        for condition, (pair_count, positive_count) in expected.items():
            output_dir = self.root / condition
            marker = preparer.prepare_condition(
                condition=condition,
                contract_path=CONTRACT_PATH,
                projection_marker_path=marker_path,
                output_dir=output_dir,
            )
            model_input = load_json(output_dir / "model_input.json")["model_input"]
            selected_gt = load_json(output_dir / "selected_relation_ground_truth.json")

            self.assertEqual(marker["counts"]["selected_pairs"], pair_count)
            self.assertEqual(marker["counts"]["request_batches"], pair_count)
            self.assertTrue(marker["gold_leakage_audit"]["passed"])
            self.assertEqual(
                sum(item["category"] == "positive" for item in selected_gt["pairs"]),
                positive_count,
            )
            serialized = json.dumps(model_input, sort_keys=True)
            for forbidden in diagnostic_runner.base_runner.FORBIDDEN_MODEL_INPUT_KEYS:
                self.assertNotIn(f'"{forbidden}"', serialized)


class CandidateRelationPipelineScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, _, relation_gt, mapping = projected_values()
        cls.pairs = relation_gt["pairs"]
        cls.mappings = mapping["mappings"]
        cls.pair_by_id = {item["pair_id"]: item for item in cls.pairs}

    def score_perfect(self, condition: str):
        ids = selected_relation_ids(
            condition,
            {"mappings": self.mappings},
        )
        matches = [perfect_match(self.pair_by_id[pair_id]) for pair_id in ids]
        return pipeline.score_condition(
            condition=condition,
            canonical_pairs=self.pairs,
            mappings=self.mappings,
            selected_relation_ids=ids,
            matches=matches,
            base_errors=[],
            base_metrics=base_metrics(matches),
            metadata=metadata(len(ids)),
        )

    def test_all_pairs_perfect_pipeline_scores_all_primary_pairs(self) -> None:
        metrics, outcomes, errors = self.score_perfect("all_pairs")

        self.assertEqual(metrics["candidate"]["selected_pair_count"], 176)
        self.assertEqual(metrics["pipeline"]["strict_accuracy"]["numerator"], 171)
        self.assertEqual(metrics["pipeline"]["positive_typed_edge_recall"]["numerator"], 80)
        self.assertEqual(metrics["pipeline"]["candidate_induced_false_negatives"], 0)
        self.assertEqual(len(outcomes), 176)
        self.assertEqual(errors, [])

    def test_rule_filter_misses_ten_positives_and_rejects_negatives_correctly(self) -> None:
        metrics, outcomes, errors = self.score_perfect("rule_filtered_v0_1")

        self.assertEqual(metrics["candidate"]["selected_pair_count"], 127)
        self.assertEqual(metrics["candidate"]["selected_positive_pairs"], 70)
        self.assertEqual(metrics["pipeline"]["candidate_induced_false_negatives"], 10)
        self.assertEqual(metrics["pipeline"]["positive_typed_edge_recall"]["numerator"], 70)
        self.assertEqual(metrics["pipeline"]["strict_accuracy"]["numerator"], 161)
        self.assertEqual(
            sum(item["candidate_outcome"] == "candidate_rejected_negative" for item in outcomes),
            91 - metrics["candidate"]["selected_hard_negative_pairs"],
        )
        self.assertEqual(
            sum(item["failure_locus"] == "candidate_induced_false_negative" for item in errors),
            10,
        )

    def test_schema_gaps_are_diagnostic_only(self) -> None:
        metrics, outcomes, _ = self.score_perfect("all_pairs")
        diagnostics = [item for item in outcomes if item["category"] == "schema_gap"]

        self.assertEqual(len(diagnostics), 5)
        self.assertTrue(all(item["pipeline_correct"] is None for item in diagnostics))
        self.assertTrue(
            all(item["failure_locus"] == "not_primary_scored" for item in diagnostics)
        )
        self.assertEqual(metrics["pipeline"]["strict_accuracy"]["denominator"], 171)

    def test_classifier_failure_loci_are_mutually_exclusive(self) -> None:
        ids = selected_relation_ids("all_pairs", {"mappings": self.mappings})
        matches = [perfect_match(self.pair_by_id[pair_id]) for pair_id in ids]
        positive = [item for item in matches if item["category"] == "positive"]
        negative = next(item for item in matches if item["category"] == "hard_negative")

        positive[0]["predicted_edge"]["relation_type"] = "NO_RELATION"
        positive[0]["relation_type_correct"] = False
        positive[0]["direction_type_conditioned_eligible"] = False
        positive[0]["direction_correct"] = None
        positive[0]["strict_edge_correct"] = False

        wrong_type = next(
            label
            for label in projector.GRAPH_RELATIONS
            if label != positive[1]["gold_edge"]["relation_type"]
        )
        positive[1]["predicted_edge"]["relation_type"] = wrong_type
        positive[1]["relation_type_correct"] = False
        positive[1]["direction_type_conditioned_eligible"] = False
        positive[1]["strict_edge_correct"] = False

        positive[2]["predicted_edge"]["source"], positive[2]["predicted_edge"]["target"] = (
            positive[2]["predicted_edge"]["target"],
            positive[2]["predicted_edge"]["source"],
        )
        positive[2]["direction_correct"] = False
        positive[2]["strict_edge_correct"] = False

        negative["predicted_edge"]["relation_type"] = "RELATED_TO"
        negative["relation_type_correct"] = False
        negative["strict_edge_correct"] = False

        metrics, _, errors = pipeline.score_condition(
            condition="all_pairs",
            canonical_pairs=self.pairs,
            mappings=self.mappings,
            selected_relation_ids=ids,
            matches=matches,
            base_errors=[],
            base_metrics=base_metrics(matches),
            metadata=metadata(len(ids)),
        )
        pipeline_metrics = metrics["pipeline"]
        self.assertEqual(pipeline_metrics["classifier_no_relation_false_negatives"], 1)
        self.assertEqual(pipeline_metrics["wrong_relation_type"], 1)
        self.assertEqual(pipeline_metrics["wrong_direction_when_type_correct"], 1)
        self.assertEqual(pipeline_metrics["false_positive_relations"], 1)
        self.assertEqual(len(errors), 4)

    def test_zero_selection_preserves_negative_rejections(self) -> None:
        metrics, outcomes, errors = pipeline.score_condition(
            condition="synthetic_zero",
            canonical_pairs=self.pairs,
            mappings=self.mappings,
            selected_relation_ids=[],
            matches=[],
            base_errors=[],
            base_metrics={
                **base_metrics([]),
                "schema_gap_pairs": 0,
            },
            metadata=metadata(0),
        )

        self.assertEqual(metrics["pipeline"]["candidate_induced_false_negatives"], 80)
        self.assertEqual(metrics["pipeline"]["strict_accuracy"]["numerator"], 91)
        self.assertEqual(
            sum(item["candidate_outcome"] == "candidate_rejected_negative" for item in outcomes),
            91,
        )
        self.assertEqual(len(errors), 80)

    def test_unknown_or_duplicate_match_set_fails(self) -> None:
        pair_id = self.pairs[0]["pair_id"]
        match = perfect_match(self.pairs[0])
        with self.assertRaisesRegex(pipeline.PipelineEvaluationError, "matches differ"):
            pipeline.score_condition(
                condition="synthetic",
                canonical_pairs=self.pairs,
                mappings=self.mappings,
                selected_relation_ids=[pair_id, pair_id],
                matches=[match, copy.deepcopy(match)],
                base_errors=[],
                base_metrics=base_metrics([match]),
                metadata=metadata(2),
            )

    def test_evidence_support_denominator_reconciles(self) -> None:
        matches = [
            {"evidence_support_status": "auto_supported_by_gold_evidence"},
            {"evidence_support_status": "supported"},
            {"evidence_support_status": "not_supported"},
            {"evidence_support_status": None},
        ]
        result = pipeline.conditional_relation_metrics_from(matches)

        self.assertEqual(result["numerator"], 2)
        self.assertEqual(result["denominator"], 3)
        self.assertEqual(result["value"], 2 / 3)


class CandidateRelationPipelineIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.commit = "a" * 40
        self.projection_paths = {
            "knowledge_objects": self.root / "projection" / "knowledge_objects.json",
            "relation_ground_truth": self.root / "projection" / "relations.json",
            "pair_mapping": self.root / "projection" / "mapping.json",
            "marker": self.root / "projection" / "projection_complete.json",
        }
        projector.build_projection_bundle(
            contract_path=CONTRACT_PATH,
            ko_output_path=self.projection_paths["knowledge_objects"],
            relation_output_path=self.projection_paths["relation_ground_truth"],
            mapping_output_path=self.projection_paths["pair_mapping"],
            marker_output_path=self.projection_paths["marker"],
        )
        self.preparation_dirs: dict[str, Path] = {}
        for condition in pipeline.CONDITIONS:
            directory = self.root / "preparation" / condition
            preparer.prepare_condition(
                condition=condition,
                contract_path=CONTRACT_PATH,
                projection_marker_path=self.projection_paths["marker"],
                output_dir=directory,
            )
            self.preparation_dirs[condition] = directory

    def materialize_run(
        self,
        condition: str,
        *,
        preceding_metadata_path: Path | None = None,
    ) -> tuple[Path, Path]:
        preparation_dir = self.preparation_dirs[condition]
        selected_gt_path = preparation_dir / "selected_relation_ground_truth.json"
        selected_gt = load_json(selected_gt_path)
        model_artifact_path = preparation_dir / "model_input.json"
        model_artifact = load_json(model_artifact_path)
        batch_plan_path = preparation_dir / "batch_plan.json"
        source_manifest = load_json(preparation_dir / "source_manifest.json")
        pair_count = len(selected_gt["pairs"])
        run_dir = self.root / "formal" / condition / "run_01"
        predictions_path = run_dir / "output" / "selected_relation_ground_truth.json"
        metadata_path = run_dir / "metadata" / "selected_relation_ground_truth.json"
        execution_plan_path = run_dir / "execution_batch_plan.json"
        predictions = perfect_predictions(selected_gt)
        write_json(predictions_path, predictions)
        write_json(execution_plan_path, load_json(batch_plan_path))
        request_parameters = {
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 8192,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }
        aggregate_metadata = {
            "provider": "deepseek",
            "experiment": "002_prompt_refinement",
            "run_id": "run_01",
            "split": "development",
            "model_requested": "deepseek-v4-flash",
            "model_returned": "deepseek-v4-flash",
            "finish_reason": "stop",
            "request_partitioning": "one_candidate_pair_per_request_v0_1",
            "request_parameters": request_parameters,
            "latency_ms": pair_count * 5,
            "git_commit_at_start": self.commit,
            "git_dirty_at_start": False,
            "run_status": "completed",
            "request_success": True,
            "json_parse_success": True,
            "prediction_schema_valid": True,
            "prediction_sha256": projector.sha256_file(predictions_path),
            "input_artifact_sha256": projector.sha256_file(model_artifact_path),
            "batch_plan_sha256": projector.sha256_file(batch_plan_path),
            "condition": condition,
            "batch_count": pair_count,
            "completed_batch_count": pair_count,
            "batch_results": [
                {
                    "batch_id": f"candidate_{index:03d}",
                    "pair_id": pair["pair_id"],
                }
                for index, pair in enumerate(selected_gt["pairs"], start=1)
            ],
            "usage": metadata(pair_count)["usage"],
            "hashes": {
                "prompt_sha256": load_json(CONTRACT_PATH)["relation_method"]["prompt"]["sha256"],
                "relation_schema_sha256": load_json(CONTRACT_PATH)["relation_method"]["schema"]["sha256"],
                "knowledge_object_ground_truth_sha256": source_manifest[
                    "knowledge_object_ground_truth_hashes"
                ],
                "lecture_sha256": model_artifact["lecture_sha256"],
            },
            "preceding_all_pairs_metadata": (
                projector.binding(preceding_metadata_path)
                if preceding_metadata_path is not None
                else None
            ),
        }
        write_json(metadata_path, aggregate_metadata)
        run_marker = {
            "artifact_type": "candidate_relation_diagnostic_run_complete",
            "version": "v0.1",
            "status": "completed",
            "condition": condition,
            "run_id": "run_01",
            "method_commit": self.commit,
            "contract": projector.binding(CONTRACT_PATH),
            "preparation": projector.binding(preparation_dir / "preparation_complete.json"),
            "implementation": projector.binding(Path(diagnostic_runner.__file__).resolve()),
            "base_runner_dependency": load_json(CONTRACT_PATH)["relation_method"][
                "base_runner_dependency"
            ],
            "artifacts": {
                "execution_batch_plan": projector.binding(execution_plan_path),
                "aggregate_metadata": projector.binding(metadata_path),
                "predictions": projector.binding(predictions_path),
            },
            "counts": {
                "candidate_pairs": pair_count,
                "request_batches": pair_count,
                "completed_batches": pair_count,
            },
            "repository": {
                "git_commit_at_start": self.commit,
                "git_dirty_at_start": False,
            },
        }
        write_json(run_dir / diagnostic_runner.RUN_MARKER_NAME, run_marker)

        evaluation_dir = run_dir / "evaluation"
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(base_evaluator.__file__).resolve()),
                "--ground-truth",
                str(selected_gt_path),
                "--predictions",
                str(predictions_path),
                "--evaluation-dir",
                str(evaluation_dir),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(load_json(evaluation_dir / "metrics.json")["evaluation_status"], "final")
        bundle_dir = run_dir / "relation_evaluation"
        finalizer.finalize_evaluation(
            condition=condition,
            contract_path=CONTRACT_PATH,
            prepared_dir=preparation_dir,
            run_dir=run_dir,
            evaluation_dir=evaluation_dir,
            adjudication_path=None,
            output_dir=bundle_dir,
        )
        return bundle_dir, metadata_path

    def test_perfect_full_pipeline_reconciles_all_denominators(self) -> None:
        all_bundle, all_metadata = self.materialize_run("all_pairs")
        filtered_bundle, _ = self.materialize_run(
            "rule_filtered_v0_1", preceding_metadata_path=all_metadata
        )
        output_dir = self.root / "pipeline_evaluation"
        completion = pipeline.evaluate_pipeline(
            contract_path=CONTRACT_PATH,
            projection_marker_path=self.projection_paths["marker"],
            bundle_dirs={
                "all_pairs": all_bundle,
                "rule_filtered_v0_1": filtered_bundle,
            },
            output_dir=output_dir,
        )
        metrics = load_json(output_dir / "pipeline_metrics.json")
        transitions = load_json(output_dir / "pair_transitions.json")

        self.assertEqual(completion["evaluation_status"], "final")
        self.assertEqual(metrics["conditions"]["all_pairs"]["pipeline"]["strict_accuracy"]["numerator"], 171)
        self.assertEqual(metrics["conditions"]["rule_filtered_v0_1"]["pipeline"]["strict_accuracy"]["numerator"], 161)
        self.assertEqual(metrics["comparison"]["missed_positive_pairs"], 10)
        self.assertEqual(
            metrics["comparison"]["missed_positives_all_pairs_strict_correct"], 10
        )
        self.assertEqual(transitions["pair_count"], 176)
        self.assertEqual(completion["integrity"]["pending_adjudications"], 0)


class CandidateRelationIntegrityTests(unittest.TestCase):
    def test_repository_state_validation_is_fail_closed_without_invoking_git(self) -> None:
        commit = "a" * 40
        diagnostic_runner.validate_repository_state(
            expected_commit=commit,
            current_commit=commit,
            dirty=False,
        )
        with self.assertRaisesRegex(
            diagnostic_runner.DiagnosticRunError, "clean working tree"
        ):
            diagnostic_runner.validate_repository_state(
                expected_commit=commit,
                current_commit=commit,
                dirty=True,
            )

    def test_stale_snapshot_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in pipeline.finalizer.COPIED_FILENAMES:
                (root / name).write_text("{}\n", encoding="utf-8")
            snapshot = {
                "artifacts": {
                    name: projector.sha256_file(root / name)
                    for name in pipeline.finalizer.COPIED_FILENAMES
                }
            }
            (root / "metrics.json").write_text('{"changed": true}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                pipeline.PipelineEvaluationError, "stale artifact"
            ):
                pipeline.validate_snapshot_artifacts(root, snapshot)


if __name__ == "__main__":
    unittest.main()
