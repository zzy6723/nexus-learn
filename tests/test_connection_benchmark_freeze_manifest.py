import hashlib
import json
import unittest
from pathlib import Path


class ConnectionBenchmarkFreezeManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.path = (
            cls.root
            / "experiments/connection_discovery/003_0_benchmark_preparation/benchmark_freeze_manifest_v0_1.json"
        )
        cls.manifest = json.loads(cls.path.read_text(encoding="utf-8"))

    def assert_binding_current(self, binding) -> None:
        path = self.root / binding["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(digest, binding["sha256"], binding["path"])

    def test_manifest_binds_the_user_supplied_content_commit(self) -> None:
        self.assertEqual(
            self.manifest["benchmark_content_commit"],
            "6a941fabab27ba3cacfb502ee4f177cf4711dabb",
        )
        self.assertEqual(self.manifest["status"], "frozen_content_binding")
        self.assertTrue(self.manifest["freeze_effective_when_manifest_is_committed"])

    def test_every_frozen_binding_is_current(self) -> None:
        self.assert_binding_current(self.manifest["completion"])
        for name, binding in self.manifest["frozen_artifacts"].items():
            if name == "schemas":
                for schema_binding in binding:
                    self.assert_binding_current(schema_binding)
            else:
                self.assert_binding_current(binding)


if __name__ == "__main__":
    unittest.main()
