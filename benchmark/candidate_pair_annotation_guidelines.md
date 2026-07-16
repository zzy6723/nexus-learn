# Candidate Pair Annotation Guidelines

**Version:** candidate_pair_annotation_v0.1
**Status:** Frozen for the 002B-2 development benchmark
**Experiment:** 002B-2 Candidate Pair Generation under Predicted KOs
**Scope:** lecture-local, unordered, non-self predicted-KO pairs

## Purpose

This guide defines the exhaustive ground truth used to evaluate whether a
candidate generator retains pairs that have a supported typed Relation. It does
not define canonical Knowledge Object identity and does not rank pedagogical
value.

The pair universe and annotations are separate artifacts. Do not add, remove,
or reorder pairs while annotating.

## Annotation Unit

Each item is one unordered pair:

```text
{KO A, KO B}
```

Both endpoints are predicted Knowledge Objects from the same lecture. First
decide whether the lecture supports any Relation in either direction. Only then
record Relation type and directed endpoints.

## Candidate Labels

Every pair receives exactly one `candidate_label`:

- `IN_SCHEMA_RELATION`: at least one Relation in the frozen schema is directly
  supported by the lecture;
- `NO_IN_SCHEMA_RELATION`: the lecture does not provide enough evidence for any
  frozen Relation;
- `OUT_OF_SCHEMA_RELATION`: the lecture supports a meaningful relation, but the
  frozen schema cannot represent it;
- `AMBIGUOUS`: the available evidence does not permit a defensible final choice
  between otherwise valid annotation outcomes.

`candidate_label` is separate from `annotation_status`. An item may be reviewed
and finalized with `candidate_label = AMBIGUOUS`; ambiguity is a diagnostic
category, not unfinished work.

Primary candidate metrics include only `IN_SCHEMA_RELATION` and
`NO_IN_SCHEMA_RELATION`. The other two labels are counted and reported
separately.

## Positive Standard

Use `IN_SCHEMA_RELATION` only when one or more exact lecture spans, read
together, support a Relation between the two candidate endpoints.

The following are not sufficient by themselves:

- appearing in the same lecture, paragraph, or sentence;
- similar names;
- sharing a symbol without an explained relation;
- both relating to a third Knowledge Object;
- a relation that is true from general mathematical knowledge but not supported
  by the current lecture.

Apply the definitions and direction rules in
`benchmark/relation_annotation_guidelines.md`. `RELATED_TO` is not an
uncertainty label.

## Negative Standard

`NO_IN_SCHEMA_RELATION` means:

> Within this lecture context and the frozen Relation schema, the material does
> not provide enough evidence for an allowed Relation between the pair.

It does not claim that the objects are unrelated everywhere in mathematics.
Record a concise `negative_rationale`; do not invent negative evidence spans.

## Out-of-Schema and Duplicate Mentions

Use `OUT_OF_SCHEMA_RELATION` when a meaningful, evidenced relation exists but
none of the frozen Relation labels can represent it. Record:

- `relation_description`;
- `schema_exclusion_rationale`;
- exact `evidence_spans`.

Two predicted mentions that appear to denote the same educational object remain
in the exhaustive pair universe. Until Experiment 002C provides canonical
identity, annotate such a pair as `OUT_OF_SCHEMA_RELATION` with an
identity-or-duplicate description. Do not silently delete or merge it.

## Multiple Defensible Relations

For `IN_SCHEMA_RELATION`, record every defensible in-schema relation in
`gold_relations`:

- exactly one relation has `role = primary`;
- additional accepted outcomes use `role = acceptable_alternative`;
- every relation independently satisfies endpoint, direction, evidence, and
  rationale requirements.

Select the primary relation using the frozen Relation annotation guide and its
strongest-supported-label principle. If the evidence genuinely does not support
a unique primary outcome, use `AMBIGUOUS` instead of choosing for convenience.

For `AMBIGUOUS`, record an `ambiguity` object containing:

- a concise rationale;
- at least two competing interpretations;
- `adjudication_status = pending_review` while under review;
- `adjudication_status = adjudicated_final` before a final ambiguous label.

Any listed `gold_relations` for an ambiguous item are possible outcomes, not a
selected primary Relation, and therefore use `role = acceptable_alternative`.

## Formula Boundaries

Do not infer `FORMALIZES` merely because a Formula is near a Concept or Method,
or because it contains a related symbol. The evidence must present the Formula
as a definition, characterization, expression, update, or solution condition of
the other endpoint.

## Evidence Rules

Each in-schema or out-of-schema positive annotation must contain one or more
non-empty evidence spans that:

- are exact substrings of the declared lecture;
- jointly identify the candidate endpoints or make their relation unambiguous;
- do not depend on unresolved references in omitted text;
- support the annotated Relation, not merely the existence of each endpoint.

Evidence is lecture-local in v0.1.

## Reusing Existing Relation Annotations

The selected 40-pair Relation benchmark may be used only as an annotation aid.
A label may be reused when all of the following hold:

- Oracle-to-predicted endpoint mapping is explicit and already frozen;
- the unordered predicted pair is identical to the mapped pair;
- the Relation judgment remains valid for the predicted objects;
- the evidence is still traceable to the lecture text.

Set `annotation_source = reused_existing_relation_annotation` and provide:

- `source_relation_id`;
- `source_artifact_path`;
- `source_artifact_sha256`.

Otherwise perform a new manual annotation with
`annotation_source = new_exhaustive_annotation`. Pairs absent from the 40-pair
benchmark are unreviewed, not automatic negatives.

## Workflow Status

Use:

- `annotation_status = draft` while an item is unreviewed or being revised;
- `annotation_status = pending_review` when a completed first-pass decision is
  awaiting review;
- `annotation_status = final` after the item has been reviewed under this guide.

Allowed `annotation_source` values are:

- `new_exhaustive_annotation`;
- `reused_existing_relation_annotation`;
- `adjudicated`.

`source_annotation` must be non-null only for reused annotations. New and
adjudicated decisions keep it null.

Do not inspect Candidate Generator outputs while creating or adjudicating ground
truth.

## Completion Gate

Before benchmark freeze:

- every pair-universe ID appears exactly once in ground truth;
- every annotation has `annotation_status = final`;
- no `candidate_label` is null;
- all positive evidence is exact and semantically relevant;
- primary and diagnostic counts reconcile to the complete universe;
- the strict checker reports no structural, grounding, or hash-binding errors;
- a separate completion marker binds the final ground-truth file hash.

Finalized `AMBIGUOUS` and `OUT_OF_SCHEMA_RELATION` items are permitted, but they
remain outside the primary candidate precision and recall denominators.

During annotation, run the strict checker with `--allow-draft` after every
lecture batch. Final freeze requires a checker run without `--allow-draft` and a
separate `candidate_pairs_development_v0_1_complete.json` completion marker.
