# Relation Extraction Holdout Comparison

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Baseline:** `001_baseline/runs/holdout_v0_1/run_01`  
**Refinement:** `002_prompt_refinement/runs/holdout_v0_1/run_01`  
**Benchmark:** `benchmark/ground_truth/relations_holdout_v0_1.json`  
**Evaluation status:** Both `final`  
**Comparison status:** Completed  
**Selected prompt:** `002_prompt_refinement` v0.2

---

# Scope and Integrity

This comparison tests whether the development changes in Prompt 002 generalize
to unseen authored lecture snippets, oracle Knowledge Objects, and candidate
pairs. The holdout contains 40 primary-scored pairs: 29 positive Relations and
11 hard negatives across 4 lectures and 36 model-facing Knowledge Objects.

Both formal runs:

- started from the same frozen commit,
  `5fd7e2b9ea02fad6a15f2a1a703193bd7d606c7d`;
- recorded `git_dirty_at_start = false`;
- used `deepseek-v4-flash`, temperature `0`, top-p `1`, and maximum output
  tokens `8192`;
- used identical ground-truth, Knowledge Object, lecture, Relation-schema, and
  model-input hashes;
- completed request execution, JSON parsing, and prediction-schema validation;
- returned all 40 unique candidate pairs with `finish_reason = stop`;
- differed only in prompt content and the resulting request-payload hash.

The holdout annotations, prompts, schema, runner, evaluator, and scoring protocol
were not changed after either formal run.

---

# Aggregate Results

| Metric | Baseline | Prompt 002 | Change |
| --- | ---: | ---: | ---: |
| Strict edge accuracy | 0.9000 (36/40) | 0.9000 (36/40) | 0.0000 |
| Relation type accuracy, ignoring direction | 0.9000 (36/40) | 1.0000 (40/40) | +0.1000 |
| Endpoint direction accuracy | 0.8571 (24/28) | 0.8571 (24/28) | 0.0000 |
| Direction accuracy when type correct | 1.0000 (24/24) | 0.8571 (24/28) | Not directly comparable |
| Positive Relation accuracy | 0.8621 (25/29) | 0.8621 (25/29) | 0.0000 |
| `NO_RELATION` accuracy | 1.0000 (11/11) | 1.0000 (11/11) | 0.0000 |
| False-positive Relations | 0 | 0 | 0 |
| Positive-to-`NO_RELATION` false negatives | 0 | 0 | 0 |
| Macro F1 over supported labels | 0.9000 | 1.0000 | +0.1000 |
| `RELATED_TO` prediction rate | 0.0000 (0/40) | 0.0000 (0/40) | 0.0000 |
| `RELATED_TO` overuse | 0 | 0 | 0 |
| Exact evidence-span rate | 1.0000 (29/29) | 1.0000 (29/29) | 0.0000 |
| Pending-case manual evidence support | 10/12 | 11/12 | +1 supported case |
| Semantic-support errors after adjudication | 2 | 1 | -1 |

The type-conditioned direction values must not be interpreted as a direction
regression from `1.0000` to `0.8571`. The baseline denominator contains only the
24 directional pairs whose type was already correct; its four reversed
`APPLIED_IN` pairs are excluded because their labels are also wrong. Prompt 002
corrects those labels, so all 28 directional pairs enter its denominator. The
endpoint direction metric uses the same 28-pair denominator for both prompts and
shows the actual result: direction performance is unchanged at `24/28`.

---

# Per-Type Results

The baseline classifies all 8 gold `REQUIRES` pairs as `REQUIRES`, but also maps
4 of the 7 gold `APPLIED_IN` pairs to `REQUIRES`. Its `APPLIED_IN` recall is
therefore `3/7`, and its `REQUIRES` precision is `8/12`.

Prompt 002 assigns the correct Relation label to every primary pair. In
particular, it changes the following four predictions from `REQUIRES` to the
gold `APPLIED_IN` label:

- `rel_holdout_013`: Log-Likelihood `APPLIED_IN` Maximum Likelihood Estimation;
- `rel_holdout_030`: Edge Relaxation `APPLIED_IN` Dijkstra's Algorithm;
- `rel_holdout_032`: Vector Field `APPLIED_IN` Forward Euler Method;
- `rel_holdout_036`: Heuristic Function `APPLIED_IN` A* Search.

This is a genuine unseen-data generalization of the prompt's type-boundary
refinement. It is not a strict-edge improvement because Prompt 002 retains the
reversed endpoint order on all four pairs.

`FORMALIZES` has 10 positive examples and is classified correctly by both
prompts. `EXTENDS` has only 3 positive examples and `CONTRASTS_WITH` only 1, so
their perfect scores are weak coverage evidence. `RELATED_TO` has no positive
holdout support; this experiment measures only whether it is overused.

---

# Pair-Level Transitions

## Strict Edge

