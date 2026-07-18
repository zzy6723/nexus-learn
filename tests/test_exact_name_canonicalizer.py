from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_deterministic_ko_canonicalization as runner


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "benchmark" / "ko_name_normalization_v0_1.json"
ALIASES_PATH = ROOT / "benchmark" / "ko_aliases_v0_1.json"
REAL_INVENTORY_PATH = (
    ROOT / "benchmark" / "ko_mentions" / "development_v0_1" / "mention_inventory.json"
)
SEMANTIC_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "ko_canonicalization"
    / "semantic_identity_cases.json"
)


class ExactNameCanonicalizerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
        cls.real_inventory = json.loads(REAL_INVENTORY_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(SEMANTIC_FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_root = Path(temporary_directory.name)

    def synthetic_inventory(self) -> dict[str, object]:
        return {
            "benchmark_split": "development",
            "mentions": self.fixture["mentions"],
        }

    def test_safe_normalization_is_auditable(self) -> None:
        wrappers = runner.validate_normalization_config(self.config)
        normalized, operations = runner.normalize_name(
            "  **Newton’s   Method**  ",
            wrappers=wrappers,
        )

        self.assertEqual(normalized, "newton's method")
        self.assertEqual(
            operations,
            [
                "apostrophe_normalization",
                "trim_whitespace",
                "outer_wrapper_removed:markdown_bold",
                "collapse_whitespace",
                "casefold",
            ],
        )

        wrapped, wrapper_operations = runner.normalize_name(
            "**Newton's Method**",
            wrappers=wrappers,
        )
        self.assertEqual(wrapped, "newton's method")
        self.assertIn("outer_wrapper_removed:markdown_bold", wrapper_operations)

    def test_exact_method_merges_only_equal_normalized_name_and_type(self) -> None:
        prediction, assignments, audit = runner.build_prediction(
            self.synthetic_inventory(),
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )

        self.assertEqual(prediction["counts"]["clusters"], 6)
        degree_cluster = next(
            cluster
            for cluster in prediction["clusters"]
            if set(cluster["mention_ids"])
            == {"ko_mention_dev_004", "ko_mention_dev_005"}
        )
        self.assertEqual(degree_cluster["canonical_type"], "Concept")
        self.assertFalse(
            any(
                set(cluster["mention_ids"])
                == {"ko_mention_dev_001", "ko_mention_dev_002"}
                for cluster in prediction["clusters"]
            )
        )
        self.assertEqual(len(assignments["assignments"]), 7)
        self.assertEqual(len(audit["records"]), 7)

    def test_alias_method_uses_only_frozen_type_scoped_equivalences(self) -> None:
        prediction, _, audit = runner.build_prediction(
            self.synthetic_inventory(),
            method_id="alias_aware_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=self.aliases,
        )

        self.assertEqual(prediction["counts"]["clusters"], 4)
        memberships = [set(cluster["mention_ids"]) for cluster in prediction["clusters"]]
        self.assertIn({"ko_mention_dev_001", "ko_mention_dev_002"}, memberships)
        self.assertIn({"ko_mention_dev_006", "ko_mention_dev_007"}, memberships)
        self.assertIn({"ko_mention_dev_004", "ko_mention_dev_005"}, memberships)
        alias_rows = [
            row for row in audit["records"] if "frozen_alias_equivalence" in row["normalization_operations"]
        ]
        self.assertGreaterEqual(len(alias_rows), 2)

    def test_cross_type_names_never_merge(self) -> None:
        inventory = {
            "benchmark_split": "development",
            "mentions": [
                {
                    "mention_id": "ko_mention_dev_001",
                    "name": "Chain Rule",
                    "type": "Method",
                },
                {
                    "mention_id": "ko_mention_dev_002",
                    "name": "Chain Rule",
                    "type": "Concept",
                },
            ],
        }
        prediction, _, _ = runner.build_prediction(
            inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )

        self.assertEqual(prediction["counts"]["clusters"], 2)

    def test_real_inventory_produces_expected_provenance_complete_partition(self) -> None:
        exact, _, _ = runner.build_prediction(
            self.real_inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )
        alias, _, _ = runner.build_prediction(
            self.real_inventory,
            method_id="alias_aware_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=self.aliases,
        )

        for prediction in (exact, alias):
            self.assertEqual(prediction["counts"], {
                "mentions": 39,
                "clusters": 38,
                "singleton_clusters": 37,
                "multi_mention_clusters": 1,
            })
            snapshots = [
                snapshot
                for cluster in prediction["clusters"]
                for snapshot in cluster["mention_provenance"]
            ]
            self.assertEqual(
                sorted(snapshots, key=lambda item: item["mention_id"]),
                sorted(self.real_inventory["mentions"], key=lambda item: item["mention_id"]),
            )

    def test_output_is_byte_deterministic_and_no_overwrite(self) -> None:
        prediction, assignments, audit = runner.build_prediction(
            self.real_inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )
        repeated = runner.build_prediction(
            self.real_inventory,
            method_id="exact_name_same_type_v0_1",
            normalization_config=self.config,
            alias_resource=None,
        )
        self.assertEqual(runner.serialize_json(prediction), runner.serialize_json(repeated[0]))

        output_dir = self.temporary_root / "run"
        kwargs = {
            "output_dir": output_dir,
            "inventory_path": REAL_INVENTORY_PATH,
            "normalization_path": CONFIG_PATH,
            "alias_path": None,
            "method_id": "exact_name_same_type_v0_1",
            "method_commit": "a" * 40,
            "git_commit_at_start": "a" * 40,
            "git_dirty_at_start": False,
            "run_id": "run_01",
            "prediction": prediction,
            "assignments": assignments,
            "audit": audit,
            "overwrite": False,
        }
        runner.write_run(**kwargs)
        first_bytes = {
            path.name: path.read_bytes() for path in output_dir.iterdir()
        }
        with self.assertRaises(runner.DeterministicCanonicalizationError):
            runner.write_run(**kwargs)
        kwargs["overwrite"] = True
        runner.write_run(**kwargs)
        second_bytes = {
            path.name: path.read_bytes() for path in output_dir.iterdir()
        }
        self.assertEqual(first_bytes, second_bytes)

    def test_repository_state_reader_records_commit_and_dirty_flag(self) -> None:
        responses = [
            mock.Mock(stdout="b" * 40 + "\n"),
            mock.Mock(stdout="?? generated.json\n"),
        ]
        with mock.patch.object(runner.subprocess, "run", side_effect=responses) as run:
            commit, dirty = runner.read_repository_state()

        self.assertEqual(commit, "b" * 40)
        self.assertTrue(dirty)
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
