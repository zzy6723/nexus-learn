# ADR-003: Knowledge Object

**Status:** Accepted  
**Version:** v0.1  
**Date:** 2026-07-10  
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Context

The project aims to support Learning Continuity by reconnecting newly acquired knowledge with previously learned concepts across time, courses, and disciplines.

Before the system can discover Relations or propose Connection Hypotheses, it needs stable units of knowledge that can participate in later typed connections.

The first technical validation focused on Knowledge Object extraction:

- `experiments/entity_extraction/001_baseline`
- `experiments/entity_extraction/002_prompt_refinement`

Experiment 002 extracted all 26 ground-truth objects across the active benchmark and assigned correct provisional types to all matched objects. It also exposed important boundary questions around useful supporting objects and exact source grounding.

This ADR defines the initial Knowledge Object model for the MVP.

---

# Decision

A Knowledge Object is a structured representation of a meaningful educational entity.

Knowledge Objects may participate in Relations and Connections, but they do not themselves own learning Evidence.

Evidence belongs to the Connection layer because Evidence justifies why two or more Knowledge Objects are related. A Knowledge Object may have source grounding, but source grounding is not the same thing as Connection-layer Evidence.

---

# Scope Boundary

For the initial MVP, Knowledge Object extraction is limited to English text or Markdown STEM learning snippets.

The following are out of scope for this ADR:

- PDF parsing
- multimodal extraction
- multilingual extraction
- personalized Learner State
- Relation extraction
- Connection Hypothesis generation
- Evidence generation

These may be introduced later after the text-only extraction boundary is validated.

---

# Initial Object Types

The MVP uses three initial Knowledge Object types.

| Type | Definition | Examples |
| --- | --- | --- |
| `Concept` | A mathematical, scientific, or technical construct, property, structure, or named idea. | `Gradient`, `Vector Space`, `Characteristic Polynomial`, `Stationary Point` |
| `Method` | A procedure, algorithm, technique, or approximation process. | `Gradient Descent`, `Line Search`, `Taylor Approximation` |
| `Formula` | A symbolic equation, update rule, displayed mathematical expression, or formula that defines or characterizes an object. | `Eigenvalue Equation`, `Gradient Descent Update`, `Conditional Probability Formula` |

These types are intentionally minimal. More types should only be added after experiments show that the current schema cannot represent important STEM learning objects.

This decision establishes an initial working schema for the MVP and Technical Validation phase. It does not claim that these three types form a complete ontology for all STEM knowledge.

---

# Type Boundary Rules

## Concept

Use `Concept` for named mathematical objects, properties, structures, and constructs.

Examples:

- `Gradient`
- `Matrix`
- `Eigenvalue`
- `Characteristic Polynomial`
- `Convex Function`

A named mathematical construct should usually remain a `Concept` even when it is closely associated with a formula.

Named mathematical laws, rules, theorems, identities, and properties should normally be represented as `Concept` unless the object describes an executable procedure.

## Method

Use `Method` for procedures, algorithms, techniques, or approximation processes.

Examples:

- `Gradient Descent`
- `Line Search`
- `Taylor Approximation`

## Formula

Use `Formula` for symbolic equations, update rules, or displayed mathematical expressions.

Examples:

- `Eigenvalue Equation`
- `Gradient Descent Update`
- `Conditional Probability Formula`

Formula object names should use human-readable descriptive labels. The symbolic expression itself should be stored in source grounding.

Displayed equations should usually be extracted as `Formula` objects when they define, characterize, or update a concept or method.

---

# Minimal Schema

The initial schema is:

```json
{
  "id": "lower_snake_case_stable_identifier",
  "name": "Canonical Name",
  "type": "Concept | Method | Formula",
  "aliases": ["optional alias"],
  "short_definition": "One sentence definition based on source material.",
  "source_refs": [
    {
      "lecture_id": "calculus_001",
      "source_span": "Exact or semantically grounded text span from the source material."
    }
  ]
}
```

