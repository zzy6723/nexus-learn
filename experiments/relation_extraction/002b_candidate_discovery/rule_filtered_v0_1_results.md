# Rule-Filtered Candidate Generator v0.1 Results

**Status:** Final development result; candidate-layer gates failed
**Method:** `rule_filtered_v0_1`
**Control:** `all_pairs_v0_1`
**Split role:** Development

## Scope

This comparison evaluates candidate selection over the frozen exhaustive
predicted-KO pair universe. It does not evaluate Relation classification,
typed-edge quality, or end-to-end Oracle recall, and it did not call a model
API.

Both methods used the same frozen inputs:

- 39 predicted KOs from four lectures;
- 176 lecture-local unordered pairs;
- 80 primary positive pairs;
- 91 primary negative pairs;
- 5 `OUT_OF_SCHEMA_RELATION` diagnostic pairs;
- the same Candidate Generation evaluator and success criteria.

The Rule-Filtered generator did not read Candidate Ground Truth. Its metadata
records `gold_artifacts_read = false`, and its full 176-pair decision audit
preserves every `pair_id`, `lecture_id`, `ko_a`, and `ko_b` endpoint.

## Aggregate Comparison

| Metric | All-Pairs | Rule-Filtered v0.1 |
| --- | ---: | ---: |
| Selected positive pairs | 80 / 80 | 70 / 80 |
| Missed positive pairs | 0 | 10 |
| Selected negative pairs | 91 / 91 | 52 / 91 |
| Filtered negative pairs | 0 | 39 / 91 |
| Selected diagnostic pairs | 5 / 5 | 5 / 5 |
| Candidate recall | 1.000000 | 0.875000 |
| Primary candidate precision | 0.467836 | 0.573770 |
| Primary pairs retained | 171 / 171 | 122 / 171 |
| Total pairs selected | 176 / 176 | 127 / 176 |
| Total workload reduction | 0.000000 | 0.278409 |
| Actionable yield over total workload | 0.454545 | 0.551181 |

Rule-Filtered v0.1 achieved a useful workload reduction and improved the share
of selected pairs that were actionable. Those gains cannot compensate for the
10 missed positive pairs under the frozen recall-first selection rule.

## Per-Lecture Recall

| Lecture | Selected positives | Candidate recall | Total selected | Workload reduction |
| --- | ---: | ---: | ---: | ---: |
| `differential_equations_001` | 19 / 25 | 0.760000 | 31 / 55 | 0.436364 |
| `graph_algorithms_001` | 19 / 21 | 0.904762 | 33 / 45 | 0.266667 |
| `numerical_root_finding_001` | 7 / 9 | 0.777778 | 13 / 21 | 0.380952 |
| `statistics_estimation_001` | 25 / 25 | 1.000000 | 50 / 55 | 0.090909 |

The aggregate recall does not hide the lecture-level failures: three of the
four lectures missed at least one positive pair.

## Per-Relation Recall

| Relation type | Selected positive pairs | Candidate recall |
| --- | ---: | ---: |
| `REQUIRES` | 32 / 39 | 0.820513 |
| `APPLIED_IN` | 20 / 23 | 0.869565 |
| `EXTENDS` | 5 / 5 | 1.000000 |
| `CONTRASTS_WITH` | 1 / 1 | 1.000000 |
| `FORMALIZES` | 10 / 10 | 1.000000 |
| `RELATED_TO` | 2 / 2 | 1.000000 |

All 10 false negatives were directional dependency or applicability edges:
seven `REQUIRES` and three `APPLIED_IN`. The local rules were reliable for the
more explicit `FORMALIZES`, `EXTENDS`, and `CONTRASTS_WITH` cases in this small
development benchmark.

## False-Negative Analysis

Every missed pair had `no_rule_triggered`. Every endpoint was valid and every
pair matched the frozen universe, so none of the misses was an implementation
or alignment error.

