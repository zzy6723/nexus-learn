# 003-2b: Two-Stage Direct-Edge Connection Discovery

**Status:** Method implementation prepared; no model run completed

## Motivation

Experiment 003-2 v0.1 and Prompt 002 both failed the frozen Oracle-canonical
classification and full-universe gates. Prompt 002 reduced overconnection, but
40 false-positive Relations remained and positive recall and direction declined.

The residual errors are architectural: one request must simultaneously decide
whether a direct edge exists, choose Evidence, select a Relation type, and
serialize direction. This method separates those decisions without modifying
the frozen benchmark, candidate set, Ground Truth, evaluator, or success
criteria.

## Method

### Stage A: Direct-edge gate

For every selected unordered canonical pair, decide:

- `DIRECT_CONNECTION`; or
- `NO_RELATION`.

A positive gate requires a non-empty set of candidate-scoped Evidence IDs that
directly connects the two endpoints without an unstated intermediate object.

### Stage B: Relation typing

Only Stage-A positives proceed. Stage B receives:

- the same canonical endpoints;
- only the Evidence blocks selected by Stage A;
- the frozen ADR-004 Relation schema.

It may still return `NO_RELATION` when the selected Evidence does not establish
one in-schema Relation. Otherwise it must type and direct the edge. Stage-B
Evidence must be a non-empty subset of the Stage-A selection.

Stage-A rationales and decisions are not passed to Stage B, preventing the
second stage from merely repeating the first stage's conclusion.

## Output

The final aggregate prediction uses the existing
`canonical_connection_predictions` v0.1 contract, so the frozen 003-2 evaluator
and success criteria remain unchanged.

## Execution Boundary

- one candidate per request;
- no gold category, edge, Evidence, score, or eligibility fields;
- exact endpoint and Evidence-ID validation;
- no-overwrite and clean-method-commit enforcement;
- raw response, parsed output, per-stage metadata, and aggregate metadata
  retention;
- fail-closed behavior for request, parse, or schema failures;
- no pair-specific prompt rules.

## Interpretation

This is a new development method version, not Prompt 003. A relative gain is not
sufficient: it must be evaluated against the unchanged frozen gates. It cannot
support an independent-validation claim because the same development benchmark
informed its design.

Stage-A diagnostics are frozen before execution to aid attribution. They do not
replace the original 003-2 success criteria:

- primary direct-edge recall: at least `0.80`;
- primary direct-edge precision: at least `0.70`;
- primary negative accuracy: at least `0.80`;
- Stage-A semantic Evidence support: at least `0.90`;
- fatal alignment errors: `0`.

The combined output must still pass every original conditional-classification
and full-universe gate before the method can advance.
