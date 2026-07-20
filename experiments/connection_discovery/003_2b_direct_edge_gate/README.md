# 003-2b: Two-Stage Direct-Edge Connection Discovery

**Status:** v0.1.1 interrupted by a transport timeout; v0.1.2 recovery prepared

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

## Execution Reliability Revision

The first two v0.1 formal attempts completed Stage A but failed at the same
Stage-B candidate because the model returned `FORMALIZES` with a non-Formula
source. The strict validator correctly rejected both attempts. Neither attempt
produced an evaluable final bundle, and neither output may be manually repaired.

Runner v0.1.1 permits at most one validator-guided repair after a Stage-B API
request and JSON parse have succeeded but schema validation has failed. The
repair request receives only:

- the unchanged candidate and Stage-A-selected Evidence;
- the model's original response;
- the deterministic validator error.

It receives no Ground Truth or scoring information. The original raw response
and repair payload are retained. Request failures, JSON parse failures, and
semantic evaluation errors are not retried. If the repair remains invalid, the
whole run still fails closed.

The two failed v0.1 attempts are bound in:

- `v0_1_execution_failures.md`;
- `v0_1_execution_failures.json`.

The first v0.1.1 formal attempt completed all 125 Stage-A requests and 37 of
83 Stage-B requests before a response read timed out. The timeout escaped the
v0.1.1 exception boundary, so no aggregate run metadata or evaluable final
prediction was produced. This is an infrastructure failure, not a model or
evaluation result. Its immutable partial artifacts are described in:

- `v0_1_1_transport_failure.md`;
- `v0_1_1_transport_failure.json`.

Runner v0.1.2 adds only execution reliability behavior:

- prepared aggregate metadata is written before the first API request;
- transport failures receive at most two bounded retries;
- retry exhaustion is recorded and remains fail closed;
- an interrupted run may be resumed only after every reused Stage-A result and
  the exact Stage-B completion prefix are re-parsed, revalidated, and hash-bound;
- no benchmark, prompt, Evidence, prediction, or schema rule is changed.

For the recorded v0.1.1 interruption, local preflight validated 125 Stage-A
results, 83 Stage-A positives, and the exact 37-result Stage-B prefix. The next
eligible Stage-B pair is `conn_dev_pair_9a51109c78e243ef`. The resumed run must
use a new directory and method commit; the source run remains unchanged and is
never itself completed or evaluated.

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
