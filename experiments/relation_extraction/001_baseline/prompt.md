# Oracle-KO Typed Relation Extraction Baseline Prompt

**Status:** Draft  
**Version:** v0.1  
**Created:** 2026-07-12

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
