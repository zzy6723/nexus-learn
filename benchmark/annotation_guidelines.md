# Annotation Guidelines

**Status:** Frozen  
**Version:** v0.1 (Frozen)  
**Created:** 2026-07-11  
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Purpose

This document defines how human ground truth should be annotated for Knowledge Object extraction.

The goal is not to create a complete STEM ontology. The goal is to create a consistent benchmark for evaluating whether an extraction system can identify useful Knowledge Objects from short STEM learning materials.

---

# Annotation Unit

The annotation unit is a Knowledge Object.

A Knowledge Object is a meaningful educational entity that may later participate in typed Relations or Connection Hypotheses.

---

# Object Categories

Each annotated object should be assigned one of three benchmark categories.

| Category | Meaning | Scoring |
| --- | --- | --- |
| `required` | The object is central to the snippet and should be extracted. | Counts toward recall. |
| `optional` | The object is grounded and useful, but not required for this snippet. | Does not hurt precision if extracted. |
| `excluded` | The object should not be extracted. | Counts as an error if extracted. |

The `optional` category exists because useful supporting objects can appear in a snippet without being the main teaching target.

---

# What Should Be Annotated

Annotate an object when it satisfies all of the following:

- It is a meaningful educational entity.
- It is explicitly named or clearly defined in the snippet.
- It could plausibly participate in a later typed Relation or Connection Hypothesis.
- It can be grounded in the source text.

Examples:

- `Gradient`
- `Vector Space`
- `Eigenvalue Equation`
- `Line Search`
- `Conditional Probability`

---

# What Should Not Be Annotated

Do not annotate:

- section headings by themselves;
- historical people;
- broad domains such as `mathematics`, `statistics`, or `optimisation`;
- isolated variables such as `x`, `n`, `k`, or `lambda`;
- raw paragraphs or chunks;
- generic words such as `method`, `value`, or `problem`;
- Relations;
- Connection Hypotheses;
- Connection-layer Evidence.

---

# Canonical Label Rules

Knowledge Object names should be concise, human-readable noun phrases.

Use:

- singular form where possible;
- standard mathematical capitalization;
- descriptive names rather than raw symbols.

Formula objects should use descriptive labels such as:

- `Eigenvalue Equation`
- `Gradient Descent Update`
- `Conditional Probability Formula`

The symbolic expression itself should be stored in `source_spans`, not used as the canonical label.

Mathematical symbols should not be used as aliases.

---

# Alias Rules

Aliases must refer to the same Knowledge Object as the canonical label.

Aliases may include:

- singular and plural variants;
- standard spelling variants;
- widely accepted alternative names.

Aliases must not include:

- mathematical symbols;
- broader or narrower concepts;
- related concepts;
- object descriptions;
- general categories.

For example, `dot product` should not be an alias for `Inner Product`, because a dot product is a specific standard inner product in Euclidean space rather than a synonym for all inner products.

---

# Type Rules

## Concept

Use `Concept` for mathematical, scientific, or technical constructs, properties, structures, or named ideas.

Examples:

- `Gradient`
- `Basis`
- `Convex Function`
- `Random Variable`

Named mathematical laws, rules, theorems, identities, and properties should normally be annotated as `Concept`.

Examples:

- `Chain Rule`
- `Bayes' Rule`
- `Characteristic Polynomial`

Named mathematical operations should normally be annotated as `Concept` unless the snippet presents them as an executable algorithm or systematic procedure.

Examples:

- `Matrix Multiplication`
- `Function Composition`

## Method

Use `Method` for procedures, algorithms, techniques, or approximation processes.

Examples:

- `Gradient Descent`
- `Line Search`
- `Orthogonal Projection`

Use `Method` only when the object describes an executable procedure, algorithm, technique, or systematic process.

## Formula

Use `Formula` for symbolic equations, update rules, or displayed mathematical expressions.

Examples:

- `Eigenvalue Equation`
- `Variance Formula`
- `Conditional Probability Formula`

A named mathematical construct should usually be annotated as `Concept`, even when it is associated with a formula.

Displayed equations should be annotated as `Formula` objects when they define, characterize, or update a concept or method.

---

# Supporting Objects

Supporting objects should be marked `optional` when they are:

- useful for later Relation Discovery;
- explicitly grounded in the snippet;
- not central enough to be required.

Examples from the development set:

- `Matrix Multiplication`
- `Gradient`

Optional objects should not be treated as false positives during evaluation.

---

# Source Spans

Each annotated object should include one or more `source_spans`.

Rules:

- Ground-truth source spans must be exact substrings of the source material.
- Keep spans short but informative.
- A span should justify why the object is present in the snippet.
- Do not use a whole paragraph when a shorter phrase or sentence is sufficient.
- Every listed ground-truth source span must occur exactly in the corresponding source material.

Exact source-span matching is evaluated separately from semantic grounding.

---

# Annotation Workflow

1. Read the snippet without looking at model outputs.
2. Mark required objects.
3. Mark optional supporting objects.
4. Mark excluded objects only when they are likely to be mistakenly extracted.
5. Assign object types.
6. Add aliases for predictable label variants.
7. Add source spans.
8. Freeze the ground truth before running models on holdout data.

---

# Holdout Rule

Holdout ground truth must be annotated before model outputs are inspected.

After holdout execution, ground truth should not be changed to make a prompt look better. If a genuine annotation error is discovered, create a new benchmark version and rerun the compared prompts under the same evaluation protocol.
