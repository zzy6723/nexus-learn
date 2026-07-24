# ADR-006: Connection Discovery Validation Boundary

**Status:** Accepted
**Version:** v0.2
**Date:** 2026-07-24
**Last Updated:** 2026-07-24
**Owner:** Project

## Context

Connection Discovery is the central product capability: the system should find
which canonical Knowledge Objects form a useful, evidence-supported learning
connection across time, courses, or disciplines.

This capability is distinct from Relation Extraction. Relation Extraction
classifies a supplied candidate pair. Connection Discovery must first retain
useful candidates, reject unrelated or merely co-occurring pairs, and then
produce the correct typed and directed edge with semantically sufficient
Evidence.

Experiment 003 evaluated this boundary with Oracle canonical Knowledge Objects
so that Entity Extraction and canonicalization errors would not obscure the
Connection classifier.

## Decision

No Connection Discovery classifier is selected as an MVP or production
default.

The following scope decisions apply:

- `overlap_bridge_v0.1` is retained only as a development candidate generator;
- one-stage Prompt 002 is not selected;
- two-stage direct-edge gating v0.1.2 is not selected;
- endpoint-linked window verification v0.1.1 is not selected;
- exact Evidence-ID transport, snapshot-bound adjudication, strict schema
  validation, and fail-closed execution remain accepted infrastructure;
- predicted-canonical Connection Discovery is not authorized as product
  validation while the Oracle-canonical classifier gate remains failed;
- learner-facing Connection ranking and explanation are not authorized as
  product validation;
- Experiment 004 must not be presented as validated product capability.

The 125 selected development pairs have informed all three classifier designs.
They remain useful for regression testing and failure analysis but cannot
support an independent generalization claim for a future method.

## Evidence

### Candidate generation

The selected candidate generator retained all 41 primary positive pairs while
reducing the eligible universe from 387 to 125 pairs. All 41 primary positives
are `overlap_bridge` cases. Candidate coverage was therefore not the dominant
failure within the overlap-bridge primary scope of the current benchmark.

The benchmark contains no disjoint-provenance primary positives. Five
disjoint-provenance compositional positives are diagnostic-only, and the
selected candidate generator recovered none of them. The `41/41` result
therefore does not establish general disjoint-provenance discovery.

### One-stage classification

The refined one-stage method produced:

- positive edge precision `0.1667`;
- positive typed-edge recall `0.3171`;
- `NO_RELATION` accuracy `0.4872`;
- semantic Evidence support `0.4512`;
- full-universe F1 `0.2185`.

### Two-stage classification

The direct-edge gate recovered 37 of 41 positives but also passed 40 of 78
selected negatives. The final typed output produced:

- positive edge precision `0.1688`;
- positive typed-edge recall `0.3171`;
- `NO_RELATION` accuracy `0.4872`;
- semantic Evidence support `0.4096`;
- full-universe F1 `0.2203`.

### Endpoint-linked verification

The v0.2 development method generated 173 minimal endpoint-linked windows and
retained window coverage for all 41 primary positives. It improved several
diagnostics but still produced:

- positive edge precision `0.2206`;
- positive typed-edge recall `0.3659`;
- `NO_RELATION` accuracy `0.5385`;
- semantic Evidence support `0.4085`;
- full-universe F1 `0.2752`;
- 17 conflicting direct-edge aggregations.

It failed five of eight predeclared development criteria. Exact Evidence
materialization and `RELATED_TO` control passed, but exact transport did not
imply semantic support.

The endpoint-linked contract itself requires a same-lecture window containing
both endpoints. It therefore cannot directly verify a truly
disjoint-provenance pair with no shared lecture Evidence. This is a declared
method scope limitation, not a candidate-generation success.

## Interpretation

The current unresolved problem is semantic edge discrimination.

The tested LLM methods repeatedly treated one or more of the following as a
direct typed Connection:

- co-occurrence in the same derivation;
- participation in a shared method or formula;
- a mediated chain through a third Knowledge Object;
- a contrast between associated methods rather than the exact endpoints;
- a relation at the wrong abstraction level;
- the correct semantic relation serialized in the wrong direction.

Deterministic endpoint linking narrows the model input and improves auditability,
but it does not by itself establish the correct graph edge.

## Reopening Conditions

A future Connection Discovery cycle may begin only when it declares a
materially different learning or decision signal before model execution.
Examples include:

- frozen contrastive direct-versus-mediated examples;
- calibrated supervised or preference-based edge classification;
- a deterministic symbolic verifier for a limited Relation subset;
- a narrower product scope with separately validated Relation families.

The future cycle must:

1. keep the current benchmark as development or regression data only;
2. freeze the new method and success criteria before formal evaluation;
3. reserve a fresh explicitly annotated source for independent validation;
4. evaluate precision, recall, hard negatives, direction, Evidence semantics,
   and conflict behaviour;
5. pass the Oracle-canonical gate before predicted-canonical propagation;
6. pass discovery correctness before learner-facing ranking or explanation.

Pair-specific prompt tuning on the existing 125 candidates does not satisfy
these conditions.

## Consequences

Positive consequences:

- the project does not hide a failed central capability behind a polished UI;
- accepted benchmark, Evidence, runner, and adjudication infrastructure remain
  reusable;
- within the frozen overlap-bridge primary evaluation, the dominant observed
  failure is localized to semantic edge discrimination rather than candidate
  coverage or Evidence transport;
- future work has a clear independent-validation boundary.

Costs and limitations:

- the current MVP cannot yet deliver its central learner-facing promise;
- Experiment 004 remains blocked as downstream product validation. Separate
  Oracle-conditioned explanation research is scientifically possible but
  cannot validate the discovery pipeline;
- a materially different modeling approach and fresh annotation work are
  required;
- no claim is made about long documents, parsed PDFs, noisy predicted
  Knowledge Objects, broad STEM coverage, personalization, or stability.

## References

- `docs/decisions/004-relation-schema.md`
- `docs/decisions/005-knowledge-object-identity.md`
- `docs/decisions/007-oracle-conditioned-learning-explanation.md`
- `experiments/connection_discovery/README.md`
- `experiments/connection_discovery/conclusion.md`
- `experiments/connection_discovery/003_1_candidate_generation/conclusion.md`
- `experiments/connection_discovery/003_2_oracle_connection_discovery/conclusion.md`
- `experiments/connection_discovery/003_2b_direct_edge_gate/conclusion.md`
- `experiments/connection_discovery/003_2c_endpoint_linked_verifier/conclusion.md`
- `experiments/connection_discovery/experiment_v0_2_development_complete.json`
