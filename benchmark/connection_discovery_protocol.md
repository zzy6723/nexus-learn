# Connection Discovery Evaluation Protocol

**Status:** Draft for Experiment 003-0
**Version:** v0.1-draft
**Owner:** Project

Terminology follows `docs/glossary.md`. Relation semantics follow ADR-004 and
`benchmark/relation_annotation_guidelines.md` unless this protocol explicitly
adds a canonical-level rule.

## Purpose

This protocol evaluates discovery of evidence-supported Connection Hypotheses
between distinct canonical Knowledge Objects. It separates candidate recall,
conditional Relation classification, complete-universe discovery, upstream
error propagation, and learner-facing selection.

## Evaluation Layers

1. Candidate generation decides which canonical pairs reach classification.
2. Relation classification predicts one typed edge or `NO_RELATION`.
3. Full-universe evaluation counts omitted positive pairs as discovery misses.
4. Predicted-canonical evaluation attributes upstream endpoint failures.
5. Selection and ranking evaluates usefulness only among discovered hypotheses.

Correctness and usefulness are not one label. A technically valid Relation may
be low priority for display, while a useful-sounding proposal is still wrong if
its Relation or Evidence is unsupported.

## Canonical Pair Universe

The base unit is one unique unordered pair of distinct canonical IDs. The pair
ID must be stable under endpoint serialization and bound to a frozen canonical
inventory snapshot.

Exclude:

- self-pairs;
- mention pairs within one canonical cluster;
- duplicate canonical pairs caused by multiple mentions;
- stale or missing canonical IDs;
- endpoints that violate the frozen canonical type and provenance contract.

## Cross-Lecture Eligibility And Strata

A pair is broadly cross-lecture eligible when at least one endpoint-mention
combination comes from different lectures.

Every eligible pair must also receive one provenance stratum:

- `disjoint_provenance`: the endpoint lecture sets do not overlap;
- `overlap_bridge`: the endpoint lecture sets overlap, but at least one
  cross-lecture mention combination exists.

Course and topic scope are independent metadata dimensions:

- `same_course_cross_lecture`;
- `cross_course`;
- `cross_topic`.

Metrics must report the two provenance strata separately. The broad aggregate
must not be described as wholly cross-document discovery.

## Ground Truth Categories

- `IN_SCHEMA_CONNECTION`: one supported ADR-004 Relation can be scored.
- `NO_IN_SCHEMA_CONNECTION`: frozen material supports no graph edge under the
  current schema.
- `OUT_OF_SCHEMA_CONNECTION`: a meaningful connection exists but the current
  schema cannot represent it faithfully.
- `AMBIGUOUS`: direction or primary Relation cannot be resolved under the
  frozen material and rules.

The first two categories form the primary denominator. Schema-gap and ambiguous
items are diagnostic unless acceptable alternatives are frozen before model
execution.

## Relation Output

Experiment 003 v0.1 uses one primary Relation per canonical pair:

- `REQUIRES`
- `APPLIED_IN`
- `EXTENDS`
- `CONTRASTS_WITH`
- `FORMALIZES`
- `RELATED_TO`
- benchmark-only `NO_RELATION`

Do not add a Relation type in response to model errors on a frozen benchmark.
Repeated schema gaps require a separate review and ADR change.

## Evidence Contract

Each candidate request receives an opaque, candidate-scoped Evidence catalog.
The model selects Evidence IDs; the runner materializes exact lecture spans.
Free-form copied Evidence is not the authoritative transport.

Positive Ground Truth records one support scope:

- `single_lecture_explicit`;
- `cross_lecture_explicit`;
- `multi_lecture_compositional`.

The first two scopes enter v0.1 primary scoring. Compositional Evidence remains
diagnostic until annotation and semantic-review behavior are validated.

Exact materialization and semantic support are separate gates. A snapshot-bound
human adjudication is required for Evidence sets that cannot be resolved by a
frozen exact match to Ground Truth Evidence.

## Metrics

Candidate generation reports:

- positive candidate recall;
- per-Relation candidate recall;
- disjoint-provenance and overlap-bridge recall;
- cross-course recall;
- workload reduction;
- candidates per canonical KO;
- duplicate and self-pair counts.

Conditional classification reports the frozen Relation metrics, including
strict edge accuracy, type accuracy, direction, `NO_RELATION` accuracy,
`RELATED_TO` use, and Evidence quality.

Full-universe discovery reports:

- Connection precision, recall, and F1;
- per-Relation recall;
- provenance-stratum and course-scope recall;
- candidate misses and classifier misses separately;
- pipeline strict success over the complete primary universe.

Predicted-canonical evaluation additionally reports endpoint recoverability,
false-merge and false-split propagation, lost provenance, duplicate
Connections, and relation failure with correct endpoints.

Selection and ranking use a separately frozen review set and do not alter
Connection correctness metrics.

## Freeze And Leakage Rules

Before the first model call, freeze:

- source and lecture metadata;
- Oracle canonical inventory;
- exhaustive pair universe;
- Ground Truth categories, labels, alternatives, and Evidence;
- candidate-generation and classification success criteria;
- matching, error, and adjudication rules;
- model-visible field allowlist.

Candidate generation and model requests must not receive gold category,
Relation, direction, Evidence, primary-scoring eligibility, or ranking labels.

## Independence Rule

Development data may be inspected and used once for method refinement.
Independent validation must use a source selected after the complete method and
criteria are frozen. A method change after viewing independent results converts
that source to development data and requires a new independent source.
