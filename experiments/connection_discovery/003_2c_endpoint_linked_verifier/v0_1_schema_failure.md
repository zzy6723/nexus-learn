# 003-2c v0.1 Schema Failure

**Status:** Recorded non-evaluable execution failure

Formal `run_01` started from clean method commit
`169a6d24e067a14b7efd27b27cb8cd9f4305ca95`. It completed and validated 42
window decisions. The 43rd API request and JSON parse succeeded, but the model
returned `FORMALIZES` with `Gradient`, a `Concept`, as the source endpoint.

The strict validator rejected the response because `FORMALIZES` requires a
`Formula` source. Metadata correctly records:

- `run_status = prediction_schema_failed`;
- `request_success = true`;
- `json_parse_success = true`;
- `prediction_schema_valid = false`;
- `completed_window_count = 42`.

No aggregate Connection prediction was produced, and the run is not evaluable.
Its raw and parsed response must not be manually edited.

Runner v0.1.1 introduces one generic validator-guided schema-repair attempt.
The repair receives only the unchanged model input, invalid response, and
deterministic validator error. It receives no Ground Truth, score, or expected
Relation. A second invalid response still fails closed.

The next formal execution must use a new clean method commit and a new run
directory. `run_01` remains immutable execution history.
