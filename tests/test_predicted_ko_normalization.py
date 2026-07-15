from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import check_ground_truth
from scripts import evaluate_entity_extraction as entity_evaluator
from scripts import normalize_predicted_kos as normalizer


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INPUT = (
    ROOT
    / "tests"
    / "fixtures"
    / "predicted_ko_relation"
    / "shared"
    / "synthetic_predicted_inventory.json"
)


class PredictedKONormalizationTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def write_input(self, filename: str, value: object) -> Path:
        path = self.temporary_root / filename
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def test_aggregate_fixture_is_structurally_normalized(self) -> None:
        result = normalizer.normalize_prediction_files([FIXTURE_INPUT])

        self.assertEqual(result["artifact_type"], "predicted_ko_normalized_inventory")
        self.assertEqual(result["split"], "development")
        self.assertEqual(
            result["structural_normalization_version"],
            normalizer.STRUCTURAL_NORMALIZATION_VERSION,
        )
        self.assertEqual(len(result["knowledge_objects"]), 5)
        refs = [
            (item["lecture_id"], item["predicted_ko_id"])
            for item in result["knowledge_objects"]
        ]
        self.assertEqual(refs, sorted(refs))

        gradient = next(
            item
            for item in result["knowledge_objects"]
            if item["predicted_ko_id"] == "predicted_gradient"
        )
        self.assertEqual(gradient["name"], "Gradient")
        self.assertEqual(gradient["type"], "Method")
        self.assertEqual(
            gradient["source_spans"],
            ["The gradient collects the partial derivatives of a scalar function."],
        )
        self.assertNotIn("aliases", gradient)
        self.assertNotIn("short_definition", gradient)
        self.assertFalse(any(item["predicted_ko_id"].startswith("ko_slot_") for item in result["knowledge_objects"]))

    def test_model_facing_unicode_content_is_not_name_normalized(self) -> None:
        name = "  Bayes’   Rule  "
        span = "p(θ∣x) ∝ p(x∣θ)p(θ)"
        source = self.write_input(
            "unicode.json",
            {
                "lecture_id": "probability_fixture_001",
                "knowledge_objects": [
                    {
                        "id": "bayes_rule",
                        "name": name,
                        "type": "Concept",
                        "aliases": ["Bayes theorem"],
                        "short_definition": "Posterior update.",
                        "source_span": span,
                    }
                ],
            },
        )

        result = normalizer.normalize_prediction_files([source])
        normalized_object = result["knowledge_objects"][0]
        self.assertEqual(normalized_object["name"], name)
        self.assertEqual(normalized_object["source_spans"], [span])
        self.assertEqual(normalizer.name_matching_key(name), "bayes' rule")
        self.assertNotIn("matching_key", normalized_object)

    def test_name_matching_reuses_entity_evaluator_implementation(self) -> None:
        self.assertIs(normalizer.name_matching_key, entity_evaluator.normalize_label)
        self.assertIs(normalizer.name_matching_key, check_ground_truth.normalize_label)
        samples = [
            "  BAYES’   RULE  ",
            "First‑Order Method",
            "Student`s t―test",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(
                    normalizer.name_matching_key(sample),
                    entity_evaluator.normalize_label(sample),
                )

    def test_enclosing_lecture_id_is_copied_and_verified(self) -> None:
        source = self.write_input(
            "lecture.json",
            {
                "lecture_id": "calculus_fixture_001",
                "knowledge_objects": [
                    {
                        "id": "gradient",
                        "name": "Gradient",
                        "type": "Concept",
                        "source_span": "The gradient is a vector.",
                    }
                ],
            },
        )
        result = normalizer.normalize_prediction_files([source])
        self.assertEqual(
            result["knowledge_objects"][0]["lecture_id"],
            "calculus_fixture_001",
        )

    def test_conflicting_lecture_provenance_is_fatal(self) -> None:
        source = self.write_input(
            "conflict.json",
            {
                "lecture_id": "calculus_fixture_001",
                "knowledge_objects": [
                    {
                        "lecture_id": "optimisation_fixture_001",
                        "id": "gradient",
                        "name": "Gradient",
                        "type": "Concept",
                        "source_span": "Gradient.",
                    }
                ],
            },
        )
        with self.assertRaises(normalizer.NormalizationError) as raised:
            normalizer.normalize_prediction_files([source])
        self.assertEqual(raised.exception.code, "conflicting_lecture_id")

    def test_duplicate_lecture_local_prediction_id_is_fatal(self) -> None:
        source = self.write_input(
            "duplicate.json",
            {
                "lecture_id": "calculus_fixture_001",
                "knowledge_objects": [
                    {"id": "gradient", "name": "Gradient", "type": "Concept", "source_span": "Gradient one."},
                    {"id": "gradient", "name": "Gradient", "type": "Concept", "source_span": "Gradient two."},
                ],
            },
        )
        with self.assertRaises(normalizer.NormalizationError) as raised:
            normalizer.normalize_prediction_files([source])
        self.assertEqual(raised.exception.code, "duplicate_predicted_ko_id")

    def test_same_prediction_id_in_different_lectures_is_allowed(self) -> None:
        first = self.write_input(
            "a.json",
            {"lecture_id": "lecture_a", "knowledge_objects": [{"id": "gradient", "name": "Gradient", "type": "Concept", "source_span": "A gradient."}]},
        )
        second = self.write_input(
            "b.json",
            {"lecture_id": "lecture_b", "knowledge_objects": [{"id": "gradient", "name": "Gradient", "type": "Concept", "source_span": "Another gradient."}]},
        )
        result = normalizer.normalize_prediction_files([second, first])
        self.assertEqual(len(result["knowledge_objects"]), 2)

    def test_invalid_type_is_fatal(self) -> None:
        source = self.write_input(
            "invalid_type.json",
            {"lecture_id": "calculus_fixture_001", "knowledge_objects": [{"id": "theorem", "name": "Theorem", "type": "Theorem", "source_span": "A theorem."}]},
        )
        with self.assertRaises(normalizer.NormalizationError) as raised:
            normalizer.normalize_prediction_files([source])
        self.assertEqual(raised.exception.code, "invalid_ko_type")

    def test_output_and_real_input_hash_are_deterministic(self) -> None:
        first = self.write_input(
            "a.json",
            {"lecture_id": "lecture_a", "knowledge_objects": [{"id": "a", "name": "A", "type": "Concept", "source_span": "A."}]},
        )
        second = self.write_input(
            "b.json",
            {"lecture_id": "lecture_b", "knowledge_objects": [{"id": "b", "name": "B", "type": "Method", "source_span": "B."}]},
        )
        forward = normalizer.normalize_prediction_files([first, second])
        reverse = normalizer.normalize_prediction_files([second, first])

        self.assertEqual(
            normalizer.serialize_json(forward),
            normalizer.serialize_json(reverse),
        )
        self.assertEqual(
            forward["normalized_content_sha256"],
            normalizer.sha256_json(forward["knowledge_objects"]),
        )
        expected_hash = hashlib.sha256(first.read_bytes()).hexdigest()
        first_record = next(
            item for item in forward["input_files"] if item["path"].endswith("a.json")
        )
        self.assertEqual(first_record["sha256"], expected_hash)

    def test_cli_no_overwrite_and_explicit_overwrite(self) -> None:
        output = self.temporary_root / "normalized.json"
        args = ["--input", str(FIXTURE_INPUT), "--output", str(output)]
        self.assertEqual(normalizer.main(args), 0)
        original_bytes = output.read_bytes()
        self.assertEqual(normalizer.main(args), 2)
        self.assertEqual(output.read_bytes(), original_bytes)
        self.assertEqual(normalizer.main([*args, "--overwrite"]), 0)
        self.assertEqual(output.read_bytes(), original_bytes)

    def test_validation_failure_writes_no_output_or_temporary_file(self) -> None:
        source = self.write_input(
            "invalid.json",
            {
                "lecture_id": "lecture_a",
                "knowledge_objects": [
                    {
                        "id": "a",
                        "name": "A",
                        "type": "Concept",
                        "source_span": "",
                    }
                ],
            },
        )
        output = self.temporary_root / "normalized.json"
        self.assertEqual(
            normalizer.main(["--input", str(source), "--output", str(output)]),
            1,
        )
        self.assertFalse(output.exists())
        self.assertEqual(list(self.temporary_root.glob(".normalized.json.*.tmp")), [])

    def test_non_substring_source_span_remains_nonfatal_at_normalization(self) -> None:
        source = self.write_input(
            "non_exact_span.json",
            {
                "lecture_id": "lecture_a",
                "knowledge_objects": [
                    {
                        "id": "gradient",
                        "name": "Gradient",
                        "type": "Concept",
                        "source_span": "This text is intentionally not checked here.",
                    }
                ],
            },
        )
        result = normalizer.normalize_prediction_files([source])
        self.assertEqual(
            result["knowledge_objects"][0]["source_spans"],
            ["This text is intentionally not checked here."],
        )


if __name__ == "__main__":
    unittest.main()
