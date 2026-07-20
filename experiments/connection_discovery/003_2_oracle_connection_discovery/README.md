# 003-2: Oracle-Canonical Connection Discovery

**Status:** Runner and evaluator implementation ready; method commit pending

## Question

Can the selected 003-1 candidate route classify evidence-supported typed and
directed Connections without overconnecting hard negatives?

## Input Boundary

The primary route contains the 125 candidates selected by
`overlap_bridge_v0.1`. Each request receives exactly one unordered canonical
pair and its frozen candidate-scoped Evidence catalog.

Model-visible input excludes candidate scores, ranks, retrieval features,
provenance strata, course/topic scope flags, Ground Truth category, Relation,
direction, Evidence selection, and scoring eligibility.

## Execution Contract

- one canonical pair per request;
- canonical endpoints must be copied exactly;
- the model returns opaque Evidence IDs, not free-form spans;
- the runner validates IDs and materializes no semantic judgment;
- no-overwrite, clean method commit, raw response retention, and fail-closed
  schema validation are required;
- `--only` is restricted to subset smoke tests and cannot become a final
  evaluation bundle.

The prompt adapts the Relation prompt selected in Experiment 002A to canonical
endpoints and Evidence-ID transport. It is an interface adaptation, not a new
post-benchmark prompt refinement.

## Evaluation

The evaluator reports both conditional metrics over the 125 selected candidates
and full-universe discovery metrics over all 376 primary-scored pairs. Omitted
positive pairs are candidate misses; omitted negatives count as correctly
suppressed graph edges.

Exact Evidence-ID materialization and semantic support are separate. Non-exact
gold Evidence selections use the frozen snapshot-bound process in
`evidence_adjudication_protocol.md`.
