# Predicted-KO Relation Artifact Contract

**Status:** Frozen for Step 4 implementation against predeclared fixtures  
**Version:** v0.1  
**Created:** 2026-07-14  
**Owner:** Project

This contract defines the machine-readable artifacts used by Experiment 002B-1.
It extends:

- `benchmark/predicted_ko_alignment_protocol.md`;
- `benchmark/predicted_ko_relation_evaluation_protocol.md`.

It does not redefine the base Relation output or scoring schema.

---

# Common Rules

All artifacts:

- are UTF-8 JSON;
- use `version = "v0.1"`;
- use unique non-empty IDs within their declared scope;
- use fully qualified KO references containing `lecture_id` and `ko_id`;
- use lowercase 64-character hexadecimal SHA-256 strings;
- reject unknown references rather than silently dropping them;
- preserve declared array order where order is part of matched execution;
- record `evaluation_status` when the artifact represents an evaluation stage.

Allowed evaluation statuses are:

- `draft_pending_adjudication`;
- `final`;
- `invalid`.

The normalization version for Step 3 is:

```text
predicted_ko_name_normalization_v0_1
```

The derivation version for pair, KO, and matched-ground-truth artifacts is:

```text
predicted_ko_projection_v0_1
```

---

# Reference Types

Raw Oracle or predicted KO reference:

```json
{
  "lecture_id": "calculus_fixture_001",
  "ko_id": "gradient"
}
```

Model-facing neutral KO reference:

```json
{
  "lecture_id": "calculus_fixture_001",
  "ko_id": "ko_slot_001"
}
```

Neutral slot IDs match `^ko_slot_[0-9]{3}$` and are unique across one matched
request. Pair IDs remain the opaque IDs from frozen ground truth.

---

# `alignment.json`

Required top-level fields:

```json
{
  "artifact_type": "predicted_ko_alignment",
  "version": "v0.1",
  "split": "development",
  "normalization_version": "predicted_ko_name_normalization_v0_1",
  "oracle_inventory_sha256": "...",
  "predicted_inventory_sha256": "...",
  "lecture_sha256": {
    "calculus_fixture_001": "..."
  },
  "evaluation_status": "final",
  "oracle_records": [],
  "predicted_records": []
}
```

Every Oracle inventory object appears exactly once in `oracle_records`. Every
predicted inventory object appears exactly once in `predicted_records`.

Oracle record required fields:

- `oracle_ref`;
- `matched_predicted_ref`, nullable;
- `linked_predicted_refs`;
- `alignment_level`: `exact`, `alias`, `manual`, or `unresolved`;
- `identity_match`;
- `type_match`;
- `predicted_source_span_exact`;
- `predicted_source_span_supports_identity`;
- `primary_structural_status`;
- `structural_flags`;
- `recoverable`;
- `adjudication_required`;
- `notes`.

Allowed primary structural statuses:

- `one_to_one`;
- `missing`;
- `duplicate`;
- `split`;
- `merge`;
- `ambiguous`;
- `granularity_mismatch`.

Allowed predicted accounting statuses:

- `one_to_one`;
- `duplicate`;
- `split_component`;
- `merge`;
- `granularity_mismatch`;
- `unmatched_extra`;
- `unresolved`.

Predicted record required fields:

- `predicted_ref`;
- `matched_oracle_ref`, nullable;
- `linked_oracle_refs`;
- `accounting_status` from the enum above;
- `identity_match`;
- `included_in_matched_inventory`;
- `notes`.

For a final one-to-one alignment, the Oracle and predicted records must point to
each other. An `unmatched_extra` has no Oracle match and is never included in the
matched inventory.

A final alignment must satisfy bidirectional reference consistency and contain no
record with `adjudication_required = true`.

---

# `alignment_pending.json`

Required fields:

```json
{
  "artifact_type": "predicted_ko_alignment_pending",
  "version": "v0.1",
  "alignment_snapshot_sha256": "...",
  "normalization_version": "predicted_ko_name_normalization_v0_1",
  "items": []
}
```

Each pending item contains:

- unique `item_id`;
- complete `oracle_snapshot`;
- complete `candidate_predicted_snapshots`;
- proposed alignment and structural status;
- `status = "pending"`.

An empty list is valid only when alignment status is `final`.

---

# `alignment_resolved.json`

Required fields:

```json
{
  "artifact_type": "predicted_ko_alignment_resolved",
  "version": "v0.1",
  "alignment_snapshot_sha256": "...",
  "normalization_version": "predicted_ko_name_normalization_v0_1",
  "decisions": []
}
```

Each decision contains:

- `item_id`;
- complete Oracle and predicted snapshots matching the pending item;
- `decision`: `matched`, `not_matched`, or `structural_error`;
- resulting alignment level and primary structural status;
- nullable `matched_predicted_ref`;
- non-empty `rationale`.

Unknown, duplicate, changed, or unused decisions are fatal stale adjudications.

---

# `recoverable_pair_manifest.json`

Required fields:

