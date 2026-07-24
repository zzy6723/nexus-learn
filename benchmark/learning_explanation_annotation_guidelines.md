# Learning Explanation Annotation Guidelines

**Status:** Ready for 004-0 freeze review
**Version:** v0.2

## Unit Of Review

The evaluation unit is one explanation of one validated Connection. Reviewers
must not reconsider whether the supplied gold Connection should exist.

## Substantive Claim Segmentation

A substantive claim is a proposition whose truth affects the explanation's
mathematical, relational, or educational meaning. Segment a sentence into
multiple claims when its clauses could be true or false independently.

Count claims about:

- endpoint definitions or roles;
- the supplied Relation and direction;
- mathematical or computational mechanism;
- applicability, consequence, or comparison;
- why the Connection helps learning.

Do not count:

- headings or discourse markers;
- purely stylistic transitions;
- restatements that add no proposition;
- Evidence IDs themselves.

Example:

> The gradient supplies the local linear term, so Taylor approximation helps
> predict nearby change.

This contains two claims:

1. the gradient supplies the local linear term;
2. first-order Taylor approximation predicts nearby change.

## Claim Support Labels

`SOURCE_GROUNDED`
: The supplied Evidence explicitly states or formally displays the claim.

`RELATION_ENTAILED`
: The claim follows from the frozen Relation semantics and exact endpoint
  roles without adding a new STEM fact.

`GENERIC_PEDAGOGICAL_INFERENCE`
: The claim states a bounded educational benefit that follows from the
  Connection without asserting learner-specific facts. Examples include that
  recognizing a prerequisite can organize dependencies, or that connecting a
  formula to a method can help interpret notation operationally.

`UNSUPPORTED`
: The claim adds a factual, causal, comparative, performance, or learner claim
  not established by the Evidence and fixed Connection.

`CONTRADICTED`
: The claim conflicts with the Evidence, Relation, endpoint roles, or direction.

`UNRESOLVED`
: The reviewer cannot determine support under the frozen material.

`SOURCE_GROUNDED`, `RELATION_ENTAILED`, and
`GENERIC_PEDAGOGICAL_INFERENCE` count as supported. `UNRESOLVED` enters
adjudication and never silently counts as supported.

Claims about what learners typically misunderstand, what they should study
next, whether they will improve, or what instructional intervention works are
not bounded generic inferences unless the supplied material directly supports
them.

## Faithfulness Dimensions

### Relation Faithfulness

Pass when the explanation preserves the exact Relation semantics.

### Direction Faithfulness

Pass when the source and target retain their supplied roles. Symmetric
`CONTRASTS_WITH` may be phrased in either order but must preserve a symmetric
contrast.

### Endpoint Faithfulness

Pass when all substantive reasoning concerns the exact canonical endpoints.
Mentioning an intermediate object is allowed only to explain Evidence already
supplied and must not replace an endpoint.

### Evidence Faithfulness

Pass when every substantive STEM claim is supported and every cited Evidence
ID is supplied to that field. Generic pedagogical inference is allowed only
under the label above. Under a no-Evidence method, Evidence faithfulness is
reported as `not_applicable`, not silently treated as a pass.

### Contradiction

Any contradicted claim fails the explanation-level faithfulness gate.

## Learning-Value Rubric

Score each dimension from 0 to 2 only after the faithfulness gate passes.

### Conceptual Mechanism

- `0`: only restates the Relation;
- `1`: gives a correct but shallow mechanism;
- `2`: clearly explains how the exact endpoints interact.

### Learning Relevance

- `0`: no meaningful account of why the Connection helps learning;
- `1`: generic but applicable value;
- `2`: specific transfer, interpretation, organization, or application value
  grounded in this Connection.

### Specificity

- `0`: generic wording reusable for almost any pair;
- `1`: names the endpoints but offers limited detail;
- `2`: uses the supplied Evidence to make the explanation pair-specific.

### Clarity

- `0`: confusing, internally inconsistent, or inaccessible;
- `1`: understandable with minor ambiguity;
- `2`: concise, coherent, and understandable to the intended STEM learner.

## Failure Labels

Apply all supported labels:

- `RELATION_DISTORTION`;
- `DIRECTION_REVERSAL`;
- `EVIDENCE_OVERREACH`;
- `ENDPOINT_DRIFT`;
- `CONTRADICTION`;
- `PEDAGOGICALLY_EMPTY`;
- `PEDAGOGICAL_OVERREACH`.

`PEDAGOGICALLY_EMPTY` applies when the explanation passes faithfulness but
scores `0` on both Conceptual Mechanism and Learning Relevance.

`PEDAGOGICAL_OVERREACH` applies when a learning-value claim invents typical
misconceptions, study order, mastery changes, learning outcomes, or
instructional effectiveness beyond the supplied Connection and Evidence.

## Reviewer Independence

Development review may be performed by the project author but must be
snapshot-bound and method-blinded when comparing methods.

Independent validation requires at least one reviewer who:

- did not design the evaluated prompt;
- did not annotate the independent benchmark;
- does not see method identity, aggregate metrics, or success outcomes;
- reviews randomized explanation instances under this frozen rubric.

When two reviewers are available, disagreements on hard-gate labels must be
adjudicated and raw decisions retained.
