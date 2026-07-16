# Experiment 002B-1: Predicted-KO Relation Classification

**Subtitle:** Controlled Error Propagation from Entity Extraction to Relation Classification
**Status:** Development gate passed; locked-reuse v0.1 stopped on repeated schema failure; v0.2 candidate-scoped revision implemented
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

The executable preflight gate, scope binding, expected reruns, and refreeze
requirement are recorded in `locked_reuse_preflight.md`.

Locked reuse execution revision:

- `locked_reuse_v0_1` remains an immutable record of two schema-invalid
  A-prime attempts; B-prime was not run;
- `locked_reuse_v0_2` reuses the same previously evaluated lectures and upstream
  extraction method but partitions Relation requests one candidate pair at a
  time;
- v0.2 is a method-revision diagnostic, not a restored unseen-holdout claim;
- the Relation prompt, Relation schema, endpoint validator, pair set, pair
  order, and evaluator remain unchanged.

See `locked_reuse_v0_1_failure.md` and
`candidate_scoped_execution_v0_2.md`.

---

# Planned Artifacts

```text
experiments/relation_extraction/002b_predicted_ko/
├── README.md
├── input_contract_audit.md
├── development_results.md
├── conclusion.md
└── runs/
    ├── development_v0_1/
    │   └── <run_id>/
    │       ├── execution_manifest.json
    │       ├── oracle_knowledge_objects.json
    │       ├── lecture_inventory.json
    │       ├── entity_predictions/
    │       │   ├── source_manifest.json
    │       │   ├── entity_source_bundle.json
    │       │   ├── entity_predictions_complete.json
    │       │   ├── rendered_inputs/
    │       │   ├── raw_responses/
    │       │   ├── output/
    │       │   └── metadata/
    │       ├── normalization/
    │       ├── alignment/
    │       ├── projection/
    │       ├── A_prime/
    │       ├── B_prime/
    │       ├── relation_evaluation/
    │       │   ├── A0/
    │       │   ├── A_prime/
    │       │   └── B_prime/
    │       └── pipeline_evaluation/
    ├── locked_reuse_v0_1/
    └── locked_reuse_v0_2/
```

Protocol extensions:

- `benchmark/predicted_ko_alignment_protocol.md`;
- `benchmark/predicted_ko_relation_evaluation_protocol.md`;
- `benchmark/predicted_ko_relation_artifact_contract.md`.

Planned implementation components:

- `scripts/normalize_predicted_kos.py` - implemented;
- `scripts/knowledge_object_matching.py` - shared Entity/alignment matcher implemented;
- `scripts/align_predicted_kos.py` - implemented;
- `scripts/project_recoverable_relation_pairs.py` - implemented;
- `scripts/evaluate_predicted_ko_relation_pipeline.py` - implemented;
- `scripts/prepare_predicted_ko_relation_run.py` - implemented;
- `scripts/finalize_entity_prediction_bundle.py` - implemented;
- `scripts/finalize_relation_evaluation_bundle.py` - implemented;
- matched-input support in `scripts/run_relation_extraction.py` - implemented.
- candidate-scoped request partitioning with atomic aggregate output in
  `scripts/run_relation_extraction.py` - implemented.

Step 4 implementation status:

- Step 4.0: executable fixture loader, independent golden-math check, and
  runtime real-hash materializer completed;
- Step 4.1: content-preserving predicted-KO structural normalization completed;
- Step 4.2: conservative inventory-level alignment and snapshot-bound
  adjudication completed against synthetic fixtures;
- Step 4.3: deterministic pair/KO projection, neutral slots, matched A-prime/
  B-prime inputs, diagnostics, hash-chain validation, and completion marker
  completed against synthetic fixtures;
- Step 4.4: snapshot-bound pipeline evaluator, recovery/conditional/pipeline
  metrics, pair transitions, descriptive failure loci, zero-recovery no-op
  handling, stale-output cleanup, and final completion marker completed against
  synthetic fixtures.

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

The pipeline evaluator does not inspect raw model responses or rescore Relation
predictions. It consumes final pair-level Relation evaluator artifacts, validates
their snapshots and matched execution metadata, and composes them with frozen
alignment and projection outputs. Grounding failures remain secondary quality
flags and do not change strict edge success.

The Step 4.4 CLI is:

```bash
python3 scripts/evaluate_predicted_ko_relation_pipeline.py \
  --original-ground-truth <original_relation_ground_truth.json> \
  --alignment <alignment_bundle/alignment.json> \
  --projection-dir <projection_bundle> \
  --a0-evaluation-dir <A0_evaluation> \
  --a-prime-evaluation-dir <A_prime_evaluation> \
  --b-prime-evaluation-dir <B_prime_evaluation> \
  --output-dir <pipeline_evaluation>
```

