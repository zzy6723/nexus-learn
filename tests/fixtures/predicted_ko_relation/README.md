# Predicted-KO Relation Pipeline Fixtures

**Fixture version:** `synthetic_v0.1`  
**Artifact contract:** `benchmark/predicted_ko_relation_artifact_contract.md`  
**Status:** Contracts and expected outcomes defined and statically validated

These fixtures define the expected behavior of Experiment 002B-1 alignment,
projection, matched-control integrity, and pipeline scoring. They are not a
development benchmark and must not be used to tune either selected prompt.

## Layout

```text
shared/                  Synthetic lectures, Oracle KOs, predicted KOs, and gold pairs
valid_bundle/            Canonical expected-output template with lower-level snapshots
normalization_cases.json Structural normalization and content-preservation cases
alignment_cases.json     Identity, quality, and structural alignment cases
manifest_cases.json      Pair/KO projection and deterministic slot cases
scoring_cases.json       Recovery, conditional, and pipeline denominator cases
integrity_cases.json     Fatal stale-reference and matched-control cases
```

Every matrix case declares its expected result before implementation. Step 4
code must conform to those expectations; fixtures must not be rewritten merely
to agree with the first implementation output.

Step 3 completion means the contracts and fixture expectations have been
defined and statically validated. It does not mean every behavioral case has
already been executed against Step 4 code.

The current matrices contain 95 predeclared cases:

- normalization: 9;
- alignment: 14;
- manifest derivation: 10;
- scoring: 8;
- integrity: 54.

Step 4.0/4.1 currently provides executable fixture/hash-chain checks and
normalization behavior tests. Alignment, projection, and pipeline cases become
executable only when their corresponding components are implemented.

## Pre-Implementation Contract Correction

Before Step 4 code was written, the v0.1 fixtures were corrected to:

- distinguish correctly recorded `collapsed_endpoints` from a projected
  collapsed pair;
- define final no-op evaluations for zero recoverable pairs;
- add A0/A-prime/B-prime lower-level Relation artifacts and run metadata;
- bind matched execution to provider, model, parameters, commit, inputs,
  predictions, and evaluation snapshots;
- freeze lexicographic pair ordering;
- separate structural normalization from name-matching normalization;
- expand previously uncovered fatal branches.

These are recorded contract corrections, not changes made to fit implementation
output.

## Canonical Bundle

The canonical expected template has four primary pairs and two excluded
diagnostics. All
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

The template also includes:

- A0, A-prime, and B-prime Relation predictions;
- final lower-level `metrics.json`, `matches.json`, and `errors.json` snapshots;
- matched run metadata and evaluation snapshot manifests;
- the deterministic single-batch plan;
- manually precomputed golden pipeline outputs.

The pipeline golden files were written from the declared pair outcomes and
reviewed independently of the future pipeline evaluator. They must never be
regenerated from the implementation under test and then treated as its oracle.

The repeated hexadecimal values used in the fixtures are valid SHA-256-shaped
reference tokens for testing equality, mismatch, and staleness behavior. The
repository copy is therefore a template, not a production-valid hash chain.
Step 4 test support materializes a temporary runtime copy, replaces tokens in
dependency order with real file hashes, and runs integrity checks on that copy.
Production validators must never accept symbolic fixture tokens.

## Boundaries

- `invalid` is reserved for artifact or control-integrity failures.
- Upstream KO quality errors and correctly represented unrecoverable pairs are
  nonfatal pipeline observations.
- Pending identity adjudication permits draft alignment artifacts only; it
  prohibits final manifests and aggregate metrics.
- Ambiguous and schema-gap pairs are diagnostic only.
- The fixtures test a single-run controlled paired diagnostic, not stability.

## Executable Validation Status

The Step 4.0/4.1 test support and normalizer currently pass alongside the full
existing Relation regression suite. This does not yet mean all 95 predeclared
behavior cases pass; most remain oracles for Steps 4.2-4.4.
