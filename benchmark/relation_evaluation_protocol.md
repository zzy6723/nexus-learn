# Relation Evaluation Protocol

**Status:** Frozen for holdout construction at `18e687d5cd7909531918b51e2d6bef38cb64a053`  
**Version:** v0.1  
**Created:** 2026-07-12  
**Owner:** Project

The scoring, matching, category, evidence, and adjudication rules are
content-locked for Relation holdout evaluation. Any semantic change after the
freeze commit requires a new protocol version.

Terminology follows `docs/glossary.md`.

---

# Purpose

This protocol defines how Typed Relation Extraction outputs should be evaluated.

It applies first to Experiment 002A: Oracle-KO Typed Relation Extraction.

---

# Evaluation Unit

The evaluation unit is an unordered candidate pair.

Model-facing inputs use an opaque `pair_id` and two fields named `ko_a` and `ko_b`. Their order does not imply direction. Gold annotations retain the correct directed `source` and `target` separately and must not be included in rendered model inputs.

The runner derives `ko_a` and `ko_b` by sorting the two fully qualified `(lecture_id, ko_id)` references. This provides deterministic serialization without using gold direction.

For each candidate pair, the model must predict:

- `pair_id`;
- `source`, containing `lecture_id` and `ko_id`;
- `target`, containing `lecture_id` and `ko_id`;
- `relation_type`;
- `evidence_spans`;
- `rationale`.

The expected `relation_type` may be a graph Relation label or `NO_RELATION`.

---

# Splits

## Development

The development set may be used for:

- relation schema debugging;
- prompt iteration;
- evaluator development;
- error analysis;
- annotation guideline refinement.

Development results must not be interpreted as evidence of generalization.

## Holdout

Relation holdout must be created from new unseen snippets after the development prompt, schema, matching rules, and scoring rules are stable.

The existing Entity Extraction holdout lectures should not be reused as Relation holdout because they have already been inspected during development.

---

# Matching Rules

Predictions are matched to ground truth by `pair_id`.

For each `pair_id`, the evaluator checks:

- the predicted fully qualified source and target form the same unordered Knowledge Object pair as the candidate;
- the predicted `relation_type` matches the ground truth label or an allowed alternative;
- direction matches the selected gold label or acceptable alternative;
- evidence spans are exact substrings of their referenced lectures;
- the rationale is present and non-empty for positive Relations.

The evaluator should reject:

- missing pair IDs;
- duplicate pair IDs;
- predictions for unknown pair IDs;
- source or target IDs outside the candidate pair;
- invalid Relation labels;
- a result count that does not match the candidate-pair count.

Fatal errors include candidate-alignment errors and prediction-schema errors that prevent reliable scoring. The evaluation status must be `invalid`, and aggregate performance metrics must not be reported as valid results.

An evidence item with an empty or whitespace-only `lecture_id` or `span` is a fatal prediction-schema error. It is not a valid evidence span and must never be counted as an exact substring.

The following are scoreable output-contract failures rather than fatal alignment errors:

- a graph Relation without evidence;
- an empty rationale;
- a `NO_RELATION` prediction with non-empty evidence;
- an evidence span that is not an exact lecture substring;
- a graph Relation predicted for a gold `NO_RELATION` pair.

These failures must remain visible in `errors.json` and the corresponding metrics. They must not prevent the evaluator from measuring the rest of the run.

Quality omissions within an otherwise valid schema, such as an empty rationale, a missing evidence list entry, or a non-exact evidence span, are nonfatal model errors.

---

# Main Metrics

The initial evaluator should report:

- strict edge accuracy;
- relation type accuracy ignoring direction;
- positive-relation type accuracy;
- endpoint direction accuracy;
- direction accuracy when Relation type is correct;
- `NO_RELATION` accuracy;
- per-type precision, recall, and confusion matrix;
- `RELATED_TO` fallback rate;
- unsupported relation count;
- exact evidence-span rate;
- missing evidence rate;
- manual adjudication count.

For Experiment 002A, the primary metric is `strict_edge_accuracy` over primary-scored candidate pairs. A prediction is strictly correct only when it uses the candidate pair, predicts the correct Relation type, and predicts the correct direction when direction applies. Correct `NO_RELATION` predictions are also strict-edge correct.

Secondary metrics are:

- relation type accuracy ignoring direction;
- positive-relation type accuracy;
- endpoint direction accuracy;
- direction accuracy when Relation type is correct;
- `NO_RELATION` accuracy;
- exact evidence-span rate.

---

# Direction Scoring

Direction is scored separately from type.

A prediction with the correct unordered pair but reversed direction should not be rejected. It should be recorded as:

