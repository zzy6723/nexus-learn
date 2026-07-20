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

## Next Gate

Design and audit a new authored development bundle before annotating the
exhaustive pair universe. Target properties are:

- 6 lectures across at least 3 declared course or topic groups;
- 24-30 Oracle canonical KOs;
- approximately 250-400 eligible cross-lecture pairs;
- multiple explicit positive bridge families;
- coverage of at least `REQUIRES`, `APPLIED_IN`, `FORMALIZES`, and `EXTENDS`;
- sufficient near-domain hard negatives;
- exact candidate-scoped Evidence blocks.

The target ranges guide workload and coverage. They are not success metrics.

## Completion Rule

003-0 is complete only after the new source, canonical inventory, exhaustive
pair annotations, schemas, evaluator behavior, and success criteria are frozen.
The current stage must not yet emit a completion marker.
