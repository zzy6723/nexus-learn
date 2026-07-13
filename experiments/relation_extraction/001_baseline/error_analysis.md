# Relation Extraction 001 Baseline Error Analysis

**Run:** `runs/development_v0_1/run_02`  
**Evaluation status:** `final`  
**Analysis status:** Completed  
**Purpose:** Diagnose development errors before designing Prompt 002

---

# Scope

This analysis uses only the finalized `run_02` artifacts:

- `evaluation/errors.json`;
- `evaluation/matches.json`;
- `evaluation/confusion_matrix.json`;
- the corresponding prediction output and frozen Relation ground truth where a
  pair-level comparison is necessary.

The analysis concerns one development request over short authored lecture
snippets with oracle Knowledge Objects. Observed patterns motivate prompt changes;
they do not establish model-wide failure mechanisms or holdout generalization.

---

# Aggregate Error Summary

| Item | Count |
| --- | ---: |
| Total candidate pairs | 41 |
| Primary-scored pairs | 38 |
| Strict-edge correct | 32 |
| Unique strict-edge failures | 6 |
| Positive pairs | 28 |
| Positive strict-edge failures | 3 |
| Hard-negative pairs | 10 |
| False-positive Relations | 3 |
| Ambiguous pairs excluded from primary scoring | 2 |
| Schema-gap pairs excluded from primary scoring | 1 |

The 12 records in `errors.json` are taxonomy records, not 12 independent failed
pairs. A false-positive pair can also be recorded as a wrong type and, for
`RELATED_TO`, as overuse.

The six primary strict-edge failures are:

- wrong direction: `rel_dev_010`, `rel_dev_020`;
- wrong positive Relation type: `rel_dev_021`;
- false-positive Relation: `rel_dev_035`, `rel_dev_037`, `rel_dev_038`.

`rel_dev_014` is strict-edge correct but has semantically unsupported evidence, so
it is an additional grounding error rather than a seventh strict-edge failure.

---

# Relation Type Confusions

| Gold label | Predicted label | Count | Pairs |
| --- | --- | ---: | --- |
| `FORMALIZES` | `APPLIED_IN` | 1 | `rel_dev_021` |
| `NO_RELATION` | `RELATED_TO` | 2 | `rel_dev_035`, `rel_dev_037` |
| `NO_RELATION` | `APPLIED_IN` | 1 | `rel_dev_038` |

There are no type confusions for the 13 primary `REQUIRES` examples or the 4
primary `APPLIED_IN` examples. Their remaining strict errors are directional.

## `rel_dev_021`: `FORMALIZES` to `APPLIED_IN`

The Normal Equations Formula was correctly oriented toward the Least Squares
Problem, but it was labeled `APPLIED_IN`. The prediction rationale says the
equations are "used to solve" least squares, while the source text states that a
least-squares solution "satisfies the normal equations" and gives the equation.

This supports a label-precedence issue: when a Formula gives an explicit defining,
update, characterization, or solution condition for a Concept or Method,
`FORMALIZES` should take precedence over the broader claim that the formula is
used in that context.

The `APPLIED_IN` precision of `0.667` reflects both this confusion and the
hard-negative false positive `rel_dev_038`. Its recall of `1.000` does not show
that the boundary is solved.

---

# Direction Errors

Both direction errors preserve the correct candidate pair and Relation type. In
both cases, the prediction rationale describes the correct dependency, but the
serialized endpoints are reversed.

## `rel_dev_010`: `REQUIRES`

Gold:

```text
Optimisation Problem REQUIRES Objective Function
```

Predicted:

```text
Objective Function REQUIRES Optimisation Problem
```

The rationale says an optimisation problem is defined in terms of an objective
function and that the objective function is required. This identifies the correct
prerequisite but assigns that prerequisite to `source` rather than `target`.

## `rel_dev_020`: `APPLIED_IN`

Gold:

```text
Orthogonal Projection APPLIED_IN Least Squares Problem
```

Predicted:

```text
Least Squares Problem APPLIED_IN Orthogonal Projection
```

