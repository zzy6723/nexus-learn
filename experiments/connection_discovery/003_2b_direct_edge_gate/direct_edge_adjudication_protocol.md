# Direct-Edge Gate Evidence Adjudication Protocol

**Status:** Ready to freeze before model execution
**Version:** v0.1

## Unit

Review one Stage-A `DIRECT_CONNECTION` decision using only its canonical
endpoints, selected materialized Evidence blocks, and rationale.

Choose:

- `supported`: the blocks, read together, directly establish one educational
  predicate between the endpoints without an unstated intermediate object;
- `not_supported`: the blocks establish only proximity, separate endpoint facts,
  a transitive chain, unresolved reference, instance membership, or an argument
  requiring outside knowledge.

Do not judge the eventual Relation type, direction, Ground Truth match, or metric
effect.

## Automatic Cases

A Stage-A positive is automatically supported only when its selected Evidence-ID
set exactly matches the frozen gold Evidence-ID set for a primary positive pair.
Every other Stage-A positive enters snapshot-bound review.

## Snapshot Binding

The adjudication must copy `prediction_content_sha256` and
`pending_snapshot_sha256` from `adjudication_pending.json` and provide exactly
one decision for every pending item:

```json
{
  "artifact_type": "direct_edge_evidence_adjudication",
  "version": "v0.1",
  "prediction_content_sha256": "...",
  "pending_snapshot_sha256": "...",
  "decisions": [
    {
      "canonical_pair_id": "conn_dev_pair_...",
      "decision": "supported",
      "rationale": "The selected blocks directly connect both endpoints."
    }
  ]
}
```

Missing, duplicate, extra, or stale decisions invalidate the evaluation.
