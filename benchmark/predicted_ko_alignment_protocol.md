# Predicted Knowledge Object Alignment Protocol

**Status:** Draft for Experiment 002B-1 development  
**Version:** v0.1-draft  
**Created:** 2026-07-14  
**Owner:** Project

This protocol defines the evaluation-only mapping from predicted Knowledge
Objects to Oracle Knowledge Objects for Experiment 002B-1. It does not implement
product Entity Resolution or canonicalization; those remain in Experiment 002C.

---

# Purpose

Alignment answers one question:

> Does this predicted object identify the same educational entity as this Oracle
> object in the current lecture?

Alignment exists only to measure upstream error propagation into Relation
classification. It must not repair Entity predictions or use Relation labels to
make identity decisions.

---

# Alignment Unit

Alignment is performed once per complete lecture inventory, before Relation
pairs are projected.

The reviewer receives:

- every Oracle KO annotation for the lecture;
- every raw predicted KO for the lecture;
- the lecture text;
- aliases frozen before the prediction was generated;
- this alignment protocol.

The same mapping is then reused for every Relation pair. Pair-by-pair alignment
is prohibited because it could map the same predicted object inconsistently or
allow Relation context to influence identity decisions.

---

# Reviewer Blinding

Automatic matching and manual adjudication must not use or reveal:

- gold Relation type;
- gold Relation direction;
- pair category or primary-scoring status;
- gold Relation rationale or evidence;
- Experiment 002A predictions or errors;
- which Relation pairs contain an Oracle KO.

Alignment reviewers may see KO types and source grounding, but type correctness
and exact-span correctness are diagnostic flags, not identity gates.

---

# Identity and Quality Are Separate

A predicted KO may be identity-matched even when it has:

- the wrong KO type;
- a non-exact source span;
- an insufficient source span;
- a different local identifier;
- a reasonable label variant not listed as an automatic alias.

If the predicted and Oracle objects still denote the same educational entity,
the mapping remains recoverable and the original errors propagate into the
Relation input.

A type or grounding difference makes an alignment unrecoverable only when it
creates genuine identity, granularity, or structural ambiguity.

---

# Match Levels

## Name Normalization

Exact and alias matching reuse the conservative Entity Extraction label
normalization defined in `benchmark/evaluation_protocol.md`:

1. apply Unicode NFKC normalization;
2. convert U+2018, U+2019, U+201B, U+0060, and U+00B4 to ASCII
   apostrophe U+0027;
3. convert U+2010, U+2011, U+2012, U+2013, U+2014, and U+2015 to ASCII
   hyphen U+002D;
4. trim leading and trailing whitespace;
5. collapse consecutive internal whitespace;
6. compare with Unicode-aware case folding.

Normalization must not perform stemming, lemmatization, singularization,
punctuation deletion, mathematical-symbol expansion, or semantic similarity.
It must not remove identity-bearing words such as `Formula`, `Method`, `Matrix`,
or `Rule`. LaTeX receives no additional whitespace or notation normalization.

These rules produce comparison keys only. They must never overwrite predicted
`name`, `source_span`, capitalization, punctuation, Unicode, or LaTeX in the
normalized inventory or B-prime model input. Structural normalization is a
separate content-preserving operation identified by
`predicted_ko_structural_normalization_v0_1`; this matching key is identified by
`predicted_ko_name_matching_v0_1`.

The executable implementation is the shared
`scripts/knowledge_object_matching.py::name_matching_key` function used by the
Entity evaluator, Entity ground-truth checker, normalizer tests, and alignment.

## Exact

The normalized predicted name equals the Oracle canonical name, the lecture
context identifies the same educational entity, and the match is uniquely
one-to-one.

String equality alone is not sufficient when the lecture contains distinct
objects with the same name.

## Frozen Alias

The normalized predicted name matches an Oracle alias that existed before the
prediction was generated, and the mapping is uniquely one-to-one.

Aliases may not be added after inspecting development or locked-reuse
predictions merely to improve recovery.

## Manual

