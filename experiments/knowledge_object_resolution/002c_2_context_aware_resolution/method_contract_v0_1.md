# 002C-2 Context Resolution Method Contract v0.1

**Status:** Frozen before formal API execution
**Method:** `candidate_scoped_context_resolution_v0_1`

## Deterministic Candidate Generation

Candidate generation is same-type and Ground-Truth blind. A pair is selected
when at least one frozen rule fires:

1. exact safely-normalized name;
2. identity under the pre-existing frozen alias resource;
3. equal ordered alphanumeric name tokens after punctuation segmentation;
4. generic initialism/name correspondence;
5. strict name-token containment;
6. an exactly equal source span.

These rules only propose pairs. They never create identity edges.

## Context Decision

Each request contains exactly one unordered candidate pair, its opaque mention
IDs, names, KO types, source spans, and the relevant lecture text. It contains
no gold cluster, canonical ID, annotation rationale, expected decision, or
success criterion.

The resolver returns `SAME_OBJECT`, `DISTINCT_OBJECT`, or `UNRESOLVED` with
exact lecture evidence. Only `SAME_OBJECT` creates an identity edge.

## Formal Request Configuration

- provider: DeepSeek;
- model: `deepseek-v4-flash`;
- temperature: `0`;
- top_p: `1`;
- max_tokens: `1200` per candidate;
- response format: JSON object;
- thinking: disabled;
- partitioning: one candidate pair per request.

## Execution Discipline

- dry runs do not count as formal attempts;
- formal attempts must begin from a clean worktree at the declared method
  commit;
- the first complete schema-valid run is evaluated;
- a new attempt is allowed only after a technical request, parse, finish-reason,
  or schema failure, never because of unfavorable semantic metrics;
- failed attempts remain preserved and do not enter metric denominators;
- at most three technical attempts are permitted;
- no `--overwrite` is used for formal runs.

## Cluster Safety

`SAME_OBJECT` connected components are provisional. A component containing an
explicit `DISTINCT_OBJECT` candidate decision fails closed. `UNRESOLVED` also
requires snapshot-bound adjudication before cluster generation. Cross-type
clusters and incomplete provenance are fatal.

## Selection Order

The Exact deterministic baseline and context-aware method are compared on the
frozen authored development challenge. Selection follows the predeclared
success criteria, prioritizing zero false merges, zero inconsistent
components, complete provenance, higher SAME_OBJECT recall, and then lower
unresolved rate. No production or unseen-generalization claim is made.
