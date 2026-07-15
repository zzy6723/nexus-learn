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

The structural normalization version is:

```text
predicted_ko_structural_normalization_v0_1
```

The separate name-matching key version is:

```text
predicted_ko_name_matching_v0_1
```

Structural normalization preserves predicted `name`, `type`, and `source_span`
content exactly. Unicode NFKC, apostrophe/dash unification, whitespace collapse,
and case folding are used only to construct an internal comparison key during
alignment. They must never overwrite model-facing predicted content.

The derivation version for pair, KO, and matched-ground-truth artifacts is:

```text
predicted_ko_projection_v0_1
```

Real development execution is run-specific. The plan and source audit live under
`runs/development_v0_1/<run_id>/`; a revised method uses a new run ID and does not
overwrite an earlier execution.

`execution_manifest.json` is written before any new API request and records the
frozen method commit, prompt/schema hashes, provider/model/parameters, six-lecture
inventory and hashes, Relation ground-truth hash, A-prime/B-prime execution
order, and the `single-run controlled paired diagnostic` claim boundary.

Before writing the manifest, the preflight must verify that the supplied method
commit is the current repository `HEAD`, that the tracked and non-ignored
untracked working tree is clean, and that every declared prompt, schema,
benchmark input, lecture, and implementation script is tracked with bytes equal
to that commit. The resulting `repository_state` and implementation SHA-256
records are part of the execution manifest. A caller-supplied commit string is
never accepted on trust alone.

`entity_predictions/source_manifest.json` records one decision per lecture:
`reuse` or `rerun_required`. Reuse requires exact lecture and Entity-prompt
hashes, identical model/request parameters, successful parse metadata, the raw
response and rendered request, and equality between the raw response content and
the parsed output. Historical `git_dirty_at_start` is retained as audit data but
does not override direct content traceability. Mixed reuse/rerun inventories are
permitted only when every lecture has explicit provenance and file hashes.

Every required rerun consumes `execution_manifest.json` directly. The Entity
runner rejects a different commit, dirty start, stale source-manifest hash,
undeclared lecture, prompt or runner hash drift, request-parameter drift, and
artifact-directory overrides. Its metadata binds the exact execution and source
manifest snapshots used at request time.

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

# `normalized_predicted_knowledge_objects.json`

Required top-level fields:

```json
{
  "artifact_type": "predicted_ko_normalized_inventory",
  "version": "v0.1",
  "split": "development",
  "structural_normalization_version": "predicted_ko_structural_normalization_v0_1",
  "input_files": [],
  "input_set_sha256": "...",
  "normalized_content_sha256": "...",
  "knowledge_objects": []
}
```

Each normalized object contains exactly:

- `lecture_id` copied from its enclosing prediction artifact or verified
  object-level provenance;
- `predicted_ko_id` copied from raw `id`;
- original `name` and `type` without text normalization;
- `source_spans`, a one-item list containing the original `source_span` as
  decoded JSON text;
- provenance containing the original prediction ID, source file, and source
  object index.

Objects are sorted lexicographically by `(lecture_id, predicted_ko_id)`. Duplicate
lecture-local prediction IDs, conflicting enclosing/object lecture IDs, missing
required fields, invalid KO types, and empty required strings are fatal.
`aliases` and `short_definition` are intentionally omitted. This component does
not read Oracle data, assign neutral slots, align identities, or inspect Relation
pairs.

---

# `alignment.json`

Required top-level fields:

```json
{
  "artifact_type": "predicted_ko_alignment",
  "version": "v0.1",
  "split": "development",
  "structural_normalization_version": "predicted_ko_structural_normalization_v0_1",
  "name_matching_normalization_version": "predicted_ko_name_matching_v0_1",
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

`predicted_source_span_supports_identity` is `true`, `false`, or `null`. `null`
means semantic support has not been manually assessed; it does not change
one-to-one recoverability.

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
- `recoverable`;
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
  "name_matching_normalization_version": "predicted_ko_name_matching_v0_1",
  "items": []
}
```

Each pending item contains:

