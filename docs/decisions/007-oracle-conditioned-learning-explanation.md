# ADR-007: Oracle-Conditioned Learning Explanation

**Status:** Proposed for 004-0 freeze
**Version:** v0.2
**Date:** 2026-07-24
**Owner:** Project

## Context

Experiment 003 closed without selecting a validated Connection Discovery
method. Consequently, explanations generated from predicted Connections cannot
be evaluated as a downstream product pipeline: a fluent explanation could make
an incorrect edge appear convincing.

Learning Explanation remains a separable component question. A controlled
experiment can supply human-validated endpoints, Relation direction, and
Evidence, then test whether a model explains that fixed Connection faithfully
and usefully.

## Decision

Experiment 004 v0.1 is defined as:

> Oracle-Conditioned Learning Explanation component validation.

Its core question is:

> Given a validated typed Connection and its supporting Evidence, can the
> system generate a faithful, traceable, and educationally useful explanation
> of why the Connection exists and why it matters for learning?

The experiment receives:

- Oracle canonical source and target Knowledge Objects;
- an Oracle Relation type and direction;
- human-validated Evidence IDs and exact materialized spans.

The experiment may generate only:

- a concise Connection summary;
- an Evidence-grounded explanation of why the Connection holds;
- a generic account of its learning value;
- field-level references to supplied Evidence IDs.

Development compares:

- a deterministic Relation-paraphrase lower bound;
- a Relation-only LLM no-Evidence control;
- an Evidence-grounded LLM method.

Only the Evidence-grounded method is eligible for selection. The Relation-only
control measures plausible unsupported elaboration; it is not an alternative
product method.

## Excluded Capabilities

Experiment 004 v0.1 does not perform:

- Connection Discovery;
- Relation classification or direction selection;
- Evidence retrieval or Evidence discovery;
- Connection ranking;
- predicted-Connection error propagation;
- Learner State inference;
- personalization, recommendation, tutoring dialogue, quizzes, or flashcards.

The model must treat the supplied Connection as fixed. It may not repair,
replace, reject, or reinterpret the edge.

## Evaluation Order

Correctness is evaluated before usefulness:

1. Relation, direction, endpoints, Evidence, contradiction, and unsupported
   claims form the faithfulness gate.
2. Clarity, specificity, conceptual mechanism, and learning value are scored
   only for explanations that pass the faithfulness gate.

A fluent or pedagogically attractive explanation cannot compensate for a
faithfulness failure.

## Data Boundary

The first development benchmark may reuse human-validated positive Connections
from Experiment 003 Ground Truth. It may not use Experiment 003 model
predictions.

Because these Connections are existing development data, they cannot support an
independent Experiment 004 claim. If a development method passes its frozen
gate, a separate explanation benchmark must be annotated and hidden before
independent evaluation.

## Consequences

Positive:

- Experiment 004 can isolate explanation capability without weakening the
  negative Experiment 003 result.
- Evidence traceability remains deterministic through opaque IDs.
- Success or failure localizes another product hypothesis.

Negative:

- Passing Experiment 004 does not unblock the end-to-end MVP.
- Human claim-level and pedagogical review is required.
- Development results inherit the short-authored-snippet and relation-coverage
  limits of the source benchmark.

## References

- `docs/product_definition.md`
- `docs/decisions/006-connection-discovery-validation-boundary.md`
- `benchmark/learning_explanation_contract.md`
- `benchmark/learning_explanation_evaluation_protocol.md`
- `experiments/learning_explanation/README.md`