The evidence and rationale say that least-squares problems use projection. The
tool being used should therefore be `source`, and the application context should
be `target`; the output reverses them.

These two cases suggest an endpoint-serialization problem rather than a failure to
understand the underlying relation. Prompt 002 should require a canonical verbal
check immediately before serialization:

- `REQUIRES`: source is the dependent object; target is the prerequisite.
- `APPLIED_IN`: source is the tool or idea being used; target is the context that
  uses it.

This is a development-supported hypothesis, not yet a holdout-validated cause.

---

# False-Positive Relations

The model correctly returned `NO_RELATION` for 7 of 10 hard negatives. All four
cross-lecture hard negatives were correct. Among six same-lecture hard negatives,
three were correct and three became false-positive edges.

This small split is descriptive only, but it localizes the observed risk: shared
lecture context makes indirect or unstated connections easier to promote into
graph edges.

## `rel_dev_035`: Hessian Matrix and Stationary Point

The model predicts `RELATED_TO` using two separate spans that independently
describe the endpoints. Its rationale introduces external knowledge about
second-order conditions and explicitly admits that the lecture does not connect
the objects.

The evidence demonstrates co-presence, not a supported relation. A rationale that
says the text does not explicitly or directly connect the objects should lead to
`NO_RELATION`, not a weak positive edge.

## `rel_dev_037`: Composite Function and Local Linear Approximation

The model predicts `RELATED_TO` through the surrounding chain-rule context. The
two evidence spans again describe the endpoints separately, and the rationale
explicitly says the lecture does not directly link them.

This is a mediated-context error: sharing an intermediate topic is not enough to
create a direct edge between the candidate endpoints.

## `rel_dev_038`: Dot Product and Normal Equations

The model predicts `APPLIED_IN`, reasoning that normal equations involve dot
products "via matrix multiplication." The selected evidence contains the normal
equations but does not mention dot product or establish its application.

This is an unsupported inferential expansion from mathematical background
knowledge. In this benchmark, a mathematically plausible connection is still
`NO_RELATION` when the supplied material does not directly support the candidate
edge.

---

# RELATED_TO Overuse

`RELATED_TO` was predicted twice among the 38 primary-scored pairs, and both
predictions were false positives. The benchmark has no primary positive
`RELATED_TO` support, so this result diagnoses overuse but cannot estimate recall
or general performance for legitimate `RELATED_TO` edges.

The two rationales show the same fallback pattern:

- the model recognizes that no strong or direct relation is stated;
- it nevertheless converts contextual association into `RELATED_TO` rather than
  choosing `NO_RELATION`.

Prompt 002 should therefore treat `RELATED_TO` as a positive Relation requiring
direct evidence of a meaningful connection. It must not serve as an uncertainty,
same-lecture, shared-context, or external-knowledge fallback. Insufficient direct
evidence should resolve to `NO_RELATION`.

---

# Evidence Support Errors

All 36 predicted evidence spans are exact substrings, but exact copying does not
guarantee semantic support. Of the 13 evidence cases sent to manual adjudication,
12 were supported and 1 was not supported.

## `rel_dev_014`: Step Size `APPLIED_IN` Gradient Descent

The selected span states that step size controls how far "the method" moves, but
the span does not identify the method as Gradient Descent. The prediction edge is
correct; the evidence snapshot is not independently sufficient to establish that
pair.

The gold evidence combines the Gradient Descent update equation with the step-size
description. Prompt 002 should require the selected evidence set, taken together,
to identify both candidate objects and establish the predicted Relation. A
pronoun or contextual phrase is acceptable only when another selected span or an
unambiguous formula resolves it.

This requirement explains why `rel_dev_026` remains supported: its `Var(X)`
formula resolves the introductory "It" without relying on an omitted antecedent.

---

# Ambiguous and Schema-Gap Cases

These cases do not contribute to primary prompt success or failure.

## Ambiguous pairs

- `rel_dev_008`: the model produced the annotated `APPLIED_IN` edge with exact
  gold evidence.
- `rel_dev_041`: the model produced the predeclared `REQUIRES` alternative for the
  cross-lecture Gradient Descent and Gradient pair. Its evidence was manually
  judged supported.

