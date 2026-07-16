# Relation Extraction Validation

This directory contains experiments for validating typed Relation Extraction between Knowledge Objects.

Relation Extraction is separate from Connection Discovery.

- Relation Extraction asks whether a candidate pair has a typed machine-readable relation.
- Connection Discovery asks which candidate pairs should be proposed to the learner as useful learning connections.

---

# Current Stage

Experiment status:

- Experiment 002A, Oracle-KO Typed Relation Extraction: completed;
- Experiment 002B-1, controlled predicted-KO pipeline coupling: completed;
- Experiment 002B-2, Candidate Pair Generation under predicted KOs: development
  benchmark frozen; generator implementation pending;
- Experiment 002C, KO Resolution / Canonicalization: pending.

The current implementation focus is Experiment 002B-2. Its definition is in:

- `experiments/relation_extraction/002b_candidate_discovery/README.md`;
- `benchmark/candidate_pair_generation_protocol.md`.

Selected method:

- `002_prompt_refinement` v0.2;
- engineering role: Relation Extraction prompt v0.1 for subsequent Technical
  Validation;
- selection record: `experiments/relation_extraction/holdout_comparison.md`;
- holdout comparison: final for both baseline and Prompt 002.

In 002A, the model receives human ground-truth Knowledge Objects and unordered candidate pairs. It predicts:

- relation type;
- relation direction;
- evidence spans;
- brief rationale.

This isolates Relation typing from Knowledge Object extraction errors.

---

# Experiment 002A Scope

In scope:

- candidate-pair classification;
- direction selection from unordered pair inputs;
- `NO_RELATION` for hard negatives;
- exact evidence-span grounding;
- rationale quality as a lightweight audit field.

Out of scope:

- extracting Knowledge Objects;
- generating candidate pairs automatically;
- ranking user-facing Connections;
- long-document or PDF inputs;
- learner-specific personalization.

---

# Relation Schema

The draft schema is defined in:

- `docs/decisions/004-relation-schema.md`

Allowed graph Relation labels:

- `REQUIRES`
- `APPLIED_IN`
- `EXTENDS`
- `CONTRASTS_WITH`
- `FORMALIZES`
- `RELATED_TO`

Benchmark-only label:

- `NO_RELATION`

---

# Benchmark

Ground truth:

- `benchmark/ground_truth/relations_development_v0_1.json`
- `benchmark/ground_truth/relations_holdout_v0_1.json`

Guidelines:

- `benchmark/relation_annotation_guidelines.md`
- `benchmark/relation_evaluation_protocol.md`

The Relation development corpus uses six mini lectures. The frozen unseen
holdout uses four newly authored lectures, 36 model-facing oracle Knowledge
Objects, and 40 primary-scored candidate pairs.

The benchmark still has partial schema coverage. `RELATED_TO` has no positive
holdout support, while `EXTENDS` and `CONTRASTS_WITH` have only 3 and 1 positive
holdout examples. Uncovered or low-support labels are not treated as broadly
validated.

---

# Runs

## Evaluator Validation

Status: Synthetic evaluator validation passed.

The v0.1 evaluator has been exercised against ten synthetic scenarios covering:

- perfect predictions;
- wrong direction with correct type;
- `NO_RELATION` overconnection;
- universal `RELATED_TO` fallback;
- nonfatal evidence and rationale errors;
- fatal candidate alignment errors;
- empty evidence-span rejection;
- stale adjudication rejection and artifact replacement;
- symmetric Relation prediction in both endpoint orders.

Validated reports are stored under:

- `tests/fixtures/relation_extraction/evaluation_v2/`

The regression harness is:

- `tests/test_relation_evaluator.py`

The evaluator, runner, and ground-truth-checker regression suite contains 21
tests and passed during holdout construction validation.

## `001_baseline`

Initial Oracle-KO Relation Extraction baseline.

Status: Completed control for development diagnosis and unseen holdout comparison.

Formal development run:

- `experiments/relation_extraction/001_baseline/runs/development_v0_1/run_02/`

Formal holdout run:

- `experiments/relation_extraction/001_baseline/runs/holdout_v0_1/run_01/`

Final result:

- strict edge accuracy: `0.8421`;
- Relation type accuracy ignoring direction: `0.8947`;
- exact evidence-span rate: `1.0000`;
- evidence adjudication: 12 supported, 1 not supported, 0 pending.

See `experiments/relation_extraction/001_baseline/conclusion.md` for scope and
limitations, and `experiments/relation_extraction/001_baseline/error_analysis.md`
for pair-level diagnosis and Prompt 002 refinement targets.

Purpose:

