# Entity Extraction Validation

This directory contains experiments for validating Knowledge Object extraction.

The experiments in this directory are runs within the same validation track, not separate product milestones.

---

# Validation Status

## Development Validation

Completed using three development mini lectures:

- Calculus
- Linear Algebra
- Optimisation

The development set was used for prompt error analysis and refinement.

Results from this set must not be interpreted as evidence of generalization.

Completed runs:

- `001_baseline`
- `002_prompt_refinement`

Automated development evaluation has been generated under each run's `evaluation/` directory.

The current development metrics use resolved manual adjudication for one Taylor-formula label variant.

| Run | Required Precision | Required Recall | Required F1 | Required Type Accuracy | Exact Source Span Rate |
| --- | --- | --- | --- | --- | --- |
| `001_baseline` | 1.000 | 0.962 | 0.980 | 0.960 | 0.556 |
| `002_prompt_refinement` | 1.000 | 1.000 | 1.000 | 1.000 | 0.786 |

## Holdout Validation

Completed.

The holdout evaluation compared the baseline and refined prompts on unseen STEM materials using a frozen benchmark, annotation protocol, and evaluation procedure.

Comparison document:

- `experiments/entity_extraction/holdout_comparison.md`

Selected prompt:

- `002_prompt_refinement`

Holdout aggregate metrics:

| Run | Required Precision | Required Recall | Required F1 | Required Type Accuracy | Exact Source Span Rate |
| --- | --- | --- | --- | --- | --- |
| `001_baseline` | 1.000 | 0.950 | 0.974 | 0.895 | 0.476 |
| `002_prompt_refinement` | 1.000 | 0.950 | 0.974 | 0.895 | 0.762 |

The refined prompt did not improve required-object identification or required-object type classification on holdout. It was selected because it improved exact source-span grounding on the current holdout benchmark without reducing the other measured extraction metrics.

---

# Current Conclusion

Development and holdout validation suggest that Knowledge Object extraction is operationally viable for the MVP on the current benchmark of short, authored STEM lecture snippets.

The refined prompt improved development performance over the baseline under the automated evaluation protocol. On holdout, it matched the baseline on required precision, recall, F1, and required type accuracy, while improving exact source-span grounding.

The current evidence supports an initial MVP schema with:

- `Concept`
- `Method`
- `Formula`

This is evidence for operational viability within the current benchmark scope, not ontology completeness or general STEM-wide performance.

---

# Next Steps

1. Use `002_prompt_refinement` as the default Knowledge Object extraction prompt for the next Technical Validation stage.
2. Decide whether to run a repeated-run stability test before making any stability claim.
3. If moving directly to Relation Extraction, record that run-to-run stability remains unvalidated.
4. Keep `001_baseline` as the valid comparison run; it should not be treated as a failed experiment.

Recommended holdout run layout:

```text
experiments/entity_extraction/<run>/runs/holdout_v0_1/run_01/
├── rendered_inputs/
├── raw_responses/
├── output/
├── metadata/
└── evaluation/
```
