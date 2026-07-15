# Predicted-KO Relation Evaluation Protocol

**Status:** Draft for Experiment 002B-1 development  
**Version:** v0.1-draft  
**Created:** 2026-07-14  
**Owner:** Project

This protocol extends `benchmark/relation_evaluation_protocol.md` for Experiment
002B-1. It does not redefine Relation type, direction, `NO_RELATION`, grounding,
or Relation adjudication metrics.

---

# Research Questions

## RQ1: Coverage Loss

When the frozen Entity Extraction prompt replaces Oracle Knowledge Objects, how
many Oracle candidate pairs retain two uniquely aligned endpoints?

## RQ2: Conditional Representation Effect

For pairs whose endpoints are strictly recoverable, how does replacing the
Oracle KO view with the content-preserving normalized predicted KO view affect
the frozen Relation classifier?

RQ1 and RQ2 must be reported separately.

---

# Experimental Conditions

## A0: Historical Oracle Reference

A0 is the completed Experiment 002A selected-prompt run:

- Oracle KOs;
- all original candidate pairs;
- historical full-batch request.

A0 provides the full-pair Oracle reference, the historical 002A conclusion, and
pair-level context. It is not a strict representation-only control when the
recoverable subset changes batch composition.

The frozen primary gold candidate-pair set defines recovery and pipeline
denominators. A0 output presence or correctness never changes those denominators.

## A-prime: Matched Oracle Control

A-prime uses:

- Oracle KO content in the common normalized KO view;
- only strictly recoverable pairs;
- the frozen pair and KO-slot manifests;
- matched batching.

## B-prime: Matched Predicted Condition

B-prime uses:

- normalized raw predicted KO content;
- the same strictly recoverable pairs;
- the same pair and KO-slot manifests;
- the same batching as A-prime.

The primary conditional comparison is A-prime versus B-prime. A0 remains a
historical and pipeline-level reference.

---

# Common KO View

Both matched conditions expose:

```json
{
  "lecture_id": "string",
  "ko_id": "ko_slot_NNN",
  "name": "string",
  "type": "Concept | Method | Formula",
  "source_spans": ["string"]
}
```

Both conditions use the same neutral `ko_slot_NNN` ID for each aligned KO slot.
Original Oracle and predicted IDs remain in the non-model-facing manifest.
Predicted educational content may be structurally normalized but not semantically
repaired.
The complete contract and historical reuse rule are recorded in:

- `experiments/relation_extraction/002b_predicted_ko/input_contract_audit.md`.

---

# Pair Projection

Projection begins only after inventory-level alignment is final.

The primary matched experiment includes only pairs whose `category` belongs to
the frozen original ground truth's top-level `primary_scoring_categories` list.
The current categories are `positive` and `hard_negative`. Ambiguous, schema-gap,
and other diagnostic pairs are excluded from the primary request. They may be
evaluated later in a separate predeclared diagnostic batch and must never share
the primary metrics.

A primary gold pair is recoverable only when:

1. each Oracle endpoint has one unique recoverable predicted match;
2. both alignments have `primary_structural_status = one_to_one`;
3. the two Oracle endpoints map to two distinct predicted objects;
4. lecture provenance is valid;
5. neither endpoint has unresolved alignment adjudication.

For a recoverable pair:

- preserve the opaque `pair_id`;
- preserve the original unordered A0 `ko_a` and `ko_b` slot roles;
- replace both endpoint IDs with their shared neutral slot IDs;
- populate A-prime slots with Oracle content;
- populate B-prime slots with the aligned predicted content;
- do not use gold Relation type, direction, rationale, evidence, category, or
  primary-scoring status to order or render the pair.

For an unrecoverable pair, record one or more reasons:

- `missing_endpoint`;
- `duplicate_endpoint`;
- `split_endpoint`;
- `merge_endpoint`;
- `ambiguous_endpoint`;
- `granularity_mismatch`;
- `collapsed_endpoints`.

Unrecoverable pairs enter pipeline denominators but are not sent to the Relation
model and do not enter conditional Relation metrics.

---

# Pair and KO Manifests

`recoverable_pair_manifest.json` is the source of truth for:

- included pair IDs;
- pair order;
- unordered endpoint slot references;
- original primary category for later aggregate reporting only;
- unrecoverable pairs and reasons in a separate non-model-facing section.

`recoverable_ko_manifest.json` is deterministically derived from the recoverable
pair manifest and final one-to-one alignment. It records:

- each KO slot;
- Oracle and predicted fully qualified identities;
- deterministic inventory order;
- all pair IDs that reference the slot;
- confirmation that no two Oracle slots collapse onto one predicted object.

The KO manifest must contain exactly the distinct endpoints referenced by the
recoverable pair manifest. Extra unmatched predicted KOs are prohibited from
both matched model requests.

