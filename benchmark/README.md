# Benchmark

This directory contains small benchmark materials used to evaluate technical validation experiments.

The benchmark is intentionally small at the beginning. Its purpose is to make experiments reproducible before scaling to larger course materials.

---

# Structure

```text
benchmark/
├── annotation_guidelines.md
├── evaluation_protocol.md
├── relation_annotation_guidelines.md
├── relation_evaluation_protocol.md
├── relation_holdout_plan.md
├── lectures/
│   ├── development/
│   │   ├── calculus_001.md
│   │   ├── linear_algebra_001.md
│   │   └── optimisation_001.md
│   ├── holdout/
│   │   ├── calculus_002.md
│   │   ├── linear_algebra_002.md
│   │   └── probability_001.md
│   └── relation_holdout/
│       ├── differential_equations_001.md
│       ├── graph_algorithms_001.md
│       ├── numerical_root_finding_001.md
│       └── statistics_estimation_001.md
├── ground_truth/
│   ├── development_v0_1.json
│   ├── holdout_v0_1.json
│   ├── relation_holdout_knowledge_objects_v0_1.json
│   ├── relations_development_v0_1.json
│   └── relations_holdout_v0_1.json
└── results/
```

---

# Entity Extraction Benchmark

# Splits

## Development

The development split is used for prompt debugging, error analysis, and benchmark design.

Current development lectures:

- `lectures/development/calculus_001.md`
- `lectures/development/linear_algebra_001.md`
- `lectures/development/optimisation_001.md`

Development results must not be interpreted as evidence of generalization.

## Entity Extraction Holdout

The holdout split is used for unseen evaluation after the prompt, schema, ground truth, matching rules, and evaluation protocol are frozen.

Current holdout lectures:

- `lectures/holdout/calculus_002.md`
- `lectures/holdout/linear_algebra_002.md`
- `lectures/holdout/probability_001.md`

Do not run models on the holdout split until the evaluation protocol is frozen.

These three lectures are no longer unseen for Relation Extraction. They were
included in the Relation development benchmark and must not be reused as the
Relation holdout.

---

# Lecture Snippets

The lecture snippets are authored for this repository.

They are inspired by standard STEM definitions and the project owner's topic selection, but they do not directly copy private course notes or long external text passages.

This keeps the benchmark suitable for public GitHub use.

---

# Ground Truth

Ground truth is hand-authored and should be treated as a small evaluation reference, not as a final ontology.

Current ground truth files:

- `ground_truth/development_v0_1.json`
- `ground_truth/holdout_v0_1.json`

The current object types are:

- `Concept`
- `Method`
- `Formula`

These types are defined for the MVP and Technical Validation phase in ADR-003.

---

# Relation Extraction Benchmark

Experiment 002A uses oracle Knowledge Objects and evaluates only typed Relation
classification, endpoint direction, and evidence grounding.

Current development assets:

- `relation_annotation_guidelines.md`;
- `relation_evaluation_protocol.md`;
- `ground_truth/relations_development_v0_1.json`.

All six current mini lectures are Relation development data because they were
inspected during Entity Extraction and Relation prompt refinement. Prompt 002 is
the selected development prompt candidate and is content-locked by its recorded
SHA-256, but it is not yet the final Relation Extraction prompt.

The unseen Relation holdout is now authored and validated. It contains four new
lectures, 41 oracle Knowledge Objects, and 40 primary-scored candidate pairs.
Its construction and evaluation procedure is recorded in
`relation_holdout_plan.md`. Construction began only after the development method
was frozen at `18e687d5cd7909531918b51e2d6bef38cb64a053`.

The completed holdout is waiting for its user-owned benchmark freeze commit.
Neither baseline nor Prompt 002 should be run before that second freeze anchor
is recorded.

---

# Results

Detailed model outputs and evaluation artifacts are stored inside the corresponding experiment directory.

`benchmark/results/` is reserved for benchmark-level aggregate summaries that compare multiple experiments.

When an experiment uses this benchmark, it should record:

- benchmark split;
- ground truth version;
- prompt or method version;
- model used;
- output file;
- evaluation notes;
- conclusion.
