# Knowledge Object Canonicalization Protocol

**Version:** ko_canonicalization_protocol_v0.1
**Status:** Development protocol
**Experiment:** 002C-1 Controlled KO Canonicalization

## Objective

Given predicted lecture-local Knowledge Object mentions, assign every mention
to exactly one canonical identity cluster while preserving mention-level source
provenance.

Canonicalization answers:

> Do these mentions denote the same educational object?

It does not answer whether two distinct objects are related, whether a
Connection is pedagogically useful, or which object is a prerequisite.

## Data Roles

The initial 39-mention source originated in an earlier Relation holdout but has
already been inspected. Its 002C role is therefore development reuse, not
unseen holdout.

Ground Truth is cluster-level. Pairwise identity labels are derived
deterministically:

- two mentions in the same gold cluster are `SAME_OBJECT`;
- two mentions in different gold clusters are `DISTINCT_OBJECT`.

No pairwise annotation file is maintained manually.

## Identity Contract

- A lecture-local extracted KO is a mention, not a canonical object.
- A canonical object is an identity record whose membership references one or
  more mentions.
- Every mention is assigned to exactly one canonical object.
- Singleton mentions receive explicit canonical records.
- Canonical IDs are opaque, stable benchmark identifiers. Names and aliases may
  evolve without changing identity.
- Canonical records retain all provenance through their mention memberships.
- Canonicalization must never delete or rewrite the source mention artifact.
- Predicted source spans are preserved verbatim. Exact-substring compliance is
  recorded separately and must not be repaired during inventory generation.

## Type Boundary

Cross-type merges are forbidden in v0.1.

Closely related objects remain distinct identities when their educational type
or role differs. Examples include:

- `Gradient` (`Concept`) and a gradient expression (`Formula`);
- `Chain Rule` (`Concept` or `Method`) and `Chain Rule Formula` (`Formula`);
- `Newton's Method` (`Method`) and `Newton Update Formula` (`Formula`).

These objects may later be connected by typed Relations. They are not identity
duplicates.

## Name And Context Rules

- Equal normalized names are candidate evidence, not unconditional identity.
- Different names may denote one object when a predeclared alias and compatible
  context support the merge.
- Same-name mentions remain distinct when their definitions, domain roles, or
  mathematical referents differ.
- Type agreement is necessary but not sufficient.
- General mathematical knowledge may support annotation, but the benchmark
  rationale must identify the contextual basis for the decision.

## Baseline Isolation

Methods under evaluation may read:

- mention names and types;
- mention source spans;
- source lecture text;
- predeclared method configuration or alias resources.

They may not read:

- canonical IDs or gold cluster membership;
- Ground Truth aliases or rationales;
- Oracle-to-predicted alignment artifacts;
- Relation labels selected for evaluation;
- mention-specific recovery rules derived from benchmark outcomes.

## Primary Evaluation

Pairwise identity metrics are derived over all unordered mention pairs:

- pairwise precision;
- pairwise recall;
- pairwise F1;
- `SAME_OBJECT` support count;
- `DISTINCT_OBJECT` support count.

Pairwise accuracy is not a primary metric because sparse positive identity
pairs allow a trivial all-distinct method to look strong.

## Cluster Evaluation

Report:

- B-cubed precision, recall, and F1;
- exact gold-cluster match rate, using gold cluster count as denominator;
- predicted cluster count and gold cluster count;
- singleton precision and recall;
- cluster-size distributions.

## Integrity Metrics

- mention coverage;
- mentions assigned exactly once;
- unique canonical IDs;
- no unknown or orphan mentions;
- no cross-type cluster;
- no duplicate canonical record;
- complete provenance retention;
- source and protocol hash validity.

Any integrity failure makes an evaluation invalid. It must not be converted into
a clustering error score.

## Error Taxonomy

- `false_merge`;
- `false_split`;
- `same_name_false_merge`;
- `alias_false_split`;
- `cross_type_merge`;
- `singleton_collapsed`;
- `duplicate_canonical_record`;
- `lost_provenance`;
- `unknown_mention`;
- `orphan_mention`;
- `ambiguous_unresolved`;
- `stale_artifact_binding`.

## Interpretation Boundary

The first benchmark is a controlled development benchmark with one natural
positive identity pair. Passing it establishes contract viability and basic
mechanical correctness only. It cannot establish alias resolution, ambiguity
handling, broad STEM coverage, or production readiness.
