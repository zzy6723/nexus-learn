# 003-0C Annotation Summary

**Status:** Complete and ready for repository freeze
**Model calls:** None

## Frozen Denominators

| Category | Count |
| --- | ---: |
| Eligible canonical pairs | 387 |
| Primary scored pairs | 376 |
| Primary positives | 41 |
| Primary negatives | 335 |
| Diagnostic pairs | 11 |
| In-schema Connections, including diagnostic | 46 |
| Schema-gap pairs | 6 |

Primary Relation support is:

| Relation | Support |
| --- | ---: |
| `APPLIED_IN` | 26 |
| `REQUIRES` | 8 |
| `FORMALIZES` | 4 |
| `EXTENDS` | 2 |
| `CONTRASTS_WITH` | 1 |
| `RELATED_TO` | 0 |

`RELATED_TO` may be evaluated for fallback overuse but cannot be described as
positively validated.

## Evidence

The gold-blind generator produced 387 candidate-scoped catalogs containing
6,093 exact semantic blocks. Ground Truth selected 99 Evidence items, all of
which match the bound catalog snapshots exactly.

Positive Evidence support comprises:

- 41 primary `single_lecture_explicit` Connections;
- 5 diagnostic `multi_lecture_compositional` Connections.

The compositional cases are excluded from v0.1 primary scoring.

## Negative Review

All eligible pairs received a category. A shared-block risk audit found five
negative pairs whose endpoint mention spans occur in the same Evidence block.
All five have explicit hard-negative rationales; none remains hidden under the
generic default-negative decision.

The audit found no stale pair, endpoint, hash, Evidence, count, or review
alignment error.

## Scope Limitation

Every primary positive is an `overlap_bridge`. The five positive
`disjoint_provenance` pairs require multi-lecture composition and are diagnostic.

Therefore Experiment 003 v0.1 can test explicit reconnection when an earlier
canonical object reappears in a later lecture. It cannot establish primary
performance on implicit disjoint-document reasoning. This limitation is frozen
in the protocol and success criteria.

## Gate

`completion.json` reports `ready_for_repository_freeze` and keeps
`model_execution_allowed = false`. A clean repository freeze and a hash-bound
execution manifest are required before 003-1.