```json
{
  "artifact_type": "recoverable_pair_manifest",
  "version": "v0.1",
  "split": "development",
  "derivation_version": "predicted_ko_projection_v0_1",
  "original_ground_truth_sha256": "...",
  "alignment_sha256": "...",
  "primary_scoring_categories": ["positive", "hard_negative"],
  "original_primary_pair_count": 4,
  "primary_pairs": [],
  "unrecoverable_primary_pairs": [],
  "diagnostic_pairs": []
}
```

`primary_pairs` contains only recoverable pairs whose category appears in
`primary_scoring_categories`. Each record contains:

- `pair_id` and `category`;
- `ko_a_slot_id` and `ko_b_slot_id` in frozen unordered order;
- Oracle and predicted endpoint mappings;
- `pair_status = "recoverable"`.

`unrecoverable_primary_pairs` contains every other primary pair exactly once,
with one or more allowed reasons:

- `missing_endpoint`;
- `duplicate_endpoint`;
- `split_endpoint`;
- `merge_endpoint`;
- `ambiguous_endpoint`;
- `granularity_mismatch`;
- `collapsed_endpoints`.

`diagnostic_pairs` contains every non-primary pair exactly once, records its
category and `excluded_from_primary = true`, and is never rendered in the primary
A-prime/B-prime request.

The union of the three arrays must equal the frozen original pair set without
duplicates or omissions.

---

# `recoverable_ko_manifest.json`

Required fields:

```json
{
  "artifact_type": "recoverable_ko_manifest",
  "version": "v0.1",
  "split": "development",
  "derivation_version": "predicted_ko_projection_v0_1",
  "alignment_sha256": "...",
  "pair_manifest_sha256": "...",
  "slots": []
}
```

The deterministic derivation is:

1. read endpoint mappings from `primary_pairs` in the pair manifest;
2. collect all distinct Oracle endpoint references;
3. sort those Oracle references lexicographically by `(lecture_id, ko_id)`;
4. assign consecutive `ko_slot_NNN` IDs in that order;
5. map each slot to exactly one predicted reference from final one-to-one
   alignment;
6. collect and lexicographically sort every referencing pair ID;
7. add no unreferenced Oracle or predicted object;
8. permit no manual addition, deletion, or reordering.

Each slot contains:

- `slot_id`;
- `oracle_ref`;
- `predicted_ref`;
- sorted `referenced_by_pair_ids`.

A changed pair-manifest or alignment hash makes the KO manifest stale.

---

# `matched_knowledge_objects.json`

This deterministic evaluator-facing file retains the standard Entity
ground-truth structure:

```json
{
  "artifact_type": "matched_knowledge_object_ground_truth",
  "version": "v0.1",
  "split": "development",
  "status": "test_fixture",
  "derivation": {
    "version": "predicted_ko_projection_v0_1",
    "ko_manifest_sha256": "..."
  },
  "lectures": []
}
```

Its lecture IDs and paths match the frozen source inventory. Its objects contain
exactly the KO-manifest slots, grouped by lecture and ordered by slot ID. Each
object uses the neutral slot ID with Oracle `name`, `type`, and `source_spans`.
The file exists so the unchanged Relation checker and evaluator can resolve
neutral references and lecture text. It is not model-facing and does not repair
B-prime content. Missing, duplicated, reordered, unreferenced, or stale slots
are fatal.

---

# `matched_relation_ground_truth.json`

This is a deterministic subset of the frozen Relation ground truth. It retains
the base Relation ground-truth schema and adds:

```json
{
  "derivation": {
    "version": "predicted_ko_projection_v0_1",
    "original_ground_truth_sha256": "...",
    "alignment_sha256": "...",
    "pair_manifest_sha256": "...",
    "ko_manifest_sha256": "...",
    "normalization_version": "predicted_ko_name_normalization_v0_1"
  }
}
```

Its pair list contains exactly `primary_pairs` from the pair manifest in manifest
order. Gold source and target references are translated to neutral slot IDs. All
other Relation annotation fields are preserved. Manual editing is prohibited.

Its `knowledge_object_ground_truths` field points to the deterministic
`matched_knowledge_objects.json` artifact. This evaluator-facing file is never
used to replace B-prime KO content in the model request.

---

# `oracle_normalized_input.json` and `predicted_normalized_input.json`

Both artifacts use:

```json
{
  "artifact_type": "matched_relation_input",
  "version": "v0.1",
  "condition": "A_prime",
  "normalization_version": "predicted_ko_name_normalization_v0_1",
  "pair_manifest_sha256": "...",
  "ko_manifest_sha256": "...",
  "matched_ground_truth_sha256": "...",
  "relation_prompt_sha256": "...",
  "relation_schema_sha256": "...",
  "batch_plan_sha256": "...",
  "ko_content_sha256": "...",
  "model_input_sha256": "...",
  "lecture_sha256": {},
  "batch_id": "batch_001",
  "batch_index": 1,
  "batch_count": 1,
  "model_input": {
    "relation_schema": {},
    "lectures": [],
    "knowledge_objects": [],
    "candidate_pairs": []
  }
}
```

