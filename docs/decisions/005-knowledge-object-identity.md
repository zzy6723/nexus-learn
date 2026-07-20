# ADR-005: Knowledge Object Identity And Mentions

**Status:** Accepted
**Version:** v0.2
**Date:** 2026-07-20
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

## Validation Evidence

Experiment 002C-2 supports the cluster model and candidate-scoped resolution
architecture on an authored development challenge. Context resolution achieved
complete identity-pair recall and precision with no provenance loss, while
Exact Name produced both false merges and false splits.

Experiment 002C-3 did not pass locked reuse. The selected resolver repeatedly
returned a Unicode evidence span that was not an exact substring of the bound
LaTeX lecture text. The strict runner rejected the response before clusters or
metrics were produced.

Experiment 002C-4 replaced copied evidence with candidate-scoped opaque IDs.
The v0.2.1 development method passed the authored challenge and the former
failure bundle with complete identity precision and recall, exact cluster
matches, no integrity or provenance failures, and semantically supported exact
evidence sets. The former failure bundle is development diagnostic data, not an
unseen holdout.

This evidence supported v0.2.1 as the candidate for independent validation. It
did not by itself authorize it as the product default.

Experiment 002C-5 freezes the complete v0.2.1 canonicalization pipeline and a
pre-existing four-lecture Entity bundle that did not participate in 002C method
development. The source contains 39 mentions, one positive identity pair, and
six selected hard-negative candidates. Benchmark, pipeline, success-criteria,
determinism, and blind Evidence-review contracts were frozen before formal
execution.

The unchanged pipeline then passed every independent gate: all seven required
candidate decisions, 38/38 exact clusters, zero integrity failures, 15/15 exact
Evidence materializations, 7/7 independently reviewed semantic Evidence sets,
and all five determinism checks. The source is independent with respect to
canonicalization method development, not a completely unseen corpus.

Identity-decision Evidence and mention provenance remain separate. Opaque
Evidence IDs preserve exact lecture spans selected for an identity decision;
they do not repair nonexact source spans inherited from Entity Extraction.

## Scope

ADR-005 authorizes the canonical mention/identity data model, the evidence-ID
transport contract, and v0.2.1 as the canonicalization method for the next
Technical Validation stage, including Experiment 003 use of canonical
endpoints. It does not authorize v0.2.1 as a production default,
learner-facing Connection ranking, or production identity resolution.

## References

- `docs/decisions/003-knowledge-object.md`
- `benchmark/ko_canonicalization_protocol.md`
- `benchmark/ko_canonicalization_annotation_guidelines.md`
- `experiments/knowledge_object_resolution/README.md`
- `experiments/knowledge_object_resolution/002c_5_independent_validation/final_results.md`
