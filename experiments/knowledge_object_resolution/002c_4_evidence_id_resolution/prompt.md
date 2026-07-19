# Context-Aware Knowledge Object Identity Resolver v0.2

Decide whether two lecture-local Knowledge Object mentions denote the same
educational object at the same granularity.

The candidate pair is unordered. Use both names, Knowledge Object types,
upstream source spans, and the supplied evidence catalog. Return exactly one
JSON object with:

```json
{
  "candidate_id": "copy exactly",
  "mention_a": "copy exactly",
  "mention_b": "copy exactly",
  "decision": "SAME_OBJECT | DISTINCT_OBJECT | UNRESOLVED",
  "evidence_ids": ["copy one or more supplied evidence IDs"],
  "rationale": "short semantic identity explanation"
}
```

Decision rules:

- `SAME_OBJECT`: both mentions denote the same educational object and have the
  same granularity. Abbreviations, orthographic variants, descriptive
  qualifiers, and symbolic/natural-language names may still be the same.
- `DISTINCT_OBJECT`: the mentions denote different objects, even if their names
  are identical or they are closely related in the subject.
- `UNRESOLVED`: the supplied evidence is insufficient to make either decision
  safely. Prefer this over an unsupported merge.

Identity is stricter than topical relatedness. A Method and its Formula, a
Concept and its formal expression, or two domain-specific senses of the same
word are not the same object. Matching type alone is not evidence of identity.

For a resolved decision, select only IDs present in `evidence_catalog`. Read
the selected entries together: they must make the identity decision
understandable. Do not copy evidence text into the response and do not invent
IDs. For `UNRESOLVED`, an empty evidence list is allowed. Return JSON only.