- unique `item_id`;
- one or more complete `oracle_snapshots`;
- complete `candidate_predicted_snapshots`;
- complete relevant `lecture_snapshot` and its SHA-256;
- `item_snapshot_sha256`;
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
  "oracle_inventory_sha256": "...",
  "predicted_inventory_sha256": "...",
  "lecture_sha256": {},
  "name_matching_normalization_version": "predicted_ko_name_matching_v0_1",
  "decisions": []
}
```

Each decision contains:

- `item_id`;
- `item_snapshot_sha256`;
- complete Oracle, predicted, and lecture snapshots matching the pending item;
- `decision`: `matched`, `not_matched`, or `structural_error`;
- resulting alignment level and primary structural status;
- nullable `matched_predicted_ref`;
- non-empty `rationale`.

Unknown, duplicate, changed, or unused decisions are fatal stale adjudications.

Relation-blind manual review scopes may be supplied to the aligner before the
initial draft. Each scope contains only an `item_id`, Oracle references,
candidate predicted references, a proposed identity/structural status, and an
error reason code. Review scopes must be inventory-level, lecture-local,
non-overlapping, and free of Relation fields. They are converted into complete
snapshot-bound pending items by the aligner.

The alignment CLI writes `alignment_bundle_complete.json` last. The marker
contains the evaluation status and SHA-256 of every artifact in the current
bundle. A directory without a valid marker is incomplete and must not be used
by projection. During overwrite, the old marker is removed before any artifact
is replaced; a stale resolved file is removed when the new bundle is draft.

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

All three arrays are sorted lexicographically by `pair_id`. Source JSON order is
not an experimental degree of freedom.

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
  "status": "derived",
  "derivation": {
    "version": "predicted_ko_projection_v0_1",
    "original_ko_ground_truth_sha256": "...",
    "alignment_sha256": "...",
    "pair_manifest_sha256": "...",
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
    "matched_knowledge_objects_sha256": "...",
    "structural_normalization_version": "predicted_ko_structural_normalization_v0_1",
    "name_matching_normalization_version": "predicted_ko_name_matching_v0_1"
  }
}
```

Its pair list contains exactly `primary_pairs` from the pair manifest in manifest
order. Gold source and target references are translated to neutral slot IDs. All
other Relation annotation fields are preserved. Manual editing is prohibited.
Because this is a filtered subset of frozen ground truth, its original opaque
pair IDs may be non-contiguous. They remain unique and lexicographically ordered.

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
  "structural_normalization_version": "predicted_ko_structural_normalization_v0_1",
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

The Relation runner must use `model_input` from this artifact verbatim after
validation. For both conditions it checks the matched-ground-truth, prompt,
schema, batch-plan, lecture, model-input, and KO-content hashes. It also checks
neutral slot identity/order and candidate-pair incidence. For A-prime, KO content
must equal the Oracle content derived from matched ground truth; for B-prime,
only the content fields may differ. The evaluator-facing
`matched_knowledge_objects.json` must never replace B-prime model content.

For zero recoverability, `batch_id` and `batch_index` are `null`, `batch_count`
is `0`, and all four model-input arrays are empty except the frozen Relation
schema object. `lecture_sha256` binds the exact model-facing lecture text, not an
unrelated file serialization.

---

# `batch_plan.json`

Required fields include:

```json
{
  "artifact_type": "matched_relation_batch_plan",
  "version": "v0.1",
  "batching_strategy": "single_deterministic_batch_v0_1",
  "pair_manifest_sha256": "...",
  "ko_manifest_sha256": "...",
  "executable_batch_count": 1,
  "batches": []
}
```

Each batch contains its ID, one-based index, pair IDs, and KO slot IDs.
Experiment 002B-1 v0.1 uses one deterministic batch unless a separately frozen
method revision introduces batching. A-prime and B-prime use the same file and
hash. With zero recoverability, `executable_batch_count = 0` and `batches = []`.

---

# `projection_errors.json`

This non-model-facing diagnostic artifact records:

- the recoverable-primary-pair numerator, denominator, and nullable rate;
- all unrecoverable primary pairs and their deterministic reason lists;
- all excluded diagnostic pairs;
- unmatched extra predicted KOs;
- nonfatal quality flags on recoverable slots.

Its pair arrays must equal the corresponding pair-manifest arrays exactly. It is
`final` when projection completed, including the zero-recoverability case. It
does not contain Relation predictions or scores.