A reviewer confirms semantic identity when exact and alias matching cannot do so
safely. The decision must state why the labels and grounding refer to the same
educational entity rather than merely related entities.

## Unresolved

Identity cannot be established uniquely. Unresolved mappings are not recoverable
for primary 002B-1 evaluation.

---

# Structural Status and Precedence

Primary evaluation accepts only `one_to_one` mappings.

Other structural statuses are recorded but not projected:

- `missing`: no predicted object identifies the Oracle object;
- `duplicate`: multiple predicted objects independently duplicate one Oracle
  object;
- `split`: the content of one Oracle object is divided across multiple predicted
  objects without one complete representative;
- `merge`: one predicted object combines multiple distinct Oracle objects;
- `ambiguous`: more than one identity mapping remains plausible;
- `granularity_mismatch`: the predicted object is materially broader or narrower
  and is not semantically equivalent.

The first primary experiment must not choose a representative from a duplicate
or split, nor expand one gold pair into several projected pairs. Such handling
may be studied later as a predeclared secondary analysis.

An alignment may retain multiple `structural_flags`. It also receives one
`primary_structural_status` for deterministic aggregation. When several flags
apply, use this precedence:

```text
merge
split
duplicate
ambiguous
granularity_mismatch
missing
```

Use `one_to_one` only when no structural error flag applies and there is one
unique identity match.

Definitions are operational:

- `duplicate`: multiple predictions each independently and completely identify
  one Oracle object;
- `split`: multiple predictions are individually incomplete but collectively
  represent one Oracle object;
- `merge`: one prediction explicitly combines multiple distinct Oracle objects;
- `ambiguous`: several mappings remain plausible and cannot be resolved;
- `granularity_mismatch`: one plausible prediction is materially broader or
  narrower than the Oracle object;
- `missing`: no plausible predicted object exists.

---

# Alignment Artifact Schema

The alignment artifact contains two linked accounting tables. Every Oracle and
every predicted object must appear exactly once in its respective table.

Its top-level structure is:

```json
{
  "version": "v0.1",
  "split": "development",
  "structural_normalization_version": "predicted_ko_structural_normalization_v0_1",
  "name_matching_normalization_version": "predicted_ko_name_matching_v0_1",
  "oracle_inventory_sha256": "...",
  "predicted_inventory_sha256": "...",
  "lecture_sha256": "...",
  "evaluation_status": "final",
  "oracle_records": [],
  "predicted_records": []
}
```

`evaluation_status` is `draft_pending_adjudication`, `final`, or `invalid`.
Final alignment requires complete bidirectional accounting and no unresolved
manual decision.

## Oracle Records

```json
{
  "oracle_ref": {
    "lecture_id": "calculus_001",
    "ko_id": "gradient"
  },
  "matched_predicted_ref": {
    "lecture_id": "calculus_001",
    "ko_id": "gradient_vector"
  },
  "linked_predicted_refs": [
    {
      "lecture_id": "calculus_001",
      "ko_id": "gradient_vector"
    }
  ],
  "alignment_level": "exact",
  "identity_match": true,
  "type_match": false,
  "predicted_source_span_exact": true,
  "predicted_source_span_supports_identity": true,
  "primary_structural_status": "one_to_one",
  "structural_flags": [],
  "recoverable": true,
  "adjudication_required": false,
  "notes": ""
}
```

`matched_predicted_ref` is non-null only for a strict one-to-one mapping.
`linked_predicted_refs` records every prediction involved in a duplicate, split,
merge, ambiguous, or one-to-one decision. This allows structural errors to be
represented without selecting a false primary match.

## Predicted-Object Records

```json
{
  "predicted_ref": {
    "lecture_id": "calculus_001",
    "ko_id": "gradient_vector"
  },
  "matched_oracle_ref": {
    "lecture_id": "calculus_001",
    "ko_id": "gradient"
  },
  "linked_oracle_refs": [
    {
      "lecture_id": "calculus_001",
      "ko_id": "gradient"
    }
  ],
  "accounting_status": "one_to_one",
  "identity_match": true,
  "recoverable": true,
  "notes": ""
}
```