| Pair | Relation | Endpoints | Block distance | Primary cause |
| --- | --- | --- | ---: | --- |
| `cand_dev_019` | `REQUIRES` | Euler Predictor -> Vector Field | 3 | Dependency carried by the stopped generic symbol `F` across blocks |
| `cand_dev_021` | `REQUIRES` | Forward Euler Update -> First-Order Equation | 2 | Formula dependency carried by generic `F`, `t`, and `y` symbols |
| `cand_dev_023` | `REQUIRES` | Heun's Update -> First-Order Equation | 5 | Long-range formula dependency carried by generic symbols |
| `cand_dev_045` | `APPLIED_IN` | Vector Field -> Heun's Method | 3 | Implicit multi-block applicability through predictor/corrector slopes |
| `cand_dev_048` | `REQUIRES` | Heun's Update -> Step Size | 2 | Formula dependency carried by the stopped generic symbol `h` |
| `cand_dev_049` | `REQUIRES` | Heun's Update -> Vector Field | 4 | Long-range dependency carried by `F` and slope context |
| `cand_dev_079` | `REQUIRES` | Edge Relaxation -> Weighted Directed Graph | 2 | Source text shares graph vocabulary, but name-only lexical overlap does not |
| `cand_dev_099` | `REQUIRES` | Relaxation Update -> Weighted Directed Graph | 2 | Formula dependency carried by the stopped generic symbol `w` |
| `cand_dev_105` | `APPLIED_IN` | Bisection Method -> Root-Finding Problem | 3 | Applicability is established by lecture context rather than one local span |
| `cand_dev_110` | `APPLIED_IN` | Damped Newton Method -> Root-Finding Problem | 2 | Source-content overlap is not used by the name-only lexical rule |

The errors form three recurring groups:

1. Six dependencies rely on mathematically meaningful but globally common
   symbols that v0.1 deliberately treats as stop symbols.
2. Two applicability edges require multi-block lecture context.
3. Two edges have useful source-content overlap that is not visible to the
   name-only lexical rule.

Blindly enabling common symbols would also connect many unrelated objects in
the same lecture. Likewise, broad context windows make almost every pair share
some vocabulary. The errors therefore expose a precision/recall limitation of
the current deterministic feature family, not a single threshold bug.

## Development Sensitivity Check

A development-only threshold probe varied only the maximum semantic-block
distance while leaving the other v0.1 rules unchanged:

| Maximum block distance | Total selected | Selected positives | Missed positives | Total reduction |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 127 | 70 / 80 | 10 | 0.278409 |
| 2 | 153 | 75 / 80 | 5 | 0.130682 |
| 3 | 168 | 78 / 80 | 2 | 0.045455 |
| 4 | 174 | 79 / 80 | 1 | 0.011364 |
| 5 | 176 | 80 / 80 | 0 | 0.000000 |

This is an error-analysis probe, not a second formal generator run. It shows
that widening proximity alone cannot satisfy both frozen development gates:
the first threshold that reaches full recall has become All Pairs.

## Gate Assessment

Frozen development requirements were:

- candidate recall `1.0`;
- missed positive count `0`;
- per-lecture recall `1.0`;
- total workload reduction at least `0.2`.

Rule-Filtered v0.1 passed only the workload-reduction requirement. Its formal
gate outcome is therefore `failed`.

## Decision

`rule_filtered_v0_1` is retained as a valid failed development baseline. It is
not promoted to holdout and is not selected for Relation Classification.

Under the frozen non-override rule, `all_pairs_v0_1` remains the selected safe
fallback for the current Candidate Generation stage. This is a recall-safety
decision, not a claim that All Pairs is an efficient production method.

No v0.2 pair-specific patch is introduced. The single permitted controlled
refinement remains available only if a general contextual signal can be
predeclared and justified beyond these 10 known pairs. Repeatedly tuning on the
same 176-pair development snapshot would create an avoidable overfitting risk.

## Limitations

- The benchmark contains four short authored lectures and 80 positive pairs.
- All pairs are lecture-local; cross-lecture discovery is not evaluated.
- The result does not cover long documents, parsed PDFs, noisy source spans, or
  canonical KO identity.
- No Relation API was called, so typed-edge and end-to-end consequences remain
  unmeasured.
- The sensitivity check is descriptive development analysis, not holdout
  evidence.

