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

Status: Not run.

Purpose:

- test whether the draft schema is understandable to the model;
- identify common type and direction confusions;
- measure whether `RELATED_TO` is overused;
- check whether evidence spans are copied exactly.

---

# Next Steps

1. Execute the standard-library regression harness once to confirm automated orchestration.
2. Implement `scripts/run_relation_extraction.py` with an explicit gold-leakage check.
3. Dry-run the rendered inputs.
4. Run `001_baseline` on the development relation pairs.
5. Perform error analysis before creating any Relation holdout.