When pair recoverability is zero, omit both matched evaluation-directory flags.
The evaluator writes two final no-op artifacts and makes no API call.

---

# Real Development Execution Gates

The real run remains run-specific under `development_v0_1/<run_id>/`. This is
intentional: a later method correction must create a new run rather than replace
the first development execution.

After the method code is committed, prepare the run without invoking an API:

```bash
python3 scripts/prepare_predicted_ko_relation_run.py \
  --method-commit <FROZEN_METHOD_COMMIT> \
  --run-dir experiments/relation_extraction/002b_predicted_ko/runs/development_v0_1/run_01
```

The preflight composes the six-lecture Oracle and lecture inventories, freezes
both model configurations, and audits historical selected-prompt Entity outputs
per lecture. Reuse requires exact request reconstruction plus raw-response,
rendered-input, parsed-output, and metadata traceability. A mixed source inventory
is allowed only when every lecture records its source and artifact hashes.

The preflight also verifies the repository rather than trusting the supplied
commit string. It requires `--method-commit` to equal the current `HEAD`, rejects
tracked or non-ignored untracked changes, verifies required files against their
committed bytes, and records repository state plus implementation hashes in the
execution manifest. Runtime output may be locally excluded only under the
declared 002B run directory; the check does not use `--untracked-files=no`.

For locked reuse, use the same preflight with an explicit execution scope and
the frozen 002A Relation holdout:

```bash
python3 scripts/prepare_predicted_ko_relation_run.py \
  --method-commit <FROZEN_LOCKED_REUSE_METHOD_COMMIT> \
  --execution-scope locked_reuse_v0_1 \
  --relation-ground-truth benchmark/ground_truth/relations_holdout_v0_1.json \
  --run-dir experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_1/run_01
```

This path records execution scope `locked_reuse_v0_1` separately from Entity
and Relation input split `holdout`. The four Relation holdout lectures have no
traceable prior Entity artifacts under the selected prompt, so the expected
source plan is four reruns and zero reuses. See `locked_reuse_preflight.md` before
creating the formal directory.

The original `locked_reuse_v0_1` Relation stage did not complete. Both the
formal A-prime request and one bounded retry changed the same endpoint for
`rel_holdout_016`; B-prime was correctly blocked by the declared execution
order. Do not create another v0.1 retry or score either failed bundle.

The execution revision uses a new repository-frozen scope:

```bash
python3 scripts/prepare_predicted_ko_relation_run.py \
  --method-commit <FROZEN_V0_2_METHOD_COMMIT> \
  --execution-scope locked_reuse_v0_2 \
  --relation-ground-truth benchmark/ground_truth/relations_holdout_v0_1.json \
  --entity-source-run <locked_reuse_v0_1/run_01/entity_predictions> \
  --run-dir experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_2/run_01
```

The copied Entity artifacts must all pass the existing exact-content reuse
audit. No Entity API request is expected. After deterministic normalization,
alignment, adjudication, and projection are finalized, both Relation conditions
must pass the same `execution_manifest.json` to the runner. That manifest fixes
`one_candidate_pair_per_request_v0_1`; the runner rejects a dirty or different
commit, stale completion markers, parameter drift, and `--overwrite`.

The current historical artifacts are expected to resolve as follows:

- reusable: `calculus_002`, `linear_algebra_002`, `probability_001`;
- rerun required: `calculus_001`, `linear_algebra_001`, `optimisation_001`.

The three older development outputs remain valid Experiment 001 results, but
they lack raw responses, rendered request payloads, and the complete hash/status
metadata required for propagation into 002B-1.

Run each required Entity request separately from the machine-readable plan. The
manifest fixes all four artifact directories, so they must not be repeated on
the command line:

```bash
python3 scripts/run_entity_extraction.py \
  --experiment 002_prompt_refinement \
  --split development \
  --ground-truth benchmark/ground_truth/development_v0_1.json \
  --execution-manifest experiments/relation_extraction/002b_predicted_ko/runs/development_v0_1/run_01/execution_manifest.json \
  --only calculus_001
```

Repeat only by changing `--only` to `linear_algebra_001` and then
`optimisation_001`. Manifest-bound execution prohibits `--overwrite`, rejects
dry-runs in the formal directory, and records the execution-manifest and
source-manifest hashes in each lecture metadata file. Validate one lecture's
output, raw response, rendered input, and metadata before starting the next.

The actual success fields are:

```text
run_status = completed
request_success = true
json_parse_success = true
prediction_schema_valid = true
finish_reason = stop
git_commit_at_start = execution_binding.method_commit
git_dirty_at_start = false
retry_count = 0
repair_status = not_attempted
```

There is no request `stop` parameter, `git_dirty_at_end`, `execution_status`, or
`parse_status` field in the current Entity metadata contract.

