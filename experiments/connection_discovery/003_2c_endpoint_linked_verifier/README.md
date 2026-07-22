# 003-2c: Endpoint-Linked Evidence Verification

**Status:** Method implementation complete; repository freeze pending

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

## Development and Validation Boundary

The existing 125-pair benchmark may be used only as a development diagnostic
because its errors informed this method. Passing it cannot establish
generalization. Before any independent claim, the frozen method must be run on
a fresh source whose pair categories are explicitly reviewed under the v0.2
scope taxonomy.

## Planned Artifacts

- `v0_1_failure_analysis.md`;
- `method_contract_v0_1.md`;
- `success_criteria_v0_1.json`;
- `window_verifier_prompt.md`;
- `method_preflight_v0_1.json`;
- deterministic Evidence-window bundle;
- candidate-scoped verifier outputs;
- existing canonical Connection predictions for final evaluation.

No formal API run is allowed until the method implementation, tests, prompt,
and success criteria are repository-frozen at one clean commit.

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
