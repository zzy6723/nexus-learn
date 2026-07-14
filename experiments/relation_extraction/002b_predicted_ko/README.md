# Experiment 002B-1: Predicted-KO Relation Classification

**Subtitle:** Controlled Error Propagation from Entity Extraction to Relation Classification
**Status:** Step 3 contracts and fixture expectations statically validated; Step 4 implementation started
**Created:** 2026-07-14

---

# Purpose

Experiment 002A established Relation classification behavior with Oracle
Knowledge Objects and human-authored candidate pairs. Experiment 002B-1 changes
only the Knowledge Object representations while retaining gold candidate pairs.

This experiment asks how Entity Extraction errors affect downstream Relation
classification. It is not candidate discovery, full graph extraction, or product
Entity Resolution.

---

# Research Questions

## RQ1: Pair Recoverability

How many primary Oracle Relation candidate pairs retain two distinct, uniquely
aligned endpoints after replacing Oracle KOs with outputs from the frozen Entity
Extraction prompt?

## RQ2: Conditional Relation Performance

For strictly recoverable pairs, how much does the frozen Relation classifier
change when Oracle KO content is replaced with content-preserving normalized
predicted KO content?

Coverage loss and conditional Relation performance must not be collapsed into a
single unexplained score.

---

# Experiment Roles

## A0: Historical Oracle Reference

The completed Experiment 002A selected-prompt run with Oracle KOs and the full
candidate-pair batch.

## A-prime: Matched Oracle Control

Oracle KO content rendered on the strictly recoverable pair and KO-slot
manifests.

## B-prime: Matched Predicted Condition

Raw predicted KO content, structurally normalized but not semantically repaired,
rendered on the same pair and KO-slot manifests.

The primary representation comparison is A-prime versus B-prime. A0 provides the
historical Oracle-condition outcomes for the full candidate-pair set. The frozen
primary gold candidate-pair set, not A0 model output, defines recovery and
pipeline denominators.

---

# Frozen Upstream Methods

Entity Extraction method:

- prompt: `experiments/entity_extraction/002_prompt_refinement/prompt.md`;
- prompt SHA-256: `12d85ea9b3ed66b751b637d7ce2e459c69368b9685bbc39c4713c24ff69feeeb`;
- selected role: default Knowledge Object extraction prompt for Technical
  Validation.

Relation Classification method:

- prompt: `experiments/relation_extraction/002_prompt_refinement/prompt.md`;
- prompt SHA-256: `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`;
- selected role: Relation Extraction prompt v0.1;
- base evaluator: `scripts/evaluate_relation_extraction.py`;
- base protocol: `benchmark/relation_evaluation_protocol.md`.

Development may change the new normalization, alignment, projection, and
pipeline-evaluation scaffolding. It must not tune either selected prompt or the
Relation schema.

---

# Common Relation Input KO View

Both matched conditions use:

```json
{
  "lecture_id": "string",
  "ko_id": "ko_slot_NNN",
  "name": "string",
  "type": "Concept | Method | Formula",
  "source_spans": ["string"]
}
```

Predicted outputs undergo only field-level normalization:

- the aligned Oracle and predicted objects receive the same neutral slot ID;
- `source_span` becomes a one-item `source_spans` list;
- `aliases` and `short_definition` are omitted.

Predicted `name`, `type`, and `source_span` content is preserved exactly.
Unicode NFKC, apostrophe/dash handling, whitespace collapse, and case folding
are alignment-key operations only and never modify B-prime model-facing fields.

Oracle values are never copied into the Predicted condition. See
`input_contract_audit.md`.

Original Oracle and predicted IDs are retained only in the non-model-facing KO
manifest. The model sees neutral `ko_slot_NNN` identifiers, so the conditional
comparison measures differences in name, type, and grounding rather than local
identifier wording.

---

# Primary Alignment Boundary

Alignment is performed once over each complete lecture inventory and without
Relation information.

Primary pair projection accepts only strict one-to-one identity mappings. A KO
may remain recoverable when its predicted type is wrong or its source span is
non-exact, provided it still identifies the same educational entity uniquely.

Missing, duplicate, split, merge, ambiguous, granularity-mismatched, and
collapsed endpoint cases are recorded as unrecoverable. They are not manually
forced into a primary Relation request.

The alignment is an evaluation scaffold, not Experiment 002C canonicalization.

---

# Matched Pair and KO Composition

The primary A-prime/B-prime request contains only recoverable pairs whose
category belongs to the frozen ground truth's `primary_scoring_categories` list.
Ambiguous and schema-gap pairs are excluded from the primary request and may be
evaluated later as a separately declared diagnostic batch.

`recoverable_pair_manifest.json` freezes the recoverable pair subset and order.

`recoverable_ko_manifest.json` is derived deterministically from that pair
manifest and records one Oracle/predicted mapping per referenced KO slot.

A-prime and B-prime must have the same:

- pair count, IDs, order, and slot incidence;
- KO slot count and order;
- lecture inventory and order;
- request batching;
- Relation prompt, schema, model, and parameters.

No unmatched predicted KO may be added to B-prime. Only KO content differs across
matched slots.

A new A-prime run is always rendered on the same neutral-ID manifests and matched
ground truth as B-prime. A0 is descriptive rather than a strict
representation-only control.

---

# Metrics

Alignment and recovery:

- unique endpoint recovery;
- pair-weighted endpoint recovery;
- overall, positive, hard-negative, within-lecture, cross-lecture, and per-type
  pair recoverability;
