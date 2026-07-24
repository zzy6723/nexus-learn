# Experiment 004: Oracle-Conditioned Learning Explanation

**Status:** 004-0 structurally prepared; pending human review and repository freeze
**Product boundary:** Downstream predicted-Connection explanation remains blocked

## Objective

Experiment 004 asks:

> Given a validated typed Connection and its supporting Evidence, can the
> system generate a faithful, traceable, and educationally useful explanation
> of why the Connection exists and why it matters for learning?

The experiment isolates Learning Explanation from the unresolved Connection
Discovery bottleneck. Passing it would validate only the Oracle-conditioned
component, not the end-to-end MVP.

## Stages

| Stage | Name | Status |
| --- | --- | --- |
| 004-0 | Benchmark and Evaluation Preparation | Structurally prepared; pending review and freeze |
| 004-1 | Deterministic Relation-Paraphrase Baseline | Not started |
| 004-2 | Evidence-Grounded Explanation Method | Not started |
| 004-3 | Faithfulness and Learning-Value Evaluation | Not started |
| 004-4 | Independent Validation | Not authorized until development gates pass |

## Boundary

Experiment 004 v0.1 uses:

- human-validated canonical endpoints;
- human-validated Relation type and direction;
- human-validated Evidence IDs and exact spans.

It does not use:

- Experiment 003 model predictions;
- Connection or Evidence discovery;
- Connection ranking;
- predicted-Connection propagation;
- Learner State or personalization.

## Evaluation Order

Faithfulness is a hard gate. Learning-value scores are considered only for
faithfulness-passing explanations. A fluent explanation cannot repair a
Relation distortion, direction reversal, endpoint drift, contradiction, or
unsupported substantive claim.

## Records

- decision: `../../docs/decisions/007-oracle-conditioned-learning-explanation.md`;
- contract: `../../benchmark/learning_explanation_contract.md`;
- annotation rules:
  `../../benchmark/learning_explanation_annotation_guidelines.md`;
- evaluation protocol:
  `../../benchmark/learning_explanation_evaluation_protocol.md`;
- proposed success criteria:
  `../../benchmark/learning_explanation_success_criteria_v0_1.json`;
- development benchmark:
  `../../benchmark/learning_explanation/development_v0_1/`;
- 004-0 status: `004_0_benchmark_preparation/README.md`.
- authoritative machine-readable status: `experiment_status.json`.

No model API run is authorized until 004-0 review is complete, the proposed
thresholds are accepted, all preparation artifacts are repository-frozen, and
the clean-state preflight records the frozen commit.
