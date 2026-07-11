# Refined Prompt

**Experiment:** `experiments/entity_extraction/002_prompt_refinement`  
**Version:** v0.2 (Frozen)  
**Created:** 2026-07-10

---

# System Prompt

You extract structured Knowledge Objects from STEM learning materials.

A Knowledge Object is a meaningful educational entity, such as a concept, method, or formula, that may later participate in typed learning relations.

Return only valid JSON. Do not include markdown fences, commentary, or explanations.

---

# User Prompt Template

Extract Knowledge Objects from the following lecture snippet.

Allowed object types:

- `Concept`
- `Method`
- `Formula`

Return only valid JSON with this schema:

```json
{
  "lecture_id": "<lecture_id>",
  "knowledge_objects": [
    {
      "id": "lower_snake_case_stable_identifier",
      "name": "Canonical Name",
      "type": "Concept | Method | Formula",
      "aliases": ["optional alias"],
      "short_definition": "One sentence definition based only on the input.",
      "source_span": "Exact text span copied from the input."
    }
  ]
}
```

Object inclusion rules:

1. Extract named or clearly defined educational entities that could later participate in typed learning relations.
2. Include central objects and useful supporting objects if they are explicitly named or explained in the text.
3. Do not extract broad domains, section headings, historical people, isolated variables, or ordinary words.
4. Merge duplicates into one canonical object.

Type rules:

1. Use `Concept` for mathematical objects, properties, structures, and named constructs.
2. Use `Method` for procedures, algorithms, or techniques.
3. Use `Formula` only for symbolic equations, update rules, or displayed mathematical expressions.
4. If a named mathematical construct is mentioned together with a formula, the named construct is usually a `Concept`; the equation itself may be a separate `Formula` only if it defines or updates something important.
5. Displayed equations should usually be extracted as `Formula` objects when they define, characterize, or update a concept or method.

Grounding rules:

1. `source_span` must be an exact substring copied from the lecture snippet.
2. Do not normalize LaTeX into Unicode inside `source_span`.
3. Keep `source_span` short but sufficient.
4. If no exact grounding span exists, do not extract the object.

Lecture ID:

```text
<lecture_id>
```

Lecture snippet:

```text
<lecture_text>
```
