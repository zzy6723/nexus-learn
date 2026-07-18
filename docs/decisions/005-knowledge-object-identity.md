# ADR-005: Knowledge Object Identity And Mentions

**Status:** Accepted
**Version:** v0.1
**Date:** 2026-07-18
**Owner:** Project

## Context

Entity Extraction produces lecture-local Knowledge Objects. Experiment 002B
showed that these predicted objects can participate in Relation Classification,
but the pipeline still treats repeated appearances across lectures as separate
records.

The product needs to distinguish a source mention from the stable educational
identity that may be referenced across time, courses, and disciplines.

## Decision

A predicted lecture-local Knowledge Object is a mention. A canonical Knowledge
Object is a separate identity record containing one or more mention references.

Canonicalization must:

- assign every mention to exactly one canonical identity;
- preserve explicit singleton identities;
- retain all mention-level source provenance;
- use stable canonical IDs that do not depend on a current display name;
- forbid cross-type identity merges by default;
- keep related-but-distinct Concepts, Methods, and Formulas separate.

Cluster-level Ground Truth is the authoritative annotation form. Pairwise
`SAME_OBJECT` and `DISTINCT_OBJECT` labels are derived from cluster membership
rather than annotated independently.

## Relationship To ADR-003

ADR-003 defines the initial Knowledge Object types and illustrates semantic
object IDs. This ADR refines the identity layer: benchmark and product identity
records should use stable IDs separate from mutable names and aliases. Semantic
names remain human-readable fields.

## Relationship To 002B-1 Alignment

The 002B-1 alignment mapped predicted mentions to an existing Oracle inventory
for evaluation. It was not a product resolution method.

Experiment 002C resolves multiple predicted mentions into canonical identities
without requiring a pre-existing Oracle object for each mention.

## Consequences

Positive consequences:

- identity is transitive by construction;
- provenance survives deduplication;
- canonical names and aliases can evolve without changing identity;
- cross-lecture candidate discovery can operate on stable objects;
- formulas and the concepts or methods they formalize remain distinguishable.

Costs and limitations:

- canonicalization requires a new benchmark and evaluator;
- exact-name matching cannot resolve aliases or contextual ambiguity;
- incorrect merges can contaminate every downstream Relation;
- conservative splitting may leave duplicates unresolved;
- canonical ID lifecycle and cluster revision need explicit versioning.

## Scope

ADR-005 authorizes Experiment 002C-1 controlled canonicalization. It does not
authorize cross-course Relation extraction, learner-facing Connection ranking,
or production identity resolution.

## References

- `docs/decisions/003-knowledge-object.md`
- `benchmark/ko_canonicalization_protocol.md`
- `benchmark/ko_canonicalization_annotation_guidelines.md`
- `experiments/knowledge_object_resolution/README.md`
