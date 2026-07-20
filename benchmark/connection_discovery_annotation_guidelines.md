# Connection Discovery Annotation Guidelines

**Status:** Draft for Experiment 003-0
**Version:** v0.1-draft
**Owner:** Project

## Annotation Unit

Annotate one frozen unordered pair of distinct canonical Knowledge Objects.
Canonical identity and mention provenance are inputs; annotators must not merge
or split identities while assigning a Connection label.

## Material Boundary

Judge only what the frozen lectures and Evidence catalog support. General STEM
knowledge may help interpret the text, but it cannot supply a missing edge.
`NO_IN_SCHEMA_CONNECTION` means unsupported in this benchmark, not impossible
in the world.

## Category Decision

Use `IN_SCHEMA_CONNECTION` when one ADR-004 Relation is clear, educationally
meaningful, and supported by the frozen material.

Use `NO_IN_SCHEMA_CONNECTION` when proximity, shared vocabulary, common
discipline, or co-occurrence is the only basis for a link.

Use `OUT_OF_SCHEMA_CONNECTION` when a real educational relation is supported
but labels such as `INSTANCE_OF`, `EQUIVALENT_TO`, or `SPECIAL_CASE_OF` would be
needed to state it faithfully. Do not hide schema gaps inside `RELATED_TO`.

Use `AMBIGUOUS` when multiple labels or directions remain equally defensible.
Acceptable alternatives must be declared before model execution.

## Relation And Direction

Apply the frozen ADR-004 direction rules. Continue to require a Formula source
for `FORMALIZES`. `RELATED_TO` is a supported weak relation, not an uncertainty
label.

Experiment 003 v0.1 records one primary Relation. If multiple Relations are
supported, select the most educationally specific frozen label. If no unique
primary label can be justified, mark the pair ambiguous instead of inventing a
priority after model output.

## Cross-Lecture Scope

Record endpoint lecture sets and assign:

- `disjoint_provenance` when they do not overlap;
- `overlap_bridge` when they overlap but also permit a cross-lecture pairing.

Also record declared course and topic relationships. Do not infer course IDs
from filenames during scoring.

An overlap-bridge pair can be a legitimate Learning Continuity example: an old
canonical object may reappear in a new lecture beside a new object. It must be
reported separately from fully disjoint provenance.

## Evidence

Positive annotations select opaque Evidence IDs from a candidate-scoped catalog.
The catalog must deterministically materialize exact lecture spans.

The selected Evidence set, read together, must identify both endpoints or make
their Relation unambiguous. Unresolved pronouns or omitted premises are not
sufficient. Keep Evidence minimal without removing required context.

Assign one support scope:

- `single_lecture_explicit`: one lecture explicitly establishes the Relation;
- `cross_lecture_explicit`: explicit support is distributed across endpoint
  provenance but does not require a new logical synthesis;
- `multi_lecture_compositional`: the edge requires combining claims across
  lectures.

Compositional items are diagnostic in v0.1.

## Negative Coverage

Include near-domain hard negatives, not only pairs from unrelated subjects.
Useful negative strata include:

- same course and adjacent topics without a supported edge;
- shared mathematical symbols with different roles;
- Method-Formula pairs where the formula does not formalize that method;
- objects connected only through an omitted intermediate object;
- broad conceptual similarity without an ADR-004 Relation.

## Usefulness Boundary

Do not score novelty, learner value, surprise, or display priority in the
Connection Ground Truth. Those dimensions belong to 003-4. Ground Truth here
answers whether a typed, Evidence-supported Connection exists.

## Workflow

1. Freeze source lectures, course/topic metadata, and Oracle canonical KOs.
2. Generate the exhaustive eligible pair universe deterministically.
3. Annotate categories without model outputs.
4. Annotate type, direction, Evidence IDs, support scope, and rationale.
5. Review schema-gap and ambiguous items separately.
6. Check pair completeness, endpoint validity, and Evidence materialization.
7. Freeze evaluation rules and success criteria.
8. Audit model-visible artifacts for gold leakage.
9. Only then execute candidate generation or Relation models.
