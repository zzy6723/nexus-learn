# Predicted-KO Relation Pipeline Fixtures

**Fixture version:** `synthetic_v0.1`  
**Artifact contract:** `benchmark/predicted_ko_relation_artifact_contract.md`  
**Status:** Expected outcomes frozen before Step 4 implementation

These fixtures define the expected behavior of Experiment 002B-1 alignment,
projection, matched-control integrity, and pipeline scoring. They are not a
development benchmark and must not be used to tune either selected prompt.

## Layout

```text
shared/                  Synthetic lectures, Oracle KOs, predicted KOs, and gold pairs
valid_bundle/            One complete final A-prime/B-prime pipeline example
alignment_cases.json     Identity, quality, and structural alignment cases
manifest_cases.json      Pair/KO projection and deterministic slot cases
scoring_cases.json       Recovery, conditional, and pipeline denominator cases
integrity_cases.json     Fatal stale-reference and matched-control cases
```

Every matrix case declares its expected result before implementation. Step 4
code must conform to those expectations; fixtures must not be rewritten merely
to agree with the first implementation output.

## Canonical Bundle

The canonical bundle has four primary pairs and two excluded diagnostics. All
four primary pairs are recoverable. One uniquely aligned `Gradient` KO has the
wrong predicted type and is referenced by exactly three primary pairs: one
within-lecture positive, one hard negative, and one cross-lecture positive.

Expected properties:

- unique endpoint recovery: `4/4`;
- pair-weighted endpoint recovery: `8/8`;
- pair recoverability: `4/4`;
- unique type mismatches: `1`;
- pair-weighted type-mismatch exposure: `3`;
- unmatched extra predicted KOs: `1`;
- A-prime strict edge accuracy: `4/4`;
- B-prime conditional strict edge accuracy: `3/4`;
- B-prime pipeline strict success: `3/4`;
- diagnostic pairs in every primary denominator: `0`.

The repeated hexadecimal values used in the fixtures are valid SHA-256-shaped
reference tokens for testing equality, mismatch, and staleness behavior. They
are intentionally not claimed to be hashes of the fixture files themselves.
Step 4 hash-function tests must separately use hashes computed from temporary
file content.

## Boundaries

- `invalid` is reserved for artifact or control-integrity failures.
- Upstream KO quality errors and correctly represented unrecoverable pairs are
  nonfatal pipeline observations.
- Pending identity adjudication permits draft alignment artifacts only; it
  prohibits final manifests and aggregate metrics.
- Ambiguous and schema-gap pairs are diagnostic only.
- The fixtures test a single-run controlled paired diagnostic, not stability.
