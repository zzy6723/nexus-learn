# Experiment 002C-2: Context-Aware KO Resolution

**Status:** Completed; context v0.1 passed the authored development challenge

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

The completed authored development challenge is stored at:

```text
benchmark/ko_canonicalization/challenge_v0_1/
```

Its final marker binds 9 lectures, 21 mentions, 13 gold clusters, 10
`SAME_OBJECT` pairs, 200 `DISTINCT_OBJECT` pairs, the challenge protocol, and
the success criteria. The challenge is development data, not an unseen
holdout. Context-resolver implementation starts only after this bundle is
committed unchanged.

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

## Implemented Method

- `scripts/generate_ko_identity_candidates.py` creates an auditable,
  Ground-Truth-blind candidate bundle;
- `scripts/run_context_ko_resolution.py` performs one candidate per request;
- `scripts/finalize_context_ko_clusters.py` checks unresolved and contradictory
  decisions before producing clusters;
- `scripts/evaluate_context_ko_resolution.py` separates candidate, resolver,
  and final-cluster metrics.

The frozen execution and retry rules are recorded in
`method_contract_v0_1.md`. Synthetic tests cover complete success, endpoint
substitution, nonexact evidence, unresolved decisions, inconsistent identity
triangles, no-overwrite behavior, and artifact hash binding.

Formal results are recorded in `development_results.md`. The context method
passed every challenge criterion and was selected for 002C-3 locked reuse.