The recoverable, unrecoverable, and diagnostic pair arrays are each ordered
lexicographically by `pair_id`. KO slots are then derived from the sorted Oracle
references of the recoverable pair manifest.

Before execution, A-prime and B-prime must have identical:

- pair-manifest hash;
- KO-slot-manifest hash;
- pair count and order;
- KO-slot count and order;
- pair-to-slot incidence pattern;
- lecture count, order, and hashes;
- Relation prompt hash;
- Relation schema hash;
- model and request parameters;
- normalization version;
- batching plan.

KO content hashes and request-payload hashes should differ.

---

# Matched Relation Ground Truth

The existing Relation evaluator expects predictions for every pair in its ground
truth. A-prime and B-prime therefore share one deterministically derived artifact:

```text
matched_relation_ground_truth.json
```

It is generated from:

```text
frozen original Relation ground truth
+
recoverable_pair_manifest.json
+
recoverable_ko_manifest.json
```

The derivation must:

- include exactly the primary recoverable pair IDs in manifest order;
- preserve each included pair's Relation type, gold direction, category,
  symmetry, acceptable alternatives, evidence, and rationale;
- translate Oracle endpoint references to neutral KO slot references;
- preserve required top-level schema and lecture declarations;
- record the original ground-truth SHA-256;
- record both manifest SHA-256 values;
- record the alignment-artifact SHA-256 and normalization version;
- prohibit all manual edits.

A-prime and B-prime use the same matched ground-truth file and hash. A changed
manifest makes every previously derived matched ground truth stale.

Gold fields in this artifact remain evaluator-only. The model-facing renderer
continues to expose only lecture text, KO views, opaque pair IDs, unordered
endpoint slots, and the Relation schema.

---

# Historical Reference and Matched Reruns

A0 always remains a historical reference. It cannot serve as A-prime because the
matched experiment:

- uses neutral KO slot IDs;
- includes only primary-scored recoverable pairs;
- uses a newly derived matched ground truth and matched KO inventory.

A-prime and B-prime must always be separately rendered and run on the same
manifests, matched ground truth, and batching plan. Comparing B-prime directly
with A0 is descriptive, not a strict representation-only comparison.

Artificial missing-KO sentinels must not be used to preserve the full batch.

---

# Alignment and Recovery Metrics

## Unique Endpoint Recovery

```text
uniquely recovered Oracle endpoint KOs
/
unique Oracle KOs referenced by primary pairs
```

## Pair-Weighted Endpoint Recovery

```text
recovered primary-pair endpoint positions
/
all primary-pair endpoint positions
```

## Pair Recoverability

```text
primary pairs with two distinct recoverable endpoints
/
all primary pairs
```

Report pair recoverability separately for:

- positive and hard-negative pairs;
- within-lecture and cross-lecture pairs;
- each gold Relation type, after alignment is complete;
- each unrecoverable reason.

Also report exact, alias, manual, wrong-type, invalid-span, split, merge,
duplicate, ambiguous, granularity-mismatch, and unmatched-extra counts.

An unrecoverable hard negative is not a correct `NO_RELATION` prediction. The
Relation classifier did not evaluate that pair.

---

# Conditional Relation Metrics

Run the existing Relation evaluator independently on A-prime and B-prime for the
same recoverable pair set.

Report:

- conditional strict edge accuracy;
- conditional Relation type accuracy;
- conditional endpoint direction accuracy;
- conditional direction accuracy when type is correct;
- conditional positive Relation accuracy;
- conditional `NO_RELATION` accuracy;
- conditional per-type confusion;
- conditional `RELATED_TO` use and overuse;
- Relation-grounding exact-span validity;
- Relation-grounding semantic support and adjudication counts.

The representation diagnostic is the paired A-prime versus B-prime difference,
not B-prime compared with the full A0 batch when their manifests differ.

---

# Pipeline Metrics

## Pipeline Strict Success

```text
strictly correct B-prime pair decisions
/
all primary gold pairs
```

Unrecoverable pairs contribute no successful decision to the numerator.

When every recoverable pair is evaluated exactly once:

```text
pipeline strict success
=
pair recoverability * B-prime conditional strict accuracy
```

If pair recoverability is zero, A-prime and B-prime are not sent to the Relation
API. Deterministic final no-op evaluation artifacts record
`not_run_no_recoverable_pairs`, provide real provenance hashes, and yield
`0/0/null` conditional rates. Pipeline strict success remains zero over all
primary pairs. A no-op evaluation is invalid if any recoverable pair exists.

This is a controlled pipeline-completion metric, not graph accuracy. It does not
measure edge precision or recall from automatic candidate generation.

Positive and hard-negative pipeline outcomes must also be reported separately.

