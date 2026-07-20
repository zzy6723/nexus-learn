# 003-2 Development Prompt Comparison

**Status:** Final
**Scope:** Oracle-canonical Connection classification on the frozen authored
development benchmark

## Experimental Control

Both runs used the same 125 candidates selected by `overlap_bridge_v0.1`, the
same canonical inventory, candidate-scoped Evidence catalogs, runner, evaluator,
model, request parameters, and frozen Ground Truth. The only intentional method
change was the prompt.

| Condition | Prompt | Method commit |
| --- | --- | --- |
| Baseline | `prompt.md` | `4ae39785c447b7dc68f854a5314ab00a4451ac52` |
| Refined | `prompt_refinement_v0_2.md` | `b1b7374a5cb13e692e8953b97727634672bc0d19` |

Both formal runs started from clean working trees, completed all 125
candidate-scoped requests, passed JSON and prediction-schema validation, and
ended with `finish_reason = stop`.

## Aggregate Results

| Metric | Baseline | Prompt 002 | Change |
| --- | ---: | ---: | ---: |
| Positive typed-edge recall | 0.3415 | 0.3171 | -0.0244 |
| Positive edge precision | 0.1284 | 0.1667 | +0.0382 |
| `NO_RELATION` accuracy | 0.1282 | 0.4872 | +0.3590 |
| Conditional strict-edge accuracy | 0.2017 | 0.4286 | +0.2269 |
| Positive Relation type accuracy | 0.5610 | 0.5854 | +0.0244 |
| Direction accuracy when type correct | 0.6087 | 0.5417 | -0.0670 |
| Exact Evidence materialization | 1.0000 | 1.0000 | 0.0000 |
| Semantic Evidence support | 0.1217 | 0.4512 | +0.3295 |
| `RELATED_TO` prediction rate | 0.0000 | 0.0252 | +0.0252 |
| Full-universe precision | 0.1284 | 0.1667 | +0.0382 |
| Full-universe recall | 0.3415 | 0.3171 | -0.0244 |
| Full-universe F1 | 0.1867 | 0.2185 | +0.0318 |
| Pipeline strict accuracy | 0.7473 | 0.8191 | +0.0718 |
| Cross-course Connection recall | 0.3214 | 0.2857 | -0.0357 |

Neither condition passes the frozen conditional-classification or full-universe
gate. Prompt 002 remains far below the required precision, recall,
`NO_RELATION`, semantic Evidence, F1, and cross-course thresholds.

## Error Counts

| Count | Baseline | Prompt 002 | Change |
| --- | ---: | ---: | ---: |
| Correct positive edges | 14 | 13 | -1 |
| Correct selected primary negatives | 10 | 38 | +28 |
| False-positive Relations | 68 | 40 | -28 |
| False-negative Relations | 0 | 3 | +3 |
| Wrong Relation type | 18 | 14 | -4 |
| Wrong direction | 9 | 11 | +2 |
| Positive Evidence cases | 115 | 82 | -33 |
| Semantically supported Evidence cases | 14 | 37 | +23 |
| Semantically unsupported Evidence cases | 101 | 45 | -56 |

The Evidence counts combine frozen exact-gold automatic matches and
snapshot-bound adjudication. Prompt 002 had 74 pending cases: 29 were adjudicated
`supported` and 45 `not_supported`; all pending items were resolved before final
metrics were produced.

## Pair Transitions

Across the 119 primary-scored selected pairs:

| Baseline to Prompt 002 | Count |
| --- | ---: |
| Correct to correct | 19 |
| Wrong to correct | 32 |
| Correct to wrong | 5 |
| Wrong to wrong | 63 |

The 32 fixes comprise 29 negative-pair corrections and three positive-edge
corrections. The five regressions comprise three positive pairs changed to
`NO_RELATION`, one positive direction reversal, and one new false-positive edge.

Prompt 002's three false negatives are:

- Step Size `APPLIED_IN` Forward Euler Method;
- Gradient `APPLIED_IN` Ordinary Least Squares;
- Ordinary Least Squares `APPLIED_IN` Linear Regression.

Its three positive-pair fixes are:

- Gradient `APPLIED_IN` Score Function;
- Log-Likelihood `APPLIED_IN` Maximum Likelihood Estimation;
- Gradient `APPLIED_IN` First-Order Taylor Approximation.

## Interpretation

Prompt 002 improves the negative gate and Evidence discipline. It rejects 28
additional selected primary negatives, reduces unsupported Evidence by 56 cases,
and raises full-universe F1 modestly. The improvement is not an all-`NO_RELATION`
shortcut: it still predicts 78 positive primary edges and its
`RELATED_TO` rate remains below the frozen ceiling.

The tradeoff is nevertheless material. Positive typed-edge recall, direction,
cross-course recall, and the number of correct positive edges decline. Forty
false-positive Relations remain, and only 37 of 82 positive Evidence sets are
semantically supported. Many residual errors infer a direct edge through an
intermediate object or confuse `APPLIED_IN` direction even when the rationale
describes the correct dependency.

## Decision

Prompt 002 is the stronger development diagnostic condition because it reduces
overconnection and improves semantic grounding without collapsing to the
negative class. It is not a selected validated Connection method: both frozen
gates fail, and its positive-edge behavior regresses on several dimensions.

No Prompt 003 should be tuned against individual pairs from this development
set. The next method change should address the decision architecture, especially
direct-edge gating and endpoint-role serialization, and must be evaluated under
a newly declared method version. Predicted-canonical propagation and
learner-facing ranking should not be interpreted as product validation while the
Oracle-canonical classification gate remains failed.

## Scope Limits

These results concern 125 candidates from short, authored STEM lectures under
Oracle canonical Knowledge Objects. They do not establish performance on noisy
Entity predictions, long documents, parsed PDFs, general STEM corpora, implicit
disjoint-provenance composition, or run-to-run stability.
