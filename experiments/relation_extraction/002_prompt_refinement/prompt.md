# Oracle-KO Typed Relation Extraction Refined Prompt

**Status:** Development candidate  
**Version:** v0.2  
**Created:** 2026-07-13

---

You identify typed educational Relations between known Knowledge Objects.

The Knowledge Objects are already provided. Do not create new Knowledge Objects.

For each unordered candidate pair, decide whether its two Knowledge Objects have one of the allowed Relation types. For a positive Relation, choose its source and target according to the direction rules.

Allowed graph Relation types:

- `REQUIRES`
- `APPLIED_IN`
- `EXTENDS`
- `CONTRASTS_WITH`
- `FORMALIZES`
- `RELATED_TO`

Benchmark-only label:

- `NO_RELATION`

`NO_RELATION` means no edge should be written to the product graph.

---

# Direction Rules

Use these direction conventions:

- `A REQUIRES B`: `B` is necessary to understand, state, or define `A`.
- `A APPLIED_IN B`: `A` is used in `B`.
- `A EXTENDS B`: `A` is a more specific, enriched, or advanced development of `B` while preserving `B` as its conceptual base.
- `A FORMALIZES B`: `A` is a Formula that explicitly defines, characterizes, expresses, or gives an update or solution condition for `B`.
- `A CONTRASTS_WITH B`: `A` and `B` are meaningfully contrasted.
- `A RELATED_TO B`: `A` and `B` have a meaningful but weak relation that does not fit a stronger type.

Do not use `RELATED_TO` merely because two objects appear in the same lecture.

If the source and target are not meaningfully related under the schema, return `NO_RELATION`.

Mere mention or frequent co-occurrence does not establish `REQUIRES` or any other graph Relation.

---

# Refinement Rules

Apply the following checks for every candidate pair. These checks are internal
decision steps; do not output the checks or any hidden reasoning.

## 1. Determine Semantic Roles Before Serializing Endpoints

Before writing `source` and `target`, verify the selected Relation in its canonical
form:

- `source REQUIRES target`: source is the dependent object; target is the
  prerequisite.
- `source APPLIED_IN target`: source is the tool or idea being used; target is the
  application context that uses it.
- `source EXTENDS target`: source is the more specific or enriched development;
  target is its conceptual base.
- `source FORMALIZES target`: source is the Formula; target is the object that the
  Formula defines, characterizes, expresses, updates, or gives a solution
  condition for.

Verify that the serialized endpoint order matches the selected statement. Do not
copy the `ko_a` / `ko_b` order.

## 2. Prefer FORMALIZES When a Formula Supplies the Formal Condition

When one candidate is a Formula and the supplied evidence directly presents that
Formula as the definition, expression, update rule, characterization, or solution
condition of the other object, prefer `FORMALIZES` over `APPLIED_IN`.

Do not use `FORMALIZES` merely because a formula contains a symbol associated with
the other object. The evidence must establish what the Formula expresses or
formalizes.

## 3. Apply an Evidence-First Positive Gate

Before assigning any graph Relation, identify an exact evidence set from the
provided lecture text that establishes the Relation between the two candidate
objects.

Two separate spans that merely describe the objects do not establish a Relation.
Do not rely on outside STEM knowledge, an unstated intermediate concept, or a
mathematically plausible inference that is absent from the supplied material.

If no exact evidence set establishes the candidate Relation, return
`NO_RELATION`.

## 4. Prefer NO_RELATION to Weak or Indirect Inference

The same lecture, topic, notation, formula, or surrounding context is not by
itself sufficient evidence of a Relation. Conceptual proximity and co-occurrence
are also insufficient.

Use `NO_RELATION` when the supplied material does not directly support one of the
defined graph Relations, even if the objects seem broadly related.

## 5. Do Not Use RELATED_TO as an Uncertainty Label

`RELATED_TO` is a positive graph Relation, not an uncertainty or fallback label.
Use it only when the supplied evidence directly establishes a meaningful
educational connection and none of the stronger Relation types applies.

When uncertainty comes from insufficient or indirect evidence, use
`NO_RELATION`.

## 6. Make the Evidence Set Self-Contained and Consistent

The selected evidence spans, read together without relying on omitted sentences,
must identify both objects or otherwise make their Relation unambiguous. Include
multiple exact spans when they are needed to establish the connection.

Avoid unresolved references such as "this method", "this formula", "this
direction", or "it" unless another selected span or an unambiguous formula in the
selected evidence resolves the reference.

The rationale must be supported by the selected evidence. If the rationale would
say that the lecture does not directly establish the connection, return
`NO_RELATION` rather than a positive Relation.

---

# Input Format

The input contains:

- relevant lecture text;
- known Knowledge Objects with names, types, and source grounding;
- unordered candidate pairs.

The input follows this structure:

```json
{
  "lectures": [
    {"lecture_id": "string", "text": "lecture text"}
  ],
  "knowledge_objects": [
    {
      "lecture_id": "string",
      "ko_id": "string",
      "name": "string",
      "type": "Concept | Method | Formula",
      "source_spans": ["string"]
    }
  ],
  "candidate_pairs": [
    {
      "pair_id": "opaque string",
      "ko_a": {"lecture_id": "string", "ko_id": "string"},
      "ko_b": {"lecture_id": "string", "ko_id": "string"}
    }
  ]
}
```

The order of `ko_a` and `ko_b` does not indicate Relation direction. Do not infer direction from `pair_id` or input order.

Do not omit, duplicate, or create candidate pairs. For each positive Relation, choose the fully qualified `source` and `target` references according to the Relation direction rules. For `NO_RELATION`, either candidate order is acceptable.

---

# Evidence Rules

For positive Relations:

- provide evidence spans copied exactly from the input lecture text;
- evidence must support the relation, not merely mention one object;
- cross-lecture relations may use evidence from both lectures.

For `NO_RELATION`:

- use an empty `evidence_spans` array;
- explain briefly why no graph edge should be created.

---

# Output Format

Return only valid JSON.

Do not include Markdown fences or explanatory prose outside the JSON.

Use this schema:

```json
{
  "results": [
    {
      "pair_id": "string",
      "source": {"lecture_id": "string", "ko_id": "string"},
      "target": {"lecture_id": "string", "ko_id": "string"},
      "relation_type": "REQUIRES | APPLIED_IN | EXTENDS | CONTRASTS_WITH | FORMALIZES | RELATED_TO | NO_RELATION",
      "evidence_spans": [
        {
          "lecture_id": "string",
          "span": "exact substring from the input"
        }
      ],
      "rationale": "one or two sentences"
    }
  ]
}
```

Return exactly one result for each candidate pair.
