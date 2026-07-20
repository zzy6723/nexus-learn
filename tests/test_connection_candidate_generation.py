from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_connection_candidates import (
    DEFAULT_GROUND_TRUTH,
    DEFAULT_SUCCESS_CRITERIA,
    score_selection,
    validate_frozen_evaluation_inputs,
)
from scripts.generate_connection_candidates import (
    DEFAULT_FREEZE_MANIFEST,
    DEFAULT_INVENTORY,
    DEFAULT_PAIR_UNIVERSE,
    DEFAULT_SOURCE_MANIFEST,
    CandidateGenerationError,
    build_selection,
    binding,
    load_json,
    validate_freeze_manifest,
    validate_inputs,
    validate_selection,
    write_bundle,
)


EXECUTION_COMMIT = "11f7696ba829e9f3c51eb2fcac04757fdcdfd2a3"
ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_connection_candidates.py"
EVALUATOR = ROOT / "scripts" / "evaluate_connection_candidates.py"


class ConnectionCandidateGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.universe = load_json(DEFAULT_PAIR_UNIVERSE)
        cls.inventory = load_json(DEFAULT_INVENTORY)
        cls.source_manifest = load_json(DEFAULT_SOURCE_MANIFEST)
        cls.freeze_manifest = load_json(DEFAULT_FREEZE_MANIFEST)
        cls.ground_truth = load_json(DEFAULT_GROUND_TRUTH)
        cls.success_criteria = load_json(DEFAULT_SUCCESS_CRITERIA)
        cls.inputs = {
            "pair_universe": binding(DEFAULT_PAIR_UNIVERSE),
            "canonical_inventory": binding(DEFAULT_INVENTORY),
            "source_manifest": binding(DEFAULT_SOURCE_MANIFEST),
        }

    def selection(self, method: str, retention_fraction: float = 0.8):
        return build_selection(
            method=method,
            pair_universe=self.universe,
            inventory=self.inventory,
            retention_fraction=retention_fraction,
            inputs=self.inputs,
        )

    def test_frozen_inputs_are_current_and_gold_free(self) -> None:
        validate_freeze_manifest(
            self.freeze_manifest,
            manifest_path=DEFAULT_FREEZE_MANIFEST,
            pair_universe_path=DEFAULT_PAIR_UNIVERSE,
            inventory_path=DEFAULT_INVENTORY,
            source_manifest_path=DEFAULT_SOURCE_MANIFEST,
        )
        validate_inputs(self.universe, self.inventory, self.source_manifest)

    def test_all_pairs_is_exact_control(self) -> None:
        selection = self.selection("all_pairs")
        self.assertEqual(selection["selected_pair_count"], 387)
        self.assertEqual(validate_selection(selection, self.universe), [])
        result = score_selection(
            pair_universe=self.universe,
            ground_truth=self.ground_truth,
            selection=selection,
            success_criteria=self.success_criteria,
        )
        self.assertEqual(
            result["metrics"]["metrics"]["primary_positive_candidate_recall"], 1.0
        )
        self.assertEqual(
            result["metrics"]["gate_assessment"]["outcome"],
            "not_applicable_control",
        )

    def test_overlap_bridge_exposes_frozen_scope_shortcut(self) -> None:
        selection = self.selection("overlap_bridge")
        self.assertEqual(selection["selected_pair_count"], 125)
        result = score_selection(
            pair_universe=self.universe,
            ground_truth=self.ground_truth,
            selection=selection,
            success_criteria=self.success_criteria,
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["metrics"]["primary_positive_candidate_recall"], 1.0)
        self.assertEqual(metrics["gate_assessment"]["outcome"], "passed")
        strata = {
            item["stratum"]: item for item in result["stratum_metrics"]["strata"]
        }
        self.assertEqual(
            strata["diagnostic_compositional_positive"][
                "diagnostic_positive_candidate_recall"
            ],
            0.0,
        )

    def test_lexical_only_is_deterministic_and_reduces_workload(self) -> None:
        first = self.selection("lexical_only")
        second = self.selection("lexical_only")
        self.assertEqual(first, second)
        self.assertEqual(first["selected_pair_count"], 309)
        self.assertEqual(validate_selection(first, self.universe), [])
        result = score_selection(
            pair_universe=self.universe,
            ground_truth=self.ground_truth,
            selection=first,
            success_criteria=self.success_criteria,
        )
        self.assertGreaterEqual(
            result["metrics"]["metrics"]["workload_reduction_total"], 0.20
        )
        self.assertEqual(
            result["metrics"]["counts"]["missed_primary_positive_pairs"], 1
        )
        self.assertEqual(result["metrics"]["gate_assessment"]["outcome"], "passed")

    def test_hybrid_separates_provenance_from_lexical_contribution(self) -> None:
        selection = self.selection("hybrid_provenance_lexical")
        result = score_selection(
            pair_universe=self.universe,
            ground_truth=self.ground_truth,
            selection=selection,
            success_criteria=self.success_criteria,
        )
        self.assertEqual(
            result["metrics"]["metrics"]["primary_positive_candidate_recall"],
            1.0,
        )
        strata = {
            item["stratum"]: item for item in result["stratum_metrics"]["strata"]
        }
        self.assertEqual(
            strata["diagnostic_compositional_positive"][
                "diagnostic_positive_candidate_recall"
            ],
            0.6,
        )

    def test_alignment_changes_are_rejected(self) -> None:
        selection = self.selection("overlap_bridge")
        invalid = copy.deepcopy(selection)
        invalid["selected_pairs"][0]["ko_a"] = invalid["selected_pairs"][1]["ko_a"]
        self.assertTrue(
            any("changed ko_a" in error for error in validate_selection(invalid, self.universe))
        )

        leaked = copy.deepcopy(selection)
        leaked["selected_pairs"][0]["category"] = "IN_SCHEMA_CONNECTION"
        self.assertTrue(
            any("field set mismatch" in error for error in validate_selection(leaked, self.universe))
        )

    def test_evaluator_inputs_are_bound_to_freeze_manifest(self) -> None:
        self.assertEqual(
            validate_frozen_evaluation_inputs(
                freeze_manifest=self.freeze_manifest,
                pair_universe_path=DEFAULT_PAIR_UNIVERSE,
                ground_truth_path=DEFAULT_GROUND_TRUTH,
                success_criteria_path=DEFAULT_SUCCESS_CRITERIA,
            ),
            [],
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied_truth = Path(temporary) / "ground_truth.json"
            copied_truth.write_bytes(DEFAULT_GROUND_TRUTH.read_bytes())
            errors = validate_frozen_evaluation_inputs(
                freeze_manifest=self.freeze_manifest,
                pair_universe_path=DEFAULT_PAIR_UNIVERSE,
                ground_truth_path=copied_truth,
                success_criteria_path=DEFAULT_SUCCESS_CRITERIA,
            )
            self.assertIn("frozen ground_truth binding mismatch", errors)

    def test_gold_field_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.universe)
        invalid["pairs"][0]["category"] = "IN_SCHEMA_CONNECTION"
        with self.assertRaises(CandidateGenerationError):
            validate_inputs(invalid, self.inventory, self.source_manifest)

    def test_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "run"
            selection = self.selection("overlap_bridge")
            input_paths = {
                "pair_universe": DEFAULT_PAIR_UNIVERSE,
                "canonical_inventory": DEFAULT_INVENTORY,
                "source_manifest": DEFAULT_SOURCE_MANIFEST,
            }
            write_bundle(
                output_dir=output_dir,
                selection=selection,
                execution_commit=EXECUTION_COMMIT,
                freeze_manifest_path=DEFAULT_FREEZE_MANIFEST,
                input_paths=input_paths,
            )
            with self.assertRaises(CandidateGenerationError):
                write_bundle(
                    output_dir=output_dir,
                    selection=selection,
                    execution_commit=EXECUTION_COMMIT,
                    freeze_manifest_path=DEFAULT_FREEZE_MANIFEST,
                    input_paths=input_paths,
                )

    def test_cli_round_trip_and_evaluator_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate_dir = root / "candidate"
            evaluation_dir = root / "evaluation"
            generated = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--method",
                    "hybrid_provenance_lexical",
                    "--execution-commit",
                    EXECUTION_COMMIT,
                    "--output-dir",
                    str(candidate_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            evaluated = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATOR),
                    "--candidate-dir",
                    str(candidate_dir),
                    "--evaluation-dir",
                    str(evaluation_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(evaluated.returncode, 0, evaluated.stdout + evaluated.stderr)
            metrics = json.loads((evaluation_dir / "metrics.json").read_text())
            self.assertEqual(metrics["evaluation_status"], "final")
            self.assertEqual(metrics["gate_assessment"]["outcome"], "passed")

            repeated = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATOR),
                    "--candidate-dir",
                    str(candidate_dir),
                    "--evaluation-dir",
                    str(evaluation_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(repeated.returncode, 1)
            self.assertIn("Refusing to overwrite", repeated.stdout)

    def test_invalid_bundle_writes_only_fatal_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate_dir = root / "candidate"
            evaluation_dir = root / "evaluation"
            generated = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--method",
                    "overlap_bridge",
                    "--execution-commit",
                    EXECUTION_COMMIT,
                    "--output-dir",
                    str(candidate_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            selection_path = candidate_dir / "candidate_selection.json"
            selection = json.loads(selection_path.read_text())
            selection["selected_pairs"][0]["ko_a"] = selection["selected_pairs"][1]["ko_a"]
            selection_path.write_text(json.dumps(selection, indent=2) + "\n")

            evaluated = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATOR),
                    "--candidate-dir",
                    str(candidate_dir),
                    "--evaluation-dir",
                    str(evaluation_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(evaluated.returncode, 1)
            completion = json.loads(
                (evaluation_dir / "evaluation_complete.json").read_text()
            )
            self.assertEqual(completion["evaluation_status"], "invalid")
            self.assertTrue((evaluation_dir / "errors.json").is_file())
            self.assertFalse((evaluation_dir / "metrics.json").exists())


if __name__ == "__main__":
    unittest.main()
