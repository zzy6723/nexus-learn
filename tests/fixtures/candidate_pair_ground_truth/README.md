# Candidate Pair Ground-Truth Checker Fixtures

This fixture set defines a complete synthetic bundle with six lecture-local
pairs. It covers:

- `IN_SCHEMA_RELATION` with one Relation;
- `IN_SCHEMA_RELATION` with a primary and acceptable alternative;
- `NO_IN_SCHEMA_RELATION`;
- finalized `AMBIGUOUS`;
- finalized `OUT_OF_SCHEMA_RELATION`;
- a second singleton lecture for cross-lecture endpoint failure tests.

`tests/test_candidate_pair_ground_truth_checker.py` builds a hash-bound bundle
from these source fixtures and applies one mutation per failure case. Covered
failures include missing, extra, duplicate, reversed-duplicate, self, unknown,
and cross-lecture pairs; invalid Relation type or direction; label/payload
mismatches; invalid Evidence; stale hashes; and invalid provenance.

The real 176-pair draft scaffold is also validated in `--allow-draft` mode.
