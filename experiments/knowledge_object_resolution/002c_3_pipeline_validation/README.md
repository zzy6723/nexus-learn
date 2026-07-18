# Experiment 002C-3: End-to-End Canonicalization And Locked Reuse

**Status:** Locked-reuse benchmark frozen; pending selected-method freeze

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

## Predeclared Source

The 002C-3 source is the final Entity output bundle from the previously
inspected 002B-1 development `run_03`. Its artifact bindings are frozen in:

```text
benchmark/ko_canonicalization/locked_reuse_v0_1/source_manifest.json
```

The source was selected before any 002C-2 context-resolver execution. This
prevents resolver behavior from influencing which downstream bundle is reused.
It does not make the data unseen.

The source has now been materialized as a 49-mention, 46-cluster evaluation
benchmark under `benchmark/ko_canonicalization/locked_reuse_v0_1/`. It contains
4 positive identity pairs and 1,172 distinct pairs. Upstream Entity grounding
is retained exactly as received: 35 spans are exact and 14 are nonexact. This
is an upstream diagnostic and must not be presented as a canonicalizer repair.

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
