# 004-0: Benchmark And Evaluation Preparation

**Status:** Repository-frozen at `cda3f9dd7f3298d0f726118db8d15e546febccab`

## Completed Preparation

The current preparation defines:

- the Oracle-conditioned component boundary;
- field-level Evidence references in the structured explanation output;
- seven semantic failure labels, including `PEDAGOGICAL_OVERREACH`;
- substantive-claim segmentation and support labels;
- correctness-first evaluation;
- a deterministic paraphrase lower bound;
- a Relation-only LLM no-Evidence control;
- one selectable Evidence-grounded method;
- proposed hard and secondary success gates;
- a 21-instance relation-stratified development benchmark;
- per-instance semantic review scaffolds defined before model output;
- strict benchmark creation and validation scripts.
- a synthetic evaluator suite covering semantic and fatal failures.

The 21 instances contain 40 human-validated Evidence items and cover:

| Relation | Instances |
| --- | ---: |
| `APPLIED_IN` | 8 |
| `REQUIRES` | 6 |
| `FORMALIZES` | 4 |
| `EXTENDS` | 2 |
| `CONTRASTS_WITH` | 1 |

`RELATED_TO` is excluded because Experiment 003 Ground Truth has no reliable
positive support.

## Development Boundary

The benchmark reuses human-validated positive Connections from Experiment 003
Ground Truth. It does not use Experiment 003 predictions. It is suitable for
development and method comparison but not for an independent claim.

No exact reference prose is treated as Ground Truth. The frozen Connection,
Evidence, required semantic points, forbidden claims, claim-level review, and
human rubric define the evaluation boundary.

## Synthetic Evaluator Validation

The offline evaluator regression suite covers:

- perfect Evidence-grounded output;
- semantic direction reversal;
- unsupported claims and Evidence overreach;
- endpoint drift;
- pedagogically empty but faithful output;
- pending claim adjudication;
- unknown Evidence references;
- missing required `why_connected` Evidence;
- `SOURCE_GROUNDED` claims without field-level Evidence references;
- missing instance alignment;
- stale review snapshots;
- no-Evidence baseline behavior.

Semantic failures remain scoreable. Alignment, snapshot, and Evidence transport
failures produce `evaluation_status = invalid` and no aggregate metrics.

## Pre-Execution Gate

Before any API call:

1. review the selected 21 Connection instances and annotation scaffolds;
2. review and accept or revise the proposed thresholds;
3. confirm claim segmentation examples and failure labels;
4. freeze the contract, schema, benchmark, rubric, and criteria in one clean
   repository commit;
5. create a clean-state execution manifest bound to that commit;
6. implement Baselines 001A and 001B before Method 002;
7. keep method identity hidden during claim and learning-value review.

The current completion marker intentionally records
`model_execution_authorized = false`.

The repository freeze was reported by the user and is bound in
`freeze_manifest.json`. No Git verification was performed by the assistant.
