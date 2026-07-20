import hashlib
import json
import unittest
from pathlib import Path


class ConnectionBenchmarkPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.completion_path = (
            cls.root
            / "experiments/connection_discovery/003_0_benchmark_preparation/completion.json"
        )
        cls.completion = json.loads(cls.completion_path.read_text(encoding="utf-8"))

    def assert_binding_current(self, binding) -> None:
        path = self.root / binding["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(digest, binding["sha256"], binding["path"])

    def test_preflight_is_complete_but_model_execution_remains_locked(self) -> None:
        self.assertEqual(
            self.completion["status"], "ready_for_repository_freeze"
        )
        self.assertFalse(self.completion["model_execution_allowed"])
        self.assertEqual(self.completion["counts"]["all_eligible_pairs"], 387)
        self.assertEqual(self.completion["counts"]["primary_positive_pairs"], 41)
        self.assertEqual(self.completion["counts"]["primary_negative_pairs"], 335)

    def test_all_preflight_bindings_are_current(self) -> None:
        artifacts = self.completion["artifacts"]
        for name, binding in artifacts.items():
            if name == "schemas":
                for schema_binding in binding:
                    self.assert_binding_current(schema_binding)
            else:
                self.assert_binding_current(binding)


if __name__ == "__main__":
    unittest.main()