Implementation experiments may temporarily use a flatter schema with `source_span` directly on the object. Production code should prefer `source_refs` so that the same Knowledge Object can be grounded in multiple materials over time.

---

# Identity Rules

Knowledge Objects should use a stable canonical identity.

Rules:

- `id` uses lower snake case.
- `name` uses a human-readable canonical name.
- `aliases` store notation variants or common alternative names.
- Duplicates should be merged into one object when they refer to the same educational entity.
- The same Knowledge Object may appear in multiple courses or lectures.

Examples:

```json
{
  "id": "gradient",
  "name": "Gradient",
  "type": "Concept",
  "aliases": ["nabla f(x)"]
}
```

```json
{
  "id": "gradient_descent_update",
  "name": "Gradient Descent Update",
  "type": "Formula",
  "aliases": []
}
```

---

# Source Grounding

Each extracted Knowledge Object should be grounded in source material.

Source grounding records where the object came from. It is used to make extraction auditable.

Source grounding is not Evidence in the glossary sense.

Rules:

- Prefer exact source spans copied from the input.
- If exact spans are not possible due to notation normalization, semantic grounding may be recorded during experiments.
- Automated evaluation should distinguish exact source-span matches from semantic source grounding.
- Future implementation may need deterministic span matching, LaTeX normalization, or post-processing.

Experiment 002 showed that prompt engineering alone did not fully solve exact source-span grounding.

---

# Supporting Objects

Useful supporting objects may be extracted if they satisfy all of the following:

- They are explicitly named or clearly explained in the source material.
- They are meaningful educational entities.
- They are likely to support later typed Relations or Connection Hypotheses.

Examples from Experiment 002:

- `Matrix Multiplication`
- `Gradient`

These were not included in the initial ground truth but are useful for later Relation Discovery. Future benchmark versions should decide whether such supporting objects are included in ground truth or tracked separately.

---

# Exclusion Rules

Do not extract:

- broad domains, such as `mathematics` or `optimization theory`;
- section headings;
- historical people;
- isolated variables, such as `x`, `n`, or `k`;
- raw paragraphs or chunks;
- generic ordinary words;
- Relations;
- Connection Hypotheses;
- Evidence.

---

# Alternatives Considered

## Chunk-based Memory

The system could store lecture chunks directly and retrieve them later.

Rejected because chunk storage supports document retrieval but does not provide stable educational entities for typed learning connections.

## Extract Every Noun Phrase

The system could extract many candidate entities and rely on later filtering.

Rejected because this would increase graph size without improving connection quality.

## Evidence Owned by Knowledge Objects

The system could attach Evidence directly to each Knowledge Object.

Rejected because Evidence should justify why a Connection exists. A single Knowledge Object can be source-grounded, but it does not by itself explain a learning connection.

## Large Ontology from the Start

The system could start with many object types, such as theorem, definition, algorithm, property, example, and dataset.

Rejected for the MVP because the initial experiments only justify a smaller schema. Additional types should be introduced only when they improve extraction quality or downstream Relation Discovery.

---

# Consequences

## Positive

- The system has stable units for Relation Discovery.
- The schema is simple enough to evaluate.
- The boundary between Knowledge Objects and Connection-layer Evidence is clear.
- The object types match early experimental evidence.
- Supporting objects can be captured without turning extraction into raw chunking.

## Negative

- Some educational entities may be forced into broad types.
- The `Concept` vs `Formula` boundary requires careful evaluation.
- Exact source grounding is not solved by the schema alone.
- Future STEM materials may require additional object types.

---

# Evaluation Implications

Entity extraction experiments should evaluate:

- object precision;
- object recall;
- type accuracy;
- duplicate rate;
- useful extra objects;
- source grounding quality;
- whether outputs are usable for Relation Discovery.

Evaluation should avoid rewarding graph size alone. Connection quality remains more important than the number of extracted objects.

---

# References

- `docs/glossary.md`
- `docs/product_definition.md`
- `experiments/entity_extraction/001_baseline`
- `experiments/entity_extraction/002_prompt_refinement`
- `benchmark/ground_truth/development_v0_1.json`
