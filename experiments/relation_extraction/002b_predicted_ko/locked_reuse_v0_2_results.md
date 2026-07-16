# Locked-Reuse v0.2 Results

**Evaluation status:** Final
**Method commit:** `3c8606d9243465a8a15639a628db80ea79155f96`
**Execution scope:** `locked_reuse_v0_2`
**Request partitioning:** `one_candidate_pair_per_request_v0_1`
**Claim boundary:** execution-method revision on previously evaluated material

## Result in Brief

Candidate-scoped execution resolved the repeated endpoint-substitution failure
that prevented `locked_reuse_v0_1` from producing a valid Relation bundle. Both
A-prime and B-prime completed 33 independent requests with no retries, endpoint
substitutions, parse failures, or schema failures.

Among the 33 recoverable pairs, predicted KO content did not reduce strict
Relation accuracy relative to the matched Oracle-KO condition. B-prime was
strictly correct on 26 pairs versus 25 for A-prime. This is a single-run paired
diagnostic, not evidence that predicted and Oracle KO representations are
generally equivalent.

End-to-end pipeline strict success was 26/40 (65.00%). The principal pipeline
loss came from missing predicted KOs, which made 7 of the 40 original pairs
unrecoverable. Relation errors already present under A-prime accounted for the
remaining 7 B-prime strict errors on recoverable pairs.

## Execution Integrity

- both conditions used `deepseek-v4-flash` with temperature 0, top-p 1, and
  `max_tokens = 8192`;
- both started from the same clean frozen commit;
- each condition completed 33/33 candidate-scoped requests;
- every request preserved its opaque pair ID and candidate endpoints;
- A-prime and B-prime used byte-identical structural execution plans;
- no request was retried;
- both Relation evaluations and the pipeline evaluation are final;
- fatal errors and pending adjudications are both zero.

The execution-plan SHA-256 was:

```text
4bb89c549f5edfa4c01384d1f69f43cfd91e79937764b635d02128e65ab61656
```

## Recoverability

| Metric | Result |
| --- | ---: |
| Unique endpoint KO recovery | 31/36 (86.11%) |
| Pair-weighted endpoint recovery | 73/80 (91.25%) |
| Recoverable primary pairs | 33/40 (82.50%) |
| Recoverable positive pairs | 25/29 (86.21%) |
| Recoverable hard negatives | 8/11 (72.73%) |
| Recoverable cross-lecture pairs | 5/5 (100.00%) |
| Recoverable within-lecture pairs | 28/35 (80.00%) |

Five missing Oracle KOs caused all seven unrecoverable pairs:

- `Derivative`;
- `Root Equation`;
- `Nonnegative Edge Weights`;
- `Initial Condition`;
- `Priority Queue`.

The predicted inventory also contained three unmatched extra KOs. They were
excluded from matched Relation inputs and did not enter the primary score.

## Conditional Relation Results

These metrics use only the same 33 recoverable pairs.

| Metric | A-prime | B-prime |
| --- | ---: | ---: |
| Strict edge accuracy | 25/33 (75.76%) | 26/33 (78.79%) |
| Relation type accuracy | 27/33 (81.82%) | 28/33 (84.85%) |
| Endpoint direction accuracy | 19/24 (79.17%) | 20/24 (83.33%) |
| Direction accuracy when type is correct | 18/20 (90.00%) | 19/21 (90.48%) |
| Positive Relation accuracy | 19/25 (76.00%) | 20/25 (80.00%) |
| `NO_RELATION` accuracy | 6/8 (75.00%) | 6/8 (75.00%) |
| False-positive Relations | 2 | 2 |
| False-negative Relations | 0 | 0 |
| `RELATED_TO` predictions | 0 | 0 |
| Exact Evidence-span rate | 34/34 (100.00%) | 32/35 (91.43%) |
| Semantic Evidence support | 17/19 (89.47%) | 18/20 (90.00%) |

The paired strict transitions were:

- 25 pairs: A-prime correct, B-prime correct;
- 6 pairs: both wrong with the same error;
- 1 pair: both wrong with different errors;
- 1 pair: A-prime wrong, B-prime correct (`rel_holdout_017`);
- 0 pairs: A-prime correct, B-prime wrong.

No strict error was newly introduced by the predicted KO representation in
this paired run.

## End-to-End Pipeline Results

| Metric | Result |
| --- | ---: |
| Pipeline strict success | 26/40 (65.00%) |
| Pipeline positive strict success | 20/29 (68.97%) |
| Pipeline hard-negative strict success | 6/11 (54.55%) |

The 40 primary pairs were assigned mutually exclusive primary loci:

- 26: no pipeline failure;
- 7: upstream unrecoverable because an endpoint KO was missing;
- 7: strict Relation error already present under A-prime;
- 0: new strict failure introduced only under B-prime.

The previous A0 result was 36/40 (90.00%), but A0 used the original full-bundle
Relation request. It is a historical reference, not an isolated estimate of the
candidate-scoped transport effect. Among the 33 recoverable pairs, A0 was
strictly correct on 29 and B-prime on 26.

## Remaining Relation Errors

The seven recoverable B-prime strict errors were:

- `rel_holdout_006`: false-positive `FORMALIZES` on a hard negative;
- `rel_holdout_013`: wrong `APPLIED_IN` direction;
- `rel_holdout_029`: `REQUIRES` predicted as `EXTENDS`;
- `rel_holdout_030`: `APPLIED_IN` predicted as `REQUIRES`;
- `rel_holdout_031`: false-positive `CONTRASTS_WITH` on a hard negative;
- `rel_holdout_032`: `APPLIED_IN` predicted as `REQUIRES`;
- `rel_holdout_036`: wrong `APPLIED_IN` direction.

All seven were already strict errors under A-prime, although the error form for
`rel_holdout_013` changed.

## Evidence Caveats

B-prime produced three non-exact Relation Evidence spans:

- `rel_holdout_004` omitted the lecture's inline LaTeX delimiters;
- `rel_holdout_025` collapsed prose and a displayed formula;
- `rel_holdout_032` joined a prose lead-in and displayed formula into one span.

Two exact-span Evidence sets were semantically insufficient in both conditions:

- `rel_holdout_007` left `this problem` unresolved;
- `rel_holdout_037` omitted the phrase linking the displayed formula to Heun's
  corrected update.

Exact substring validity and semantic support remain separate requirements.

## Decision

`locked_reuse_v0_2` is complete as a method-revision diagnostic. It supports
three limited conclusions:

1. candidate-scoped transport is operationally reliable for this 33-pair run;
2. on recoverable pairs, predicted KO content did not cause an observed net
   strict-accuracy loss relative to matched Oracle KO content;
3. the current end-to-end pipeline is not production-ready because KO coverage,
   Relation classification, and exact Evidence grounding still impose material
   losses.

The result must not be described as a fresh unseen holdout, a stability result,
or a causal estimate. No further prompt or protocol tuning should use these
same locked-reuse pairs without declaring a new experiment version.

## Artifacts

The final machine-readable results are under:

```text
experiments/relation_extraction/002b_predicted_ko/runs/
  locked_reuse_v0_2/run_01/
```

Key outputs are:

- `relation_evaluation/A0/evaluation_snapshot.json`;
- `relation_evaluation/A_prime/evaluation_snapshot.json`;
- `relation_evaluation/B_prime/evaluation_snapshot.json`;
- `pipeline_evaluation/pipeline_metrics.json`;
- `pipeline_evaluation/pipeline_errors.json`;
- `pipeline_evaluation/pair_transitions.json`;
- `pipeline_evaluation/pipeline_evaluation_complete.json`.