Neither pair should drive a corrective Prompt 002 change. In particular, the
current protocol does not require both candidate lectures to contribute evidence
for a cross-lecture Relation.

## Schema gap

For `rel_dev_034`, the model predicts that Line Search is `APPLIED_IN` Step Size.
The lecture instead says that line search is a method for choosing a step size.
This suggests a possible selection or determination relation that the v0.1 schema
does not express cleanly.

One schema-gap example is not sufficient evidence to add a new Relation type or
change the current schema. It should remain documented and excluded from primary
error rates.

---

# Prompt-Level Causes

The following are development-supported hypotheses:

1. **Endpoint role and endpoint serialization are insufficiently coupled.** The
   model's rationales can identify the correct semantic roles while its output
   reverses `source` and `target`.
2. **`FORMALIZES` lacks an explicit precedence rule over `APPLIED_IN`.** A formula
   used in a domain can be mislabeled even when it provides the formal condition
   for the target object.
3. **The positive-edge evidence threshold is too permissive in shared contexts.**
   Separate endpoint mentions, mediated context, external knowledge, and symbolic
   inference can be promoted into edges unsupported by the supplied lecture.
4. **`RELATED_TO` is functioning as a fallback for uncertainty.** The model uses
   it even while acknowledging that the text does not directly link the pair.
5. **Exact-span compliance is stronger than semantic-evidence selection.** The
   model copies valid text but can omit the context needed to make the evidence
   set self-contained.

These are hypotheses inferred from one development run. Prompt 002 can test them;
only later unseen evaluation can show whether the resulting changes generalize.

---

# Benchmark-Level Observations

- Same-lecture hard negatives expose a more difficult discrimination problem than
  the current cross-lecture negatives: `3/6` versus `4/4` correct in this small
  development set.
- `REQUIRES` has 13 primary positives and no type errors, but one direction error.
- `APPLIED_IN` has 4 primary positives and no type errors, but one direction error.
- `FORMALIZES` has 10 primary positives and one confusion into `APPLIED_IN`.
- `EXTENDS` has only one positive example, so its perfect development result does
  not support a strong conclusion.
- `CONTRASTS_WITH` is not covered.
- `RELATED_TO` has no primary positive example, so only overuse can be assessed.

No annotation defect is established by the current error analysis.

---

# Recommended Refinement Targets

Prompt 002 should make only the following evidence-driven changes:

1. Require a canonical endpoint-role paraphrase before writing `source` and
   `target`, especially for `REQUIRES` and `APPLIED_IN`.
2. Add a label-precedence rule: when a Formula explicitly defines, characterizes,
   updates, or states a solution condition for the other object, prefer
   `FORMALIZES` over `APPLIED_IN`.
3. Add an evidence-first positive-edge gate: a positive Relation requires supplied
   text that establishes the two endpoints and their relation, not merely two
   separate mentions or outside mathematical knowledge.
4. Make `NO_RELATION` the required result when direct support is insufficient.
   Reserve `RELATED_TO` for a directly evidenced meaningful relation that cannot
   be represented by a stronger label.
5. Require the complete evidence set to be semantically self-contained. Include
   multiple exact spans when needed to resolve pronouns or connect a formula to
   its named object.
6. Require consistency between rationale and label: a rationale admitting that
   the lecture does not directly establish the connection cannot justify a
   positive edge.

These changes should be expressed as general decision rules rather than
pair-specific instructions copied from the development examples.

---

# Non-Targets

Prompt refinement must not change the following in response to this run:

- the development benchmark or candidate pairs;
- ground-truth labels, directions, evidence, or categories;
- the evaluator, metrics, denominators, or adjudication decisions;
- the v0.1 Relation schema;
- ambiguous-pair alternatives or schema-gap scoring;
- the cross-lecture evidence protocol;
- model parameters or the single-request runner design;
- exact-span syntax requirements, which already achieved `1.000`.

A benchmark or protocol change would require independent evidence of an annotation
or methodological defect and should be versioned separately. No such defect was
found here.
