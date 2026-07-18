# Knowledge Object Resolution Experiments

This directory validates how lecture-local predicted Knowledge Object mentions
become stable canonical Knowledge Objects without losing source provenance.

Knowledge Object Resolution is separate from Relation Extraction:

- identity asks whether two mentions denote the same educational object;
- a Relation asks how two distinct Knowledge Objects are connected.

## Current Stage

Experiment 002C-1 has frozen its controlled canonicalization benchmark and
strict artifact checks. The first benchmark reuses the inspected four-lecture,
39-mention inventory from Experiment 002B as development data. It is not unseen
evidence.

```text
predicted lecture-local KO mentions
-> canonical identity clusters
-> stable canonical KO records
-> provenance-preserving mention membership
```

The active experiment is documented in
`002c_controlled_canonicalization/README.md`.

The next gate is the exact-normalized-name deterministic baseline. No API-based
resolver is authorized at this stage.

## Programme Boundary

Experiment 002C does not classify typed Relations, generate candidate edges, or
rank learner-facing Connections. Cross-lecture Relation discovery begins only
after identity resolution has a validated contract.
