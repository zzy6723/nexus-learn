# 003-0: Benchmark and Evaluation Preparation

**Status:** Freeze manifest prepared; repository commit pending
**API calls:** None

## Purpose

003-0 defines the discovery problem before any candidate generator or Relation
model is evaluated.

It must produce and freeze:

- a development source bundle with explicit course and topic metadata;
- an Oracle canonical KO inventory with mention provenance;
- an exhaustive eligible canonical-pair universe;
- Connection Ground Truth and exact Evidence catalogs;
- annotation and evaluation protocols;
- success criteria and error taxonomy;
- leakage and completeness checks.

## 003-0A Result

The four-lecture source used by 002C-5 was audited first. Its structural audit
is complete, but the source is not selected unchanged as the primary 003
development benchmark.

Reasons:

- 38 canonical KOs produce 543 eligible cross-lecture pairs, slightly above
  the intended first-benchmark workload;
- course and topic identifiers are not declared;
- the material contains only one explicit cross-context bridge family, around
  Newton's method and maximum likelihood estimation;
- preliminary screening does not support broad Relation-type coverage;
- most disjoint-provenance pairs are obvious negatives rather than useful
  hard negatives.

The source remains useful as a later sparse diagnostic. It must not be called
an unseen 003 holdout because it has already been inspected.

## 003-0B Result

The new authored development bundle is structurally complete:

- 6 lectures across 3 declared course sequences;
- 29 Oracle canonical KOs and 44 exact mention spans;
- 387 eligible cross-lecture pairs;
- 262 disjoint-provenance and 125 overlap-bridge pairs;
- 139 same-course cross-lecture pairs and 330 pairs with a cross-course
  combination;
- explicit bridge families for multiple Relation types and intentional schema
  gaps.

See `development_source_design.md`. The machine-readable universe is
`benchmark/connection_discovery/development_v0_1/pair_universe.json`.

## 003-0C Result

All 387 eligible pairs are annotated. Candidate-scoped Evidence catalogs,
schema gaps, explicit hard negatives, success criteria, schemas, and the
annotation review audit are complete. See `annotation_summary.md`.

The non-Git completion artifact is `completion.json`. The hash-bound
`benchmark_freeze_manifest_v0_1.json` records benchmark content commit
`6a941fabab27ba3cacfb502ee4f177cf4711dabb`. The freeze becomes effective only
after that manifest and its validation test are committed. Model execution
remains disabled until then.

## Completion Rule

003-0 is methodologically complete but not yet repository-frozen. No 003-1
runner or model may consume the benchmark before the clean freeze gate.