- exact, alias, manual, wrong-type, invalid-span, duplicate, split, merge,
  ambiguous, granularity-mismatch, and unmatched-extra counts.

Conditional Relation metrics on the matched recoverable subset:

- strict edge accuracy;
- Relation type accuracy;
- endpoint direction metrics;
- positive Relation and `NO_RELATION` accuracy;
- per-type confusion and `RELATED_TO` use;
- Relation-grounding exactness and semantic support.

Pipeline reporting:

- pipeline strict success over all primary pairs;
- positive and hard-negative outcomes separately;
- A0/A-prime/B-prime pair-level transitions;
- deterministic descriptive failure decomposition plus secondary upstream flags.

This experiment does not report complete graph edge precision or recall because
candidate pairs remain human-authored.

---

# Claim Boundary

The initial design uses one matched run per condition and must be described as a:

> single-run controlled paired diagnostic

It does not establish run-to-run stability or an average causal effect. Repeated
runs may be added later if the observed difference is small or decision-critical.

---

# Split Policy

Development:

- run frozen Entity Extraction on Relation development lectures;
- build and test alignment, projection, and pipeline evaluation;
- complete manual alignment adjudication;
- generate matched A-prime/B-prime runs and error analysis;
- freeze the complete 002B-1 method.

Locked reuse evaluation:

- only after method freeze, generate Entity predictions for the 002A holdout
  lectures;
- apply the same protocol without changing it;
- describe the result as locked reuse, not a fresh unseen 002B holdout.

---

# Planned Artifacts

```text
experiments/relation_extraction/002b_predicted_ko/
├── README.md
├── input_contract_audit.md
├── conclusion.md
└── runs/
    ├── development_v0_1/
    │   └── <run_id>/
    │       ├── entity_predictions/
    │       ├── normalization/
    │       ├── alignment/
    │       │   ├── alignment.json
    │       │   ├── alignment_pending.json
    │       │   └── alignment_resolved.json
    │       ├── manifests/
    │       │   ├── recoverable_pair_manifest.json
    │       │   └── recoverable_ko_manifest.json
    │       ├── matched_ground_truth/
    │       │   ├── matched_knowledge_objects.json
    │       │   └── matched_relation_ground_truth.json
    │       ├── oracle_control/
    │       ├── predicted_condition/
    │       └── pipeline_evaluation/
    └── locked_reuse_v0_1/
```

Protocol extensions:

- `benchmark/predicted_ko_alignment_protocol.md`;
- `benchmark/predicted_ko_relation_evaluation_protocol.md`;
- `benchmark/predicted_ko_relation_artifact_contract.md`.

Planned implementation components:

- `scripts/normalize_predicted_kos.py` - implemented;
- `scripts/knowledge_object_matching.py` - shared Entity/alignment matcher implemented;
- `scripts/align_predicted_kos.py` - implemented;
- `scripts/project_recoverable_relation_pairs.py`;
- `scripts/evaluate_predicted_ko_relation_pipeline.py`.

Step 4 implementation status:

- Step 4.0: executable fixture loader, independent golden-math check, and
  runtime real-hash materializer completed;
- Step 4.1: content-preserving predicted-KO structural normalization completed;
- Step 4.2: conservative inventory-level alignment and snapshot-bound
  adjudication completed against synthetic fixtures;
- Step 4.3: projection and matched artifact generation pending;
- Step 4.4: pipeline evaluator pending.

The normalizer validates raw Entity prediction structure, preserves predicted
educational content, records real input hashes and provenance, and writes a
deterministically ordered inventory. It does not read Oracle ground truth or
Relation pairs.

The aligner reuses the Entity evaluator's single shared name-matching function.
It automatically finalizes only unique conflict-free exact or frozen-alias
one-to-one components. Duplicate, semantic-variant, split, merge, ambiguous,
granularity, and same-label contextual cases are preserved or sent through
Relation-blind snapshot adjudication without greedy representative selection.
Every Oracle and predicted KO receives exactly one accounting record. Relation
pair membership is intentionally absent and is introduced only by Step 4.3.

The existing Relation evaluator remains authoritative for A-prime and B-prime
Relation scoring.

---

# Execution Status

Completed:

- input-contract audit;
- common normalized KO view;
- draft alignment protocol;
- draft predicted-KO Relation evaluation protocol;
- initial experiment boundary and metrics;
- frozen v0.1 artifact schemas and fatal/nonfatal/pending boundaries;
- canonical valid A-prime/B-prime synthetic bundle;
- predeclared alignment, manifest, scoring, and control-integrity fixture
  matrices under `tests/fixtures/predicted_ko_relation/`;
- static JSON, provenance-shape, denominator, leakage, and existing Relation
  ground-truth checks;
- Step 4.0 fixture loader and runtime real-hash materializer;
- Step 4.1 `normalize_predicted_kos.py` and its executable tests;
- Step 4.2 `align_predicted_kos.py`, all 14 predeclared alignment cases,
  bidirectional accounting, deterministic ordering, Relation-leakage,
  no-overwrite, and stale-adjudication tests;
- full regression suite: 50 tests passing, including the existing Relation
  evaluator, runner, and ground-truth checker tests.

Pending:

- executable behavior coverage for the Step 4.3 and Step 4.4 manifest,
  scoring, and remaining integrity cases;
- Steps 4.3-4.4 projection and pipeline evaluator implementation;
- development Entity predictions;
- alignment adjudication;
- matched A-prime/B-prime development runs;
- development error analysis and method freeze;
- locked reuse evaluation.

No API run has been performed for Experiment 002B-1.
