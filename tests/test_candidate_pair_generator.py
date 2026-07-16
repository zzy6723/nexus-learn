from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_candidate_pair_universe import (
    build_pair_universe,
    serialize_json,
    sha256_file,
    write_outputs,
)
from scripts.generate_candidate_pairs import (
    CandidatePairGenerationError,
    build_all_pairs_selection,
    validate_candidate_selection,
    write_generation_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "candidate_pair_ground_truth"
INVENTORY_PATH = FIXTURE_DIR / "synthetic_inventory.json"
LECTURE_INVENTORY_PATH = FIXTURE_DIR / "synthetic_lecture_inventory.json"
OUTPUT_SCHEMA_PATH = (
    ROOT / "benchmark" / "schema" / "candidate_pair_generation_output.schema.json"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_universe_bundle(root: Path) -> tuple[dict, Path, Path]:
    inventory = load_json(INVENTORY_PATH)
    lecture_inventory = load_json(LECTURE_INVENTORY_PATH)
    universe = build_pair_universe(
        inventory,
        source_inventory_path=str(INVENTORY_PATH.relative_to(ROOT)),
        source_inventory_sha256=sha256_file(INVENTORY_PATH),
        lecture_inventory=lecture_inventory,
        lecture_inventory_path=str(LECTURE_INVENTORY_PATH.relative_to(ROOT)),
        lecture_inventory_sha256=sha256_file(LECTURE_INVENTORY_PATH),
        benchmark_split="development",
    )
    universe_path = root / "pair_universe.json"
    marker_path = root / "pair_universe_complete.json"
    write_outputs(
        output_path=universe_path,
        marker_path=marker_path,
        pair_universe=universe,
        source_inventory_path=INVENTORY_PATH,
        source_inventory_sha256=sha256_file(INVENTORY_PATH),
        lecture_inventory_path=LECTURE_INVENTORY_PATH,
        lecture_inventory_sha256=sha256_file(LECTURE_INVENTORY_PATH),
        overwrite=False,
    )
    return universe, universe_path, marker_path


class CandidatePairGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.universe, self.universe_path, self.marker_path = make_universe_bundle(
            self.root
        )
        self.selection = build_all_pairs_selection(
            self.universe,
            pair_universe_path=self.universe_path,
        )

    def assert_selection_error(self, mutate, expected: str) -> None:
        selection = copy.deepcopy(self.selection)
        mutate(selection)
        errors = validate_candidate_selection(
            selection,
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            require_all_pairs_contract=True,
        )
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_all_pairs_is_deterministic_and_gold_free(self) -> None:
        errors = validate_candidate_selection(
            self.selection,
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            require_all_pairs_contract=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            self.selection["selected_pair_count"], self.universe["total_pair_count"]
        )
        self.assertEqual(
            [item["pair_id"] for item in self.selection["selected_pairs"]],
            [item["pair_id"] for item in self.universe["pairs"]],
        )
        def collect_keys(value):
            if isinstance(value, dict):
                return set(value).union(
                    *(collect_keys(item) for item in value.values())
                )
            if isinstance(value, list):
                return set().union(*(collect_keys(item) for item in value))
            return set()

        all_keys = collect_keys(self.selection)
        for forbidden in (
            "candidate_label",
            "relation_type",
            "gold_relations",
            "evidence_spans",
            "ground_truth",
        ):
            self.assertNotIn(forbidden, all_keys)

    def test_duplicate_unknown_missing_and_order_fail(self) -> None:
        self.assert_selection_error(
            lambda data: data["selected_pairs"].__setitem__(
                1, copy.deepcopy(data["selected_pairs"][0])
            ),
            "duplicate selected pair",
        )
        self.assert_selection_error(
            lambda data: data["selected_pairs"][0].__setitem__(
                "pair_id", "cand_dev_999"
            ),
            "unknown pair",
        )

        def remove_pair(data: dict) -> None:
            data["selected_pairs"].pop()
            data["selected_pair_count"] -= 1

        self.assert_selection_error(remove_pair, "requires every universe pair")

        def reverse_order(data: dict) -> None:
            data["selected_pairs"][0], data["selected_pairs"][1] = (
                data["selected_pairs"][1],
                data["selected_pairs"][0],
            )

        self.assert_selection_error(reverse_order, "order differs")

    def test_endpoint_hash_and_gold_leakage_fail(self) -> None:
        self.assert_selection_error(
            lambda data: data["selected_pairs"][0]["ko_a"].__setitem__(
                "ko_id", "changed_endpoint"
            ),
            "endpoint mismatch",
        )
        self.assert_selection_error(
            lambda data: data["pair_universe"].__setitem__("sha256", "0" * 64),
            "universe mismatch",
        )
        self.assert_selection_error(
            lambda data: data.__setitem__("ground_truth_sha256", "0" * 64),
            "forbidden fields",
        )

    def test_bundle_is_hash_bound_and_rejects_overwrite(self) -> None:
        output_dir = self.root / "run_01"
        selection_path, metadata_path, completion_path = write_generation_bundle(
            output_dir=output_dir,
            selection=self.selection,
            pair_universe=self.universe,
            pair_universe_path=self.universe_path,
            pair_universe_marker_path=self.marker_path,
            output_schema_path=OUTPUT_SCHEMA_PATH,
        )
        metadata = load_json(metadata_path)
        completion = load_json(completion_path)

        self.assertEqual(metadata["status"], "final")
        self.assertFalse(metadata["integrity"]["gold_artifacts_read"])
        self.assertEqual(metadata["output"]["sha256"], sha256_file(selection_path))
        self.assertEqual(completion["status"], "final")
        self.assertEqual(
            completion["counts"]["selected_pairs"],
            self.universe["total_pair_count"],
        )
        self.assertEqual(completion["counts"]["missing_universe_pairs"], 0)

        with self.assertRaisesRegex(
            CandidatePairGenerationError, "Refusing to overwrite"
        ):
            write_generation_bundle(
                output_dir=output_dir,
                selection=self.selection,
                pair_universe=self.universe,
                pair_universe_path=self.universe_path,
                pair_universe_marker_path=self.marker_path,
                output_schema_path=OUTPUT_SCHEMA_PATH,
            )


if __name__ == "__main__":
    unittest.main()
