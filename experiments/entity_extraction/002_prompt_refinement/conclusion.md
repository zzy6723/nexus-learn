# Conclusion

**Experiment:** `experiments/entity_extraction/002_prompt_refinement`  
**Status:** Completed; selected as default prompt for the next Technical Validation stage  
**Created:** 2026-07-10

---

# Summary

The refined prompt improved Knowledge Object boundary control compared with the baseline.

The model extracted all 26 required ground-truth objects across the active development benchmark and assigned correct provisional types to all matched required objects.

This includes one resolved manual adjudication item for a Taylor-formula label variant.

It also extracted two useful supporting objects:

- `Matrix Multiplication`
- `Gradient`

These objects are grounded and potentially valuable for later Relation Discovery. They are now represented as optional objects in the development ground truth.

Aggregate development metrics:

- required precision: 1.000
- required recall: 1.000
- required F1: 1.000
- required type accuracy: 1.000
- exact source-span rate: 0.786
- manual matches: 1
- unresolved adjudications: 0

Holdout comparison later showed that the refined prompt matched the baseline on required-object precision, recall, F1, and required-object type accuracy, while improving exact `source_span` grounding on the current holdout benchmark.

---

# Findings

- The model now extracts `Eigenvalue Equation` as a separate `Formula`.
- The model now types `Characteristic Polynomial` as `Concept`.
- Calculus recall stayed stable.
- Optimisation extraction remained strong.
- Useful supporting objects continue to appear; the benchmark now treats them as optional rather than unsupported errors.
- Exact source-span grounding improved in some places but remains inconsistent.

---

# Design Implications

The current provisional object types remain useful:

- `Concept`
- `Method`
- `Formula`

The refined prompt suggests these types are workable if ADR-003 defines clearer boundaries:

- `Formula` should be reserved for symbolic equations, update rules, or displayed mathematical expressions.
- Named mathematical constructs should usually be `Concept`, even when they are associated with formulas.
- `Method` should cover procedures, algorithms, and techniques.
- Useful supporting objects may be allowed if they are explicitly grounded and likely to support later typed Relations.

Exact `source_span` should not be treated as solved by prompt engineering alone. Future implementation may need deterministic span matching, text normalization, or post-processing.

---

# Decision

This experiment provides enough development evidence to support ADR-003 as an initial MVP schema decision.

ADR-003 should not overfit to this small benchmark, but it can define the initial conceptual schema and boundary rules for:

- Knowledge Object identity,
- allowed provisional object types,
- source grounding,
- useful supporting objects,
- distinction between Knowledge Objects and Connection-layer Evidence.

After holdout comparison, `002_prompt_refinement` is selected as the default Knowledge Object extraction prompt for the next Technical Validation stage.

This selection is based on improved exact source grounding, not improved object coverage or type classification. On holdout, the refined prompt achieved the same required precision, required recall, required F1 score, required-object type accuracy, false-positive count, and false-negative count as the baseline, while increasing the exact source-span rate from `0.476` to `0.762`.

This result is limited to the current benchmark of short, authored STEM lecture snippets and should not be interpreted as evidence of general STEM-wide performance.

---

# Next Step

Use `002_prompt_refinement` as the default Knowledge Object extraction prompt for the next Technical Validation stage.

Before making any stability claim, run a repeated-run stability test. If the project proceeds directly to Relation Extraction, record that run-to-run stability remains unvalidated.
