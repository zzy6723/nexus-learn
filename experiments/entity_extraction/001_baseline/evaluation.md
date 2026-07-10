# Evaluation

**Experiment:** `experiments/entity_extraction/001_baseline`  
**Version:** v0.1  
**Created:** 2026-07-10  
**Status:** Completed

---

# Goal

Evaluate whether the baseline prompt extracts useful Knowledge Objects from short STEM lecture snippets.

The evaluation compares model output against:

- `benchmark/ground_truth/knowledge_objects_v0_1.json`

---

# Manual Metrics

## Precision

Among extracted objects, how many are valid Knowledge Objects grounded in the lecture text?

## Recall

Among ground-truth objects, how many were extracted by the model?

## Type Accuracy

For matched objects, how often does the model assign the correct provisional type?

## Source Grounding Quality

Does each extracted object include a short `source_span` that appears in the input and justifies the object?

## Duplicate Rate

How often does the model extract the same object multiple times under different names?

## Noise Rate

How often does the model extract non-objects such as headings, generic words, full sentences, or vague topics?

---

# Error Categories

| Error Category | Description | Example |
| --- | --- | --- |
| Missing Object | Ground-truth object not extracted | `Eigenvalue Equation` omitted from the linear algebra snippet |
| Spurious Object | Extracted object is meaningful but not included in ground truth | `Gradient` extracted from the optimisation snippet |
| Wrong Type | Object extracted but assigned wrong type | `Characteristic Polynomial` labeled as `Formula` instead of `Concept` |
| Duplicate | Same object appears multiple times | `Gradient` and `Gradient Vector` as separate objects |
| Bad Grounding | `source_span` is absent, invented, or too broad | Whole paragraph used as source span |
| Overly Broad Object | Extracted object is too general for later relation discovery | `mathematics` |
| Overly Narrow Object | Extracted object is too small or syntactic | `x` or `n` |

---

# Failure Indicators

The experiment should be considered unsuccessful if:

- Most extracted objects are chunks, headings, or generic terms.
- A large proportion of objects lack valid source grounding.
- Formula objects are frequently missed.
- Similar concepts are typed inconsistently across lectures.
- The output would not be usable for Relation Discovery without heavy manual cleanup.

---

# Run Configuration

| Field | Value |
| --- | --- |
| Model requested | `deepseek-v4-flash` |
| Model returned | `deepseek-v4-flash` |
| Temperature | `0.0` |
| Max tokens | `4096` |
| System fingerprint | `fp_8b330d02d0_prod0820_fp8_kvcache_20260402` |
| Output directory | `experiments/entity_extraction/001_baseline/output/` |
| Metadata directory | `experiments/entity_extraction/001_baseline/metadata/` |

The original `ml_optimization_001` run was superseded after the benchmark was revised to use a pure optimisation snippet. The old output is archived under `output/superseded/`.

---

# Results

| Lecture | Precision | Recall | Type Accuracy | Grounding Quality | Notes |
| --- | --- | --- | --- | --- | --- |
| `calculus_001` | 7/7 | 7/7 | 7/7 | Good, but not always exact-string | All expected objects extracted. `First-order Taylor Approximation Formula` was named `First-Order Taylor Approximation`, but the object is semantically correct and typed as `Formula`. |
| `linear_algebra_001` | 8/9 | 8/9 | 7/8 | Good, but not always exact-string | Added `Matrix Multiplication`; missed `Eigenvalue Equation` as a separate Formula; typed `Characteristic Polynomial` as `Formula` instead of `Concept`. |
| `optimisation_001` | 10/11 | 10/10 | 10/10 | Good, but not always exact-string | All expected objects extracted. Added `Gradient`, which is meaningful but not included in this lecture's ground truth. |

Overall:

| Metric | Result |
| --- | --- |
| Total extracted objects | 27 |
| Ground-truth objects | 26 |
| Matched ground-truth objects | 25 |
| Approximate precision | 25/27 |
| Approximate recall | 25/26 |
| Type accuracy on matched objects | 24/25 |

Precision and recall are approximate because matching was manually judged by semantic equivalence rather than exact ID equality.

---

# Main Errors

## Missing Object

- `linear_algebra_001`: missed `Eigenvalue Equation` as a separate Formula object, although the equation appeared inside the `Eigenvalue` source span.

## Spurious Object

- `linear_algebra_001`: extracted `Matrix Multiplication`, which is meaningful but not included in the current ground truth.
- `optimisation_001`: extracted `Gradient`, which is meaningful and useful for later cross-course connections, but not included in this lecture's ground truth.

These may indicate that the ground truth is slightly under-specified rather than that the model is simply wrong.

## Wrong Type

- `linear_algebra_001`: extracted `Characteristic Polynomial` as `Formula`; the ground truth labels it as `Concept`.

This suggests that the boundary between `Concept` and `Formula` needs refinement.

## Bad Grounding

No object was completely ungrounded.

However, several `source_span` values are semantically grounded but not exact string copies from the input because the model normalized LaTeX notation. For example, it returned unicode mathematical notation where the source text used Markdown/LaTeX notation.

This is acceptable for manual review, but future automated evaluation should distinguish exact-span grounding from semantic grounding.

---

# Interpretation

The baseline prompt is strong enough to continue the project.

It extracts stable central mathematical objects and avoids obvious chunk extraction, generic headings, and unsupported hallucinations.

The main weakness is not noise; it is boundary control.

The model tends to:

- Extract meaningful but unannotated supporting objects.
- Merge a formula into a related concept instead of extracting it as a separate object.
- Treat some formula-like concepts as `Formula`.
- Normalize notation in `source_span`, which complicates exact grounding checks.

---

# Evaluation Conclusion

Experiment 001 provides positive evidence that LLM-based Knowledge Object extraction is feasible on small STEM snippets.

The next iteration should focus on:

- clearer object inclusion rules,
- clearer separation between `Concept` and `Formula`,
- a decision on whether benchmark ground truth should include useful supporting objects such as `Matrix Multiplication` and `Gradient`,
- stricter `source_span` requirements if automated grounding evaluation is planned.

The result supports continuing to ADR-003 after one more prompt iteration or after expanding the benchmark.
