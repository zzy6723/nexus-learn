# Conclusion

**Experiment:** `experiments/entity_extraction/001_baseline`  
**Status:** Completed  
**Created:** 2026-07-10

---

# Summary

The baseline DeepSeek run successfully produced valid JSON outputs for all three active benchmark lecture snippets.

The active benchmark now covers:

- calculus,
- linear algebra,
- optimisation.

The model extracted 27 Knowledge Objects. Evaluation under `benchmark/evaluation_protocol.md`, including one resolved manual adjudication item, found 25 matched required objects out of 26 required ground-truth objects, plus 2 optional supporting objects.

Aggregate development metrics:

- required precision: 1.000
- required recall: 0.962
- required F1: 0.980
- required type accuracy: 0.960
- exact source-span rate: 0.556
- manual matches: 1
- unresolved adjudications: 0

The experiment supports the core assumption that short STEM learning materials can be converted into structured Knowledge Objects before Relation Discovery.

---

# Findings

- The model extracted the main mathematical and optimisation objects reliably.
- The model did not produce obvious generic chunks, headings, or hallucinated objects.
- `calculus_001` was almost perfectly extracted.
- `linear_algebra_001` exposed ambiguity between `Concept` and `Formula`, especially for `Characteristic Polynomial`.
- `optimisation_001` extracted all required objects and added optional `Gradient`, which is meaningful for later cross-course connections.
- Source grounding was semantically valid in many cases, but exact-string matching failed often because notation was normalized or copied without Markdown escape characters.

---

# Design Implications

Knowledge Object extraction is feasible enough to remain part of the core pipeline.

However, ADR-003 should not be finalized from this single baseline. The experiment suggests that the object schema needs clearer boundary rules, especially for:

- `Concept` vs `Formula`,
- central objects vs useful supporting objects,
- formula objects that appear inside concept definitions,
- exact source span vs semantic source grounding.

The current provisional object types are usable for experimentation:

- `Concept`
- `Method`
- `Formula`

But they should remain provisional until at least one more prompt iteration or benchmark expansion.

---

# Superseded Run

The original third benchmark snippet was named `ml_optimization_001` and mixed machine learning with optimisation.

That snippet has been replaced by `optimisation_001` to keep the benchmark focused on mathematical optimisation.

The old output is archived under:

- `experiments/entity_extraction/001_baseline/output/superseded/ml_optimization_001.json`
- `experiments/entity_extraction/001_baseline/metadata/superseded/ml_optimization_001.json`

---

# Next Iteration

The next iteration should revise the prompt to:

1. extract displayed equations as separate `Formula` objects when they define or update a concept;
2. require `source_span` to be an exact substring from the input where possible;
3. clarify that named formula-related objects may still be `Concept` if the object is a mathematical construct rather than the equation itself;
4. decide whether useful supporting objects should be added to ground truth or treated as spurious.

After that, compare future runs against this baseline under the same evaluation protocol.
