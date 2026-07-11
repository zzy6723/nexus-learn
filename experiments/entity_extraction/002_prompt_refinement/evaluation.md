# Evaluation

**Experiment:** `experiments/entity_extraction/002_prompt_refinement`  
**Version:** v0.2  
**Created:** 2026-07-10  
**Status:** Completed

---

# Goal

Evaluate whether the refined prompt improves boundary control compared with `001_baseline`.

The evaluation compares model output against:

- `benchmark/ground_truth/development_v0_1.json`

---

# Run Configuration

| Field | Value |
| --- | --- |
| Model requested | `deepseek-v4-flash` |
| Model returned | `deepseek-v4-flash` |
| Temperature | `0.0` |
| Max tokens | `4096` |
| Output directory | `experiments/entity_extraction/002_prompt_refinement/output/` |
| Metadata directory | `experiments/entity_extraction/002_prompt_refinement/metadata/` |

---

# Prompt Changes Tested

The v0.2 prompt added explicit rules for:

- central vs supporting objects,
- `Concept` vs `Formula`,
- displayed equations,
- exact source span copying,
- avoiding variables, headings, and broad domain terms.

---

# Results

| Lecture | Required Precision | Required Recall | Type Accuracy | Exact Source Spans | Notes |
| --- | --- | --- | --- | --- | --- |
| `calculus_001` | 7/7 | 7/7 | 7/7 | 3/7 | Same object quality as baseline, but the model still normalized several mathematical spans. |
| `linear_algebra_001` | 9/9 | 9/9 | 9/9 | 8/10 | Fixed both baseline boundary errors: `Eigenvalue Equation` was extracted as `Formula`, and `Characteristic Polynomial` was typed as `Concept`; extracted optional `Matrix Multiplication`. |
| `optimisation_001` | 10/10 | 10/10 | 10/10 | 11/11 | Extracted all required objects and optional `Gradient`. Some spans are exact but short. |

Overall:

| Metric | Result |
| --- | --- |
| Total extracted objects | 28 |
| Required ground-truth objects | 26 |
| Optional ground-truth objects extracted | 2 |
| Matched required objects | 26 |
| Unsupported objects | 0 |
| Required precision | 26/26 |
| Required recall | 26/26 |
| Type accuracy on matched required objects | 26/26 |
| Exact source spans | 22/28 |

Precision and recall use the `required` / `optional` scoring policy from `benchmark/evaluation_protocol.md`. Matching was manually judged by semantic equivalence rather than exact ID equality.

---

# Comparison with Baseline

| Check | Baseline | Prompt Refinement | Result |
| --- | --- | --- | --- |
| Extract `Eigenvalue Equation` as separate `Formula` | No | Yes | Improved |
| Type `Characteristic Polynomial` as `Concept` | No | Yes | Improved |
| Preserve calculus recall | 7/7 | 7/7 | Preserved |
| Extract useful supporting objects | Yes | Yes | Preserved |
| Improve exact source spans | Partial | Partial | Still unresolved |

---

# Main Errors

## Useful Extra Objects

- `linear_algebra_001`: extracted `Matrix Multiplication`.
- `optimisation_001`: extracted `Gradient`.

Both objects are grounded and useful for later Relation Discovery. They are now treated as optional objects in the development ground truth.

## Source Span Problems

The refined prompt did not fully solve exact source-span grounding.

The model still normalized some mathematical notation, especially in `calculus_001`.

Examples:

- It returned `∇f(x)` where the benchmark text used `\(\nabla f(x)\)`.
- It returned `f(a+h) ≈ f(a) + ∇f(a)·h.` where the benchmark text used LaTeX notation.

In `optimisation_001`, all spans were exact substrings, but several were short, such as `step size` and `stationary point`. Exact substring matching alone is therefore insufficient; future evaluation should also check whether the span is informative enough.

---

# Interpretation

The v0.2 prompt improves object boundary control.

The most important improvement is in `linear_algebra_001`, where the baseline missed a displayed equation and mistyped a named mathematical construct.

The main remaining weakness is grounding:

- exact substring compliance is inconsistent,
- short exact spans may be insufficient,
- LaTeX notation remains vulnerable to normalization.

---

# Evaluation Conclusion

The prompt refinement succeeded on boundary control but only partially succeeded on source grounding.

This suggests that ADR-003 can begin drafting the conceptual Knowledge Object schema, but exact grounding should remain an engineering concern for later implementation.

The next step is holdout validation under the frozen annotation and evaluation protocol.
