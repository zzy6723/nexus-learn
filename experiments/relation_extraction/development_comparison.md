# Relation Extraction Development Comparison

**Baseline:** `001_baseline/runs/development_v0_1/run_02`  
**Refinement:** `002_prompt_refinement/runs/development_v0_1/run_01`  
**Evaluation status:** Both `final`  
**Comparison status:** Completed

---

# Scope and Integrity

Both runs use the same 41 candidate pairs, 46 Knowledge Objects, 6 lectures,
model, model input, request parameters, ground truth, KO ground truth, and lecture
content. The prompt and therefore the complete request-payload hash differ as
intended. The refinement formal run started from a clean working tree and
completed with successful request, JSON parsing, schema validation, and
`finish_reason = stop`.

This is a development comparison on data used to design Prompt 002. It supports a
development decision but does not establish unseen-data generalization.

---

# Aggregate Comparison

| Metric | Baseline | Prompt 002 | Change |
| --- | ---: | ---: | ---: |
| Strict edge accuracy | 0.8421 (32/38) | 0.9211 (35/38) | +0.0789 |
| Relation type accuracy | 0.8947 (34/38) | 0.9737 (37/38) | +0.0789 |
| Endpoint direction accuracy | 0.9286 (26/28) | 0.8929 (25/28) | -0.0357 |
| Direction accuracy when type correct | 0.9259 (25/27) | 0.9259 (25/27) | 0.0000 |
| Positive Relation accuracy | 0.8929 (25/28) | 0.8929 (25/28) | 0.0000 |
| `NO_RELATION` accuracy | 0.7000 (7/10) | 1.0000 (10/10) | +0.3000 |
| False-positive Relations | 3 | 0 | -3 |
| Positive-to-`NO_RELATION` false negatives | 0 | 0 | 0 |
| `RELATED_TO` prediction rate | 0.0526 (2/38) | 0.0000 (0/38) | -0.0526 |
| `RELATED_TO` overuse | 2 | 0 | -2 |
| Exact evidence-span rate | 1.0000 | 1.0000 | 0.0000 |
| Pending-case manual evidence support | 12/13 | 12/13 | Not directly compositional |
| Semantic-support errors after adjudication | 1 | 1 | 0 |

The strict-edge gain is three pairs. It comes from eliminating all three
hard-negative false positives. Positive Relation accuracy does not improve: one
positive type error is fixed, one new positive type-and-endpoint error appears,
and the same two direction errors remain.

Prompt 002 is not over-conservative on this development set. It increases
`NO_RELATION` accuracy without producing any positive-to-`NO_RELATION` false
negative.

---

# Primary Pair Transitions

| Transition | Count |
| --- | ---: |
| Correct to correct | 31 |
| Wrong to correct | 4 |
| Correct to wrong | 1 |
| Wrong to wrong | 2 |

## Fixed

- `rel_dev_021`: `FORMALIZES -> APPLIED_IN` is corrected to `FORMALIZES`.
- `rel_dev_035`: false `RELATED_TO` becomes `NO_RELATION`.
- `rel_dev_037`: false `RELATED_TO` becomes `NO_RELATION`.
- `rel_dev_038`: false `APPLIED_IN` becomes `NO_RELATION`.

## Still wrong

- `rel_dev_010`: the `REQUIRES` endpoints remain reversed.
- `rel_dev_020`: the `APPLIED_IN` endpoints remain reversed.

## New regression

- `rel_dev_017`: the baseline correctly predicts Jacobian Matrix `APPLIED_IN`
  Multivariable Chain Rule Formula. Prompt 002 changes this to Multivariable Chain
  Rule Formula `REQUIRES` Jacobian Matrix and reverses the endpoints. Its rationale
  understands that the formula uses the Jacobian but maps that statement to the
  wrong label and serialization.

This regression explains why raw endpoint direction accuracy decreases. The
type-conditioned direction metric remains unchanged because `rel_dev_017` is
excluded from that denominator once its Relation type is wrong.

---

# Refinement Target Outcomes

| Prompt 002 target | Development outcome |
| --- | --- |
| Endpoint-role serialization | **Not achieved.** Both original direction errors remain, and `rel_dev_017` adds an endpoint reversal with a type error. |
| `FORMALIZES` precedence | **Partially achieved.** `rel_dev_021` is fixed, but a different `APPLIED_IN` example regresses to `REQUIRES`. |
| Evidence-first positive gate | **Achieved for observed hard negatives.** All three false-positive edges are removed. |
| `NO_RELATION` under insufficient support | **Achieved without observed positive suppression.** Hard-negative accuracy reaches 10/10 and positive-to-`NO_RELATION` errors remain zero. |
| Prevent `RELATED_TO` fallback | **Achieved for the measured overuse cases.** Overuse falls from 2 to 0; legitimate `RELATED_TO` recall remains unmeasured because the benchmark has no primary positive support. |
| Self-contained evidence | **Not achieved.** `rel_dev_014` remains semantically unsupported. |
| Rationale/label consistency | **Improved for false positives.** The previous rationales admitting no direct connection now accompany `NO_RELATION`; the broader positive label boundary remains imperfect at `rel_dev_017`. |

---

# Evidence Comparison

Both prompts preserve perfect exact-substring grounding. Both also produce 13
pending semantic-support snapshots, with 12 supported and 1 not supported after
independent adjudication.

The equal `12/13` rates do not imply identical evidence behavior. The pending sets
differ: Prompt 002 fixes `rel_dev_021`, which then requires adjudication, while its
incorrect `rel_dev_017` edge no longer qualifies for evidence adjudication.
`rel_dev_014` is the unsupported case in both runs.

---

# Ambiguous and Schema-Gap Cases

- `rel_dev_008` remains an acceptable `APPLIED_IN` prediction.
- `rel_dev_041` moves from the accepted `REQUIRES` alternative to the canonical
  `APPLIED_IN` edge; both are acceptable and excluded from primary conclusions.
- `rel_dev_034` remains the same `APPLIED_IN` schema-gap prediction and remains
  excluded from primary scoring.

No benchmark, ground-truth, evaluator, schema, or protocol change is justified by
this comparison.

---

# Development Conclusion

Prompt 002 is a net development improvement in strict accuracy and hard-negative
precision. It removes all observed false-positive Relations without increasing
positive-to-`NO_RELATION` false negatives, and it fixes the targeted
`FORMALIZES -> APPLIED_IN` confusion.

The improvement is incomplete. Direction handling does not improve, raw endpoint
accuracy decreases, one previously correct positive pair regresses, and the known
self-contained-evidence error remains. Prompt 002 should therefore be described
as the stronger current development candidate, not as a fully validated or frozen
Relation prompt.

A subsequent decision should explicitly choose between:

- freezing Prompt 002 for unseen holdout evaluation, accepting the documented
  direction and evidence limitations; or
- making one further minimal development refinement focused only on endpoint
  serialization, the `APPLIED_IN/REQUIRES` boundary, and self-contained evidence,
  while acknowledging increased development-overfitting risk.
