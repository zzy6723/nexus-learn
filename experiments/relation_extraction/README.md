# Relation Extraction Validation

This directory contains experiments for validating typed Relation Extraction between Knowledge Objects.

Relation Extraction is separate from Connection Discovery.

- Relation Extraction asks whether a candidate pair has a typed machine-readable relation.
- Connection Discovery asks which candidate pairs should be proposed to the learner as useful learning connections.

---

# Current Stage

Current stage:

`Experiment 002A: Oracle-KO Typed Relation Extraction`

In 002A, the model receives human ground-truth Knowledge Objects and unordered candidate pairs. It predicts:

- relation type;
- relation direction;
- evidence spans;
- brief rationale.

This isolates Relation typing from Knowledge Object extraction errors.

---

# Scope

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

Development ground truth:

- `benchmark/ground_truth/relations_development_v0_1.json`

Guidelines:

- `benchmark/relation_annotation_guidelines.md`
- `benchmark/relation_evaluation_protocol.md`

The current Relation development corpus uses all six existing mini lectures. A new Relation holdout should be created only after the Relation prompt and evaluation procedure are stable.

The current benchmark has partial schema coverage. Conclusions must be limited to relation labels with positive development support; uncovered labels are not treated as validated.

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

The harness has been added but was not executed as part of its creation.

## `001_baseline`

Initial Oracle-KO Relation Extraction baseline.

Status: Development baseline and error analysis completed.

Formal run:

- `experiments/relation_extraction/001_baseline/runs/development_v0_1/run_02/`

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

Status: Selected for unseen holdout evaluation; freeze commit pending.

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

The selected prompt content is locked. It is a holdout candidate, not yet the
final Relation Extraction prompt.

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

Because the baseline is a single long request, every formal run must be checked
for a normal `finish_reason`, exactly 41 returned results, and a successful
prediction-schema validation. A truncated or incomplete run must be preserved
under its original run ID rather than silently replaced with `--overwrite`.

Runner regression tests are defined in:

- `tests/test_relation_runner.py`

They use mocked API responses and temporary directories. The tests were added but
were not executed as part of the runner implementation.

---

# Next Steps

1. Create and record the user-owned freeze commit for the selected Prompt 002 result.
2. Construct and annotate the unseen Relation holdout under the frozen protocol.
3. Run both baseline and Prompt 002 on the same holdout with identical settings.
4. Blind and finalize evidence adjudication before comparing holdout results.
