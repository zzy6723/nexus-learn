# Conclusion

**Experiment:** `experiments/entity_extraction/002_prompt_refinement`  
**Status:** Completed  
**Created:** 2026-07-10

---

# Summary

The refined prompt improved Knowledge Object boundary control compared with the baseline.

The model extracted all 26 ground-truth objects across the active benchmark and assigned correct provisional types to all matched objects.

It also extracted two useful supporting objects:

- `Matrix Multiplication`
- `Gradient`

These objects are grounded and potentially valuable for later Relation Discovery, but they are not included in the current ground truth.

---

# Findings

- The model now extracts `Eigenvalue Equation` as a separate `Formula`.
- The model now types `Characteristic Polynomial` as `Concept`.
- Calculus recall stayed stable.
- Optimisation extraction remained strong.
- Useful supporting objects continue to appear, which suggests the benchmark boundary needs a deliberate policy.
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

This experiment provides enough evidence to start drafting ADR-003: Knowledge Object.

ADR-003 should not overfit to this small benchmark, but it can define the initial conceptual schema and boundary rules for:

- Knowledge Object identity,
- allowed provisional object types,
- source grounding,
- useful supporting objects,
- distinction between Knowledge Objects and Connection-layer Evidence.

---

# Next Step

Draft `docs/decisions/003-knowledge-object.md`.

Before Relation Discovery begins, create a benchmark v0.2 decision:

1. whether to add useful supporting objects to ground truth;
2. whether `source_span` requires exact substring matching or semantic grounding;
3. whether automated evaluation should normalize LaTeX before span matching.
