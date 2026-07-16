from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_candidate_pair_ground_truth import (
    build_completion_marker as build_ground_truth_completion_marker,
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
from scripts.evaluate_candidate_pair_generation import score_candidate_selection
from scripts.generate_candidate_pair_universe import serialize_json
from scripts.generate_candidate_pairs import (
    build_all_pairs_selection,
    write_generation_bundle,
)
from tests.test_candidate_pair_generator import (
    FIXTURE_DIR as GROUND_TRUTH_FIXTURE_DIR,
    OUTPUT_SCHEMA_PATH,
    load_json,
    make_universe_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "scripts" / "evaluate_candidate_pair_generation.py"
SCORING_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "candidate_pair_generation"
    / "selection_scenarios.json"
)
ANNOTATIONS_PATH = GROUND_TRUTH_FIXTURE_DIR / "valid_annotations.json"


def write_json(path: Path, value) -> None:
    path.write_text(serialize_json(value), encoding="utf-8")


def build_scoring_values(*, include_ambiguous: bool = False):
    fixture = load_json(SCORING_FIXTURE)
    items = copy.deepcopy(fixture["pairs"])
    if include_ambiguous:
        items.append(copy.deepcopy(fixture["final_ambiguous_pair"]))
    universe_pairs = [
        {
            "pair_id": item["pair_id"],
            "lecture_id": item["lecture_id"],
            "ko_a": item["ko_a"],
            "ko_b": item["ko_b"],
        }
        for item in items
    ]
    universe = {
        "artifact_type": "candidate_pair_universe",
        "version": "v0.1",
        "benchmark_split": "development",
        "scope": "lecture_local_unordered_nonself",
        "pairs": universe_pairs,
    }
    annotations = []
    for item in items:
        relations = [
            {"relation_type": relation_type}
            for relation_type in item["gold_relation_types"]
        ]
        annotations.append(
            {
                "pair_id": item["pair_id"],
                "candidate_label": item["candidate_label"],
                "gold_relations": relations,
            }
        )
    ground_truth = {
        "allowed_relation_types": [
            "REQUIRES",
            "APPLIED_IN",
            "EXTENDS",
            "CONTRASTS_WITH",
            "FORMALIZES",
            "RELATED_TO",
        ],
        "annotations": annotations,
    }
    return fixture, universe, ground_truth


def make_selection(universe: dict, selected_ids: list[str]) -> dict:
    pair_by_id = {item["pair_id"]: item for item in universe["pairs"]}
    return {
        "generator": {"name": "rule_filtered"},
        "selected_pairs": [
            {
                **copy.deepcopy(pair_by_id[pair_id]),
                "candidate_reasons": ["fixture"],
            }
            for pair_id in selected_ids
        ],
    }


def make_strict_bundle(root: Path) -> dict[str, Path]:
    universe, universe_path, universe_marker_path = make_universe_bundle(root)
    ground_truth_path = root / "ground_truth.json"
    ground_truth_marker_path = root / "ground_truth_complete.json"
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
    errors, summary = validate_candidate_pair_ground_truth(
        universe_path,
        ground_truth_path,
        allow_draft=False,
    )
    if errors:
        raise AssertionError(errors)
    ground_truth_marker = build_ground_truth_completion_marker(
        pair_universe_path=universe_path,
        ground_truth_path=ground_truth_path,
        ground_truth=ground_truth,
        summary=summary,
    )
    write_json(ground_truth_marker_path, ground_truth_marker)

    candidate_dir = root / "candidate_run"
    selection = build_all_pairs_selection(
        universe,
        pair_universe_path=universe_path,
    )
    selection_path, metadata_path, candidate_marker_path = write_generation_bundle(
        output_dir=candidate_dir,
        selection=selection,
        pair_universe=universe,
        pair_universe_path=universe_path,
        pair_universe_marker_path=universe_marker_path,
        output_schema_path=OUTPUT_SCHEMA_PATH,
    )
    return {
        "pair_universe": universe_path,
        "pair_universe_marker": universe_marker_path,
        "ground_truth": ground_truth_path,
        "ground_truth_marker": ground_truth_marker_path,
        "candidate_selection": selection_path,
        "candidate_metadata": metadata_path,
        "candidate_marker": candidate_marker_path,
    }


def evaluator_command(paths: dict[str, Path], evaluation_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(EVALUATOR),
        "--pair-universe",
        str(paths["pair_universe"]),
        "--pair-universe-completion-marker",
        str(paths["pair_universe_marker"]),
        "--ground-truth",
        str(paths["ground_truth"]),
        "--ground-truth-completion-marker",
        str(paths["ground_truth_marker"]),
        "--candidate-selection",
        str(paths["candidate_selection"]),
        "--candidate-metadata",
        str(paths["candidate_metadata"]),
        "--candidate-completion-marker",
        str(paths["candidate_marker"]),
        "--evaluation-dir",
        str(evaluation_dir),
    ]


class CandidatePairGenerationScoringTests(unittest.TestCase):
    def score(self, scenario: str, *, include_ambiguous: bool = False):
        fixture, universe, ground_truth = build_scoring_values(
            include_ambiguous=include_ambiguous
        )
        ids = fixture["selection_scenarios"][scenario]
        if include_ambiguous and scenario == "all_pairs":
            ids = ids + [fixture["final_ambiguous_pair"]["pair_id"]]
        return score_candidate_selection(
            pair_universe=universe,
            ground_truth=ground_truth,
            selection=make_selection(universe, ids),
        )

    def test_denominator_guard_all_pairs(self) -> None:
        result = self.score("all_pairs")
        counts = result["metrics"]["counts"]
        metrics = result["metrics"]["metrics"]
        diagnostics = result["metrics"]["diagnostics"]

        self.assertEqual(counts["positive_pairs"], 2)
        self.assertEqual(counts["negative_pairs"], 2)
        self.assertEqual(counts["diagnostic_pairs"], 1)
        self.assertEqual(metrics["candidate_recall"], 1.0)
        self.assertEqual(metrics["candidate_precision"], 0.5)
        self.assertEqual(metrics["retention_rate_primary"], 1.0)
        self.assertEqual(metrics["workload_retained_total"], 1.0)
        self.assertEqual(
            diagnostics["OUT_OF_SCHEMA_RELATION"]["selection_rate"], 1.0
        )

    def test_positive_negative_partial_and_empty_selections(self) -> None:
        positives = self.score("positives_only")["metrics"]
        self.assertEqual(positives["metrics"]["candidate_recall"], 1.0)
        self.assertEqual(positives["metrics"]["candidate_precision"], 1.0)
        self.assertEqual(positives["metrics"]["workload_retained_total"], 0.4)

        negatives = self.score("negatives_only")["metrics"]
        self.assertEqual(negatives["metrics"]["candidate_recall"], 0.0)
        self.assertEqual(negatives["metrics"]["candidate_precision"], 0.0)

        partial = self.score("partial_recall")["metrics"]
        self.assertEqual(partial["metrics"]["candidate_recall"], 0.5)
        self.assertEqual(partial["counts"]["missed_positive_pairs"], 1)

        empty = self.score("zero_selected")["metrics"]
        self.assertEqual(empty["metrics"]["candidate_recall"], 0.0)
        self.assertIsNone(empty["metrics"]["candidate_precision"])
        self.assertIsNone(empty["metrics"]["actionable_yield_total"])

    def test_diagnostics_do_not_enter_primary_precision(self) -> None:
        result = self.score("diagnostic_only")["metrics"]
        self.assertIsNone(result["metrics"]["candidate_precision"])
        self.assertEqual(result["counts"]["retrieved_primary_pairs"], 0)
        self.assertEqual(result["counts"]["retrieved_diagnostic_pairs"], 1)

        with_ambiguous = self.score("all_pairs", include_ambiguous=True)["metrics"]
        self.assertEqual(with_ambiguous["counts"]["primary_pairs"], 4)
        self.assertEqual(with_ambiguous["counts"]["diagnostic_pairs"], 2)
        self.assertEqual(with_ambiguous["metrics"]["candidate_precision"], 0.5)
        self.assertEqual(
            with_ambiguous["diagnostics"]["AMBIGUOUS"]["selected"], 1
        )

    def test_relation_pair_and_instance_coverage_are_separate(self) -> None:
        result = self.score("positives_only")
        relations = {
            item["relation_type"]: item
            for item in result["per_relation_metrics"]["relations"]
        }
        self.assertEqual(relations["FORMALIZES"]["positive_pair_support"], 1)
        self.assertEqual(relations["FORMALIZES"]["relation_instance_support"], 1)
        self.assertEqual(relations["RELATED_TO"]["candidate_recall"], 1.0)
        self.assertIsNone(relations["APPLIED_IN"]["candidate_recall"])

    def test_zero_positive_and_zero_negative_denominators(self) -> None:
        fixture, universe, ground_truth = build_scoring_values()
        all_ids = fixture["selection_scenarios"]["all_pairs"]
        zero_positive = copy.deepcopy(ground_truth)
        for annotation in zero_positive["annotations"]:
            if annotation["candidate_label"] == "IN_SCHEMA_RELATION":
                annotation["candidate_label"] = "NO_IN_SCHEMA_RELATION"
                annotation["gold_relations"] = []
        result = score_candidate_selection(
            pair_universe=universe,
            ground_truth=zero_positive,
            selection=make_selection(universe, all_ids),
        )["metrics"]
        self.assertIsNone(result["metrics"]["candidate_recall"])
        self.assertEqual(result["metrics"]["candidate_precision"], 0.0)

        zero_negative = copy.deepcopy(ground_truth)
        for annotation in zero_negative["annotations"]:
            if annotation["candidate_label"] == "NO_IN_SCHEMA_RELATION":
                annotation["candidate_label"] = "IN_SCHEMA_RELATION"
                annotation["gold_relations"] = [{"relation_type": "RELATED_TO"}]
        result = score_candidate_selection(
            pair_universe=universe,
            ground_truth=zero_negative,
            selection=make_selection(universe, all_ids),
        )["metrics"]
        self.assertEqual(result["counts"]["negative_pairs"], 0)
        self.assertEqual(result["metrics"]["candidate_precision"], 1.0)


class CandidatePairGenerationEvaluatorIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.paths = make_strict_bundle(self.root)

    def run_evaluator(self, evaluation_name: str):
        evaluation_dir = self.root / evaluation_name
        completed = subprocess.run(
            evaluator_command(self.paths, evaluation_dir),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed, evaluation_dir

    def test_strict_all_pairs_bundle_produces_final_complete_artifacts(self) -> None:
        completed, evaluation_dir = self.run_evaluator("evaluation")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        expected_files = {
            "metrics.json",
            "matches.json",
            "errors.json",
            "per_relation_metrics.json",
            "per_lecture_metrics.json",
            "evaluation_complete.json",
        }
        self.assertEqual(
            {path.name for path in evaluation_dir.iterdir()}, expected_files
        )
        metrics = load_json(evaluation_dir / "metrics.json")
        matches = load_json(evaluation_dir / "matches.json")
        completion = load_json(evaluation_dir / "evaluation_complete.json")
        self.assertEqual(metrics["evaluation_status"], "final")
        self.assertEqual(metrics["gate_assessment"]["outcome"], "not_applicable_control")
        self.assertEqual(len(matches), 6)
        self.assertEqual(completion["evaluation_status"], "final")

    def test_stale_ground_truth_marker_is_invalid_without_formal_metrics(self) -> None:
        marker = load_json(self.paths["ground_truth_marker"])
        marker["counts"]["primary_denominator"] += 1
        write_json(self.paths["ground_truth_marker"], marker)
        completed, evaluation_dir = self.run_evaluator("stale_ground_truth")

        self.assertEqual(completed.returncode, 1)
        self.assertFalse((evaluation_dir / "metrics.json").exists())
        self.assertFalse((evaluation_dir / "matches.json").exists())
        completion = load_json(evaluation_dir / "evaluation_complete.json")
        self.assertEqual(completion["evaluation_status"], "invalid")
        errors = load_json(evaluation_dir / "errors.json")
        self.assertTrue(
            any("denominator reconciliation" in item["message"] for item in errors)
        )

    def test_stale_generator_marker_is_invalid(self) -> None:
        marker = load_json(self.paths["candidate_marker"])
        marker["artifacts"]["candidate_selection"]["sha256"] = "0" * 64
        write_json(self.paths["candidate_marker"], marker)
        completed, evaluation_dir = self.run_evaluator("stale_generator")

        self.assertEqual(completed.returncode, 1)
        completion = load_json(evaluation_dir / "evaluation_complete.json")
        self.assertEqual(completion["evaluation_status"], "invalid")
        self.assertFalse((evaluation_dir / "metrics.json").exists())

    def test_duplicate_selection_is_invalid(self) -> None:
        selection = load_json(self.paths["candidate_selection"])
        selection["selected_pairs"][1] = copy.deepcopy(selection["selected_pairs"][0])
        write_json(self.paths["candidate_selection"], selection)
        completed, evaluation_dir = self.run_evaluator("duplicate_selection")

        self.assertEqual(completed.returncode, 1)
        errors = load_json(evaluation_dir / "errors.json")
        self.assertTrue(
            any("duplicate selected pair" in item["message"] for item in errors)
        )


if __name__ == "__main__":
    unittest.main()
