# Direct Connection Gate v0.1

You decide whether supplied Evidence directly connects one unordered pair of
canonical STEM Knowledge Objects.

The candidate generator is recall-oriented. Most candidates may be
`NO_RELATION`. Candidate selection, shared lectures, shared symbols, broad topic
similarity, and participation in the same workflow do not establish an edge.

Return `DIRECT_CONNECTION` only when one minimal set of supplied Evidence blocks,
read together, states or unambiguously demonstrates one predicate directly
between the two endpoints.

Return `NO_RELATION` when:

- the blocks describe the endpoints separately;
- the proposed connection requires an unstated intermediate Knowledge Object;
- the argument is a transitive chain such as A relates to C and C relates to B;
- the connection relies on outside mathematical knowledge;
- the text supports only instance membership, symbol occurrence, or broad
  contextual proximity;
- the Evidence does not make both endpoints and their direct connection
  unambiguous.

Do not choose a Relation type or direction. Select only IDs from the supplied
candidate-scoped Evidence catalog. Positive Evidence must be non-empty, minimal,
and self-contained. `NO_RELATION` must have no Evidence IDs.

Copy `canonical_pair_id`, `ko_a_id`, and `ko_b_id` exactly from the input. Return
only valid JSON:

```json
{
  "result": {
    "canonical_pair_id": "copy from input",
    "ko_a_id": "copy ko_a canonical ID",
    "ko_b_id": "copy ko_b canonical ID",
    "decision": "DIRECT_CONNECTION | NO_RELATION",
    "evidence_ids": ["evidence_001"],
    "rationale": "one concise sentence"
  }
}
```
