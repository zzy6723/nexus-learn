# Experiment 002C-5: Independent Canonicalization Validation

**Status:** Completed; limited independent validation passed

## Question

Does the frozen v0.2.1 canonicalization pipeline execute correctly on a
pre-existing Entity bundle that did not participate in 002C method development?

## Source

The source is the four-lecture 002B relation-holdout Entity bundle. It predates
002C and was not consumed by 002C-0 through 002C-4. It was previously inspected
for Relation work, so the claim is canonicalization-method independence rather
than universal unseen-data purity.

## Frozen Flow

```text
39 predicted KO mentions
-> frozen normalization and alias resources
-> frozen candidate generator
-> 7 candidate pairs
-> frozen evidence-ID resolver v0.2.1
-> contradiction checks and connected components
-> stable canonical IDs and complete provenance
-> cluster evaluator
-> blind semantic Evidence review
```

No candidate, identity label, Evidence rule, prompt, or metric may change after
formal execution starts.

The frozen pre-execution graph is recorded in:

- `full_pipeline_manifest_v0_1.json`;
- `preflight_complete.json`;
- `benchmark/ko_canonicalization/independent_v0_1/benchmark_complete.json`.

The method freeze covers normalization, aliases, Ground-Truth-blind candidate
generation, the v0.2.1 runner and prompt, Evidence-ID materialization,
clustering, stable canonical IDs, provenance preservation, structural
evaluation, run-specific determinism checks, and blind semantic Evidence
review.

## Coverage Limitation

The source naturally contains only one SAME_OBJECT pair and six selected hard
negatives. Passing supports independent locked reuse for this source, not broad
generalization, stability, or production readiness.

The upstream Entity bundle contains 34 exact and five nonexact mention source
spans. Identity Evidence IDs guarantee exact transport for the identity
decision only; they do not repair those five inherited mention spans.

## Evaluation Order

The formal order is fixed:

1. run the seven candidate-scoped resolver requests from a clean freeze commit;
2. create the neutral Evidence review package before aggregate metrics exist;
3. complete snapshot-bound blind human Evidence review;
4. finalize clusters;
5. evaluate candidate, resolver, cluster, and integrity metrics;
6. run the order-invariance checker;
7. combine every gate in `independent_validation_complete.json`.

The reviewer must not inspect Ground Truth, method identity, aggregate metrics,
or expected pass/fail labels. The current project conversation has already
examined Ground Truth, so its participants cannot be treated as blind reviewers
for this run.

## Execution Rule

If any frozen gate fails, this source becomes development data. The method may
be revised only for a separately frozen future validation source.

Passing completes the limited independent-validation stage of 002C. It does
not by itself select a production canonicalizer or establish run-to-run
stability.

## Final Result

The formal resolver, cluster finalizer, structural evaluator, and run-specific
determinism checker completed successfully. All seven required identity
decisions, all 38 clusters, all integrity gates, and all determinism checks
passed. Fifteen of fifteen selected Evidence spans materialized exactly.

An independent reviewer assessed the frozen neutral review set without access
to Ground Truth, metrics, cluster results, or the earlier diagnostic. All seven
Evidence sets were supported. The snapshot-bound Evidence finalizer and overall
independent-validation finalizer both returned `final`, with no stale, unused,
pending, or failed gate.

See `final_results.md`, `conclusion.md`, and
`runs/independent_v0_1/independent_validation_complete.json`. The earlier
`interim_results.md` and structural marker remain as audit history.
