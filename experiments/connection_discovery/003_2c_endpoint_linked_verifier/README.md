# 003-2c: Endpoint-Linked Evidence Verification

**Status:** v0.1.1 development evaluation completed; frozen criteria failed

## Objective

Experiment 003-2c tests whether Connection precision improves when the model no
longer searches an entire candidate Evidence catalog while deciding an edge.
Instead, a deterministic preprocessor constructs minimal same-lecture Evidence
windows that explicitly cover both candidate endpoints. The model classifies
each window before any graph edge is emitted.

This is a new Experiment 003 v0.2 method cycle. It does not reopen or overwrite
the completed v0.1 result.

## Method Boundary

For each selected canonical pair:

1. link Evidence blocks to endpoint A and endpoint B using only canonical names,
   frozen aliases, and frozen mention source spans;
2. construct minimal contiguous same-lecture windows of at most three blocks
   that cover both endpoints;
3. classify each window as `DIRECT_IN_SCHEMA`, `DIRECT_OUT_OF_SCHEMA`,
   `MEDIATED_OR_CONTEXTUAL`, or `INSUFFICIENT`;
4. emit a typed graph edge only when the window is `DIRECT_IN_SCHEMA`;
5. aggregate window decisions deterministically and fail closed to
   `NO_RELATION` when no direct edge exists or direct windows conflict.

The model never receives Ground Truth category, gold Relation, gold Evidence,
primary-scoring eligibility, or annotation rationale.

Because each valid window belongs to one lecture and must cover both endpoints,
this method cannot directly verify a truly disjoint-provenance pair for which
no single lecture contains both endpoints. Such pairs are outside the primary
v0.2 scope.

## Development and Validation Boundary

The existing 125-pair benchmark may be used only as a development diagnostic
because its errors informed this method. Passing it cannot establish
generalization. Before any independent claim, the frozen method must be run on
a fresh source whose pair categories are explicitly reviewed under the v0.2
scope taxonomy.

## Artifacts

- `v0_1_failure_analysis.md`;
- `method_contract_v0_1.md`;
- `success_criteria_v0_1.json`;
- `window_verifier_prompt.md`;
- `method_preflight_v0_1.json`;
- `method_preflight_v0_1_1.json`;
- deterministic Evidence-window bundle;
- candidate-scoped verifier outputs;
- final canonical Connection predictions and evaluation;
- `development_results.md`;
- `development_comparison.json`;
- `aggregation_analysis.json`;
- `conclusion.md`;
- `development_validation_complete.json`.

No formal API run is allowed until the method implementation, tests, prompt,
and success criteria are repository-frozen at one clean commit.

## v0.1 Execution Failure

The first formal run completed 42 windows before the model returned
`FORMALIZES` with a `Concept` source. The API request and JSON parse succeeded,
but strict schema validation failed. No aggregate prediction was produced and
the run is not evaluable.

Runner v0.1.1 adds one generic validator-guided schema-repair attempt. This is
an execution-contract repair, not a prompt or benchmark change. The failure is
bound in `v0_1_schema_failure.md` and `v0_1_schema_failure.json`. A new formal
run must use a new directory; `run_01` is retained unchanged.

## Deterministic Development Diagnostic

The gold-free generator produces 173 minimal windows over 111 of the 125
selected pairs. Fourteen pairs receive deterministic no-window rejections.
When the generated pair coverage is compared with Ground Truth only after
generation, all 41 primary positive pairs retain at least one window and 65 of
78 primary negatives retain a window.

This confirms that the preprocessor can narrow Evidence without losing a
current development positive. It is not a validation result because the old
benchmark informed the three-block limit and endpoint-linking design. The
machine-readable record is `development_window_diagnostic.json`.

## Final Development Result

Runner v0.1.1 completed 173 window requests and emitted predictions for all 125
candidates. Three schema-invalid model responses were handled by the frozen
single-repair contract. The final evaluation resolved all 65 pending Evidence
cases and reached `evaluation_status = final`.

The method improved several diagnostics but failed five of eight predeclared
003-2c criteria. It achieved `0.2206` positive precision, `0.3659` positive
typed-edge recall, `0.5385` `NO_RELATION` accuracy, and `0.4085` semantic
Evidence support. Seventeen aggregation conflicts also exceeded the maximum of
two. No Connection Discovery default is selected.
