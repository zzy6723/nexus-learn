# Evidence-ID Context Resolution Contract v0.2.1

**Status:** Development method candidate

v0.2.1 corrects the paragraph partitioner so that a final block followed by a
single trailing newline remains available in the catalog. The first v0.2
development run exposed this implementation defect when two Forward Euler
formula blocks were omitted. Identity labels and prompt semantics are
unchanged.

## Purpose

This iteration changes only evidence transport. It does not alter Knowledge
Object identity labels, candidate generation, cluster Ground Truth, or the
requirement that final evidence be an exact substring of a bound lecture.

## Deterministic Evidence Catalog

For each candidate request, the runner:

1. selects only the lectures referenced by the two candidate mentions;
2. partitions each lecture into non-empty paragraph blocks without rewriting
   source bytes;
3. assigns candidate-scoped opaque IDs in lecture and source order;
4. includes each ID, lecture ID, and exact block in `evidence_catalog`.

IDs have meaning only inside their candidate request. They are not product
identifiers and must not be compared across candidates or runs.

## Model Contract

The model returns candidate and endpoint IDs unchanged, one identity decision,
zero or more supplied evidence IDs, and a rationale. It never returns copied
evidence text.

The runner rejects unknown or duplicate evidence IDs. For every accepted ID,
it mechanically materializes the catalog entry into an exact
`{lecture_id, span}` record. A resolved decision requires at least one evidence
ID.

## Audit Boundary

The output retains both:

- the model-selected `evidence_ids`;
- runner-materialized exact `evidence_spans`.

Original Entity source spans and their exactness status remain unchanged in the
mention inventory. Evidence-ID materialization does not repair or overwrite
upstream Entity provenance.

## Validation Boundary

The authored 002C-2 challenge may be rerun to verify that v0.2 preserves known
identity behavior. The 002C-3 locked-reuse bundle may be used only as
development evidence for the transport fix because it caused the change.

A generalization or production-readiness claim requires a newly frozen source
that did not influence this contract or implementation.
