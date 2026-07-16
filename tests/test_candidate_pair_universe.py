from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.create_candidate_pair_annotation_template import build_annotation_template
from scripts.generate_candidate_pair_universe import (
    DEFAULT_INVENTORY,
    DEFAULT_LECTURE_INVENTORY,
    CandidatePairUniverseError,
    build_pair_universe,
    serialize_json,
    sha256_bytes,
    sha256_file,
    sha256_json,
    validate_inventory,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]


def make_inventory() -> dict:
    objects = [
        {
            "lecture_id": "lecture_b",
            "predicted_ko_id": "method_b",
            "name": "Method B",
            "type": "Method",
            "source_spans": ["Method B is introduced."],
        },
        {
            "lecture_id": "lecture_a",
            "predicted_ko_id": "zeta",
            "name": "Zeta",
            "type": "Concept",
            "source_spans": ["Zeta is defined."],
        },
        {
            "lecture_id": "lecture_a",
            "predicted_ko_id": "alpha",
            "name": "Alpha",
            "type": "Formula",
            "source_spans": ["Alpha is a formula."],
        },
        {
            "lecture_id": "lecture_b",
            "predicted_ko_id": "concept_b",
            "name": "Concept B",
            "type": "Concept",
            "source_spans": ["Concept B is defined."],
        },
        {
            "lecture_id": "lecture_a",
            "predicted_ko_id": "middle",
            "name": "Middle",
            "type": "Method",
            "source_spans": ["Middle is a method."],
        },
    ]
    return {
        "artifact_type": "predicted_ko_normalized_inventory",
        "version": "v0.1",
        "split": "source_split",
        "structural_normalization_version": "test_normalization_v0.1",
        "knowledge_objects": objects,
        "normalized_content_sha256": sha256_json(objects),
    }


def make_lecture_inventory() -> dict:
    texts = {
        "lecture_a": (
            "Alpha is a formula. Middle is a method. Zeta is defined."
        ),
        "lecture_b": "Concept B is defined. Method B is introduced.",
    }
    return {
        "artifact_type": "predicted_ko_relation_lecture_inventory",
        "version": "v0.1",
        "split": "source_split",
        "sources": [
            {
                "lecture_id": lecture_id,
                "path": f"{lecture_id}.md",
                "markdown_sha256": "b" * 64,
                "model_text_sha256": sha256_bytes(text.encode("utf-8")),
            }
            for lecture_id, text in sorted(texts.items())
        ],
        "lectures": [
            {"lecture_id": lecture_id, "text": text}
            for lecture_id, text in sorted(texts.items())
        ],
    }


def build_test_universe(inventory: dict | None = None) -> dict:
    return build_pair_universe(
        inventory or make_inventory(),
        source_inventory_path="inventory.json",
        source_inventory_sha256="a" * 64,
        lecture_inventory=make_lecture_inventory(),
        lecture_inventory_path="lecture_inventory.json",
        lecture_inventory_sha256="c" * 64,
        benchmark_split="development",
    )


