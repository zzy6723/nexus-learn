# Relation Annotation Guidelines

**Status:** Frozen for holdout construction at `18e687d5cd7909531918b51e2d6bef38cb64a053`  
**Version:** v0.1  
**Created:** 2026-07-12  
**Owner:** Project

The annotation rules are content-locked for Relation holdout construction. Any
semantic change after the freeze commit requires a new version and invalidates
direct v0.1 holdout comparison.

Terminology follows `docs/glossary.md`.

---

# Purpose

This document defines how human ground truth should be annotated for Typed Relation Extraction.

The goal is not to create a complete STEM knowledge graph. The goal is to create a consistent development benchmark for evaluating whether a model can assign useful typed Relations between known Knowledge Objects.

---

# Experiment Boundary

The first Relation experiment is:

`Experiment 002A: Oracle-KO Typed Relation Extraction`

In 002A, the input Knowledge Objects come from human ground truth. The model is not asked to extract Knowledge Objects.

This isolates the question:

Can a model identify relation type, direction, evidence, and rationale when the Knowledge Objects are already correct?

End-to-end Relation Extraction using predicted Knowledge Objects is deferred to Experiment 002B.

---

# Annotation Unit

The annotation unit is an unordered candidate Knowledge Object pair plus a directed gold Relation.

The model-facing candidate contains:

- an opaque `pair_id` that does not encode either Knowledge Object;
- `ko_a` and `ko_b` references;
- the known names, types, and source grounding for both Knowledge Objects;
- relevant lecture text.

The order of `ko_a` and `ko_b` does not imply Relation direction. The gold annotation separately contains:

- directed `source` and `target` references;
- one relation label;
- evidence spans;
- a short annotation rationale.

The runner must never expose gold direction, label, category, evidence, rationale, or acceptable alternatives to the model.

For reproducibility, the runner should derive `ko_a` and `ko_b` by sorting the two fully qualified `(lecture_id, ko_id)` references. This ordering is only serialization; the prompt explicitly states that it carries no Relation meaning.

---

# Allowed Relation Labels

Graph Relation labels:

| Label | Meaning |
| --- | --- |
| `REQUIRES` | The target is necessary to understand, state, or define the source. |
| `APPLIED_IN` | The source object is used or applied in the target object, method, or problem context. |
| `EXTENDS` | The source is a more specific, enriched, or advanced development of the target while preserving it as a conceptual base. |
| `CONTRASTS_WITH` | The source and target are meaningfully contrasted. |
| `FORMALIZES` | The source is a Formula that explicitly defines, characterizes, expresses, or gives an update or solution condition for the target. |
| `RELATED_TO` | The source and target have a meaningful but weak relation that does not fit stronger labels. |

Benchmark-only label:

| Label | Meaning |
| --- | --- |
| `NO_RELATION` | No relation should be written to the knowledge graph for this candidate pair. |

`NO_RELATION` is used for evaluation only. It is not a Relation in the product graph.

---

# Direction Rules

Relations are directional unless explicitly documented otherwise.

Use the following direction conventions:

- `A REQUIRES B`: `B` is necessary to understand, state, or define `A`.
- `A APPLIED_IN B`: `A` is used in `B`.
- `A EXTENDS B`: `A` is a more specific, enriched, or advanced development of `B` while preserving `B` as its conceptual base.
- `A FORMALIZES B`: `A` is a Formula that defines, characterizes, expresses, or gives an update or solution condition for `B`.

`REQUIRES` includes definitional and conceptual dependency; it is not limited to formal course prerequisites. Mere mention or frequent co-occurrence does not establish `REQUIRES`.

For Experiment 002A v0.1, the source of every `FORMALIZES` relation must be a Knowledge Object of type `Formula`.

For `CONTRASTS_WITH`, choose a canonical direction in the benchmark. The evaluation protocol may allow reversed direction for this label only if specified in advance.

---

# Positive Pairs

Annotate a positive pair when the source and target have a clear educational relation supported by the input material.

Examples:

- `Gradient` `APPLIED_IN` `Gradient Descent`
- `Orthogonal Projection` `APPLIED_IN` `Least Squares Problem`
- `Conditional Probability` `REQUIRES` `Event`
- `Multivariable Chain Rule Formula` `FORMALIZES` `Chain Rule`

The exact label and direction must follow the frozen annotation rules, not intuition after seeing model output.

---

# Hard Negative Pairs

Hard negative pairs are related by broad subject area or mathematical maturity but should not receive a Relation under the current schema.

Examples:

- `Variance` and `Orthogonal Projection`
- `Basis` and `Conditional Probability`
- `Line Search` and `Bayes' Rule`

These should be labelled `NO_RELATION`.

Hard negatives are important because they test whether the model can avoid over-connecting the graph. The development set should include same-lecture or same-discipline negatives, not only obvious cross-discipline pairs. The current development target of roughly 25% negatives is a benchmark design choice, not a universal class prior.

---

# Ambiguous Pairs

Some pairs may have multiple plausible labels or directions.

Before running a model, each ambiguous pair must be handled in one of three ways:

- exclude it from primary scoring;
- define acceptable alternative labels;
- rewrite the pair or schema so the intended label is clear.

Do not decide ambiguity after seeing model outputs.

---

# Evidence Rules

Each positive Relation should include one or more evidence spans.

Rules:

- Evidence spans must be exact substrings of the referenced lecture.
- Evidence should support the relation, not merely mention one object.
- Cross-lecture relations may include evidence from both lectures.
- Do not use whole paragraphs when a shorter span is sufficient.
- `NO_RELATION` pairs may include optional notes but do not require evidence spans.

Evidence spans are Relation evidence. They are different from Knowledge Object source grounding.

---

# `RELATED_TO` Rules

Use `RELATED_TO` only when:

- the pair is educationally meaningful;
- evidence supports a real connection;
- no stronger relation label fits.

Do not use `RELATED_TO` for:

- vague co-occurrence;
- same lecture membership;
- same discipline membership;
- uncertainty about the correct stronger label.

If `RELATED_TO` becomes frequent, the schema or prompt likely needs revision.

The v0.1 development benchmark does not need positive examples for every proposed label. Unsupported labels must be reported as not covered rather than treated as validated. `RELATED_TO` may be monitored for overuse even when positive support is absent.

---

# Development Corpus

For Relation development, all six existing mini lectures may be used:

- `calculus_001`
- `linear_algebra_001`
- `optimisation_001`
- `calculus_002`
- `linear_algebra_002`
- `probability_001`

These lectures were already used during Entity Extraction work, so they should be treated as Relation development material, not Relation holdout material.

A future Relation holdout should use newly authored unseen snippets.

---

# Annotation Workflow

1. Select candidate pairs from ground-truth Knowledge Objects.
2. Label positive, hard negative, and ambiguous pairs before model execution.
3. Assign relation type and direction.
4. Add exact evidence spans for positive pairs.
5. Add a short rationale.
6. Freeze the development benchmark before comparing prompts.
7. Create a new unseen holdout only after prompt and evaluation rules are stable.
