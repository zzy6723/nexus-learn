# Relation Extraction Holdout Plan

**Status:** Construction and validation completed; holdout benchmark freeze commit pending  
**Created:** 2026-07-13  
**Target split:** `holdout`  
**Target version:** `v0.1`

---

# Purpose

The Relation holdout tests whether the development improvement from Prompt 002
generalizes to unseen STEM lecture material, unseen Knowledge Objects, and unseen
candidate pairs.

The holdout must compare `001_baseline` and `002_prompt_refinement` under the same
inputs and execution conditions. Running Prompt 002 alone would not establish
that its development gain generalizes.

---

# Freeze Boundary

Selected development prompt:

- path: `experiments/relation_extraction/002_prompt_refinement/prompt.md`;
- version: `v0.2`;
- SHA-256: `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`.

Content-locked methodology:

- `docs/decisions/004-relation-schema.md`;
- `benchmark/relation_annotation_guidelines.md`;
- `benchmark/relation_evaluation_protocol.md`;
- `scripts/run_relation_extraction.py`;
- `scripts/evaluate_relation_extraction.py`.

Before holdout construction begins, the user must create a development-method
freeze commit from a clean working tree and record its commit ID here:

```text
development_method_freeze_commit: 18e687d5cd7909531918b51e2d6bef38cb64a053
```

No holdout lecture, Knowledge Object annotation, candidate pair, or gold label
should be authored before that anchor exists. After construction begins, neither
baseline prompt nor Prompt 002 may change.

After the holdout lectures, oracle Knowledge Objects, candidate pairs, and gold
annotations have been completed and validated, the user must create a second
freeze commit. Its ID will be captured authoritatively by both formal run
metadata files and then backfilled here after the runs:

```text
holdout_benchmark_freeze_commit: PENDING_USER_COMMIT
```

The first commit proves that the method was fixed before unseen data was
authored. The second commit freezes the completed unseen benchmark before either
prompt is run. Formal baseline and Prompt 002 runs must both start from the
second commit.

The placeholder must not be edited between the freeze commit and formal model
runs, because doing so would make the working tree dirty and create a different
execution state. Backfill it only after both metadata files confirm the same
`git_commit_at_start` value.

---

# Data Isolation

The holdout must use:

- newly authored lecture snippets not present in Relation development;
- new lecture IDs and Knowledge Object IDs;
- a dedicated Knowledge Object ground-truth file;
- candidate pairs not reused from development;
- wording that does not copy development relation examples.

Constructed paths:

```text
benchmark/lectures/relation_holdout/
benchmark/ground_truth/relation_holdout_knowledge_objects_v0_1.json
benchmark/ground_truth/relations_holdout_v0_1.json
```

The existing Entity Extraction holdout lectures are Relation development data and
must not be reused.

---

# Composition Goals

The holdout should remain small enough for careful human annotation while being
large enough to expose the development trade-offs.

Target shape:

- 3 to 5 new short authored STEM lectures;
- approximately 25 to 40 primary-scored candidate pairs;
- approximately 25% to 35% hard negatives;
- both within-lecture and cross-lecture hard negatives;
- direction-sensitive positive Relations;
- several `REQUIRES`, `APPLIED_IN`, and `FORMALIZES` examples;
- more than one `EXTENDS` example when the material supports it naturally;
- `CONTRASTS_WITH` only when the lecture explicitly presents a real contrast;
- `RELATED_TO` only when direct evidence supports a meaningful weak connection;
- at most a small number of predeclared ambiguous or schema-gap pairs outside
  primary scoring.

Coverage goals are not quotas. Do not manufacture unnatural examples merely to
populate a Relation label.

## Constructed Composition

The completed holdout contains:

- 4 newly authored lectures;
- 41 oracle Knowledge Objects, of which 36 are referenced by candidate pairs;
- 40 primary-scored candidate pairs;
- 29 positive pairs;
- 11 hard negatives, a rate of `0.275`;
- 7 within-lecture and 4 cross-lecture hard negatives;
- 1 cross-lecture positive Relation;
- 8 `REQUIRES`, 7 `APPLIED_IN`, 10 `FORMALIZES`, 3 `EXTENDS`, and
  1 symmetric `CONTRASTS_WITH` positive;
- no positive `RELATED_TO`, ambiguous, or schema-gap pair.

