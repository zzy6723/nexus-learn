# Relation Extraction 001 Baseline

**Experiment:** `experiments/relation_extraction/001_baseline`  
**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Status:** Development baseline and error analysis completed
**Created:** 2026-07-12

---

# Hypothesis

Given human-annotated Knowledge Objects and unordered candidate pairs, an LLM can assign typed and directed educational Relations with grounded evidence under a constrained schema.

---

# Input

Ground truth candidate pairs:

- `benchmark/ground_truth/relations_development_v0_1.json`

Annotation and evaluation references:

- `benchmark/relation_annotation_guidelines.md`
- `benchmark/relation_evaluation_protocol.md`
- `docs/decisions/004-relation-schema.md`

---

# Output Contract

For each candidate pair, the model must return:

- `pair_id`;
- fully qualified `source` with `lecture_id` and `ko_id`;
- fully qualified `target` with `lecture_id` and `ko_id`;
- `relation_type`;
- `evidence_spans`;
- `rationale`.

The model-facing input uses opaque pair IDs and unordered `ko_a` / `ko_b` fields. Gold labels, direction, evidence, rationale, categories, and acceptable alternatives must never appear in rendered inputs.

For `NO_RELATION`, `evidence_spans` should be an empty array and the rationale should explain why no graph edge should be created.

---

# Artifact Layout

```text
experiments/relation_extraction/001_baseline/
├── prompt.md
├── runs/
│   └── development_v0_1/
│       └── run_02/
│           ├── rendered_inputs/
│           ├── raw_responses/
│           ├── output/
│           ├── metadata/
│           └── evaluation/
└── conclusion.md
```

---

# Status

The formal clean-state development baseline is complete under:

- `runs/development_v0_1/run_02/`

The final evaluation and adjudication artifacts are under:

- `runs/development_v0_1/run_02/evaluation/`

Evaluation status is `final`: 13 pending evidence cases were manually resolved,
with 12 judged `supported`, 1 judged `not_supported`, and 0 remaining pending.
The manual adjudication support rate among pending evidence cases is `12/13`; it
is not an all-evidence semantic-support accuracy.

Primary development results:

- strict edge accuracy: `0.8421`;
- Relation type accuracy ignoring direction: `0.8947`;
- endpoint direction accuracy: `0.9286`;
- `NO_RELATION` accuracy: `0.7000`;
- exact evidence-span rate: `1.0000`.

The full scoped conclusion is recorded in `conclusion.md`. Structured pair-level
diagnosis and evidence-supported refinement targets are recorded in
`error_analysis.md`.

---

# Implementation Notes

The evaluator is implemented at `scripts/evaluate_relation_extraction.py` and its synthetic validation has passed.

The runner is implemented at `scripts/run_relation_extraction.py`. Before writing
artifacts, it converts each gold candidate into a deterministic unordered pair and
checks the rendered model input against an explicit field whitelist. It also
records repository state, request parameters, source hashes, artifact paths, and
request/parse/schema status in metadata.

The v0.1 development baseline is one global request containing all 41 candidate
pairs, the 46 referenced Knowledge Objects, and all 6 relevant lectures. After a
formal run, `finish_reason`, result count, pair alignment, and
`prediction_schema_valid` must be checked before evaluation. Any incomplete run
must remain preserved under its original run ID; it must not be silently replaced
using `--overwrite`.

Runner regression tests are defined in `tests/test_relation_runner.py` and use
mocked API behavior.

The baseline error analysis is complete. Prompt 002 has not yet been created; any
refinement should be limited to the targets in `error_analysis.md`.
