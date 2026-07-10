# Benchmark

This directory contains small benchmark materials used to evaluate technical validation experiments.

The benchmark is intentionally small at the beginning. Its purpose is to make experiments reproducible before scaling to larger course materials.

---

# Structure

```text
benchmark/
├── lectures/
│   ├── calculus_001.md
│   ├── linear_algebra_001.md
│   └── optimisation_001.md
├── ground_truth/
│   └── knowledge_objects_v0_1.json
└── results/
```

---

# Lecture Snippets

The lecture snippets are authored for this repository.

They are inspired by standard STEM definitions and the project owner's topic selection, but they do not directly copy private course notes or long external text passages.

This keeps the benchmark suitable for public GitHub use.

---

# Ground Truth

`ground_truth/knowledge_objects_v0_1.json` defines the expected Knowledge Objects for Experiment 001.

The ground truth is hand-authored and should be treated as a small evaluation reference, not as a final ontology.

The current object types are provisional:

- `Concept`
- `Method`
- `Formula`

These types should be revised after Experiment 001 before ADR-003 is finalized.

---

# Results

Experiment outputs and evaluation summaries may be stored in `results/` or inside the corresponding experiment directory.

When an experiment uses this benchmark, it should record:

- Input version
- Prompt or method version
- Model used
- Output file
- Evaluation notes
- Conclusion
