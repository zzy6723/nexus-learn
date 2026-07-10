# Experiment 002: Prompt Refinement for Knowledge Object Extraction

**Status:** Planned  
**Version:** v0.2  
**Created:** 2026-07-10  
**Experiment Area:** Entity Extraction

---

# Purpose

This experiment tests whether a refined prompt can improve boundary control in Knowledge Object extraction.

It follows `experiments/entity_extraction/001_baseline` and uses the same benchmark lecture snippets.

---

# Hypothesis

Compared with the baseline prompt, a refined prompt with explicit boundary rules should:

- preserve high recall,
- reduce `Concept` vs `Formula` type errors,
- extract displayed equations as separate Formula objects when appropriate,
- improve exact `source_span` grounding,
- distinguish useful supporting objects from noise.

---

# Inputs

Canonical benchmark inputs:

- `benchmark/lectures/calculus_001.md`
- `benchmark/lectures/linear_algebra_001.md`
- `benchmark/lectures/optimisation_001.md`

Ground truth:

- `benchmark/ground_truth/knowledge_objects_v0_1.json`

---

# Main Prompt Changes

The v0.2 prompt adds explicit rules for:

- central vs supporting objects,
- `Concept` vs `Formula`,
- displayed equations,
- exact source span copying,
- avoiding variables, headings, and broad domain terms.

---

# Running the Experiment

```bash
python3 scripts/run_entity_extraction.py --experiment 002_prompt_refinement
```

Run only one input:

```bash
python3 scripts/run_entity_extraction.py --experiment 002_prompt_refinement --only linear_algebra_001
```

Outputs are written to:

- `experiments/entity_extraction/002_prompt_refinement/output/`

Metadata is written to:

- `experiments/entity_extraction/002_prompt_refinement/metadata/`
