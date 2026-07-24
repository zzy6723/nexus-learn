# Learning Explanation Benchmark

**Status:** 004-0 development benchmark ready for freeze review

This benchmark evaluates explanation of validated Connections. It does not use
Connection Discovery predictions and does not validate an end-to-end product
pipeline.

## Development Source

`development_v0_1` is deterministically selected from human-validated positive
Connections in Experiment 003 Ground Truth. It is development-only because the
source was previously used for Connection-method development.

The 21-instance selection is relation-stratified:

- every primary `FORMALIZES`, `EXTENDS`, and `CONTRASTS_WITH` example is
  retained because support is small;
- fixed subsets of `APPLIED_IN` and `REQUIRES` provide domain and Evidence-set
  variety;
- `RELATED_TO` is excluded because the source has no positive support.

No reference prose is treated as an exact target. Each instance instead has
pre-model required semantic points, non-exhaustive forbidden or unsupported
claims, and risk tags. These annotations are reviewer scaffolding and are
forbidden from model input.

## Files

- `development_v0_1/selection_spec.json`: pre-model deterministic selection;
- `development_v0_1/annotation_scaffold_spec.json`: manually authored
  semantic review constraints;
- `development_v0_1/source_manifest.json`: source hashes;
- `development_v0_1/connection_instances.json`: Oracle Connection instances;
- `development_v0_1/annotation_scaffold.json`: instance-aligned review
  scaffold;
- `development_v0_1/benchmark_complete.json`: structural completion marker.

Independent validation requires a separately annotated source created only
after a development method is frozen.
