import unittest

from scripts.audit_connection_discovery_source import build_audit


class ConnectionDiscoverySourceAuditTests(unittest.TestCase):
    def test_pair_strata_and_counts_are_derived_from_provenance(self) -> None:
        canonical_bundle = {
            "clusters": [
                {
                    "canonical_id": "c1",
                    "canonical_type": "Concept",
                    "mention_provenance": [
                        {
                            "lecture_id": "l1",
                            "source_span_exact_flags": [True],
                        }
                    ],
                },
                {
                    "canonical_id": "c2",
                    "canonical_type": "Method",
                    "mention_provenance": [
                        {
                            "lecture_id": "l1",
                            "source_span_exact_flags": [False],
                        }
                    ],
                },
                {
                    "canonical_id": "c3",
                    "canonical_type": "Formula",
                    "mention_provenance": [
                        {
                            "lecture_id": "l2",
                            "source_span_exact_flags": [True],
                        }
                    ],
                },
                {
                    "canonical_id": "c4",
                    "canonical_type": "Concept",
                    "mention_provenance": [
                        {
                            "lecture_id": "l1",
                            "source_span_exact_flags": [True],
                        },
                        {
                            "lecture_id": "l2",
                            "source_span_exact_flags": [True],
                        },
                    ],
                },
            ]
        }
        source_manifest = {"lecture_ids": ["l1", "l2"]}

        audit = build_audit(
            canonical_bundle,
            source_manifest,
            canonical_path="clusters.json",
            source_manifest_path="manifest.json",
        )

        self.assertEqual(audit["counts"]["canonical_knowledge_objects"], 4)
        self.assertEqual(audit["counts"]["knowledge_object_mentions"], 5)
        self.assertEqual(audit["counts"]["exact_source_spans"], 4)
        self.assertEqual(audit["counts"]["nonexact_source_spans"], 1)
        self.assertEqual(
            audit["pair_universe"]["all_unique_unordered_canonical_pairs"], 6
        )
        self.assertEqual(audit["pair_universe"]["eligible_cross_lecture_pairs"], 5)
        self.assertEqual(audit["pair_universe"]["disjoint_provenance_pairs"], 2)
        self.assertEqual(audit["pair_universe"]["overlap_bridge_pairs"], 3)
        self.assertEqual(
            audit["pair_universe"]["ineligible_same_lecture_only_pairs"], 1
        )
        self.assertFalse(audit["metadata_coverage"]["course_ids_declared"])
        self.assertFalse(audit["metadata_coverage"]["topic_ids_declared"])

    def test_rejects_undeclared_lecture(self) -> None:
        canonical_bundle = {
            "clusters": [
                {
                    "canonical_id": "c1",
                    "canonical_type": "Concept",
                    "mention_provenance": [
                        {
                            "lecture_id": "unknown",
                            "source_span_exact_flags": [True],
                        }
                    ],
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "undeclared lecture"):
            build_audit(
                canonical_bundle,
                {"lecture_ids": ["l1"]},
                canonical_path="clusters.json",
                source_manifest_path="manifest.json",
            )


if __name__ == "__main__":
    unittest.main()
