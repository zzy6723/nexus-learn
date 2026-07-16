# 002B-2 Downstream Typed-Edge Diagnostic Runbook

**Version:** v0.1
**Status:** Pre-API execution runbook
**Scope:** Inspected development diagnostic

## Frozen Order

```text
projection
-> condition preparation
-> repository-level method freeze
-> dry-run All-Pairs
-> dry-run Rule-Filtered
-> formal All-Pairs
-> formal Rule-Filtered
-> independent base evaluations
-> independent Evidence adjudications
-> independent final snapshots
-> full-universe pipeline comparison
```

The formal runs use one candidate pair per request. Rule-Filtered may start only
after the completed All-Pairs aggregate metadata is available. Neither condition
may reuse, patch, or skip an individual response from the other condition.

## Canonical Paths

```bash
ROOT=experiments/relation_extraction/002b_candidate_discovery/runs/downstream_diagnostic_v0_1
PREP="$ROOT/preparation"
FORMAL="$ROOT/formal"
DRY="$ROOT/dry_runs"
```

## Pre-Freeze Validation

```bash
python3 -m py_compile \
  scripts/project_candidate_pairs_to_relations.py \
  scripts/prepare_candidate_relation_diagnostic.py \
  scripts/run_candidate_relation_diagnostic.py \
  scripts/finalize_candidate_relation_evaluation.py \
  scripts/evaluate_candidate_relation_pipeline.py \
  tests/test_candidate_relation_downstream.py

python3 -m unittest tests.test_candidate_relation_downstream -v
python3 scripts/check_relation_ground_truth.py \
  --ground-truth benchmark/ground_truth/candidate_relation_projection_development_v0_1.json
```

Before any API request, the user creates the repository-level freeze and confirms
that the worktree is clean. The assistant must not perform that Git operation.

## Dry Runs

Set `METHOD_COMMIT` to the full freeze commit selected by the user.

```bash
python3 scripts/run_candidate_relation_diagnostic.py \
  --condition all_pairs \
  --expected-commit "$METHOD_COMMIT" \
  --run-id dry_run_01 \
  --dry-run

python3 scripts/run_candidate_relation_diagnostic.py \
  --condition rule_filtered_v0_1 \
  --expected-commit "$METHOD_COMMIT" \
  --run-id dry_run_01 \
  --dry-run
```

Expected dry-run counts:

| Condition | Selected pairs | Requests | Primary positives | Diagnostics |
| --- | ---: | ---: | ---: | ---: |
| All-Pairs | 176 | 176 | 80 | 5 |
| Rule-Filtered v0.1 | 127 | 127 | 70 | 5 |

Both gold-leakage audits must pass with zero gold fields in model-facing input.

## Formal Runs

Run All-Pairs first without `--overwrite`:

```bash
python3 scripts/run_candidate_relation_diagnostic.py \
  --condition all_pairs \
  --expected-commit "$METHOD_COMMIT" \
  --run-id run_01
```

After checking its aggregate metadata, run Rule-Filtered with explicit order
provenance:

```bash
ALL_META="$FORMAL/all_pairs/run_01/metadata/selected_relation_ground_truth.json"

python3 scripts/run_candidate_relation_diagnostic.py \
  --condition rule_filtered_v0_1 \
  --expected-commit "$METHOD_COMMIT" \
  --run-id run_01 \
  --preceding-all-pairs-metadata "$ALL_META"
```

For both conditions require:

```text
run_status = completed
request_success = true
json_parse_success = true
prediction_schema_valid = true
finish_reason = stop
git_commit_at_start = METHOD_COMMIT
git_dirty_at_start = false
batch_count = completed_batch_count = selected pair count
```

## Base Evaluation

```bash
python3 scripts/evaluate_relation_extraction.py \
  --ground-truth "$PREP/all_pairs/selected_relation_ground_truth.json" \
  --predictions "$FORMAL/all_pairs/run_01/output/selected_relation_ground_truth.json" \
  --evaluation-dir "$FORMAL/all_pairs/run_01/evaluation"

python3 scripts/evaluate_relation_extraction.py \
  --ground-truth "$PREP/rule_filtered_v0_1/selected_relation_ground_truth.json" \
  --predictions "$FORMAL/rule_filtered_v0_1/run_01/output/selected_relation_ground_truth.json" \
  --evaluation-dir "$FORMAL/rule_filtered_v0_1/run_01/evaluation"
```

Each `draft_pending_adjudication` result receives a separate prediction-bound
`adjudication_resolved.json`. Do not copy an adjudication from the other
condition. Re-run the base evaluator with `--adjudication` until both report
`evaluation_status = final` and `pending_adjudication_count = 0`.

## Final Evaluation Snapshots

If a condition used manual decisions, include its own `--adjudication` path.

```bash
python3 scripts/finalize_candidate_relation_evaluation.py \
  --condition all_pairs \
  --run-dir "$FORMAL/all_pairs/run_01" \
  --adjudication "$FORMAL/all_pairs/run_01/evaluation/adjudication_resolved.json"

python3 scripts/finalize_candidate_relation_evaluation.py \
  --condition rule_filtered_v0_1 \
  --run-dir "$FORMAL/rule_filtered_v0_1/run_01" \
  --adjudication "$FORMAL/rule_filtered_v0_1/run_01/evaluation/adjudication_resolved.json"
```

Omit `--adjudication` only if that condition's final metrics report
`manual_adjudication_count = 0`.

## Full-Universe Evaluation

```bash
python3 scripts/evaluate_candidate_relation_pipeline.py
```

The valid final bundle contains:

```text
pipeline_metrics.json
pipeline_errors.json
pair_transitions.json
summary.md
pipeline_evaluation_complete.json
```

The completion marker is written last. It must bind two final condition
snapshots, report 171 primary pairs and 5 diagnostics, preserve 10
Rule-Filtered candidate misses, and keep `candidate_gate_overridden = false`.

## Interpretation Lock

This diagnostic can quantify how many of the 10 filtered positives the frozen
All-Pairs classifier would have recovered. It cannot make those candidates
recoverable, reverse the failed Candidate recall gate, create an unseen-holdout
claim, or establish production scalability.
