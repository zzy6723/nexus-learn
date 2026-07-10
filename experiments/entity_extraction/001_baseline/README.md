# Experiment 001: Baseline Knowledge Object Extraction
 
**Version:** v0.1 (Planned)
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

- `benchmark/lectures/calculus_001.md`
- `benchmark/lectures/linear_algebra_001.md`
- `benchmark/lectures/optimisation_001.md`

Ground truth:

- `benchmark/ground_truth/knowledge_objects_v0_1.json`

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

Manual evaluation should compare model output against `benchmark/ground_truth/knowledge_objects_v0_1.json`.

Core checks:

- Precision
- Recall
- Type accuracy
- Name normalization quality
- Source grounding quality
- Duplicate rate
- Noise rate

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
```

Outputs are written to:

- `experiments/entity_extraction/001_baseline/output/calculus_001.json`
- `experiments/entity_extraction/001_baseline/output/linear_algebra_001.json`
- `experiments/entity_extraction/001_baseline/output/optimisation_001.json`

Run metadata is written to:

- `experiments/entity_extraction/001_baseline/metadata/`
