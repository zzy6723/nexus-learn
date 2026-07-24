# 004-0: Benchmark And Evaluation Preparation

**Status:** Structural preflight passed; pending human review and repository freeze

## Completed Preparation

The current preparation defines:

- the Oracle-conditioned component boundary;
- the structured explanation output;
- six semantic failure labels;
- substantive-claim segmentation and support labels;
- correctness-first evaluation;
- a deterministic paraphrase lower bound;
- proposed hard and secondary success gates;
- a 17-instance relation-stratified development benchmark;
- strict benchmark creation and validation scripts.

The 17 instances contain 30 human-validated Evidence items and cover:

| Relation | Instances |
| --- | ---: |
| `APPLIED_IN` | 6 |
| `REQUIRES` | 4 |
| `FORMALIZES` | 4 |
| `EXTENDS` | 2 |
| `CONTRASTS_WITH` | 1 |

`RELATED_TO` is excluded because Experiment 003 Ground Truth has no reliable
positive support.

## Development Boundary

The benchmark reuses human-validated positive Connections from Experiment 003
Ground Truth. It does not use Experiment 003 predictions. It is suitable for
development and method comparison but not for an independent claim.

No exact reference prose is treated as Ground Truth. The frozen Connection and
Evidence define correctness; claim-level review and a human rubric evaluate
generated text.

## Pre-Execution Gate

Before any API call:

1. review the selected 17 Connection instances;
2. review and accept or revise the proposed thresholds;
3. confirm claim segmentation examples and failure labels;
4. freeze the contract, schema, benchmark, rubric, and criteria in one clean
   repository commit;
5. create a clean-state execution manifest bound to that commit;
6. implement and test the deterministic Baseline 001 before the learned method.

The current completion marker intentionally records
`model_execution_authorized = false`.
