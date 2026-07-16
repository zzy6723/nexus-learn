# 002B-2 Downstream Typed-Edge Diagnostic

**Status:** Final
**Scope:** Inspected development diagnostic, not unseen holdout evidence

| Metric | All-Pairs v0.1 | Rule-Filtered v0.1 |
| --- | ---: | ---: |
| Candidate selected | 176 | 127 |
| Candidate positive recall | 1.0000 | 0.8750 |
| Conditional Relation strict | 0.3626 | 0.3689 |
| End-to-end strict /171 | 0.3626 | 0.4912 |
| Positive typed-edge recall /80 | 0.5000 | 0.4500 |
| Positive typed-edge precision | 0.2703 | 0.3214 |
| Candidate-induced FN | 0 | 10 |
| Classifier NO_RELATION FN | 1 | 1 |
| Wrong Relation type | 35 | 30 |
| Wrong direction | 4 | 3 |
| False-positive Relations | 69 | 43 |
| Exact Evidence span | 0.7751 | 0.7875 |
| API requests | 176 | 127 |

## Interpretation

- Rule-Filtered v0.1 remains failed at the frozen Candidate recall gate.
- It omitted 10 primary positive pairs; the frozen All-Pairs classifier was strictly
  correct on 4 of those omitted pairs.
- Downstream results diagnose the observed loss under the frozen classifier; they do
  not make omitted candidates recoverable and cannot reverse the Candidate gate.
- All-Pairs v0.1 remains the current lecture-local safety fallback, while its quadratic
  workload and false-positive exposure remain material limitations.
