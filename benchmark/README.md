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
├── predicted_ko_alignment_protocol.md
├── predicted_ko_relation_evaluation_protocol.md
├── predicted_ko_relation_artifact_contract.md
├── candidate_pair_generation_protocol.md
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
inspected during Entity Extraction and Relation prompt refinement. Prompt 002
was selected as Relation Extraction prompt v0.1 after the completed development
and holdout comparisons. Its content remains locked by its recorded SHA-256.

The unseen Relation holdout is now authored and validated. It contains four new
lectures, 41 oracle Knowledge Objects, and 40 primary-scored candidate pairs.
Its construction and evaluation procedure is recorded in
`relation_holdout_plan.md`. Construction began only after the development method
was frozen at `18e687d5cd7909531918b51e2d6bef38cb64a053`.

The completed holdout was frozen at
`5fd7e2b9ea02fad6a15f2a1a703193bd7d606c7d`. Baseline and Prompt 002 were run
from that same clean commit, and both evaluations reached `final` after separate
Evidence adjudication. The completed aggregate comparison is recorded in
`experiments/relation_extraction/holdout_comparison.md`.

Experiment 002B-1 extends the base Relation protocol to measure controlled error
propagation from predicted Knowledge Objects. Its development protocols and
frozen Step 3 artifact contract are:

- `predicted_ko_alignment_protocol.md`;
- `predicted_ko_relation_evaluation_protocol.md`;
- `predicted_ko_relation_artifact_contract.md`.

Predeclared synthetic fixtures for alignment, projection, matched-control
integrity, and pipeline scoring are stored under
`tests/fixtures/predicted_ko_relation/`. They freeze expected outcomes before
the Step 4 implementation is written.

These protocols do not redefine the Experiment 002A Relation metrics and do not
implement candidate discovery or product Entity Resolution.

Experiment 002B-1 is now complete. Its evaluation-scoped alignment remains
separate from product canonicalization.

Experiment 002B-2 introduces candidate pair generation. Its protocol is:

- `candidate_pair_generation_protocol.md`.

The existing 40-pair Relation holdout is not an exhaustive annotation of all
possible pairs among its Knowledge Objects. Unlisted pairs must not be treated
as `NO_RELATION`, and candidate precision, reduction, or all-pairs edge recall
must not be calculated from that selected benchmark. Experiment 002B-2 requires
a separately versioned complete pair universe.

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
