# Knowledge Object Identity Evidence Review Protocol

**Version:** v0.1  
**Status:** Frozen before 002C-5 model execution

## Question

For a predicted identity decision, do the selected, mechanically materialized
lecture spans semantically support that decision without relying on omitted
text or external knowledge?

Exact substring validity and semantic support are different checks. The runner
verifies exact materialization mechanically. This protocol governs human review
of semantic self-containment.

## Review Labels

- `supported`: the selected spans, read together, identify both mentions or
  otherwise make the predicted identity decision unambiguous.
- `not_supported`: the decision may be correct, but the selected spans do not
  establish it, rely on unresolved references, or omit required mathematical
  content.
- `pending`: the reviewer cannot safely decide from the review package. Pending
  items prevent a final Evidence result.

## Blind Review Package

The review package must be generated before aggregate identity metrics are
opened. Each item receives a neutral `review_item_id` and contains only:

- candidate and mention IDs;
- mention names and types;
- predicted identity decision;
- selected evidence IDs and materialized spans;
- model rationale;
- the relevant lecture IDs.

The package must not contain:

- method, model, experiment, run, or prompt identity;
- aggregate scores or error labels;
- gold cluster IDs or gold identity labels;
- whether the item is expected to pass.

Review order is deterministic by neutral review item ID. The reviewer must not
open Ground Truth, aggregate metrics, or experiment identity until all items
are labelled.

## Adjudication Artifact

The adjudication must contain:

- the SHA-256 of the prediction bundle;
- the SHA-256 of the blind review package;
- exactly one decision for every review item;
- a non-empty rationale for `not_supported` and `pending`;
- no duplicate, unknown, stale, or unused decisions.

Any prediction or review-package hash mismatch invalidates the adjudication.
Finalization reports reviewed, supported, not-supported, pending, stale, and
unused counts. `pending`, stale, or unused decisions prevent final status.

## Scoring

Semantic support is reported at candidate-set level:

```text
supported candidate sets / reviewed candidate sets
```

It is not called model accuracy because the review denominator contains only
the model-selected Evidence sets. Exact materialization is reported separately
at selected-ID/span level.

## Development Audit Disclosure

The 002C-4 audits predate this frozen blind protocol. They were manual,
retrospective, and unblinded, and are retained as development diagnostics.
Only an audit executed under this protocol may support the 002C-5 independent
Evidence claim.