| Transition | Count |
| --- | ---: |
| Correct to correct | 36 |
| Wrong to correct | 0 |
| Correct to wrong | 0 |
| Wrong to wrong | 4 |

## Relation Type

| Transition | Count |
| --- | ---: |
| Correct to correct | 36 |
| Wrong to correct | 4 |
| Correct to wrong | 0 |
| Wrong to wrong | 0 |

The only four primary errors for Prompt 002 are the same four strict-edge
failures listed above. Their labels are fixed, but their endpoints remain
reversed. Two other serialized edges change without affecting correctness:
`rel_holdout_016` is symmetric `CONTRASTS_WITH`, and `rel_holdout_031` is
`NO_RELATION`, so endpoint order is not scored for either pair.

---

# Development-to-Holdout Findings

## Hard-Negative Rejection

Prompt 002 removed three development false-positive Relations and raised
development `NO_RELATION` accuracy from `0.7000` to `1.0000`. That relative
advantage cannot be reproduced on this holdout because the baseline also scores
all 11 hard negatives correctly. The healthy behavior does persist: Prompt 002
has no false-positive Relation, no positive-to-`NO_RELATION` false negative, and
does not obtain its result by suppressing positive edges.

## `RELATED_TO` Fallback

Neither prompt predicts `RELATED_TO` on holdout, so Prompt 002 continues to avoid
using it as an uncertainty fallback. Because the holdout has no gold
`RELATED_TO` positive, legitimate `RELATED_TO` recall remains unmeasured.

## Relation Type and Direction

The development type improvement generalizes: Prompt 002 fixes all four unseen
`APPLIED_IN -> REQUIRES` confusions and reaches `40/40` type accuracy. The
development direction weakness also repeats. Both prompts reverse the same four
holdout `APPLIED_IN` edges, and Prompt 002 makes no strict-edge correction.

Direction is therefore a cross-split limitation, not a one-off development
artifact. The model can identify that a concept or operation is applied in a
method while still serializing the method as the source. Future work should
target this semantic-role mapping, but the inspected holdout must not be reused
as unseen evidence for such a refinement.

## Evidence Self-Containment

Both prompts retain perfect exact-substring grounding. Separate snapshot-bound
adjudication produced:

- baseline: 12 adjudicated, 10 supported, 2 not supported, 0 pending;
- Prompt 002: 12 adjudicated, 11 supported, 1 not supported, 0 pending;
- stale or unused adjudication decisions: 0 for both runs.

These ratios apply only to evidence cases sent for manual adjudication. They are
not all-evidence semantic-support accuracies.

`rel_holdout_039` improves under Prompt 002 because its evidence explicitly
names Bisection instead of relying on an unresolved "It" plus a generic midpoint
formula. `rel_holdout_007` remains unsupported for both prompts because "this
problem" is not resolved to the single-source shortest-path problem inside the
selected evidence. Together with the development failure at `rel_dev_014`, this
shows that evidence self-containment remains an incomplete cross-split behavior.

---

# Decision

Prompt 002 is selected as the **Relation Extraction prompt v0.1 for subsequent
Technical Validation**.

The decision is based on the following combined evidence:

- unseen Relation type accuracy improves from `36/40` to `40/40`;
- all four unseen `APPLIED_IN -> REQUIRES` confusions are corrected;
- strict edge, positive Relation, endpoint direction, and hard-negative
  performance do not regress;
- no positive edge is suppressed into `NO_RELATION`;
- `RELATED_TO` is not used as a fallback;
- exact evidence grounding remains perfect;
- pending-case evidence support improves from `10/12` to `11/12`.

This is an engineering default, not a claim that Prompt 002 is production-ready
or uniformly superior. It does not improve strict edge accuracy on holdout and
does not solve endpoint direction. The selection reflects better type
classification and slightly better evidence discipline with no observed loss on
the other measured outcomes.

Experiment 002A is complete. The baseline remains a valid control and must not be
described as a failed experiment.

---

# Limitations

The conclusion is limited to one run per prompt on a small benchmark of short,
authored STEM lecture snippets with oracle Knowledge Objects and preselected
candidate pairs. It does not establish:

- run-to-run stability;
- performance on full lectures, PDFs, parsed or noisy text, or long contexts;
- robustness to automatically extracted or imperfect Knowledge Objects;
- automatic candidate-pair generation performance;
- general performance across STEM disciplines;
- reliable `RELATED_TO` recall;
- mature performance for low-support `EXTENDS` or `CONTRASTS_WITH` cases.

No statistical significance claim is made.

---

# Next Step

Proceed to Experiment 002B, where the selected Prompt 002 is evaluated with
predicted rather than oracle Knowledge Objects. Carry endpoint direction and
evidence self-containment forward as explicit known limitations.

Do not create Prompt 003 by tuning against these holdout pairs. If a future
direction-focused refinement uses any observed holdout error, this holdout has
become development data and a new unseen holdout is required before making a
generalization claim.
