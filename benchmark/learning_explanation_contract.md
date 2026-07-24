# Learning Explanation Contract

**Status:** Ready for 004-0 review
**Version:** v0.1

## Capability

A Learning Explanation turns one validated typed Connection into a
learner-facing account of:

1. what connects the two exact Knowledge Objects;
2. why the supplied Relation holds under the supplied Evidence;
3. why understanding that Connection is useful for learning.

The capability is explanatory. It is not discovery, classification, ranking,
recommendation, or personalization.

## Oracle Input

Each input contains exactly one validated Connection instance:

- `explanation_instance_id`;
- canonical source KO ID, name, and type;
- canonical target KO ID, name, and type;
- frozen Relation type and direction;
- one or more opaque Evidence IDs;
- the exact Evidence catalog entries referenced by those IDs.

The model must not receive:

- alternative candidate Relations;
- Connection Discovery predictions;
- gold scoring fields or rubric decisions;
- source annotation rationale, provenance stratum, scope flags, or data role;
- reference explanation prose;
- learner history or Learner State;
- success thresholds.

`connection_instances.json` is an annotation and evaluation artifact, not a
model-ready payload. A future runner must use an explicit whitelist and render
only:

- explanation instance ID;
- source KO ID, name, and type;
- Relation type;
- target KO ID, name, and type;
- supplied Evidence IDs, lecture IDs, and exact spans.

All other instance fields are forbidden from the model request.

## Output

The v0.1 output is:

```json
{
  "explanation_instance_id": "copy exactly",
  "source_ko_id": "copy exactly",
  "relation_type": "copy exactly",
  "target_ko_id": "copy exactly",
  "connection_summary": "one concise learner-facing sentence",
  "why_connected": "evidence-grounded conceptual mechanism",
  "learning_value": "generic educational value without personalization",
  "evidence_ids": ["copy one or more supplied IDs"]
}
```

IDs, Relation type, and endpoint order are immutable transport fields.

## Field Semantics

`connection_summary`
: States the supplied typed Connection in learner-facing language. It must not
  weaken, strengthen, reverse, or replace the Relation.

`why_connected`
: Explains the mechanism established by the supplied Evidence. It must remain
  about the exact source and target objects.

`learning_value`
: Explains how understanding this Connection can help a generic learner
  transfer, organize, interpret, or apply knowledge. It must not invent learner
  history, mastery, goals, mistakes, or recommendations.

`evidence_ids`
: References only supplied Evidence entries used by the explanation. The
  runner materializes exact spans deterministically; the model never copies or
  edits Evidence text as an authoritative artifact.

## Hard Boundaries

An output is invalid when it:

- changes any immutable transport field;
- references an unknown Evidence ID;
- omits a required field;
- returns non-JSON content;
- contains an empty explanation field;
- returns additional undeclared fields.

A schema-valid output may still fail semantic evaluation.

## Semantic Failure Taxonomy

`RELATION_DISTORTION`
: The explanation changes the supplied Relation meaning.

`DIRECTION_REVERSAL`
: The explanation assigns source and target the opposite semantic roles.

`EVIDENCE_OVERREACH`
: A substantive claim is unsupported by the supplied Evidence or fixed
  Connection.

`ENDPOINT_DRIFT`
: The explanation substitutes a broader, narrower, associated, or intermediate
  object for an exact endpoint.

`CONTRADICTION`
: A claim conflicts with the supplied Evidence or Connection.

`PEDAGOGICALLY_EMPTY`
: The output is faithful but only paraphrases the Relation and provides no
  meaningful conceptual mechanism or learning value.

These errors are not mutually exclusive.

## Claim Boundary

Faithfulness is evaluated at the substantive-claim level under
`benchmark/learning_explanation_annotation_guidelines.md`. Surface fluency,
tone, and length do not make an unsupported claim acceptable.
