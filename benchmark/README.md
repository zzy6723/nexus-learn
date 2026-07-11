# Benchmark

This directory contains small benchmark materials used to evaluate technical validation experiments.

The benchmark is intentionally small at the beginning. Its purpose is to make experiments reproducible before scaling to larger course materials.

---

# Structure

```text
benchmark/
├── annotation_guidelines.md
├── evaluation_protocol.md
├── lectures/
│   ├── development/
│   │   ├── calculus_001.md
│   │   ├── linear_algebra_001.md
│   │   └── optimisation_001.md
│   └── holdout/
│       ├── calculus_002.md
│       ├── linear_algebra_002.md
│       └── probability_001.md
├── ground_truth/
│   ├── development_v0_1.json
│   └── holdout_v0_1.json
└── results/
```

---

# Splits

## Development

The development split is used for prompt debugging, error analysis, and benchmark design.

Current development lectures:

- `lectures/development/calculus_001.md`
- `lectures/development/linear_algebra_001.md`
- `lectures/development/optimisation_001.md`

Development results must not be interpreted as evidence of generalization.

## Holdout

The holdout split is used for unseen evaluation after the prompt, schema, ground truth, matching rules, and evaluation protocol are frozen.

Current holdout lectures:

- `lectures/holdout/calculus_002.md`
- `lectures/holdout/linear_algebra_002.md`
- `lectures/holdout/probability_001.md`

Do not run models on the holdout split until the evaluation protocol is frozen.

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
