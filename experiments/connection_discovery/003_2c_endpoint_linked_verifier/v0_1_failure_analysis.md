# Experiment 003 v0.1 Failure Analysis

**Status:** Final development analysis
**Input:** Final 003-2b Stage-A and combined evaluations

## Observed Failure Structure

The selected candidate generator retained all 41 primary positives, so the main
v0.1 limitation is downstream decision quality rather than candidate recall.

Stage A predicted 83 direct Connections:

- 37 were gold positive pairs;
- 40 were selected primary negatives;
- 36 of 61 manually reviewed Evidence sets were supported;
- 25 were not supported.

The final typed output contained:

- 13 correct positive edges;
- 24 wrong typed or directed edges on gold-positive pairs;
- four gold-positive pairs predicted as `NO_RELATION`;
- 40 edges on gold-negative pairs;
- 38 correctly rejected gold negatives;
- 15 wrong Relation types;
- nine wrong directions;
- 49 semantically unsupported Evidence sets.

## Repeated Error Modes

### Mediated inference

The model often connected endpoints through an unstated or separately modeled
intermediate object. Examples include linking Gradient to MLE through Score
Function, or linking Taylor Approximation to an ODE problem through Forward
Euler. These are plausible paths, but not direct graph edges between the given
endpoints.

### Shared-context inference

Objects appearing in the same formula, method, or lecture were treated as if
one were `APPLIED_IN` the other. Gradient and Step Size are both components of
the Gradient Descent update, but that does not establish an `APPLIED_IN` edge
between Gradient and Step Size.

### Endpoint-role and abstraction drift

The model moved between a method, its objective, and its formula without
preserving the requested endpoints. This produced edges such as a general
Objective Function relation inferred from a specific Least Squares Objective,
or a method relation inferred from its update formula.

### `RELATED_TO` as residual uncertainty

When no stronger type fit, the model sometimes emitted `RELATED_TO` instead of
rejecting the edge. The two-stage method exceeded the frozen `RELATED_TO` rate
ceiling.

### Scope-contract disagreement

Eleven of the 40 false-positive Relations received `supported` Evidence
adjudications even though their frozen category was `NO_IN_SCHEMA_CONNECTION`.
Several came from generic `reviewed_default_negative` annotations. This does
not change v0.1 scores, but it shows that semantic support and direct graph-edge
eligibility were not separated sharply enough for method development.

## Consequence for v0.2

Prompt-only refinement is not an adequate response. A v0.2 method must:

- constrain Evidence before edge classification;
- require both exact endpoints to be grounded in the reviewed Evidence window;
- distinguish direct in-schema edges from mediated, contextual, and
  out-of-schema connections;
- aggregate multiple Evidence windows deterministically;
- use explicitly reviewed negatives in fresh validation data;
- preserve the existing typed Relation evaluator for final graph-edge scoring.

The old benchmark remains immutable. Its supported false positives are method
development observations, not grounds for retroactively changing v0.1 labels.
