# Experiment 002: Prompt Refinement for Knowledge Object Extraction

**Status:** Completed on development set  
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

- `benchmark/lectures/development/calculus_001.md`
- `benchmark/lectures/development/linear_algebra_001.md`
- `benchmark/lectures/development/optimisation_001.md`

Ground truth:

- `benchmark/ground_truth/development_v0_1.json`

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

Render request payloads without calling the API:

```bash
python3 scripts/run_entity_extraction.py --experiment 002_prompt_refinement --dry-run --overwrite
```

The runner refuses to overwrite existing per-lecture artifacts by default. Use a new run directory for holdout runs, or pass `--overwrite` only when deliberately replacing a previous dry run or failed run.

Outputs are written to:

- `experiments/entity_extraction/002_prompt_refinement/output/`

Metadata is written to:

- `experiments/entity_extraction/002_prompt_refinement/metadata/`

Rendered request payloads are written to:

- `experiments/entity_extraction/002_prompt_refinement/rendered_inputs/`

Raw API responses are written to:

- `experiments/entity_extraction/002_prompt_refinement/raw_responses/`

---

# Evaluation

Run:

```bash
python3 scripts/evaluate_entity_extraction.py \
  --experiment 002_prompt_refinement \
  --adjudication adjudication_resolved.json
```

Evaluation artifacts are written to:

- `experiments/entity_extraction/002_prompt_refinement/evaluation/metrics.json`
- `experiments/entity_extraction/002_prompt_refinement/evaluation/matches.json`
- `experiments/entity_extraction/002_prompt_refinement/evaluation/errors.json`
- `experiments/entity_extraction/002_prompt_refinement/evaluation/summary.md`
