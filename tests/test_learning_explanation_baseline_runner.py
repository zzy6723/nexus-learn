from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_learning_explanation_baselines as runner


METHOD_COMMIT = "b" * 40


class LearningExplanationBaselineRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.benchmark = runner.load_json(runner.DEFAULT_BENCHMARK)

    def args(self, method: str, run_dir: Path, *extra: str):
        return runner.parse_args(
            [
                "--method",
                method,
                "--method-commit",
                METHOD_COMMIT,
                "--run-dir",
                str(run_dir),
                *extra,
            ]
        )

    @staticmethod
    def valid_response(*, api_key, payload):
        model_input = json.loads(payload["messages"][1]["content"])
        output = {
            "explanation_instance_id": model_input[
                "explanation_instance_id"
            ],
            "source_ko_id": model_input["source_ko"]["canonical_ko_id"],
            "relation_type": model_input["relation_type"],
            "target_ko_id": model_input["target_ko"]["canonical_ko_id"],
            "connection_summary": {
                "text": "The supplied objects have the validated Relation.",
                "evidence_refs": [],
            },
            "why_connected": {
                "text": "The explanation remains bounded to the Relation semantics.",
                "evidence_refs": [],
            },
            "learning_value": {
                "text": "The link can help organize the two named objects.",
                "evidence_refs": [],
            },
        }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(output)},
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            },
        }

    def run_with_state(self, args, api_call=None):
        if api_call is None:
            api_call = mock.Mock(
                side_effect=AssertionError("API must not be called")
            )
        code = runner.run(
            args,
            api_call=api_call,
            repository_reader=lambda: (METHOD_COMMIT, False),
        )
        return code, api_call

    def test_model_input_is_gold_free_and_contains_no_evidence(self):
        self.assertEqual(len(self.benchmark["instances"]), 21)
        for instance in self.benchmark["instances"]:
            model_input = runner.build_model_input(instance)
            self.assertEqual(
                set(model_input),
                {
                    "explanation_instance_id",
                    "source_ko",
                    "relation_type",
                    "symmetric",
                    "target_ko",
                    "evidence_catalog",
                },
            )
            self.assertEqual(model_input["evidence_catalog"], [])
            self.assertEqual(
                runner.collect_keys(model_input)
                & runner.FORBIDDEN_MODEL_KEYS,
                set(),
            )

    def test_deterministic_baseline_completes_without_api(self):
        run_dir = self.root / "deterministic"
        code, api = self.run_with_state(
            self.args("001a_deterministic_paraphrase", run_dir)
        )
        self.assertEqual(code, 0)
        api.assert_not_called()

        predictions = json.loads(
            (run_dir / "output/predictions.json").read_text()
        )
        self.assertEqual(
            predictions["method_id"], "001a_deterministic_paraphrase"
        )
        self.assertEqual(len(predictions["results"]), 21)
        for result in predictions["results"]:
            for field in runner.FIELD_NAMES:
                self.assertEqual(result[field]["evidence_refs"], [])
                self.assertTrue(result[field]["text"])

        metadata = json.loads(
            (run_dir / "metadata/run_metadata.json").read_text()
        )
        self.assertEqual(metadata["run_status"], "completed")
        self.assertEqual(metadata["api_call_count"], 0)
        self.assertIsNone(metadata["request_parameters"])
        self.assertEqual(metadata["git_commit_at_start"], METHOD_COMMIT)
        self.assertFalse(metadata["git_dirty_at_start"])
        self.assertEqual(
            metadata["004_0_freeze_commit"],
            "cda3f9dd7f3298d0f726118db8d15e546febccab",
        )

    def test_deterministic_output_is_byte_stable(self):
        first = self.root / "deterministic_1"
        second = self.root / "deterministic_2"
        self.assertEqual(
            self.run_with_state(
                self.args("001a_deterministic_paraphrase", first)
            )[0],
            0,
        )
        self.assertEqual(
            self.run_with_state(
                self.args("001a_deterministic_paraphrase", second)
            )[0],
            0,
        )
        self.assertEqual(
            (first / "output/predictions.json").read_bytes(),
            (second / "output/predictions.json").read_bytes(),
        )

    def test_relation_only_full_dry_run_makes_no_api_call(self):
        run_dir = self.root / "relation_only_dry"
        code, api = self.run_with_state(
            self.args(
                "001b_relation_only_llm",
                run_dir,
                "--dry-run",
            )
        )
        self.assertEqual(code, 0)
        api.assert_not_called()
        rendered = sorted(
            (run_dir / "rendered_inputs/instances").glob("*.json")
        )
        self.assertEqual(len(rendered), 21)
        for path in rendered:
            payload = json.loads(path.read_text())
            model_input = json.loads(payload["messages"][1]["content"])
            self.assertEqual(model_input["evidence_catalog"], [])
            self.assertEqual(
                runner.collect_keys(model_input)
                & runner.FORBIDDEN_MODEL_KEYS,
                set(),
            )
        metadata = json.loads(
            (run_dir / "metadata/run_metadata.json").read_text()
        )
        self.assertEqual(metadata["run_status"], "dry_run_complete")
        self.assertEqual(metadata["instance_count"], 21)
        self.assertEqual(metadata["api_call_count"], 0)
        self.assertFalse(
            (run_dir / "output/predictions.json").exists()
        )

    def test_relation_only_valid_subset_response_completes(self):
        run_dir = self.root / "relation_only_subset"
        instance_id = self.benchmark["instances"][0][
            "explanation_instance_id"
        ]
        with mock.patch.dict(
            "os.environ",
            {"DEEPSEEK_API_KEY": "test-key"},
        ):
            code, _ = self.run_with_state(
                self.args(
                    "001b_relation_only_llm",
                    run_dir,
                    "--only",
                    instance_id,
                ),
                api_call=self.valid_response,
            )
        self.assertEqual(code, 0)
        metadata = json.loads(
            (run_dir / "metadata/run_metadata.json").read_text()
        )
        self.assertEqual(metadata["run_status"], "completed_subset")
        self.assertTrue(metadata["request_success"])
        self.assertTrue(metadata["json_parse_success"])
        self.assertTrue(metadata["prediction_schema_valid"])
        self.assertEqual(metadata["finish_reason"], "stop")
        self.assertEqual(metadata["api_call_count"], 1)

    def test_relation_only_nonempty_evidence_ref_fails_schema(self):
        def invalid_response(*, api_key, payload):
            response = self.valid_response(api_key=api_key, payload=payload)
            output = json.loads(
                response["choices"][0]["message"]["content"]
            )
            output["why_connected"]["evidence_refs"] = ["evidence_001"]
            response["choices"][0]["message"]["content"] = json.dumps(
                output
            )
            return response

        run_dir = self.root / "invalid_ref"
        instance_id = self.benchmark["instances"][0][
            "explanation_instance_id"
        ]
        with mock.patch.dict(
            "os.environ",
            {"DEEPSEEK_API_KEY": "test-key"},
        ):
            code, _ = self.run_with_state(
                self.args(
                    "001b_relation_only_llm",
                    run_dir,
                    "--only",
                    instance_id,
                ),
                api_call=invalid_response,
            )
        self.assertEqual(code, 1)
        metadata = json.loads(
            (run_dir / "metadata/run_metadata.json").read_text()
        )
        self.assertEqual(
            metadata["run_status"], "prediction_schema_failed"
        )
        self.assertTrue(
            (
                run_dir
                / f"parsed_responses/instances/{instance_id}.json"
            ).is_file()
        )

    def test_no_overwrite_and_dirty_repository_fail_before_writes(self):
        existing = self.root / "existing"
        existing.mkdir()
        code, _ = self.run_with_state(
            self.args(
                "001b_relation_only_llm",
                existing,
                "--dry-run",
            )
        )
        self.assertEqual(code, 1)

        dirty = self.root / "dirty"
        code = runner.run(
            self.args(
                "001b_relation_only_llm",
                dirty,
                "--dry-run",
            ),
            api_call=mock.Mock(
                side_effect=AssertionError("API must not be called")
            ),
            repository_reader=lambda: (METHOD_COMMIT, True),
        )
        self.assertEqual(code, 1)
        self.assertFalse(dirty.exists())

    def test_prompt_is_instance_agnostic_and_explicitly_no_evidence(self):
        prompt = runner.DEFAULT_PROMPT.read_text()
        self.assertNotIn("le_dev_", prompt)
        self.assertNotIn("conn_dev_pair_", prompt)
        self.assertIn("No Evidence is supplied", prompt)
        self.assertIn("evidence_refs", prompt)
        self.assertIn("reclassify", prompt)


if __name__ == "__main__":
    unittest.main()