- correct pair;
- correct or incorrect type depending on label;
- wrong direction.

For `CONTRASTS_WITH`, reversed direction may be accepted only if the benchmark marks the relation as symmetric.

For `NO_RELATION`, direction is not scored and either ordering of the candidate Knowledge Objects is accepted.

`endpoint_direction_accuracy` measures whether predicted source and target order matches the gold endpoint order. Its denominator is all non-symmetric positive pairs for which the prediction uses the correct unordered candidate pair and predicts a graph Relation. This metric is independent of Relation type and is retained for diagnosis.

`direction_accuracy_when_type_correct` uses the same rules but additionally requires the predicted Relation type to match the gold Relation type. This is the preferred standalone direction metric.

The legacy `direction_accuracy` field is retained as an alias of `endpoint_direction_accuracy` for compatibility with earlier synthetic reports.

---

# `NO_RELATION` Scoring

`NO_RELATION` is correct only when the benchmark label is `NO_RELATION`.

If a model predicts a graph Relation for a `NO_RELATION` pair, record:

- false positive relation;
- `NO_RELATION` error.

If a model predicts `NO_RELATION` for a positive pair, record:

- false negative relation;
- missing relation type;
- missing evidence if no evidence is supplied.

---

# Evidence Scoring

Evidence is evaluated in two stages.

## Exact Span Validity

Each evidence span must be an exact substring of the referenced lecture.

This can be checked automatically.

For Experiment 002A, an evidence span may reference only a lecture containing one of the candidate Knowledge Objects. A span copied exactly from any other lecture is not valid Relation evidence for that pair. This is a nonfatal `evidence_lecture_outside_candidate` error and does not count toward the exact-span numerator.

## Evidence Support

Evidence must support the predicted relation, not merely mention one object.

This may require manual adjudication during early experiments.

The evaluator should separate:

- exact span validity;
- semantic support for the relation.

# Manual Adjudication

Every resolved adjudication must bind to:

- `pair_id`;
- the complete predicted edge;
- the complete predicted evidence-span set;
- the decision;
- a non-empty rationale.

Before applying a decision, the evaluator must verify that the current prediction edge and evidence still match the adjudicated snapshot and that the pair still requires adjudication. Unknown, changed, auto-resolved, or otherwise unused decisions are fatal `stale_or_unused_adjudication` errors.

---

# Ambiguous Pairs

Ambiguous pairs should not be included in the primary score unless acceptable alternatives are defined before model execution.

Allowed alternatives must be stored in ground truth.

After model execution, do not add alternatives only to improve scores.

The evaluator should report `acceptable_accuracy_ambiguous` separately from primary metrics. An ambiguous prediction is acceptable when it matches either the complete primary edge or one of the complete predeclared alternative edges.

# Schema-Gap Pairs

Pairs marked `schema_gap` are excluded from primary metrics and the normal confusion matrix. Their predictions are reported under `schema_gap_predictions` for later schema analysis. A prediction of either `RELATED_TO` or `NO_RELATION` does not by itself validate the current schema.

# Per-Type Reporting

Per-type precision, recall, F1, and support must be reported together. If macro F1 is calculated, it must be named `macro_f1_supported_labels` and include only labels with positive ground-truth support. The report must list the included labels and must not describe this value as full-schema macro F1.

---

# Error Taxonomy

Initial error types:

- `wrong_relation_type`;
- `wrong_direction`;
- `false_positive_relation`;
- `false_negative_relation`;
- `overused_related_to`;
- `invalid_evidence_span`;
- `evidence_lecture_outside_candidate`;
- `missing_evidence`;
- `unexpected_evidence_for_no_relation`;
- `evidence_does_not_support_relation`;
- `candidate_pair_mismatch`;
- `invalid_relation_type`;
- `unknown_pair_id`;
- `duplicate_pair_id`;
- `schema_error`;
- `stale_or_unused_adjudication`;
- `evaluation_runtime_error`;
- `manual_adjudication_required`.

---

# Reporting

Each run should write:

```text
experiments/relation_extraction/<run>/evaluation/
├── metrics.json
├── matches.json
├── errors.json
├── confusion_matrix.json
├── adjudication_pending.json
└── summary.md
```

Metrics should clearly mark whether the evaluation is:

- `draft`;
- `draft_pending_adjudication`;
- `final`.

`metrics.json` should include counts and denominators for the primary and secondary metrics, benchmark Relation coverage, `acceptable_accuracy_ambiguous`, and `schema_gap_predictions`. Unsupported or low-support labels must not be described as validated.

Any runtime failure must overwrite the standard evaluation artifacts with an explicit `invalid` result. Existing metrics or summaries from an earlier evaluation must not remain readable as current valid output.
