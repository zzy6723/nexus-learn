# Experiment 002C-2: Context-Aware KO Resolution

**Status:** Protocol boundary predeclared; challenge benchmark pending 002C-1 closure

## Question

Can context resolve candidate mention pairs that deterministic names and frozen
aliases cannot decide without increasing false-merge risk?

## Frozen Architecture Boundary

```text
deterministic identity-candidate generation
-> candidate-scoped context decision
-> SAME_OBJECT / DISTINCT_OBJECT / UNRESOLVED
-> transitivity and contradiction checker
-> cluster finalizer or human adjudication
```

The resolver does not inspect every mention pair, emit arbitrary canonical IDs,
or silently resolve contradictory triangles.

## Challenge Requirements

Before method implementation, a separate challenge set must be frozen with
natural or authored educational contexts covering:

- aliases and abbreviations;
- same-name, same-type, different-referent cases;
- symbol and natural-language variants;
- at least one cluster with three mentions;
- related-but-distinct cross-type objects;
- explicit singleton mentions.

Synthetic fixtures alone cannot establish feasibility.

## Required Metrics

- candidate-pair recall for gold `SAME_OBJECT` pairs;
- `SAME_OBJECT` precision, recall, and F1;
- unresolved rate;
- inconsistent triangle count;
- false merges and false splits;
- manual adjudication count;
- final B-cubed and exact-cluster metrics;
- provenance and mention-coverage integrity.

Any contradictory identity component fails closed and enters adjudication. The
context-aware method may be omitted from the selected v0.1 pipeline only after
the frozen challenge evidence shows that deterministic resolution is adequate.
