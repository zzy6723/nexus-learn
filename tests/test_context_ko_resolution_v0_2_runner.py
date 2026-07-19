from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import finalize_context_ko_clusters as finalizer
from scripts import generate_ko_identity_candidates as generator
from scripts import run_context_ko_resolution_v0_2 as runner


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1"
NORMALIZATION = ROOT / "benchmark" / "ko_name_normalization_v0_1.json"


class ContextKOResolutionV02RunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate_dir = self.root / "candidates"
        self.assertEqual(generator.main(["--output-dir", str(self.candidate_dir)]), 0)

    def args(self, run_dir: Path, *extra: str):
        return runner.parse_args(
            [
                "--candidate-dir", str(self.candidate_dir),
                "--lecture-inventory", str(CHALLENGE / "lecture_inventory.json"),
                "--method-commit", "a" * 40,
                "--run-dir", str(run_dir),
                *extra,
            ]
        )

    @staticmethod
    def response_for_payload(*, api_key, payload):
        model_input = json.loads(payload["messages"][1]["content"])
        mentions = model_input["unordered_mentions"]
        result = {
            "candidate_id": model_input["candidate_id"],
            "mention_a": mentions[0]["mention_id"],
            "mention_b": mentions[1]["mention_id"],
            "decision": "SAME_OBJECT",
            "evidence_ids": [model_input["evidence_catalog"][0]["evidence_id"]],
            "rationale": "The supplied contexts identify the same object.",
        }
        return {
            "id": "mock", "model": "deepseek-v4-flash",
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}],
            "usage": {},
        }

    def test_exact_block_catalog_preserves_latex_source_bytes(self) -> None:
        text = "The gradient \\(\\nabla f(x)\\) is exact.\n\n\\[x_{k+1}=x_k\\]"
        candidate = {
            "mention_a": {"lecture_id": "lecture_1"},
            "mention_b": {"lecture_id": "lecture_1"},
        }
        catalog = runner.build_evidence_catalog(candidate, {"lecture_1": text})

        self.assertEqual(len(catalog), 2)
        self.assertEqual(catalog[0]["evidence_id"], "evidence_001")
        self.assertIn(r"\(\nabla f(x)\)", catalog[0]["span"])
        self.assertTrue(all(item["span"] in text for item in catalog))

    def test_dry_run_exposes_catalog_and_not_free_form_output_contract(self) -> None:
        run_dir = self.root / "dry"
        code = runner.run(
            self.args(run_dir, "--dry-run"),
            repository_reader=lambda: ("b" * 40, True),
        )

        self.assertEqual(code, 0)
        rendered = sorted((run_dir / "rendered_inputs" / "pairs").glob("*.json"))
        self.assertEqual(len(rendered), 11)
        payload = json.loads(rendered[0].read_text())
        model_input = json.loads(payload["messages"][1]["content"])
        self.assertIn("evidence_catalog", model_input)
        self.assertNotIn("lectures", model_input)
        self.assertTrue(model_input["evidence_catalog"])

    def test_valid_ids_materialize_to_exact_spans_and_complete(self) -> None:
        run_dir = self.root / "success"
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code = runner.run(
                self.args(run_dir),
                api_call=self.response_for_payload,
                repository_reader=lambda: ("a" * 40, False),
            )

        self.assertEqual(code, 0)
        output = json.loads((run_dir / "output" / "identity_decisions.json").read_text())
        lectures = json.loads((CHALLENGE / "lecture_inventory.json").read_text())["lectures"]
        lecture_by_id = {item["lecture_id"]: item["text"] for item in lectures}
        for result in output["results"]:
            self.assertTrue(result["evidence_ids"])
            self.assertTrue(result["evidence_spans"])
            for evidence in result["evidence_spans"]:
                self.assertIn(evidence["span"], lecture_by_id[evidence["lecture_id"]])
        metadata = json.loads((run_dir / "metadata" / "run_metadata.json").read_text())
        self.assertEqual(metadata["method_id"], runner.METHOD_ID)
        self.assertEqual(metadata["evidence_transport"], "candidate_scoped_opaque_ids_v0_2")

    def test_unknown_evidence_id_fails_closed(self) -> None:
        def unknown_id(*, api_key, payload):
            response = self.response_for_payload(api_key=api_key, payload=payload)
            content = json.loads(response["choices"][0]["message"]["content"])
            content["evidence_ids"] = ["evidence_999"]
            response["choices"][0]["message"]["content"] = json.dumps(content)
            return response

        run_dir = self.root / "unknown"
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            code = runner.run(
                self.args(run_dir), api_call=unknown_id,
                repository_reader=lambda: ("a" * 40, False),
            )

        self.assertEqual(code, 1)
        metadata = json.loads((run_dir / "metadata" / "run_metadata.json").read_text())
        self.assertEqual(metadata["run_status"], "candidate_failed")
        self.assertIn("unknown evidence ID", metadata["error"])
        failed_output = run_dir / "output" / "pairs" / "ko_identity_candidate_001.json"
        self.assertTrue(failed_output.is_file())
        self.assertEqual(json.loads(failed_output.read_text())["evidence_ids"], ["evidence_999"])
        self.assertFalse((run_dir / "resolution_complete.json").exists())

    def test_finalizer_preserves_v02_method_identity(self) -> None:
        run_dir = self.root / "resolution"
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            self.assertEqual(
                runner.run(
                    self.args(run_dir), api_call=self.response_for_payload,
                    repository_reader=lambda: ("a" * 40, False),
                ),
                0,
            )
        cluster_dir = self.root / "clusters"
        self.assertEqual(
            finalizer.main(
                [
                    "--mention-inventory", str(CHALLENGE / "mention_inventory.json"),
                    "--normalization-config", str(NORMALIZATION),
                    "--candidate-dir", str(self.candidate_dir),
                    "--resolution-run-dir", str(run_dir),
                    "--output-dir", str(cluster_dir),
                ]
            ),
            0,
        )
        clusters = json.loads((cluster_dir / "canonical_clusters.json").read_text())
        metadata = json.loads((cluster_dir / "metadata.json").read_text())
        self.assertEqual(clusters["method"]["method_id"], runner.METHOD_ID)
        self.assertEqual(clusters["method"]["version"], "v0.2")
        self.assertEqual(metadata["method_id"], runner.METHOD_ID)


if __name__ == "__main__":
    unittest.main()
