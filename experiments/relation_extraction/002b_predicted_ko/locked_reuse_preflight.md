# Locked Reuse Preflight

**Status:** `closed_execution_incomplete`
**Scope:** `locked_reuse_v0_1`
**Relation benchmark:** `benchmark/ground_truth/relations_holdout_v0_1.json`

The repository bridge was subsequently frozen and all upstream gates completed.
The Relation stage then closed after the original A-prime request and one
bounded retry both substituted the same third endpoint. B-prime was not run.
See `locked_reuse_v0_1_failure.md`. Do not create another v0.1 retry; the
versioned transport revision is `candidate_scoped_execution_v0_2.md`.

## Original Gate Finding

At the time this preflight note was first written, no locked-reuse API request
had been made.

The first repository freeze preserved a development-only execution bridge:

- the preflight manifest wrote `development_v0_1` unconditionally;
- manifest-bound Entity reruns accepted only `--split development`;
- the runner therefore could not execute the four 002A Relation holdout lectures
  under a correctly labelled, manifest-bound locked-reuse plan.

Creating `locked_reuse_v0_1/run_01` with that implementation would have produced
an internally inconsistent audit trail. The formal run was therefore stopped
before preflight artifacts or model outputs were created.

## Remediation

The execution bridge now:

- distinguishes execution scope from benchmark split;
- binds `development_v0_1` to the Relation `development` split;
- binds `locked_reuse_v0_1` to the Relation `holdout` split;
- records both values in the execution and Entity source manifests;
- permits manifest-bound Entity reruns with the frozen input split;
- rejects scope/split disagreement before writing a formal plan.

The change does not alter Entity or Relation prompts, Knowledge Object matching,
alignment decisions, recoverability, projection, Relation scoring, Evidence
adjudication, pipeline metrics, or failure-locus precedence. It is execution
plumbing required to apply those frozen rules to the predeclared locked reuse.

At that milestone, the complete regression suite passed with 95 tests.

## Original Refreeze Requirement (Completed)

The existing development freeze tag must remain an immutable record of the
development result. The locked reuse used a new method freeze containing the
execution-bridge fix. That repository gate was subsequently completed; the
commands below are retained as the historical v0.1 procedure.

After the repository is clean and the new method commit is frozen, set:

```bash
METHOD_COMMIT=<NEW_LOCKED_REUSE_METHOD_COMMIT>
RUN_DIR=experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_1/run_01
```

Then create the formal preflight once, without overwrite:

```bash
python3 scripts/prepare_predicted_ko_relation_run.py \
  --method-commit "$METHOD_COMMIT" \
  --execution-scope locked_reuse_v0_1 \
  --relation-ground-truth benchmark/ground_truth/relations_holdout_v0_1.json \
  --run-dir "$RUN_DIR"
```

## Expected Preflight Result

The execution manifest must record:

```text
experiment = 002B-1
split = locked_reuse_v0_1
benchmark.relation_split = holdout
entity_execution.input_split = holdout
method_commit = NEW_LOCKED_REUSE_METHOD_COMMIT
repository_state.worktree_clean = true
claim_boundary = locked reuse of the previously evaluated 002A holdout
```

The Entity source manifest must record:

```text
lectures = 4
reused = 0
rerun_required = 4
```

The expected rerun IDs are:

```text
statistics_estimation_001
numerical_root_finding_001
differential_equations_001
graph_algorithms_001
```

Each formal Entity request must use the composed Oracle inventory and the
manifest-bound artifact directories:

```bash
python3 scripts/run_entity_extraction.py \
  --experiment 002_prompt_refinement \
  --split holdout \
  --ground-truth "$RUN_DIR/oracle_knowledge_objects.json" \
  --execution-manifest "$RUN_DIR/execution_manifest.json" \
  --only <LECTURE_ID>
```

Run the four lecture IDs separately. Do not use `--overwrite`. Finalization,
normalization, Relation-blind alignment, projection, matched A-prime/B-prime
execution, Relation evaluation, adjudication, and pipeline evaluation must then
follow the frozen development order.

## Claim Boundary

This stage reuses materials already evaluated in Experiment 002A. Its result is
a locked reuse evaluation, not a fresh unseen 002B holdout and not evidence of
general STEM-wide performance or run-to-run stability.