- test whether the draft schema is understandable to the model;
- identify common type and direction confusions;
- measure whether `RELATED_TO` is overused;
- check whether evidence spans are copied exactly.

## `002_prompt_refinement`

Minimal development prompt refinement derived from the completed baseline error
analysis.

Status: Selected for subsequent Technical Validation; Experiment 002A complete.

The refinement preserves the benchmark, Relation schema, runner, evaluator, and
I/O contract. It targets endpoint serialization, `FORMALIZES` precedence, direct
evidence gating, `NO_RELATION` under insufficient support, `RELATED_TO` fallback
prevention, and self-contained evidence selection.

See:

- `experiments/relation_extraction/002_prompt_refinement/README.md`;
- `experiments/relation_extraction/002_prompt_refinement/prompt.md`;
- `experiments/relation_extraction/002_prompt_refinement/conclusion.md`.

Prompt 002 is the stronger current development candidate: strict-edge accuracy
increased from `0.8421` to `0.9211`, and all three observed false-positive
Relations were removed without positive-to-`NO_RELATION` false negatives. It also
introduced one positive-pair regression and did not improve the known direction
or self-contained-evidence errors. See
`experiments/relation_extraction/development_comparison.md` for the complete
multi-metric comparison.

Selected prompt SHA-256:

- `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`

The selected prompt content is locked. It is selected for subsequent Technical
Validation, but is not a claim of production readiness.

---

# Runner

The Relation runner is implemented at:

- `scripts/run_relation_extraction.py`

Its model-facing input is built from the frozen Relation candidate pairs, their
referenced Knowledge Objects, and the relevant lecture text. Candidate endpoints
are serialized deterministically as unordered `ko_a` / `ko_b` values.

The Experiment 002A development baseline uses one request containing all 41
candidate pairs and their referenced materials: 6 lectures and 46 Knowledge
Objects. This single-request design is the v0.1 baseline; deterministic batching
is deferred unless a preserved run demonstrates an output-length failure.

The completed unseen holdout also uses one request. Its model-facing
input contains 40 candidate pairs, 4 lectures, and 36 referenced oracle Knowledge
Objects. Both prompts were run from the same clean holdout freeze commit, and
both evaluations are now `final` after separate Evidence adjudication.

Allowed model-facing candidate data:

- opaque `pair_id`;
- unordered KO references;
- KO `lecture_id`, `ko_id`, `name`, `type`, and `source_spans`;
- relevant lecture text;
- the Relation label schema and experiment prompt.

Gold labels, gold direction, benchmark category, symmetry metadata, acceptable
alternatives, gold evidence, gold rationale, and primary-scoring status are not
rendered. The runner applies a field whitelist and a structured gold-leakage audit
before writing any run artifact.

The default run-specific layout is:

```text
experiments/relation_extraction/001_baseline/
└── runs/development_v0_1/<run_id>/
    ├── rendered_inputs/
    ├── raw_responses/
    ├── output/
    └── metadata/
```

The runner supports dry runs, no-overwrite protection, explicit run directories,
request and input hashes, repository state captured at startup, raw responses,
parsed outputs, and API/parse/schema failure metadata.

Because each split uses a single request, every formal run must be checked for a
normal `finish_reason`, the split's exact result count (`41` for development or
`40` for holdout), and a successful prediction-schema validation. A truncated
or incomplete run must be preserved under its original run ID rather than
silently replaced with `--overwrite`.

Runner regression tests are defined in:

- `tests/test_relation_runner.py`
- `tests/test_relation_ground_truth_checker.py`

Runner tests use mocked API responses, mocked repository state, and temporary
directories. The complete Relation evaluator, runner, and ground-truth-checker
suite contains 21 tests and passed during holdout construction validation.

---

# Next Steps

Experiments 002A and 002B-1 are closed. Prompt 002 remains the frozen Relation
classifier for subsequent Technical Validation. Experiment 002B-1 established
how predicted-KO errors propagate when the candidate pair universe is supplied;
it did not generate candidate pairs.

Experiment 002B-2 now has a frozen, exhaustive development benchmark over 39
predicted KOs and all 176 lecture-local unordered pairs. It contains 80
in-schema positives, 91 primary negatives, and 5 out-of-schema diagnostics; all
annotations pass the strict checker in final mode and are bound by the Ground
Truth completion marker.

The remaining gates are:

1. implement and verify the All-Pairs control;
2. implement one deterministic Rule-Filtered method;
3. compare candidate metrics without calling the Relation API;
4. run the frozen Relation classifier for the downstream comparison;
5. freeze the selected generator and evaluate it on a lecture-disjoint holdout.

Cross-lecture mention resolution and canonical IDs remain Experiment 002C.
Learner-facing Connection ranking remains Experiment 003.
