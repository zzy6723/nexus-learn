# Learning Explanation Contract

**Status:** Ready for 004-0 freeze review
**Version:** v0.2

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

The v0.2 output is:

```json
{
  "explanation_instance_id": "copy exactly",
  "source_ko_id": "copy exactly",
  "relation_type": "copy exactly",
  "target_ko_id": "copy exactly",
  "connection_summary": {
    "text": "one concise learner-facing sentence",
    "evidence_refs": []
  },
  "why_connected": {
    "text": "evidence-grounded conceptual mechanism",
    "evidence_refs": ["copy one or more supplied Evidence IDs"]
  },
  "learning_value": {
    "text": "generic educational value without personalization",
    "evidence_refs": []
  }
}
```

IDs, Relation type, and endpoint order are immutable transport fields.
Evidence references are field-local: they state which supplied Evidence entries
support that field's substantive STEM claims.

## Field Semantics

`connection_summary`
: States the supplied typed Connection in learner-facing language. It must not
  weaken, strengthen, reverse, or replace the Relation. Its `evidence_refs` may
  be empty when the sentence only paraphrases the fixed Relation.

`why_connected`
: Explains the mechanism established by the supplied Evidence. It must remain
  about the exact source and target objects. Under the Evidence-grounded method,
  its `evidence_refs` must contain at least one supplied Evidence ID.

`learning_value`
: Explains how understanding this Connection can help a generic learner
  transfer, organize, interpret, or apply knowledge. It must not invent learner
  history, mastery, goals, mistakes, outcomes, or recommendations. Its
  `evidence_refs` may be empty when it makes only a bounded generic
  pedagogical inference.

`evidence_refs`
: References only supplied Evidence entries used by that field. The runner
  materializes exact spans deterministically; the model never copies or edits
  Evidence text as an authoritative artifact. A field must not cite Evidence
  that does not support its substantive claims.

## Method-Specific Evidence Contract

`001a_deterministic_paraphrase`
: Receives only immutable Connection fields. All `evidence_refs` arrays must be
  empty.

`001b_relation_only_llm`
: Receives immutable Connection fields but no Evidence IDs or Evidence text.
  All `evidence_refs` arrays must be empty. This is a no-Evidence hallucination
  control and cannot be selected as the Experiment 004 method.

`002_evidence_grounded`
: Receives immutable Connection fields and the supplied Evidence catalog.
  `why_connected.evidence_refs` must contain at least one valid supplied ID.

## Hard Boundaries

An output is invalid when it:

- changes any immutable transport field;
- references an unknown Evidence ID;
- references any Evidence ID under a no-Evidence method;
- omits Evidence from `why_connected` under the Evidence-grounded method;
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

`PEDAGOGICAL_OVERREACH`
: The learning-value account makes ungrounded claims about typical learner
  difficulties, study order, mastery, outcomes, or instructional effectiveness.

These errors are not mutually exclusive.

## Claim Boundary

Faithfulness is evaluated at the substantive-claim level under
`benchmark/learning_explanation_annotation_guidelines.md`. Surface fluency,
tone, and length do not make an unsupported claim acceptable.
