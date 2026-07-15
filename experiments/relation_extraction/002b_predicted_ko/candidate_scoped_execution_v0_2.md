# Candidate-Scoped Relation Execution v0.2

**Scope:** `locked_reuse_v0_2`
**Request partitioning:** `one_candidate_pair_per_request_v0_1`
**Claim boundary:** execution-method revision on previously evaluated material

## Purpose

The v0.1 full-bundle request exposed a repeatable pair-to-output association
failure. v0.2 changes request transport without changing Relation semantics.

For every recoverable candidate pair, the model receives exactly:

- the selected Relation prompt and frozen Relation schema;
- one opaque candidate pair;
- its two neutral KO-slot records;
- the lecture text belonging to its endpoints.

The model never receives gold Relation labels, directions, categories,
evidence, rationales, or scoring status.

## Frozen Controls

The following remain unchanged:

- Entity prompt and Entity outputs;
- Relation prompt and Relation schema;
- matched ground truth and candidate order;
- neutral KO-slot mapping;
- strict endpoint and prediction-schema validation;
- Relation evaluator, adjudication protocol, and pipeline metrics.

The request-partitioning change is applied identically to A-prime and B-prime.
Their structural `execution_batch_plan.json` files must have the same SHA-256.

## Failure Boundary

There is no automatic repair or retry. If any candidate request fails at the
request, finish-reason, parse, or schema layer:

- preserve all artifacts already written for that attempt;
- mark the condition incomplete;
- do not write the aggregate prediction;
- do not evaluate the condition;
- do not run the paired B-prime condition after an A-prime failure.

## Required Gates

1. Freeze the revised implementation in a clean repository commit.
2. Prepare `locked_reuse_v0_2` and audit-copy the four v0.1 Entity artifacts.
3. Finalize the all-reused Entity source bundle without an Entity API call.
4. Rebuild normalization, Relation-blind alignment, and projection
   deterministically from the copied artifacts.
5. Complete alignment adjudication before Relation rendering.
6. Dry-run A-prime and B-prime in separate directories.
7. Confirm equal structural execution-plan hashes and 33 one-pair payloads.
8. Run formal A-prime, inspect its aggregate metadata, then run B-prime.
9. Evaluate, adjudicate Evidence independently, finalize both snapshots, and
   run the existing pipeline evaluator.

## Relation Commands

After projection is final, set:

```bash
RUN_DIR=experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_2/run_01
MANIFEST="$RUN_DIR/execution_manifest.json"
GROUND_TRUTH="$RUN_DIR/projection/matched_relation_ground_truth.json"
BATCH_PLAN="$RUN_DIR/projection/batch_plan.json"
```

Render A-prime without calling the API:

```bash
python3 scripts/run_relation_extraction.py \
  --experiment 002_prompt_refinement \
  --split holdout \
  --ground-truth "$GROUND_TRUTH" \
  --input-artifact "$RUN_DIR/projection/oracle_normalized_input.json" \
  --batch-plan "$BATCH_PLAN" \
  --execution-manifest "$MANIFEST" \
  --run-id run_01 \
  --run-dir "$RUN_DIR/dry_runs/A_prime" \
  --model deepseek-v4-flash \
  --temperature 0 \
  --top-p 1 \
  --max-tokens 8192 \
  --dry-run
```

Render B-prime by changing the input artifact to
`predicted_normalized_input.json` and the run directory to
`dry_runs/B_prime`. The two generated `execution_batch_plan.json` files must be
byte-identical and each dry run must contain 33 rendered pair requests.

For formal execution, use the same commands without `--dry-run` and write to
`$RUN_DIR/A_prime` followed by `$RUN_DIR/B_prime`. Do not chain them: inspect the
A-prime aggregate metadata first. Do not use `--overwrite`.

The final report must retain the v0.1 failure and describe v0.2 as a revised
execution diagnostic, not as an untouched holdout result.
