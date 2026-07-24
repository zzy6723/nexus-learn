# Learning Explanation Benchmark

**Status:** 004-0 development preparation in progress

This benchmark evaluates explanation of validated Connections. It does not use
Connection Discovery predictions and does not validate an end-to-end product
pipeline.

## Development Source

`development_v0_1` is deterministically selected from human-validated positive
Connections in Experiment 003 Ground Truth. It is development-only because the
source was previously used for Connection-method development.

The selection is relation-stratified:

- every primary `FORMALIZES`, `EXTENDS`, and `CONTRASTS_WITH` example is
  retained because support is small;
- fixed subsets of `APPLIED_IN` and `REQUIRES` provide domain and Evidence-set
  variety;
- `RELATED_TO` is excluded because the source has no positive support.

No reference prose is treated as an exact target. Evaluation uses a frozen
Connection, Evidence, claim-level faithfulness decisions, and a human
learning-value rubric.

## Files

- `development_v0_1/selection_spec.json`: pre-model deterministic selection;
- `development_v0_1/source_manifest.json`: source hashes;
- `development_v0_1/connection_instances.json`: Oracle Connection instances;
- `development_v0_1/benchmark_complete.json`: structural completion marker.

Independent validation requires a separately annotated source created only
after a development method is frozen.
