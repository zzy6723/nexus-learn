# KO Canonicalization Annotation Guidelines

**Version:** ko_canonicalization_annotation_v0.1
**Status:** Development annotation guide
**Experiment:** 002C-1 Controlled KO Canonicalization

## Annotation Unit

Annotate canonical clusters, not isolated mention pairs. Each predicted mention
must appear in exactly one cluster. A cluster may contain one or more mentions.

## Same-Object Standard

Merge mentions only when they denote the same educational entity at the same KO
type and granularity.

Useful evidence includes:

- compatible names after conservative normalization;
- explicit aliases;
- definitions or source spans with the same referent;
- compatible mathematical role and notation;
- one mention applying the same named object in a new lecture context.

The merge rationale must explain why identity, rather than a weaker Relation,
is appropriate.

## Distinct-Object Standard

Keep mentions in separate clusters when any of the following holds:

- their KO types differ;
- one is a formula and the other is the concept or method it formalizes;
- one method extends or applies another method;
- names are similar but definitions or referents differ;
- the available material supports only a Relation, not identity;
- identity cannot be defended under the current evidence.

Conservative singleton preservation is preferred to an unsupported merge.

## Same Name And Aliases

Equal names do not guarantee identity. Inspect type and context before merging.

Different names may be merged only when they are genuine aliases at the same
granularity. Record such names in `aliases`. Do not store broader topics,
notations with a different educational role, or related formulas as aliases.

## Canonical Record

Each record contains:

- an opaque `canonical_id` assigned in first-mention order;
- a human-readable `canonical_name`;
- one `canonical_type` shared by all member mentions;
- all member `mention_ids` in mention-inventory order;
- zero or more normalized textual aliases;
- `annotation_status`;
- a concise `identity_rationale`.

Canonical names are labels, not identifiers. Renaming a canonical object must
not create a new identity.

## Singleton Rule

Every confirmed singleton receives its own canonical record. Omitting
singletons makes it impossible to distinguish a reviewed singleton from an
unreviewed mention.

## Provenance Rule

Do not copy only a preferred name into the canonical Ground Truth. Membership
must continue to resolve through the mention inventory to:

- lecture ID;
- predicted KO ID;
- original prediction file and object index;
- source spans;
- source-span exactness flags;
- source lecture.

## Workflow

Use:

- `draft` for unreviewed scaffold records;
- `pending_review` after a first-pass identity decision;
- `final` after review.

Final Ground Truth requires every cluster to be `final`, every mention to be
assigned exactly once, and every identity rationale to be non-empty.

## Benchmark Isolation

Do not inspect a canonicalization method's predictions while creating or
revising Ground Truth. Alias rules used by a method are method artifacts and
must not be silently copied from gold cluster membership.

## Current Development Coverage

The initial 39-mention inventory contains one reviewed multi-mention cluster:
the Method `Newton's Method` appears in numerical root finding and statistics
estimation. All other mentions are reviewed singletons.

This benchmark has no natural alias-only merge and no same-name/different-object
case. Those are required in future real benchmark construction even though
synthetic fixtures cover structural tests.