The projection CLI writes `projection_bundle_complete.json` last. The marker
binds the SHA-256 of the two manifests, both matched ground-truth artifacts,
both matched inputs, the batch plan, and projection diagnostics. A missing or
stale marker means the directory is incomplete and must not be consumed by a
runner or Step 4.4 evaluator. On overwrite, the old marker is removed before
any managed artifact is replaced. Its `upstream` block also binds the real
SHA-256 of `alignment_bundle_complete.json`, so projection cannot silently move
to a different alignment bundle while retaining the same directory shape.

---

# Matched Run Metadata and Base Evaluation Snapshots

Each A-prime/B-prime formal run retains the existing Relation runner metadata.
The pipeline validator compares at least:

- `provider` and `model_requested`;
- `temperature`, `top_p`, `max_tokens`, `stream`, `response_format`, and
  `thinking`;
- `git_commit_at_start` and `git_dirty_at_start`;
- `input_artifact_sha256` and `batch_plan_sha256`;
- prediction artifact SHA-256.

The two conditions must use the same provider, model, request parameters,
commit, and batch plan. Their input and prediction hashes are
condition-specific. Formal matched runs require a non-null equal commit and
`git_dirty_at_start = false`.

Each condition has an `evaluation_snapshot.json` binding the exact prediction,
run metadata, `metrics.json`, `matches.json`, and `errors.json` hashes. Pipeline
evaluation reads pair-level correctness from `matches.json`; it does not accept
caller-supplied aggregate counts as a substitute.

`scripts/finalize_relation_evaluation_bundle.py` creates this snapshot from a
final authoritative base evaluation. It requires zero pending adjudications and
a completed, parse-successful, schema-valid run. It copies `metrics.json`,
`matches.json`, `errors.json`, predictions, and run metadata without rescoring,
adds the exact prediction hash to the packaged metadata, removes any old marker
before overwrite, and writes `evaluation_snapshot.json` last.

---

# Zero-Recoverability No-Op Evaluation

When no primary pair is recoverable, neither matched condition calls the
Relation API. The pipeline deterministically writes one no-op evaluation per
condition:

```json
{
  "artifact_type": "empty_matched_relation_evaluation",
  "version": "v0.1",
  "condition": "A_prime",
  "evaluation_status": "final",
  "execution_status": "not_run_no_recoverable_pairs",
  "pair_count": 0,
  "aggregate_metrics": null,
  "pair_manifest_sha256": "...",
  "ko_manifest_sha256": "..."
}
```

The no-op artifacts have real file hashes and satisfy the A-prime/B-prime
evaluation provenance fields. Conditional rates are `0/0/null`, pipeline strict
success is `0 / all primary pairs`, and every transition is upstream
unrecoverable. A no-op artifact is invalid when any recoverable pair exists.

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
- `B_prime_evaluation_sha256`;
- `A_prime_input_sha256` and `B_prime_input_sha256`;
- `A_prime_run_metadata_sha256` and `B_prime_run_metadata_sha256`;
- `A_prime_prediction_sha256` and `B_prime_prediction_sha256`;
- `batch_plan_sha256`.

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
- zero or more secondary quality flags.

Allowed failure loci and precedence are defined in the predicted-KO Relation
evaluation protocol.

Grounding quality is not a strict failure locus. A strict-correct edge with
nonexact or unsupported grounding remains a strict pipeline success and carries
the corresponding secondary quality flag.

The Step 4.4 CLI writes `pipeline_evaluation_complete.json` last. For a final
evaluation it binds `pipeline_metrics.json`, `pipeline_errors.json`, and
`pair_transitions.json`, plus any generated zero-recoverability no-op artifacts.
Its `upstream` block binds the current alignment and projection completion-marker
hashes and all consumed Relation evaluation snapshots. An invalid evaluation
removes stale aggregate artifacts and writes only an invalid
`pipeline_errors.json` before writing an invalid completion marker.

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
- a pair marked recoverable, or a matched model request, assigns both distinct
  Oracle endpoints to the same neutral slot;
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

A correctly recorded `collapsed_endpoints` reason in
`unrecoverable_primary_pairs` is nonfatal. It becomes fatal only if that pair is
projected as recoverable or rendered with one slot for both endpoints.

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
