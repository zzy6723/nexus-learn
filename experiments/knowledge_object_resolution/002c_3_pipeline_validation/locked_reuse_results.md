# 002C-3 Locked-Reuse Results

## Scope

The locked-reuse benchmark contains 49 previously inspected Entity mentions,
46 gold clusters, 4 positive identity pairs, and 1,172 distinct pairs. Its
upstream grounding contains 35 exact and 14 nonexact source spans.

Candidate generation selected six pairs:

- all four gold identity pairs;
- `Hessian Matrix` versus `Matrix`;
- `Jacobian Matrix` versus `Matrix`.

## Execution Outcome

The selected v0.1 method did not complete a schema-valid run. Two formal
attempts used the same frozen payload and failed on the first candidate before
any aggregate prediction was produced.

Both attempts returned a semantically plausible `SAME_OBJECT` decision for two
Gradient mentions, but copied this upstream span:

```text
The gradient ∇f(x) collects these partial derivatives into a vector.
```

The bound lecture text contains a different byte-level representation:

```text
The gradient \(\nabla f(x)\) collects these partial derivatives into a vector.
```

The runner therefore correctly rejected the evidence as nonexact. The second
attempt repeated the same evidence mismatch on the same candidate under the
same request-payload set. Retrying stopped at that point; no output was edited,
no validator was relaxed, and no failed partial bundle entered evaluation.

## Formal Status

```text
execution status: failed
schema-valid complete runs: 0
cluster finalization: not run
pipeline metrics: not produced
```

The snapshot-bound failure record is stored at:

```text
runs/locked_reuse_v0_1/execution_failure_summary.json
```

## Interpretation

002C-3 does not show a semantic false merge or false split. It shows that the
v0.1 free-form exact-evidence interface is not operationally compatible with
this upstream bundle's Unicode/LaTeX representation mismatch.

The locked-reuse data has now influenced diagnosis and must be treated as
development data for any remediation. A future validation claim requires a new
locked-reuse or unseen source selected before the revised method is run.
