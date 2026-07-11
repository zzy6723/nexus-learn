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

Pending.

The holdout evaluation will compare the baseline and refined prompts on unseen STEM materials using a frozen benchmark, annotation protocol, and evaluation procedure.

---

# Current Development Conclusion

Development validation suggests that Knowledge Object extraction is operationally feasible for short English STEM snippets.

The refined prompt improves development performance over the baseline under the automated evaluation protocol, especially on required-object recall, required type accuracy, and exact source-span grounding.

The current evidence supports an initial MVP schema with:

- `Concept`
- `Method`
- `Formula`

This is evidence for operational viability, not ontology completeness.

---

# Next Steps

1. Commit the frozen benchmark, prompts, runner, and evaluator before running holdout.
2. Use run-specific directories for holdout execution so development and holdout artifacts cannot mix.
3. Run both `001_baseline` and `002_prompt_refinement` on the holdout split.
4. Compare results under the same frozen evaluation protocol.
5. Decide whether a later stability run is necessary.
6. Update the final Entity Extraction conclusion.

Recommended holdout run layout:

```text
experiments/entity_extraction/<run>/runs/holdout_v0_1/run_01/
├── rendered_inputs/
├── raw_responses/
├── output/
├── metadata/
└── evaluation/
```