class CandidatePairUniverseTests(unittest.TestCase):
    def test_pair_universe_is_exhaustive_and_deterministic(self) -> None:
        inventory = make_inventory()
        universe = build_test_universe(inventory)

        self.assertEqual(universe["total_ko_count"], 5)
        self.assertEqual(universe["total_pair_count"], 4)
        self.assertEqual(
            [
                (item["lecture_id"], item["ko_count"], item["pair_count"])
                for item in universe["lectures"]
            ],
            [
                ("lecture_a", 3, 3),
                ("lecture_b", 2, 1),
            ],
        )
        self.assertEqual(
            [pair["pair_id"] for pair in universe["pairs"]],
            ["cand_dev_001", "cand_dev_002", "cand_dev_003", "cand_dev_004"],
        )
        self.assertEqual(
            [
                (pair["lecture_id"], pair["ko_a"]["ko_id"], pair["ko_b"]["ko_id"])
                for pair in universe["pairs"]
            ],
            [
                ("lecture_a", "alpha", "middle"),
                ("lecture_a", "alpha", "zeta"),
                ("lecture_a", "middle", "zeta"),
                ("lecture_b", "concept_b", "method_b"),
            ],
        )

        shuffled = copy.deepcopy(inventory)
        shuffled["knowledge_objects"].reverse()
        shuffled["normalized_content_sha256"] = sha256_json(
            shuffled["knowledge_objects"]
        )
        self.assertEqual(build_test_universe(shuffled)["pairs"], universe["pairs"])

    def test_duplicate_predicted_ko_reference_is_rejected(self) -> None:
        inventory = make_inventory()
        inventory["knowledge_objects"].append(
            copy.deepcopy(inventory["knowledge_objects"][0])
        )
        inventory["normalized_content_sha256"] = sha256_json(
            inventory["knowledge_objects"]
        )

        with self.assertRaisesRegex(
            CandidatePairUniverseError, "Duplicate predicted Knowledge Object"
        ):
            validate_inventory(inventory)

    def test_normalized_content_hash_mismatch_is_rejected(self) -> None:
        inventory = make_inventory()
        inventory["normalized_content_sha256"] = "0" * 64

        with self.assertRaisesRegex(
            CandidatePairUniverseError, "does not match its objects"
        ):
            validate_inventory(inventory)

    def test_outputs_are_hash_bound_and_no_overwrite_by_default(self) -> None:
        universe = build_test_universe()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory_path = root / "inventory.json"
            lecture_inventory_path = root / "lecture_inventory.json"
            output_path = root / "pair_universe.json"
            marker_path = root / "pair_universe_complete.json"
            inventory_path.write_text(serialize_json(make_inventory()), encoding="utf-8")
            lecture_inventory_path.write_text(
                serialize_json(make_lecture_inventory()), encoding="utf-8"
            )
            inventory_hash = sha256_file(inventory_path)
            lecture_inventory_hash = sha256_file(lecture_inventory_path)

            write_outputs(
                output_path=output_path,
                marker_path=marker_path,
                pair_universe=universe,
                source_inventory_path=inventory_path,
                source_inventory_sha256=inventory_hash,
                lecture_inventory_path=lecture_inventory_path,
                lecture_inventory_sha256=lecture_inventory_hash,
                overwrite=False,
            )

            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], "final")
            self.assertEqual(marker["counts"]["pairs"], 4)
            self.assertEqual(marker["pair_universe"]["sha256"], sha256_file(output_path))
            self.assertEqual(marker["source_inventory"]["sha256"], inventory_hash)
            self.assertEqual(
                marker["lecture_inventory"]["sha256"], lecture_inventory_hash
            )

            with self.assertRaisesRegex(
                CandidatePairUniverseError, "Refusing to overwrite"
            ):
                write_outputs(
                    output_path=output_path,
                    marker_path=marker_path,
                    pair_universe=universe,
                    source_inventory_path=inventory_path,
                    source_inventory_sha256=inventory_hash,
                    lecture_inventory_path=lecture_inventory_path,
                    lecture_inventory_sha256=lecture_inventory_hash,
                    overwrite=False,
                )

    def test_annotation_template_is_separate_and_entirely_draft(self) -> None:
        universe = build_test_universe()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            universe_path = root / "pair_universe.json"
            guidelines = root / "guidelines.md"
            evaluation = root / "evaluation.md"
            success = root / "success.json"
            relation = root / "relation.md"
            pair_schema = root / "pair_schema.json"
            ground_truth_schema = root / "ground_truth_schema.json"
            universe_path.write_text(serialize_json(universe), encoding="utf-8")
            for path in (
                guidelines,
                evaluation,
                success,
                relation,
                pair_schema,
                ground_truth_schema,
            ):
                path.write_text("frozen test document\n", encoding="utf-8")

            template = build_annotation_template(
                universe,
                pair_universe_path=universe_path,
                guidelines_path=guidelines,
                evaluation_protocol_path=evaluation,
                success_criteria_path=success,
                relation_guidelines_path=relation,
                pair_universe_schema_path=pair_schema,
                ground_truth_schema_path=ground_truth_schema,
            )

        self.assertEqual(template["status"], "draft_annotation_required")
        self.assertEqual(len(template["annotations"]), 4)
        self.assertEqual(
            [item["pair_id"] for item in template["annotations"]],
            [item["pair_id"] for item in universe["pairs"]],
        )
        self.assertTrue(
            all(item["candidate_label"] is None for item in template["annotations"])
        )
        self.assertTrue(
            all(item["annotation_status"] == "draft" for item in template["annotations"])
        )

    def test_current_locked_reuse_inventory_yields_176_pairs(self) -> None:
        inventory = json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))
        lecture_inventory = json.loads(
            DEFAULT_LECTURE_INVENTORY.read_text(encoding="utf-8")
        )
        universe = build_pair_universe(
            inventory,
            source_inventory_path=str(DEFAULT_INVENTORY),
            source_inventory_sha256=sha256_file(DEFAULT_INVENTORY),
            lecture_inventory=lecture_inventory,
            lecture_inventory_path=str(DEFAULT_LECTURE_INVENTORY),
            lecture_inventory_sha256=sha256_file(DEFAULT_LECTURE_INVENTORY),
            benchmark_split="development",
        )

        self.assertEqual(universe["total_ko_count"], 39)
        self.assertEqual(universe["total_pair_count"], 176)
        self.assertEqual(
            {item["lecture_id"]: item["pair_count"] for item in universe["lectures"]},
            {
                "differential_equations_001": 55,
                "graph_algorithms_001": 45,
                "numerical_root_finding_001": 21,
                "statistics_estimation_001": 55,
            },
        )


if __name__ == "__main__":
    unittest.main()