`RELATED_TO` remains a monitored fallback label rather than a required coverage
quota. Pair categories are interleaved under opaque contiguous IDs so their
position does not reveal the gold category.

## Validation Record

Completed before either prompt was run:

- both new JSON files parse successfully;
- the existing development ground truth still passes the strict checker;
- the holdout passes with 40 contiguous `rel_holdout_NNN` IDs;
- all 41 oracle-KO source spans are exact lecture substrings;
- every Relation evidence span is exact and belongs to a candidate lecture;
- all candidate references are valid and unordered pairs are unique;
- every `FORMALIZES` source is a `Formula`;
- model-input construction renders 40 pairs, 36 referenced Knowledge Objects,
  and 4 lectures;
- the model-input gold-leakage audit passes;
- all 21 Relation evaluator, runner, and checker regression tests pass.

---

# Annotation Order

1. Author all new lecture snippets without running either prompt.
2. Annotate oracle Knowledge Objects under the existing object schema.
3. Select unordered candidate pairs.
4. Annotate category, Relation label, direction, exact evidence, rationale, and
   any acceptable alternatives before model execution.
5. Validate exact spans and candidate references.
6. Review ambiguity and schema-gap decisions independently of model output.
7. Mark `relations_holdout_v0_1.json` as `frozen_not_run` and create the
   user-owned holdout benchmark freeze commit.
8. Do not change holdout labels or scoring rules after either model is run.

Holdout pair IDs should use opaque contiguous IDs:

```text
rel_holdout_001
rel_holdout_002
...
```

The checker now derives the strict ID prefix from the declared split:

- `development` uses `rel_dev_NNN`;
- `holdout` uses `rel_holdout_NNN`.

This split-aware change does not alter annotation or scoring semantics. Both the
existing development ground truth and the new holdout ground truth pass the
checker, and regression tests cover both prefixes.

Steps 1 through 6 and the pre-commit validation are complete without running
either prompt. The files are marked `frozen_not_run`; step 7 awaits the
user-owned holdout benchmark freeze commit.

---

# Execution Protocol

Run both experiments on the frozen holdout:

```text
001_baseline/runs/holdout_v0_1/run_01
002_prompt_refinement/runs/holdout_v0_1/run_01
```

Both runs must use:

- the same `holdout_benchmark_freeze_commit`, as captured in
  `git_commit_at_start`;
- the same model and provider;
- identical temperature, top-p, maximum tokens, and response settings;
- the same holdout ground truth, lectures, Knowledge Objects, runner, and
  evaluator;
- one request per prompt unless a predeclared deterministic batching change is
  required before either run.

The only intended difference is the prompt hash.

Generated run artifacts are not currently ignored by repository rules. To keep
`git_dirty_at_start = false` for both prompts, use separate clean executions. A
simple local workflow is to run the baseline, temporarily move its complete
`run_01` directory outside the repository, run Prompt 002, and then restore the
baseline directory to its documented path. Do not edit either metadata file.

---

# Blinded Evidence Adjudication

After both initial evaluations:

1. Build anonymous adjudication packets labelled with neutral run aliases rather
   than experiment names.
2. Preserve each exact predicted edge and evidence snapshot.
3. Randomize packet order without changing snapshot contents.
4. Judge only whether the evidence supports the predicted edge.
5. Do not inspect aggregate metrics or prompt identity during adjudication.
6. Apply the resolved decisions to their original runs and require both
   evaluations to reach `final`.

The alias mapping must be preserved separately for audit and revealed only after
both adjudications are complete.

---

# Holdout Comparison

The final comparison must report:

- strict edge accuracy;
- Relation type accuracy;
- endpoint direction accuracy;
- direction accuracy when type is correct;
- positive Relation accuracy;
- `NO_RELATION` accuracy;
- false-positive Relation count;
- positive-to-`NO_RELATION` false-negative count;
- `RELATED_TO` prediction and overuse counts;
- exact evidence-span rate;
- pending-case semantic-support decisions with denominators;
- pair-level correct/wrong transitions;
- ambiguous and schema-gap outcomes outside primary conclusions.

Prompt 002 may be selected as the Relation Extraction prompt v0.1 only if the
holdout comparison shows a healthy overall improvement or stable advantage that
is not produced by suppressing supported positive Relations.
