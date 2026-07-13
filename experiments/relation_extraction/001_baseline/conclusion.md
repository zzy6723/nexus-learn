# Relation Extraction 001 Baseline Conclusion

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Run:** `runs/development_v0_1/run_02`  
**Status:** Development baseline and error analysis completed  
**Evaluation status:** `final`

---

# Scope

This result evaluates one development request containing 41 candidate pairs, 46
human-annotated Knowledge Objects, and 6 short authored STEM lectures. It tests
Relation type, direction, `NO_RELATION`, and evidence grounding with oracle
Knowledge Objects.

It is a development result used for prompt diagnosis. It is not evidence of
holdout generalization, long-document performance, automatic candidate
generation, or end-to-end extraction performance.

---

# Run Integrity

- Provider and model: `deepseek` / `deepseek-v4-flash`
- Temperature: `0.0`
- Top-p: `1.0`
- Maximum output tokens: `8192`
- Finish reason: `stop`
- Request success: `true`
- JSON parse success: `true`
- Prediction schema valid: `true`
- Git commit at start: `acaaebe25d99ea822c55fc4f3fe11ed969112a9d`
- Git dirty at start: `false`

---

# Final Metrics

| Metric | Result |
| --- | ---: |
| Strict edge accuracy | 0.8421 |
| Relation type accuracy ignoring direction | 0.8947 |
| Endpoint direction accuracy | 0.9286 |
| Direction accuracy when type correct | 0.9259 |
| Positive Relation accuracy | 0.8929 |
| `NO_RELATION` accuracy | 0.7000 |
| Exact evidence-span rate | 1.0000 |
| Primary-scored pairs | 38 / 41 |

Ambiguous and schema-gap pairs are excluded from the primary denominator.

---

# Evidence Adjudication

The initial evaluation produced 13 pending semantic-support cases. All were
resolved against the frozen prediction edge and evidence snapshot:

- manually adjudicated: 13;
- supported: 12;
- not supported: 1;
- pending: 0.

The manual adjudication support rate among pending evidence cases is `12/13`
(`0.923`). This is not an all-evidence semantic-support accuracy: predictions
whose evidence exactly matched the gold evidence were resolved automatically and
are not part of this denominator.

`rel_dev_014` was judged `not_supported`. Its evidence explains the role of a
step size but refers only to "the method" without identifying that method as
Gradient Descent inside the selected span.

`rel_dev_026` remains `supported`: although its introduction uses "It", the
displayed `Var(X)` equation identifies Variance unambiguously.

`rel_dev_041` is an accepted boundary case. The optimisation evidence establishes
Gradient Descent's dependency on the gradient concept, while the target is the
corresponding Gradient Knowledge Object from the calculus lecture. The current
protocol permits evidence from either candidate lecture and does not require a
span from both sides of a cross-lecture edge. No new dual-evidence rule is inferred
from this development result.

---

# Coverage Boundary

- `REQUIRES`, `APPLIED_IN`, and `FORMALIZES` have development support.
- `EXTENDS` has only one exploratory positive example.
- `CONTRASTS_WITH` has no benchmark coverage.
- `RELATED_TO` has no primary positive support and is currently observed only as
  an overuse risk.
- `NO_RELATION` includes within-lecture and cross-lecture hard negatives.

---

# Next Step

The structured analysis is recorded in `error_analysis.md`. Its evidence-supported
targets are endpoint-role serialization, `FORMALIZES` precedence, a stricter
positive-edge evidence gate, `NO_RELATION` under insufficient support,
`RELATED_TO` fallback prevention, and self-contained evidence selection.

The next step is to decide whether to create `002_prompt_refinement` using only
those targets. The benchmark, ground truth, evaluator, Relation schema, candidate
pairs, and adjudication decisions remain unchanged.