If a formal request fails, preserve that run unchanged. The current runner does
not implement mutable attempt slots inside one run, so do not delete its failure
artifacts or retry with `--overwrite`. Prepare a new run ID and, when useful,
pass the previous run's `entity_predictions/` as an audited
`--entity-source-run`; compatible successful artifacts can then be reused while
failed or incomplete lectures remain in the new rerun plan.

After all three reruns pass, finalize the six-lecture source bundle before
normalization. This validates both the three copied historical artifacts and the
three manifest-bound reruns without modifying `source_manifest.json`:

```bash
python3 scripts/finalize_entity_prediction_bundle.py \
  --execution-manifest experiments/relation_extraction/002b_predicted_ko/runs/development_v0_1/run_03/execution_manifest.json
```

Success writes `entity_source_bundle.json` followed by the validity marker
`entity_predictions_complete.json` under `run_03/entity_predictions/`. Both are
no-overwrite artifacts. Normalization must not begin until the marker status is
`final` with six lectures, three reused artifacts, and three new reruns.

After final alignment and projection, the Relation runner must consume the
frozen input artifact directly. It must not reconstruct B-prime KO content from
the evaluator-facing matched ground truth:

```bash
python3 scripts/run_relation_extraction.py \
  --experiment 002_prompt_refinement \
  --split development \
  --ground-truth <projection/matched_relation_ground_truth.json> \
  --input-artifact <projection/oracle_normalized_input.json> \
  --batch-plan <projection/batch_plan.json> \
  --run-dir <run/A_prime> \
  --dry-run
```

Use `predicted_normalized_input.json` and the B-prime run directory for the
paired condition. The runner validates all frozen hashes, neutral slots, pair
order, lecture text, prompt, schema, and batch contents before rendering.

Once the authoritative base evaluator is final, bind its outputs to the exact
prediction and run metadata before Step 4.4 composition:

```bash
python3 scripts/finalize_relation_evaluation_bundle.py \
  --condition A_prime \
  --base-evaluation-dir <base_evaluation> \
  --predictions <A_prime_prediction.json> \
  --run-metadata <A_prime_metadata.json> \
  --output-dir <relation_evaluation/A_prime>
```

The same process applies to A0 and B-prime. The finalizer does not rescore any
edge; it copies the authoritative final artifacts and writes the hash-bound
`evaluation_snapshot.json` last.

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
- Step 4.3 `project_recoverable_relation_pairs.py`, all 10 predeclared manifest
  cases, strict matched-ground-truth checks, zero recoverability, matched-input
  structural controls, projection diagnostics, no-overwrite, and atomic
  completion-marker tests;
- Step 4.4 `evaluate_predicted_ko_relation_pipeline.py`, all 8 predeclared
  scoring cases, matched metadata and evaluation-snapshot integrity failures,
  zero recoverability, failure-locus precedence, grounding-quality separation,
  no-overwrite, stale-output cleanup, and final/invalid completion markers;
- repository-verified preflight and manifest-bound Entity rerun guards,
  including exact-HEAD, clean-state, tracked-content, frozen-configuration,
  stale-manifest, and fixed-artifact-directory checks;
- immutable six-lecture Entity source-bundle finalization with direct
  raw/rendered/parsed/metadata revalidation and a hash-bound completion marker;
- final real-development `run_03`, including Entity execution, Relation-blind
  alignment adjudication, 36-pair A-prime/B-prime matched runs, final Relation
  evaluation snapshots, and final pipeline composition;
- full regression suite passing across the synthetic pipeline and
  real-execution bridges, including candidate-scoped transport, all-reused
  Entity finalization, atomic aggregate failure, and paired-plan integrity. The
  frozen development Relation
  ground truth remains 41 total pairs, 38 primary pairs, and 3 diagnostic pairs.
- repository-frozen `locked_reuse_v0_2` execution under method commit
  `3c8606d9243465a8a15639a628db80ea79155f96`;
- all-reused four-lecture Entity bundle, final alignment, and 33-pair matched
  projection;
- 33/33 candidate-scoped requests completed independently for both A-prime and
  B-prime with no retries or endpoint substitutions;
- final A0, A-prime, and B-prime Relation evaluation snapshots;
- final locked-reuse pipeline evaluation with 33/40 recoverable pairs and 26/40
  end-to-end strict successes. See `locked_reuse_v0_2_results.md`.

Pending:

- user-managed repository commit for the completed v0.2 result documents and
  retained experiment artifacts;
- definition of the next experiment version; no further tuning on the same
  locked-reuse pairs is authorized under 002B-1.

Real development execution completed under `development_v0_1/run_03`.
Entity extraction, alignment adjudication, matched A-prime/B-prime API runs,
Relation evaluation, and final pipeline evaluation are complete. The
development feasibility gate passed with an Evidence exact-span compliance
caveat. See `development_results.md` and `conclusion.md`.