---

# Pair-Level Transitions and Descriptive Failure Decomposition

For every primary `pair_id`, report one primary transition:

- `A0_correct_to_B_unrecoverable`;
- `A0_correct_to_B_correct`;
- `A0_correct_to_B_wrong_type`;
- `A0_correct_to_B_wrong_direction`;
- `A0_wrong_to_B_unrecoverable`;
- `A0_wrong_to_B_correct`;
- `A0_wrong_to_B_same_error`;
- `A0_wrong_to_B_different_error`.

For recoverable pairs, also report the matched A-prime to B-prime transition so
that batch/run variation is not conflated with the representation comparison.
The matched transition enum is:

- `A_prime_correct_to_B_prime_correct`;
- `A_prime_correct_to_B_prime_wrong`;
- `A_prime_wrong_to_B_prime_correct`;
- `A_prime_wrong_to_B_prime_same_error`;
- `A_prime_wrong_to_B_prime_different_error`.

The experiment does not causally attribute a B-prime error to one predicted KO
field. Name, type, and grounding may change together, and a single paired run
cannot identify which field caused an output change.

Each pair instead receives one descriptive `primary_failure_locus` using this
precedence:

```text
upstream_unrecoverable
pre_existing_A_prime_strict_error
B_prime_relation_false_positive
B_prime_relation_false_negative
B_prime_relation_type_error
B_prime_relation_direction_error
B_prime_other_strict_error
none
```

Definitions:

- `upstream_unrecoverable`: the pair never reaches the matched Relation model;
- `pre_existing_A_prime_strict_error`: A-prime already has an incorrect strict-edge
  decision and B-prime also remains strict-edge incorrect on the matched pair;
- `B_prime_relation_false_positive`: B-prime predicts a graph Relation for a
  gold hard negative;
- `B_prime_relation_false_negative`: B-prime predicts `NO_RELATION` for a gold
  positive;
- `B_prime_relation_type_error`: B-prime predicts another wrong Relation type;
- `B_prime_relation_direction_error`: B-prime has the correct type but wrong
  endpoint direction;
- `B_prime_other_strict_error`: another scored edge error remains;
- `none`: B-prime is strict-edge correct.

Fatal Relation output-contract failures invalidate the whole pipeline
evaluation; they are not converted into a pair-level primary locus.

An `A-prime wrong -> B-prime correct` transition receives `none`. Grounding
quality never changes strict edge success and is reported through secondary
flags instead.

Secondary quality flags are reported independently:

- `ko_name_changed`;
- `ko_type_mismatch`;
- `predicted_source_span_invalid`;
- `predicted_source_span_insufficient`;
- `manual_identity_alignment`.

Relation-level secondary flags are:

- `relation_grounding_nonexact`;
- `relation_grounding_unsupported`.

These flags describe co-occurring input changes and must not be presented as
causal explanations. Primary-locus counts are mutually exclusive; secondary
flags may overlap.

---

# Integrity Failures

The pipeline evaluation is invalid if any of the following occurs:

- A-prime and B-prime use different recoverable pair manifests;
- KO-slot manifests differ or contain extra objects;
- matched-ground-truth hashes differ;
- matched ground truth contains a pair outside the recoverable manifest;
- a manifest pair is missing from matched ground truth;
- original ground-truth or alignment-artifact hashes do not match derivation
  metadata;
- normalization versions differ across alignment, manifests, ground truth, or
  rendered requests;
- pair or KO ordering differs;
- pair-to-slot incidence differs;
- batching differs;
- unknown, missing, or duplicate pair IDs appear;
- an Oracle or predicted endpoint is placed in the wrong slot;
- gold Relation information enters model-facing input;
- unresolved or stale alignment adjudication remains;
- Relation evaluation is not final.

Invalid runs must not produce aggregate metrics that can be mistaken for final
results.

---

# Repetition and Claim Boundary

The minimum development design uses one A-prime run and one B-prime run. Such a
result is a:

> single-run controlled paired diagnostic

It is not an estimate of the average causal effect of KO representation across
repeated API executions.

If the observed A-prime/B-prime difference is small, unstable-looking, or
decision-critical, add three matched runs per condition and report pair-level
agreement, metric range, mean, and whether the representation difference exceeds
run variation. Repetition is not a blocker for building the initial development
pipeline.

---

# Split Policy

Relation development lectures may be used to refine normalization, alignment,
projection, fixtures, evaluator behavior, and reporting.

Before generating or inspecting Entity predictions for the 002A holdout
lectures, the complete 002B-1 method must be content-locked. The later evaluation
is a locked reuse evaluation, not a fresh unseen 002B holdout.

A fresh 002B holdout is required only for a stronger generalization claim after
the controlled method has proved useful.
