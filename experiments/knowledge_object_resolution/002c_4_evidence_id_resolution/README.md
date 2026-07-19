# Experiment 002C-4: Evidence-ID Remediation

**Status:** Infrastructure implemented; formal development execution pending

## Question

Can opaque evidence IDs preserve the v0.1 identity decisions while eliminating
free-form Unicode/LaTeX evidence-copy failures?

## Fixed Scope

002C-4 changes only the evidence transport interface. It retains:

- candidate-scoped identity classification;
- `SAME_OBJECT`, `DISTINCT_OBJECT`, and `UNRESOLVED`;
- the existing candidate generator and cluster evaluator;
- exact lecture grounding after deterministic ID materialization;
- fail-closed endpoint and schema validation.

## Development Gates

1. The rendered catalog consists only of exact lecture substrings.
2. The model can select only supplied, candidate-scoped IDs.
3. Runner output contains mechanically materialized exact spans.
4. The 002C-2 challenge retains its successful identity and cluster metrics.
5. The former 002C-3 failure case can complete as a development diagnostic.

Passing these gates does not validate generalization. A new source must be
frozen before v0.2 can become the selected canonicalization method.
