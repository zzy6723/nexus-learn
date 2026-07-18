# 002C-2 Context Resolution Challenge Protocol

**Version:** ko_resolution_challenge_v0.1
**Status:** Frozen before context-resolver execution
**Data role:** Authored development challenge, not unseen holdout

## Objective

Test identity decisions that cannot be established safely from exact normalized
names alone. The challenge evaluates candidate generation, candidate-scoped
context decisions, transitivity checks, cluster finalization, and provenance.

## Composition

- 9 authored STEM mini lectures;
- 21 KO mentions;
- 13 canonical clusters;
- 6 multi-mention clusters and 7 singleton clusters;
- 10 `SAME_OBJECT` and 200 `DISTINCT_OBJECT` unordered mention pairs;
- 21/21 exact source spans.

The semantic coverage includes aliases, abbreviations, same-name homonyms, a
three-mention cluster, a symbol/name Formula identity, and cross-type
related-but-distinct objects.

## Candidate Boundary

Candidate generation is deterministic, type-preserving, Ground Truth blind,
and versioned separately from the resolver. It may use names, frozen aliases,
source spans, and lecture context. It may not read gold clusters, canonical IDs,
gold aliases, or mention-specific rules.

Candidate recall over gold `SAME_OBJECT` pairs is reported separately from
resolver quality. Unselected pairs are not silently treated as evidence that
the resolver predicted `DISTINCT_OBJECT`; they are attributed to candidate
generation.

## Resolver Boundary

The resolver receives exactly one unordered candidate pair with:

- opaque mention IDs;
- names and KO types;
- exact source spans;
- the two relevant lecture texts.

It returns exactly one of:

- `SAME_OBJECT`;
- `DISTINCT_OBJECT`;
- `UNRESOLVED`.

It does not emit canonical IDs or complete clusters. `UNRESOLVED` is preferred
to an unsupported merge.

## Cluster Finalization

Only `SAME_OBJECT` decisions create identity edges. Connected components form
provisional clusters. Before finalization, code checks every candidate decision
within each component for contradictions. A component containing both an
identity path and an explicit `DISTINCT_OBJECT` edge fails closed and requires
adjudication.

## Metrics

- candidate recall over gold `SAME_OBJECT` pairs;
- candidate reduction and candidate hard-negative count;
- SAME_OBJECT precision, recall, and F1;
- unresolved rate;
- inconsistent triangle/component count;
- manual adjudication count;
- false merges and false splits;
- B-cubed precision, recall, and F1;
- exact gold-cluster match rate;
- mention and provenance integrity.

Pairwise accuracy is not a primary metric.

## Interpretation

This is an authored development challenge. Passing supports method selection
for locked reuse; it does not establish generalization to unseen course data.
