# Experiment 002C-4: Evidence-ID Remediation

**Status:** v0.2.1 implementation ready for a new formal development run

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
frozen before v0.2.1 can become the selected canonicalization method.

## v0.2 Development Finding

The first formal v0.2 runs completed and fixed the original Unicode/LaTeX copy
failure. Post-run evidence review found that the deterministic partitioner had
omitted display-math blocks at end of file when the source ended with a single
newline. The formula identity decision remained correct, but its selected
evidence was not self-contained because the required formula blocks were not
available to the model.

The failed catalog assumption is retained as development evidence. v0.2.1
fixes the partitioner and requires a new method commit and new run directories;
the v0.2 artifacts must not be overwritten.
