# ADR-003: Knowledge Object

**Status:** Accepted  
**Version:** v0.2  
**Date:** 2026-07-12  
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Context

The project aims to support Learning Continuity by reconnecting newly acquired knowledge with previously learned concepts across time, courses, and disciplines.

Before the system can discover Relations or propose Connection Hypotheses, it needs stable units of knowledge that can participate in later typed connections.

The first technical validation focused on Knowledge Object extraction using development and holdout mini lecture benchmarks:

- `experiments/entity_extraction/001_baseline`
- `experiments/entity_extraction/002_prompt_refinement`

Development validation was used for prompt iteration and error analysis. Holdout validation was then run under the frozen benchmark and evaluation protocol.

On holdout, the baseline and refined prompts achieved the same required-object precision, recall, F1 score, and required-object type accuracy. The refined prompt did not improve object identification or type classification on unseen materials, but it improved exact source grounding on the current holdout benchmark.

This ADR defines the initial Knowledge Object model for the MVP.

---

# Decision

A Knowledge Object is a structured representation of a meaningful educational entity.

Knowledge Objects may participate in Relations and Connections, but they do not themselves own learning Evidence.

Evidence belongs to the Connection layer because Evidence justifies why two or more Knowledge Objects are related. A Knowledge Object may have source grounding, but source grounding is not the same thing as Connection-layer Evidence.

For the next Technical Validation stage, `experiments/entity_extraction/002_prompt_refinement/prompt.md` is the default Knowledge Object extraction prompt.

This prompt is selected because it improved exact `source_span` grounding on the current holdout benchmark without reducing required-object precision, recall, F1 score, required-object type accuracy, false-positive count, or false-negative count. It is not selected because it improved object coverage or type classification.

---

# Scope Boundary

For the initial MVP, Knowledge Object extraction is limited to English text or Markdown STEM learning snippets.

The current validation evidence applies only to short, authored STEM lecture snippets. It does not establish general STEM-wide extraction performance.

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

Entity extraction validation showed that prompt engineering alone did not fully solve exact source-span grounding.

---

# Supporting Objects

Useful supporting objects may be extracted if they satisfy all of the following:

- They are explicitly named or clearly explained in the source material.
- They are meaningful educational entities.
- They are likely to support later typed Relations or Connection Hypotheses.

Examples from development prompt refinement:

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

# Validation Evidence

Entity Extraction validation is recorded in:

- `experiments/entity_extraction/holdout_comparison.md`

The holdout comparison used:

- ground truth: `benchmark/ground_truth/holdout_v0_1.json`;
- baseline prompt: `experiments/entity_extraction/001_baseline/prompt.md`;
- refined prompt: `experiments/entity_extraction/002_prompt_refinement/prompt.md`;
- model: `deepseek-v4-flash`;
- temperature: `0.0`;
- top-p: `1.0`;
- max tokens: `4096`.

Holdout aggregate results:

| Metric | `001_baseline` | `002_prompt_refinement` |
| --- | ---: | ---: |
| Required precision | 1.000 | 1.000 |
| Required recall | 0.950 | 0.950 |
| Required F1 | 0.974 | 0.974 |
| Required type accuracy | 0.895 | 0.895 |
| False positives | 0 | 0 |
| False negatives | 1 | 1 |
| Exact source-span rate | 0.476 | 0.762 |

The result supports the operational viability of Knowledge Object extraction for the MVP on the current benchmark of short, authored STEM lecture snippets.

The result does not show that:

- the schema is a complete STEM ontology;
- the approach generalizes to long documents, parsed PDFs, noisy text, or all STEM disciplines;
- Knowledge Object extraction is stable across repeated runs;
- Relation Extraction or Connection Discovery is solved.

Known remaining limitations include type-boundary ambiguity and exact Markdown or LaTeX span preservation.

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
- The object types match current MVP benchmark evidence.
- Supporting objects can be captured without turning extraction into raw chunking.
- The selected extraction prompt has better exact source grounding on the current holdout benchmark than the baseline.

## Negative

- Some educational entities may be forced into broad types.
- The `Concept`, `Method`, and `Formula` boundaries require careful evaluation.
- Exact source grounding is not solved by the schema alone.
- Future STEM materials may require additional object types.
- Run-to-run stability has not yet been validated.

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
- `benchmark/ground_truth/holdout_v0_1.json`
- `benchmark/annotation_guidelines.md`
- `benchmark/evaluation_protocol.md`
- `experiments/entity_extraction/holdout_comparison.md`
