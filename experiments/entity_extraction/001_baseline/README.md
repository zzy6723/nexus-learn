# Experiment 001: Baseline Knowledge Object Extraction
 
**Version:** v0.1 (Completed on development set)
**Experiment Area:** Entity Extraction

---

# Purpose

This experiment validates whether a baseline LLM prompt can extract stable Knowledge Objects from short STEM learning materials.

The experiment intentionally focuses on Knowledge Object extraction only. It does not generate Relations, Connections, or Connection Hypotheses.

---

# Research Question

Given short STEM lecture snippets, can an LLM extract meaningful educational entities with correct types, normalized names, aliases, and source grounding?

---

# Inputs

Canonical benchmark inputs:

- `benchmark/lectures/development/calculus_001.md`
- `benchmark/lectures/development/linear_algebra_001.md`
- `benchmark/lectures/development/optimisation_001.md`

Ground truth:

- `benchmark/ground_truth/development_v0_1.json`

---

# Output Schema

Each model output should be a JSON object with the following shape.

```json
{
  "lecture_id": "calculus_001",
  "knowledge_objects": [
    {
      "id": "gradient",
      "name": "Gradient",
      "type": "Concept",
      "aliases": ["\\nabla f(x)"],
      "short_definition": "A vector collecting the partial derivatives of a scalar-valued differentiable function.",
      "source_span": "The gradient \\(\\nabla f(x)\\) collects these partial derivatives into a vector."
    }
  ]
}
```

Allowed object types for this baseline:

- `Concept`
- `Method`
- `Formula`

These types are provisional and should be refined after the experiment before ADR-003 is finalized.

---

# Evaluation

Automated evaluation compares model output against `benchmark/ground_truth/development_v0_1.json`.

Core checks:

- Precision
- Recall
- Type accuracy
- Name normalization quality
- Source grounding quality
- Duplicate rate
- Noise rate

Run:

```bash
python3 scripts/evaluate_entity_extraction.py \
  --experiment 001_baseline \
  --adjudication adjudication_resolved.json
```

Evaluation artifacts are written to:

- `experiments/entity_extraction/001_baseline/evaluation/metrics.json`
- `experiments/entity_extraction/001_baseline/evaluation/matches.json`
- `experiments/entity_extraction/001_baseline/evaluation/errors.json`
- `experiments/entity_extraction/001_baseline/evaluation/summary.md`

---

# Failure Indicators

The baseline is considered weak if:

- Most extracted objects are chunks, headings, or generic words rather than educational entities.
- Many objects lack a valid `source_span`.
- The model repeatedly invents objects not grounded in the input.
- Types are inconsistent across similar objects.
- The output is too noisy to support later Relation Discovery.

---

# Expected Next Step

The conclusion of this experiment should identify:

- Which Knowledge Object types are stable
- Which prompt constraints improve extraction quality
- Which objects are difficult to normalize
- Whether the ground truth schema needs revision

---

# Running the Experiment

This experiment can be run with the DeepSeek API.

The runner reads `DEEPSEEK_API_KEY` from the shell environment or from a local `.env` file.

```bash
python3 scripts/run_entity_extraction.py
```

Optional arguments:

```bash
python3 scripts/run_entity_extraction.py --model deepseek-v4-flash --temperature 0
python3 scripts/run_entity_extraction.py --only calculus_001
python3 scripts/run_entity_extraction.py --dry-run --overwrite
```

The runner refuses to overwrite existing per-lecture artifacts by default. Use a new run directory for holdout runs, or pass `--overwrite` only when deliberately replacing a previous dry run or failed run.

Outputs are written to:

- `experiments/entity_extraction/001_baseline/output/calculus_001.json`
- `experiments/entity_extraction/001_baseline/output/linear_algebra_001.json`
- `experiments/entity_extraction/001_baseline/output/optimisation_001.json`

Run metadata is written to:

- `experiments/entity_extraction/001_baseline/metadata/`

Rendered request payloads are written to:

- `experiments/entity_extraction/001_baseline/rendered_inputs/`

Raw API responses are written to:

- `experiments/entity_extraction/001_baseline/raw_responses/`
