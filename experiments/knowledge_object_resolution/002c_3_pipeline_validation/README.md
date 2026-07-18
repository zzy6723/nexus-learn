# Experiment 002C-3: End-to-End Canonicalization And Locked Reuse

**Status:** Pending selected-method freeze

## Question

Can the frozen canonicalization method generate a complete, auditable canonical
KO inventory when reused unchanged on another frozen predicted-KO bundle?

## Required Flow

```text
lecture artifacts
-> frozen Entity Extraction outputs
-> predicted KO mention inventory
-> selected canonicalization method v0.1
-> canonical KO inventory
-> provenance and downstream-readiness audit
```

Previously inspected data must be labelled `locked_reuse`, not unseen holdout.
A true holdout requires new lectures that did not influence normalization,
aliases, candidate rules, context resolution, or success criteria.

## Required Audits

- all mentions assigned exactly once;
- no orphan or duplicate assignments;
- no cross-type clusters;
- complete mention-to-source provenance;
- false merge, false split, and singleton outcomes;
- upstream Entity omissions separated from canonicalizer errors;
- canonical endpoint uniqueness and readiness for Experiment 003;
- cross-lecture and multi-mention cluster counts.

002C-3 does not run cross-lecture Relation classification, Connection ranking,
or learner-facing explanation.
