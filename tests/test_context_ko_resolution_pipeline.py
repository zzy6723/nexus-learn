from __future__ import annotations

import json
import os
import tempfile
import unittest
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

from scripts import evaluate_context_ko_resolution as evaluator
from scripts import finalize_context_ko_clusters as finalizer
from scripts import generate_ko_identity_candidates as generator
from scripts import run_context_ko_resolution as runner


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"
NORMALIZATION = ROOT / "benchmark" / "ko_name_normalization_v0_1.json"


class ContextKOResolutionPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate_dir = self.root / "candidates"
        self.assertEqual(generator.main(["--output-dir", str(self.candidate_dir)]), 0)
        ground_truth = json.loads((CHALLENGE / "ground_truth.json").read_text())
        self.gold_same = {
            frozenset(pair)
            for cluster in ground_truth["clusters"]
            for pair in combinations(cluster["mention_ids"], 2)
        }

    def api_response(self, *, override=None):
        def respond(*, api_key, payload):
            model_input = json.loads(payload["messages"][1]["content"])
            mentions = model_input["unordered_mentions"]
            pair = frozenset((mentions[0]["mention_id"], mentions[1]["mention_id"]))
            decision = "SAME_OBJECT" if pair in self.gold_same else "DISTINCT_OBJECT"
            if override is not None:
                decision = override(model_input, decision)
            evidence = []
            if decision != "UNRESOLVED":
                evidence = [
                    {
                        "lecture_id": mentions[0]["lecture_id"],
                        "span": mentions[0]["source_spans"][0],
                    }
                ]
            result = {
                "candidate_id": model_input["candidate_id"],
                "mention_a": mentions[0]["mention_id"],
                "mention_b": mentions[1]["mention_id"],
                "decision": decision,
                "evidence_spans": evidence,
                "rationale": "Synthetic context decision for pipeline validation.",
            }
            return {
                "id": "mock", "model": "deepseek-v4-flash",
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}],
                "usage": {},
            }
        return respond

    def run_resolution(self, *, override=None) -> Path:
        run_dir = self.root / "resolution"
        args = runner.parse_args(
            [
                "--candidate-dir", str(self.candidate_dir),
                "--lecture-inventory", str(CHALLENGE / "lecture_inventory.json"),
                "--method-commit", "a" * 40,
                "--run-dir", str(run_dir),
            ]
        )
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            self.assertEqual(
                runner.run(
                    args, api_call=self.api_response(override=override),
                    repository_reader=lambda: ("a" * 40, False),
                ),
                0,
            )
        return run_dir

    def finalize(self, resolution_dir: Path) -> tuple[int, Path]:
        cluster_dir = self.root / "clusters"
        code = finalizer.main(
            [
                "--mention-inventory", str(CHALLENGE / "mention_inventory.json"),
                "--normalization-config", str(NORMALIZATION),
                "--candidate-dir", str(self.candidate_dir),
                "--resolution-run-dir", str(resolution_dir),
                "--output-dir", str(cluster_dir),
            ]
        )
        return code, cluster_dir

    def test_perfect_pipeline_passes_all_challenge_gates(self) -> None:
        resolution_dir = self.run_resolution()
        code, cluster_dir = self.finalize(resolution_dir)
        self.assertEqual(code, 0)
        evaluation_dir = self.root / "evaluation"

        return_code = evaluator.main(
            [
                "--mention-inventory", str(CHALLENGE / "mention_inventory.json"),
                "--ground-truth", str(CHALLENGE / "ground_truth.json"),
                "--ground-truth-marker", str(CHALLENGE / "ground_truth_complete.json"),
                "--success-criteria", str(CHALLENGE / "success_criteria.json"),
                "--candidate-dir", str(self.candidate_dir),
                "--resolution-run-dir", str(resolution_dir),
                "--cluster-dir", str(cluster_dir),
                "--evaluation-dir", str(evaluation_dir),
            ]
        )

        self.assertEqual(return_code, 0)
        metrics = json.loads((evaluation_dir / "metrics.json").read_text())
        self.assertTrue(metrics["success_criteria"]["passed"])
        self.assertEqual(metrics["candidate_generation"]["gold_same_object_pair_recall"], 1.0)
        self.assertEqual(metrics["resolver"]["same_object_precision"], 1.0)
        self.assertEqual(metrics["resolver"]["same_object_recall_end_to_end"], 1.0)
        self.assertEqual(metrics["resolver"]["homonym_decision"], "DISTINCT_OBJECT")
        self.assertEqual(metrics["cluster_quality"]["b_cubed_f1"], 1.0)

    def test_unresolved_pair_stops_before_cluster_generation(self) -> None:
        resolution_dir = self.run_resolution(
            override=lambda model_input, decision: (
                "UNRESOLVED" if model_input["candidate_id"] == "ko_identity_candidate_001" else decision
            )
        )
        code, cluster_dir = self.finalize(resolution_dir)

        self.assertEqual(code, 2)
        pending = json.loads((cluster_dir / "adjudication_pending.json").read_text())
        self.assertEqual(pending["unresolved_candidate_ids"], ["ko_identity_candidate_001"])
        self.assertFalse((cluster_dir / "generation_complete.json").exists())

    def test_inconsistent_triangle_fails_closed(self) -> None:
        resolution_dir = self.run_resolution(
            override=lambda model_input, decision: (
                "DISTINCT_OBJECT"
                if model_input["candidate_id"] == "ko_identity_candidate_005"
                else decision
            )
        )
        code, cluster_dir = self.finalize(resolution_dir)

        self.assertEqual(code, 2)
        pending = json.loads((cluster_dir / "adjudication_pending.json").read_text())
        self.assertEqual(len(pending["inconsistent_components"]), 1)

    def test_canonical_assignments_and_ids_are_order_invariant(self) -> None:
        inventory = json.loads((CHALLENGE / "mention_inventory.json").read_text())
        normalization = json.loads(NORMALIZATION.read_text())
        candidates = json.loads((self.candidate_dir / "candidate_pairs.json").read_text())
        decisions = []
        for candidate in candidates["candidates"]:
            pair = frozenset(
                (candidate["mention_a"]["mention_id"], candidate["mention_b"]["mention_id"])
            )
            decisions.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "decision": "SAME_OBJECT" if pair in self.gold_same else "DISTINCT_OBJECT",
                }
            )

        def materialize(inv, decision_rows):
            mention_ids = [item["mention_id"] for item in inv["mentions"]]
            groups, contradictions = finalizer.provisional_components(
                mention_ids, candidates, decision_rows
            )
            self.assertFalse(contradictions)
            prediction, assignments, _ = finalizer.build_cluster_artifacts(
                inv, groups, normalization
            )
            assignment_map = {
                item["mention_id"]: item["canonical_id"]
                for item in assignments["assignments"]
            }
            cluster_map = {
                frozenset(item["mention_ids"]): item["canonical_id"]
                for item in prediction["clusters"]
            }
            return assignment_map, cluster_map

        baseline = materialize(inventory, decisions)
        reversed_inventory = {**inventory, "mentions": list(reversed(inventory["mentions"]))}
        self.assertEqual(baseline, materialize(reversed_inventory, decisions))
        self.assertEqual(baseline, materialize(inventory, list(reversed(decisions))))


if __name__ == "__main__":
    unittest.main()
