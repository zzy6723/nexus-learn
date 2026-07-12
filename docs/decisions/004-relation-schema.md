# ADR-004: Relation Schema

**Status:** Proposed
**Version:** v0.1
**Date:** 2026-07-12
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Context

ADR-003 defines Knowledge Objects as the stable educational entities used by the MVP.

The next Technical Validation stage evaluates whether the system can identify typed educational Relations between Knowledge Objects.

This ADR defines the initial Relation schema for Experiment 002A: Oracle-KO Typed Relation Extraction.

Experiment 002A uses human-annotated Knowledge Objects as input so that Relation typing can be evaluated without mixing in Knowledge Object extraction errors.

---

# Decision

A Relation is a typed, machine-readable edge between two Knowledge Objects.

The MVP starts with a small Relation schema:

| Type | Directional Meaning |
| --- | --- |
| `REQUIRES` | The source has a definitional or conceptual dependency on the target. |
| `APPLIED_IN` | The source object is used or applied in the target object, method, or problem context. |
| `EXTENDS` | The source is a more specific, enriched, or advanced development of the target while preserving it as a conceptual base. |
| `CONTRASTS_WITH` | The source and target are meaningfully contrasted. This is semantically symmetric but stored in one canonical direction. |
| `FORMALIZES` | The source is a Formula that explicitly defines, characterizes, expresses, or gives an update or solution condition for the target. |
| `RELATED_TO` | The source and target have a meaningful but weak relation that does not fit the stronger labels. |

`NO_RELATION` is not a graph Relation type. It is a benchmark label used during evaluation to mark candidate pairs that should not become graph edges.

---

# Direction Rules

Relations are directional unless explicitly documented otherwise.

`A REQUIRES B` means `B` is necessary to understand, state, or define `A`. Mere mention or frequent co-occurrence does not establish this dependency.

`A APPLIED_IN B` means `A` is used in `B`.

`A EXTENDS B` means `A` is a more specific, enriched, or advanced development of `B` while preserving `B` as its conceptual base.

`A FORMALIZES B` means `A` is a Knowledge Object of type `Formula` that explicitly defines, characterizes, expresses, or provides an update or solution condition for `B`.

`A CONTRASTS_WITH B` should be stored using the canonical pair order from the benchmark. Evaluation may treat reversed direction as acceptable only when the protocol explicitly says so.

---

# Relation Quality Rules

Relations should be:

- typed;
- directional when applicable;
- supported by evidence spans from the input material;
- educationally meaningful;
- useful for later Connection Discovery.

The system should not create a Relation merely because two objects appear in the same lecture.

`RELATED_TO` is allowed only as a weak fallback. A high rate of `RELATED_TO` is a product-quality problem because it creates edges without explaining useful learning structure.

---

# Scope Boundary

This schema is for initial Technical Validation only.

It does not yet cover:

- personalized Learner State;
- ranking Connection Hypotheses;
- long-document relation discovery;
- relation extraction from noisy parsed PDFs;
- evidence quality beyond source-span grounding and brief rationale;
- end-to-end propagation from predicted Knowledge Objects.

---

# Evaluation Implications

Experiment 002A should evaluate:

- strict edge accuracy, combining type and direction;
- relation type accuracy;
- relation direction accuracy;
- `NO_RELATION` accuracy;
- per-type confusion;
- `RELATED_TO` fallback rate;
- unsupported relation count;
- exact evidence-span rate;
- whether evidence supports the Relation;
- manual adjudication count.

Experiment 002B should later evaluate how errors from Knowledge Object extraction affect Relation Extraction.

---

# Consequences

## Positive

- The schema is small enough to annotate and evaluate.
- `NO_RELATION` prevents the model from being forced to create edges for every candidate pair.
- `FORMALIZES` gives formula objects a useful role without forcing them into `RELATED_TO`.
- Oracle-KO evaluation isolates Relation typing from Knowledge Object extraction errors.

## Negative

- `EXTENDS` may need tighter subdivision after error analysis.
- `RELATED_TO` can become a low-quality fallback if not monitored.
- Some STEM relations may not fit the initial schema cleanly.
- The development benchmark does not yet provide positive coverage of every proposed Relation type.
- Direction rules will require careful annotation and adjudication.

---

# References

- `docs/glossary.md`
- `docs/decisions/003-knowledge-object.md`
- `benchmark/relation_annotation_guidelines.md`
- `benchmark/relation_evaluation_protocol.md`
- `benchmark/ground_truth/relations_development_v0_1.json`
- `experiments/relation_extraction/README.md`
