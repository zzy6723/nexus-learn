# Endpoint-Linked Verifier Method Contract v0.1

**Status:** Draft for implementation freeze

## Inputs

The deterministic window generator receives only:

- the frozen candidate selection;
- the Oracle canonical inventory;
- the candidate-scoped Evidence catalogs;
- a declared maximum window size of three contiguous blocks.

It must reject duplicate pair IDs, endpoint mismatches, duplicate Evidence IDs,
non-contiguous block ordering, unknown canonical objects, and any input carrying
gold category, Relation, Evidence, rationale, or scoring fields.

## Endpoint Linking

An Evidence block covers one endpoint when it contains at least one frozen:

- canonical name;
- alias; or
- mention source span.

Matching uses NFKC normalization, case folding, whitespace normalization, and
token-boundary phrase matching. No embedding model, Relation label, or Ground
Truth field participates.

## Window Construction

A valid Evidence window:

- belongs to one lecture;
- contains one to three contiguous Evidence blocks;
- covers both endpoints across those blocks;
- is minimal, meaning no strict subwindow also covers both endpoints.

Window identity is a stable hash of pair ID, lecture ID, and ordered Evidence
IDs. Pairs without a valid window are deterministically eligible only for
`NO_RELATION` under this method.

## Window Verification Labels

`DIRECT_IN_SCHEMA`
: The selected window itself establishes one ADR-004 Relation between the exact
  endpoints without an omitted intermediate object.

`DIRECT_OUT_OF_SCHEMA`
: The selected window explicitly connects the endpoints, but none of the frozen
  Relation types represents the connection faithfully.

`MEDIATED_OR_CONTEXTUAL`
: The endpoints share a context or are connected only through another object,
  method, formula, or multi-step path.

`INSUFFICIENT`
: The window does not establish a meaningful connection between the endpoints.

Only `DIRECT_IN_SCHEMA` may contain a Relation type, directed endpoints, and
selected Evidence IDs for a final graph edge.

## Deterministic Aggregation

For each canonical pair:

- no `DIRECT_IN_SCHEMA` window produces `NO_RELATION`;
- one unique directed typed edge produces that edge;
- multiple windows supporting the same edge select the smallest Evidence set,
  then the lexicographically first window ID;
- conflicting direct edges fail closed to `NO_RELATION` and are recorded as an
  aggregation conflict.

Aggregation may not use confidence scores or gold-aware tie breaking.

## Evaluation Boundary

Development evaluation reports:

- endpoint-window coverage;
- windows and model requests per pair;
- deterministic no-window rejections;
- support-class distribution;
- aggregation conflicts;
- final conditional and full-universe Connection metrics;
- exact and semantic Evidence support.

The existing v0.1 Connection evaluator remains authoritative for final graph
edges. Window-level labels are diagnostic until a separately annotated window
benchmark exists.
