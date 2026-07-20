# 002C-5 Final Results

## Status

Experiment 002C-5 passed every frozen independent-validation gate.

The overall completion artifact is
`runs/independent_v0_1/independent_validation_complete.json`.

## Scope

The frozen v0.2.1 pipeline ran on a pre-existing four-lecture Entity bundle
that did not participate in canonicalization method development. The source
had previously been used for Relation experiments, so the result is
independent with respect to canonicalization development rather than a claim
of universally unseen educational data.

## Execution Integrity

The resolver ran from freeze commit
`7ab00e00a7ba64b8ce906eb31ee6512983e82a3b` with a clean worktree. All seven
candidate-scoped requests completed with valid JSON, valid schemas, exact
candidate alignment, and `finish_reason = stop`.

## Results

| Layer | Metric | Result |
| --- | --- | ---: |
| Benchmark | Mentions | 39 |
| Benchmark | Gold clusters | 38 |
| Candidate | Gold SAME_OBJECT recall | 1.000 |
| Candidate | Selected candidates | 7 |
| Candidate | Selected hard negatives | 6 |
| Resolver | SAME_OBJECT precision | 1.000 |
| Resolver | SAME_OBJECT end-to-end recall | 1.000 |
| Resolver | DISTINCT_OBJECT candidate accuracy | 1.000 |
| Resolver | Unresolved rate | 0.000 |
| Cluster | B-cubed precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Cluster | Exact gold-cluster match | 38/38 |
| Cluster | Singleton precision / recall | 1.000 / 1.000 |
| Integrity | False merges / false splits | 0 / 0 |
| Integrity | Duplicate / orphan assignments | 0 / 0 |
| Integrity | Cross-type clusters | 0 |
| Integrity | Lost-provenance mentions | 0 |
| Evidence | Exact materialization | 15/15 |
| Evidence | Blind semantic support | 7/7 |
| Determinism | Frozen checks passed | 5/5 |

The blind adjudication was snapshot-bound to the formal prediction and neutral
review package. It contained no pending, stale, duplicate, or unused decision.
The earlier unblinded 7/7 diagnostic remains preserved separately and was not
used as the formal Evidence gate.

## Provenance Boundary

Identity-decision Evidence and upstream mention provenance are separate.
Evidence IDs materialized every selected identity span exactly. They do not
repair the five nonexact mention source spans inherited from Entity Extraction;
the source bundle contains 34 exact and five nonexact upstream spans.

## Execution Note

The first direct-file determinism-checker invocation failed before writing an
artifact because that invocation did not expose the project namespace. The
same frozen checker bytes completed through the Python module entry point. No
method, checker, prompt, benchmark, or criterion changed.

## Interpretation

The result supports limited independent locked reuse of
`candidate_scoped_context_resolution_evidence_ids_v0_2_1` on this source. It
does not establish broad generalization, run-to-run stability, long-document
performance, robustness to severe Entity noise, or production readiness. The
independent source includes only one positive identity pair and six selected
hard negatives.
