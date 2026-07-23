# Experiment 003: Connection Discovery

**Status:** v0.1 and v0.2 development cycles completed with negative results
**Current stage:** Experiment 003 closed; no validated Connection method selected

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
| 003-1 | Oracle-Canonical Candidate Generation | Completed and repository-frozen |
| 003-2 | Oracle-Canonical Connection Discovery | Completed; frozen gates failed |
| 003-2b | Two-Stage Direct-Edge Connection Discovery | Completed; execution recovered, frozen quality gates failed |
| 003-2c | Endpoint-Linked Evidence Verification | Completed; modest diagnostic gains, frozen development criteria failed |
| 003-3 | Predicted-Canonical End-to-End Discovery | Not executed; Oracle gate precondition failed |
| 003-4 | Connection Selection and Ranking | Not executed; no validated Connection set |
| 003-5 | Independent Validation | Not executed; no method qualified |

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
- 003-2 comparison: `003_2_oracle_connection_discovery/development_comparison.md`
- 003-2 conclusion: `003_2_oracle_connection_discovery/conclusion.md`
- 003-2b method: `003_2b_direct_edge_gate/README.md`
- 003-2b results: `003_2b_direct_edge_gate/development_results.md`
- 003-2b conclusion: `003_2b_direct_edge_gate/conclusion.md`
- 003-2c method: `003_2c_endpoint_linked_verifier/README.md`
- 003-2c results: `003_2c_endpoint_linked_verifier/development_results.md`
- 003-2c comparison: `003_2c_endpoint_linked_verifier/development_comparison.json`
- 003-2c conclusion: `003_2c_endpoint_linked_verifier/conclusion.md`
- Experiment conclusion: `conclusion.md`
- v0.1 machine-readable closure: `experiment_validation_complete.json`
- v0.2 development closure: `experiment_v0_2_development_complete.json`
- Draft protocol: `../../benchmark/connection_discovery_protocol.md`
- Draft annotation rules:
  `../../benchmark/connection_discovery_annotation_guidelines.md`

## Final v0.1 Decision

Candidate generation was feasible, but one-stage and two-stage
Oracle-canonical Connection classification both failed the frozen conditional
and full-universe gates. No validated Connection classifier is selected.

Stages 003-3 through 003-5 were intentionally not executed because their
preconditions were not met. Experiment 003 v0.1 is closed as a valid negative
result. Any future v0.2 must declare a materially revised method and use fresh
evaluation data rather than continue pair-specific prompt tuning on the current
development benchmark.

## Final v0.2 Development Decision

The endpoint-linked v0.1.1 verifier completed all 173 window requests over the
same 125 development candidates. It modestly improved positive precision,
typed-edge recall, negative accuracy, direction, and full-universe F1, but
failed five of eight predeclared 003-2c criteria. Semantic Evidence support
remained `0.4085`, and 17 conflicting window-level edges forced fail-closed
aggregation.

No endpoint-linked verifier is selected. The old benchmark is now exhausted as
development data for these methods; it cannot support an independent claim.
Experiment 003 is closed as a negative Technical Validation programme. Stages
003-3 through 003-5 remain unexecuted, and Experiment 004 product validation is
not authorized.
