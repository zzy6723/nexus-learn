# 003-0: Benchmark and Evaluation Preparation

**Status:** In progress
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

## Next Gate

003-0C must annotate all 387 pairs before any model run. It must create exact
candidate-scoped Evidence catalogs, review every default-negative decision,
freeze schema-gap and ambiguous handling, and define success criteria from the
completed denominators.

## Completion Rule

003-0 is complete only after the new source, canonical inventory, exhaustive
pair annotations, schemas, evaluator behavior, and success criteria are frozen.
The current stage must not yet emit a completion marker.
