import json
import unittest
from pathlib import Path

from scripts import check_context_ko_resolution_determinism as determinism
from scripts import create_ko_independent_source_manifest as source_manifest
from scripts import create_ko_resolution_pipeline_manifest as pipeline_manifest
from scripts import finalize_ko_evidence_id_development_validation as development_finalizer
from scripts import finalize_ko_independent_benchmark as benchmark_finalizer
from scripts import finalize_ko_independent_preflight as preflight_finalizer
from scripts import finalize_ko_independent_validation as validation_finalizer


ROOT = Path(__file__).resolve().parents[1]


class KOIndependentValidationTest(unittest.TestCase):
    def test_independent_source_and_benchmark_are_frozen_with_limited_denominators(self) -> None:
        source = source_manifest.build_independent_manifest(source_manifest.DEFAULT_SOURCE_RUN)
        self.assertEqual(source["data_role"], "independent_canonicalization_validation")
        self.assertFalse(
            source["canonicalization_independence"]["consumed_by_002c_0_through_002c_4"]
        )

        benchmark = benchmark_finalizer.build_marker(benchmark_finalizer.DEFAULT_ROOT)
        self.assertEqual(benchmark["counts"]["mentions"], 39)
        self.assertEqual(benchmark["counts"]["same_object_pairs"], 1)
        self.assertEqual(benchmark["counts"]["resolver_expected_hard_negatives"], 6)
        self.assertEqual(benchmark["counts"]["nonexact_source_spans"], 5)

    def test_full_pipeline_and_preflight_bind_the_same_frozen_artifacts(self) -> None:
        pipeline = pipeline_manifest.build_manifest()
        preflight = preflight_finalizer.build_marker()
        self.assertEqual(pipeline["pipeline_id"], "ko_canonicalization_pipeline_v0_2_1")
        self.assertEqual(pipeline["components"]["benchmark_completion"], preflight["artifacts"]["benchmark_completion"])
        self.assertEqual(pipeline["components"]["candidate_completion"], preflight["artifacts"]["candidate_completion"])
        self.assertEqual(preflight["counts"]["selected_candidates"], 7)
        self.assertFalse(preflight["model_run_started"])

    def test_development_completion_marker_binds_full_v021_runs(self) -> None:
        marker = development_finalizer.build_marker()
        self.assertTrue(marker["claim_boundary"]["development_validation_completed"])
        self.assertFalse(marker["claim_boundary"]["independent_validation_completed"])
        self.assertFalse(marker["claim_boundary"]["development_reviews_blind"])
        self.assertIn("resolution_completion", marker["runs"]["challenge_v0_1_v0_2_1"])
        self.assertIn("cluster_completion", marker["runs"]["locked_reuse_diagnostic_v0_1_v0_2_1"])

    def test_run_specific_determinism_check_passes_historical_v021_snapshot(self) -> None:
        challenge = ROOT / "benchmark/ko_canonicalization/challenge_v0_1"
        run = ROOT / "experiments/knowledge_object_resolution/002c_4_evidence_id_resolution/runs/challenge_v0_1_v0_2_1"
        report = determinism.build_report(
            inventory_path=challenge / "mention_inventory.json",
            normalization_path=ROOT / "benchmark/ko_name_normalization_v0_1.json",
            candidate_dir=ROOT / "experiments/knowledge_object_resolution/002c_2_context_aware_resolution/runs/challenge_v0_1/candidates",
            resolution_dir=run / "context/run_01",
            cluster_dir=run / "clusters/run_01",
        )
        self.assertEqual(report["status"], "final")
        self.assertTrue(all(report["checks"].values()))

    def test_independent_gate_combiner_separates_evidence_and_determinism(self) -> None:
        criteria = json.loads(
            (ROOT / "benchmark/ko_canonicalization/independent_v0_1/success_criteria.json").read_text()
        )
        metrics = {
            "candidate_generation": {
                "gold_same_object_pair_recall": 1.0,
                "selected_candidates": 7,
                "selected_hard_negatives": 6,
                "required_candidate_decisions": [{"passed": True} for _ in range(7)],
            },
            "resolver": {
                "same_object_precision": 1.0,
                "same_object_recall_end_to_end": 1.0,
                "distinct_object_accuracy_on_candidates": 1.0,
                "unresolved_rate": 0.0,
                "inconsistent_component_count": 0,
                "schema_failure_rate": 0.0,
            },
            "cluster_quality": {
                "b_cubed_precision": 1.0,
                "b_cubed_recall": 1.0,
                "b_cubed_f1": 1.0,
                "exact_gold_cluster_match_rate": 1.0,
                "singleton_precision": 1.0,
                "singleton_recall": 1.0,
            },
            "integrity": {
                "mention_coverage": 1.0,
                "duplicate_assignments": 0,
                "orphan_mentions": 0,
                "lost_provenance_mentions": 0,
                "cross_type_clusters": 0,
            },
            "cluster_error_counts": {},
        }
        audit = {
            "status": "final",
            "reviewed_blind": True,
            "counts": {
                "reviewed_candidates": 7,
                "supported": 7,
                "not_supported": 0,
                "pending": 0,
                "stale_decisions": 0,
                "unused_decisions": 0,
            },
        }
        determinism_report = {
            "status": "final",
            "checks": {key: True for key in criteria["determinism_gates"]},
        }
        self.assertEqual(
            validation_finalizer.evaluate_gates(
                metrics=metrics,
                criteria=criteria,
                evidence_audit=audit,
                determinism=determinism_report,
                exact_evidence=14,
                total_evidence=14,
            ),
            [],
        )

        audit["counts"]["supported"] = 6
        determinism_report["checks"]["canonical_id_invariant_to_mention_order"] = False
        failures = validation_finalizer.evaluate_gates(
            metrics=metrics,
            criteria=criteria,
            evidence_audit=audit,
            determinism=determinism_report,
            exact_evidence=14,
            total_evidence=14,
        )
        self.assertIn("semantic_evidence_support", failures)
        self.assertIn("canonical_id_invariant_to_mention_order", failures)


if __name__ == "__main__":
    unittest.main()
