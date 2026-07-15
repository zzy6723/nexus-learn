# Locked-Reuse v0.1 Execution Failure

**Status:** Closed as execution-incomplete
**Scope:** `locked_reuse_v0_1`
**Condition reached:** A-prime only

## What Happened

The original formal A-prime request and one bounded retry both completed at the
API and JSON layers but failed the frozen prediction schema:

```text
request_success = true
json_parse_success = true
finish_reason = stop
prediction_schema_valid = false
prediction_schema_error = Prediction result 12 changed the candidate endpoints.
```

The frozen candidate `rel_holdout_016` contained:

```text
ko_slot_017 = Bisection Method
ko_slot_020 = Newton's Method
```

Both responses instead returned:

```text
ko_slot_018 = Damped Newton Method
ko_slot_020 = Newton's Method
relation_type = EXTENDS
```

That substituted edge is the edge belonging to the later candidate
`rel_holdout_035`. The two raw responses had different request IDs and hashes,
and differed on other predictions, so this was not replay of one raw response.
The parser did not transform endpoints, and the validator already permits a
source/target reversal when the unordered endpoint set is unchanged.

## Decision

- Preserve both failed attempts unchanged.
- Do not manually repair, omit, or score their predictions.
- Do not run B-prime without a valid paired A-prime condition.
- Do not continue retrying the same frozen single-request method.
- Record the failure as output-alignment unreliability of the full-bundle
  request, not as a Relation accuracy result.

The separately frozen `locked_reuse_v0_2` method revision uses one candidate
pair per request. It retains the endpoint validator and produces no aggregate
prediction unless all pair requests are valid.