`matched_oracle_ref` is non-null only for a strict one-to-one identity match.
`linked_oracle_refs` retains every Oracle object involved in a structural or
unresolved case. `recoverable` is an inventory-level identity property and is
true only for a final strict one-to-one match. Whether the object is referenced
by a primary Relation pair is computed later by projection and must not appear
in the Relation-blind alignment artifact.

Allowed predicted accounting statuses are:

- `one_to_one`;
- `duplicate`;
- `split_component`;
- `merge`;
- `granularity_mismatch`;
- `unmatched_extra`;
- `unresolved`.

The two tables must agree bidirectionally. A reference present in one table but
missing from the other is a fatal alignment-artifact error.

`recoverable` is true only when:

- `identity_match` is true;
- `primary_structural_status` is `one_to_one`;
- exactly one predicted object is mapped to the Oracle object;
- the predicted object is not mapped to another distinct Oracle object.

`type_match` and grounding flags do not determine recoverability.

---

# Predicted Object Accounting

Every predicted object must be accounted for as one of:

- used in a one-to-one identity match;
- duplicate;
- split component;
- merge;
- unmatched extra;
- unresolved.

Unmatched extras are reported as upstream Entity Extraction output. They are not
added to the primary projected candidate-pair inventory. Therefore 002B-1 does
not measure edges caused by spurious predicted KOs; that belongs to Candidate
Discovery.

The accounting table must also verify that no predicted object is silently used
as the unique match for two distinct Oracle objects. Such a case is a `merge`,
not two recoverable mappings.

---

# Manual Adjudication

Manual decisions must bind to an immutable snapshot containing:

- the Oracle KO fields;
- the predicted KO fields;
- the lecture ID and relevant lecture text;
- the proposed alignment level and structural status;
- the decision and non-empty rationale.

Changed, unknown, duplicate, or unused decisions are stale and must make the
alignment evaluation invalid. A pending decision prevents final recoverability
metrics.

Resolved decisions must also bind to the Oracle-inventory, predicted-inventory,
lecture, and normalization-version hashes. A decision from a previous Entity run
must not be reused when any bound snapshot changes.

## Relation-Blind Review Scopes

Exact and alias matching are automatic only for unique, conflict-free
one-to-one components. Semantic variants, same-label contextual conflicts,
split, merge, ambiguous, and granularity cases require a reviewer to nominate a
Relation-blind review scope containing only Oracle references, predicted
references, KO snapshots, and lecture context. The review scope may not contain
candidate-pair membership or any Relation label, direction, evidence, category,
or result.

Review scopes are not repair instructions. They only define which inventory
objects require a snapshot-bound identity or structural decision. No object may
occur in more than one review scope.

A one-to-many or many-to-one name-candidate component is automatically marked
`ambiguous` and sent to review. Graph shape alone never finalizes `duplicate`,
`split`, `merge`, or `granularity_mismatch`; those semantic statuses require a
snapshot-bound structural adjudication.

## Conservative Staleness Policy

Each decision is checked against its item-level canonical snapshot. Experiment
002B-1 additionally binds decisions to the complete Oracle inventory,
predicted inventory, lecture hash map, and draft alignment snapshot. Therefore
any upstream byte-level inventory change invalidates prior adjudication even if
the affected item appears semantically unchanged. This is an intentionally
strict policy: it may require repeated review after irrelevant formatting or
ordering changes, but it prevents a decision from surviving an unnoticed
change to the complete inventory context or candidate graph.

---

# Development and Locked Reuse

Development inventories may be used to refine this protocol, the automatic
matching implementation, and the error taxonomy.

Before generating or inspecting Entity predictions for the locked-reuse
evaluation, the following must be content-locked:

- normalization rules;
- exact and alias rules;
- manual adjudication rules;
- structural-status definitions and precedence;
- bidirectional artifact schema;
- one-to-one recoverability rule;
- upstream quality flags;
- stale-decision handling.

The 002A holdout may then be used only as a locked reuse evaluation. It is not a
fresh unseen 002B holdout.