Allowed conditions are `A_prime` and `B_prime`. A-prime and B-prime must have the
same structural hashes, lecture hashes, batching, pair IDs, pair order, KO slot
IDs, KO order, and pair-to-slot incidence. Only `name`, `type`, and
`source_spans` may differ between matched KO slots. `ko_content_sha256` and
`model_input_sha256` are condition-specific and may differ; a structural hash is
not allowed to conceal a content difference.

---

# `pipeline_metrics.json`

Required fields:

```json
{
  "artifact_type": "predicted_ko_pipeline_metrics",
  "version": "v0.1",
  "evaluation_status": "final",
  "aggregate_metrics_valid": true,
  "provenance": {},
  "denominators": {},
  "alignment_metrics": {},
  "pair_recoverability": {},
  "conditional_A_prime": {},
  "conditional_B_prime": {},
  "pipeline_metrics": {},
  "counts": {}
}
```

Every rate is stored with `numerator`, `denominator`, and nullable `value`.
`value` is null when the denominator is zero. Final values must equal numerator
divided by denominator within floating-point tolerance.

If status is `invalid`, `aggregate_metrics_valid` is false and aggregate metric
objects must be absent or explicitly null.

`provenance` is shared by `pipeline_metrics.json`, `pipeline_errors.json`, and
`pair_transitions.json`. It requires:

- `original_ground_truth_sha256`;
- `alignment_sha256`;
- `pair_manifest_sha256`;
- `ko_manifest_sha256`;
- `matched_ground_truth_sha256`;
- `A0_evaluation_sha256`;
- `A_prime_evaluation_sha256`;
- `B_prime_evaluation_sha256`.

A changed or missing provenance reference makes the aggregate artifact stale
and invalid.

---

# `pipeline_errors.json`

Required fields:

```json
{
  "artifact_type": "predicted_ko_pipeline_errors",
  "version": "v0.1",
  "evaluation_status": "final",
  "provenance": {},
  "fatal_errors": [],
  "nonfatal_errors": [],
  "pending_items": []
}
```

Every error contains `error_code`, a nullable `pair_id`, relevant references,
and a non-empty message. Final status requires empty fatal and pending arrays.

---

# `pair_transitions.json`

Required fields:

```json
{
  "artifact_type": "predicted_ko_pair_transitions",
  "version": "v0.1",
  "evaluation_status": "final",
  "provenance": {},
  "transitions": []
}
```

Every original primary pair appears exactly once. Each transition contains:

- `pair_id`;
- A0 outcome;
- nullable A-prime and B-prime outcomes;
- recoverability status and reasons;
- one `primary_failure_locus`;
- zero or more secondary upstream flags.

Allowed failure loci and precedence are defined in the predicted-KO Relation
evaluation protocol.

---

# Fatal, Nonfatal, and Pending Boundary

## Fatal

Fatal conditions make `evaluation_status = "invalid"` and
`aggregate_metrics_valid = false`:

- duplicate Oracle or predicted KO identity;
- unknown KO, pair, slot, or lecture reference;
- duplicate or missing pair ID;
- incomplete bidirectional alignment accounting;
- pair manifest projecting an unresolved or structural-error endpoint;
- KO manifest not deterministically derivable from current pair manifest;
- stale alignment, pair-manifest, KO-manifest, matched-ground-truth, prompt,
  schema, lecture, normalization, or batching hash;
- A-prime/B-prime pair IDs, order, slot incidence, KO inventory, lecture order,
  or batching mismatch;
- extra KO in either matched request;
- changed or unused adjudication;
- unresolved adjudication presented as final;
- matched ground truth containing a pair outside the manifest or omitting a
  manifest pair;
- neutral slot mismatch or two endpoints collapsed into one slot;
- gold Relation information leaked into model-facing input;
- non-final or invalid base Relation evaluation.

Fatal evaluation must remove or replace stale aggregate artifacts so they cannot
be mistaken for current valid results.

## Nonfatal Upstream Quality Errors

These are preserved, counted, and propagated:

- wrong KO type with one-to-one identity;
- invalid or insufficient source span with one-to-one identity;
- changed KO name with one-to-one identity;
- unmatched extra predicted KO;
- manual one-to-one identity match;
- missing or structural KO errors that make specific pairs unrecoverable.

An unrecoverable pair is a pipeline failure, not a fatal artifact-integrity
failure, when the alignment and manifests represent it correctly.

## Pending

Manual semantic identity decisions produce
`draft_pending_adjudication`. Draft alignment and error artifacts may be written,
but final recoverability, manifests, matched ground truth, matched requests, and
pipeline aggregate metrics must not be generated until all pending decisions are
resolved.

---

# Step 3 Fixture Rule

Each synthetic case declares expected status, errors, counts, denominators, and
rates before implementation. Step 4 code must conform to those declared outcomes.
Fixtures must not be edited merely to match the first implementation output.
