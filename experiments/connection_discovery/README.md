# Experiment 003: Connection Discovery

**Status:** In progress
**Current stage:** 003-1 candidate-generation implementation

## Objective

Experiment 003 evaluates whether the system can discover evidence-supported,
typed Connection Hypotheses between distinct canonical Knowledge Objects.

The experiment starts from the canonical mention/identity model accepted in
ADR-005. The selected v0.2.1 canonicalization pipeline is an authorized
Technical Validation input, not a production-ready component.

## Boundary

Experiment 003 separates four questions:

1. Which canonical pairs should reach Relation classification?
2. Which typed and directed Relation, if any, is supported?
3. How much upstream Entity and canonicalization error propagates?
4. Which correct Connections are useful enough to show a learner?

The first three questions concern discovery correctness. Educational selection
and ranking are evaluated separately. Full learner-facing explanations remain
deferred to Experiment 004.

## Stages

| Stage | Name | Status |
| --- | --- | --- |
| 003-0 | Benchmark and Evaluation Preparation | Completed and repository-frozen |
| 003-1 | Oracle-Canonical Candidate Generation | Implementation in progress |
| 003-2 | Oracle-Canonical Connection Discovery | Pending |
| 003-3 | Predicted-Canonical End-to-End Discovery | Pending |
| 003-4 | Connection Selection and Ranking | Pending |
| 003-5 | Independent Validation | Pending |

No Connection model run is allowed before the 003-0 source, pair universe,
Ground Truth, evaluation protocol, success criteria, and leakage audit are
frozen.

The 003-0 freeze manifest was committed at
`11f7696ba829e9f3c51eb2fcac04757fdcdfd2a3`. 003-1 formal artifacts must bind
both this manifest and the later candidate-method commit.

## Initial v0.1 Decisions

- Endpoints are distinct canonical Knowledge Objects.
- Candidate identity is one stable unordered canonical pair.
- Relation output is one primary Relation under ADR-004 or `NO_RELATION`.
- Same-canonical-object mention pairs are excluded.
- `OUT_OF_SCHEMA_CONNECTION` and `AMBIGUOUS` remain diagnostic by default.
- Candidate-scoped opaque Evidence IDs are materialized deterministically.
- Multi-lecture compositional Evidence is diagnostic in the first benchmark.
- Oracle canonical endpoints are evaluated before predicted endpoints.

## Records

- 003-0 status: `003_0_benchmark_preparation/README.md`
- First source audit: `003_0_benchmark_preparation/source_adequacy_audit.md`
- Draft protocol: `../../benchmark/connection_discovery_protocol.md`
- Draft annotation rules:
  `../../benchmark/connection_discovery_annotation_guidelines.md`
