# 003-2 Evidence Semantic-Support Adjudication Protocol

**Status:** Ready to freeze before model execution
**Version:** v0.1

## Unit

Review one predicted positive canonical edge together with only its selected,
deterministically materialized Evidence blocks and rationale.

Choose:

- `supported`: the selected blocks, read together, directly establish the
  predicted Relation and direction;
- `not_supported`: the blocks mention endpoints, provide only proximity, leave
  a required reference unresolved, or otherwise fail to establish the edge.

Do not judge whether the prediction matches Ground Truth, whether the result
helps a metric, or whether outside STEM knowledge makes the edge plausible.

## Automatic Cases

A predicted edge is automatically supported only when it matches a frozen gold
edge and selects exactly the frozen gold Evidence-ID set. A positive prediction
with no Evidence is automatically not supported. Every other positive
prediction enters the snapshot-bound review set.

## Snapshot Binding

The adjudication must copy both `prediction_content_sha256` and
`pending_snapshot_sha256` from `adjudication_pending.json` and provide exactly
one decision for every pending pair. Missing, duplicate, extra, or stale
decisions invalidate evaluation.

Use this structure:

```json
{
  "artifact_type": "canonical_connection_evidence_adjudication",
  "version": "v0.1",
  "prediction_content_sha256": "...",
  "pending_snapshot_sha256": "...",
  "decisions": [
    {
      "canonical_pair_id": "conn_dev_pair_...",
      "decision": "supported",
      "rationale": "The selected blocks directly establish the predicted edge."
    }
  ]
}
```

Re-evaluation may replace a draft evaluation only when the prediction binding
is unchanged. A final or invalid evaluation is never overwritten.
