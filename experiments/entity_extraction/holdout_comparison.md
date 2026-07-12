# Holdout Comparison

**Experiment Track:** Entity Extraction Validation  
**Holdout Ground Truth:** `benchmark/ground_truth/holdout_v0_1.json`  
**Split:** `holdout`  
**Run:** `run_01`  
**Status:** Completed  
**Date:** 2026-07-12

---

# Scope

This comparison evaluates whether the refined Knowledge Object extraction prompt improves over the baseline on unseen short, authored STEM lecture snippets.

The comparison covers:

- required Knowledge Object identification;
- required Knowledge Object type classification;
- false positives and false negatives;
- exact `source_span` grounding;
- manual adjudication status.

The comparison does not evaluate long documents, parsed PDFs, heterogeneous course materials, full STEM-wide coverage, learner-state modelling, Relation Extraction, Connection Discovery, or run-to-run stability.

---

# Experimental Setup

Both runs used the same frozen holdout benchmark, model, decoding parameters, runner, and evaluator.

| Field | Value |
| --- | --- |
| Baseline run | `experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01` |
| Refined run | `experiments/entity_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01` |
| Ground truth | `benchmark/ground_truth/holdout_v0_1.json` |
| Model | `deepseek-v4-flash` |
| Temperature | `0.0` |
| Top-p | `1.0` |
| Max tokens | `4096` |
| Evaluation status | `final` for both runs |

Each run contains the required artifact directories:

- `rendered_inputs/`
- `raw_responses/`
- `output/`
- `metadata/`
- `evaluation/`

Both runs contain outputs for the same three holdout lectures:

- `calculus_002`
- `linear_algebra_002`
- `probability_001`

---

# Reproducibility Note

Both runs used the same frozen repository commit:

`8c8d061dd0f09129b7c01dfa92d7cdec71150545`

This commit corresponds to:

`Freeze entity extraction holdout protocol v0.1`

The baseline run recorded `git_dirty_at_start = false`.

The refined run recorded `git_dirty_at_start = true` because untracked artifacts from the preceding baseline run were already present under the experiment `runs/` directories.

Tracked-file verification confirmed that no tracked benchmark, prompt, runner, evaluator, or protocol files changed between the two runs:

- `git status --porcelain --untracked-files=no` produced no output;
- `git diff --name-only HEAD` produced no output;
- `git diff --cached --name-only` produced no output.

The remaining untracked files were run artifacts under the holdout run directories. Therefore, the dirty-state flag is a repository cleanliness caveat, not evidence of benchmark, prompt, or evaluator contamination.

---

# Aggregate Results

| Metric | `001_baseline` | `002_prompt_refinement` |
| --- | ---: | ---: |
| Required total | 20 | 20 |
| Prediction total | 21 | 21 |
| Required true positives | 19 | 19 |
| False positives | 0 | 0 |
| False negatives | 1 | 1 |
| Required precision | 1.000 | 1.000 |
| Required recall | 0.950 | 0.950 |
| Required F1 | 0.974 | 0.974 |
| Required type accuracy | 0.895 | 0.895 |
| Matched optional objects | 2 | 2 |
| Manual matches | 1 | 0 |
| Unresolved adjudications | 0 | 0 |
| Exact source spans | 10 | 16 |
| Invalid source spans | 11 | 5 |
| Exact source-span rate | 0.476 | 0.762 |

The baseline and refined prompts achieved the same required-object precision, recall, F1 score, and required-object type accuracy. The refinement therefore did not improve Knowledge Object identification or type classification on unseen materials.

However, the refined prompt increased the exact source-span rate from `0.476` to `0.762` on the current holdout benchmark without reducing the other measured extraction metrics. This indicates that the refined grounding instructions improved compliance with the requirement that each `source_span` be copied exactly from the input.

---

# Per-Lecture Results

| Lecture | Run | Precision | Recall | F1 | Type Accuracy | Exact Source-Span Rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `calculus_002` | `001_baseline` | 1.000 | 1.000 | 1.000 | 0.750 | 0.000 |
| `calculus_002` | `002_prompt_refinement` | 1.000 | 1.000 | 1.000 | 0.750 | 0.000 |
| `linear_algebra_002` | `001_baseline` | 1.000 | 1.000 | 1.000 | 1.000 | 0.714 |
| `linear_algebra_002` | `002_prompt_refinement` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `probability_001` | `001_baseline` | 1.000 | 0.900 | 0.947 | 0.889 | 0.556 |
| `probability_001` | `002_prompt_refinement` | 1.000 | 0.900 | 0.947 | 0.889 | 1.000 |

The refined prompt improved exact source-span grounding on `linear_algebra_002` and `probability_001`. It did not improve the exact source-span rate on `calculus_002`, where all predicted spans still failed exact substring validation.

---

# Error Analysis

The refined prompt reduced invalid source-span errors from 11 to 5.

Remaining errors in the refined run:

- `calculus_002`: invalid source spans for all five predicted objects;
- `calculus_002`: `Chain Rule` typed as `Method` while the ground truth labels it as `Concept`;
- `probability_001`: `Bayes' Rule` typed as `Formula` while the ground truth labels it as `Concept`;
- `probability_001`: missing required object `Bayes' Rule Formula`.

The source-span failures in `calculus_002` appear related to exact Markdown or LaTeX preservation rather than object identification failure. The model selected educationally relevant source text, but not exact substrings under the current evaluator.

Named mathematical rules remain sensitive to the boundary between `Concept`, `Method`, and `Formula`. In this holdout run, `Chain Rule` and `Bayes' Rule` are the concrete type-boundary failures.

---

# Manual Adjudication

The baseline run required one manual adjudication:

| Lecture | Prediction | Decision | Ground Truth |
| --- | --- | --- | --- |
| `probability_001` | `Expected Value Formula (Discrete)` | `matched` | `expected_value_formula` |

The prediction refers to the same discrete expected value formula as the ground-truth `Formula` object. The parenthetical qualifier only makes the lecture context explicit.

The refined run required no manual adjudication.

---

# Decision

`002_prompt_refinement` is selected as the default Knowledge Object extraction prompt for the next Technical Validation stage.

This decision is based on improved exact source grounding, not improved object coverage or type classification.

The refined prompt is selected because it achieved the same required precision, required recall, required F1 score, required-object type accuracy, false-positive count, and false-negative count as the baseline while increasing the exact source-span rate on the current holdout benchmark.

---

# Limitations

Knowledge Object extraction is operationally viable for the MVP on the current holdout benchmark of short, authored STEM lecture snippets.

This result should not be interpreted as evidence of general STEM-wide performance. The holdout benchmark is small and does not evaluate:

- full lecture notes or long documents;
- parsed PDFs;
- OCR or noisy text;
- heterogeneous course materials;
- all STEM disciplines;
- run-to-run stability;
- relation extraction or connection discovery.

Type-boundary errors and exact Markdown or LaTeX span preservation remain known limitations.

---

# Next Step

Use `002_prompt_refinement` as the default Knowledge Object extraction prompt for the next Technical Validation stage.

Before claiming extraction stability, run a repeated-run stability test on the selected prompt. If the project moves directly to Relation Extraction instead, record that run-to-run stability remains unvalidated.
