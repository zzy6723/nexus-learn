# Candidate Pair Generation Evaluation Protocol

**Status:** Draft v0.1 for Experiment 002B-2 benchmark construction
**Scope:** lecture-local predicted Knowledge Objects
**Owner:** Project

## Purpose

This protocol evaluates whether a candidate generator can reduce the unordered
Knowledge Object pair universe without losing true typed Relations. It governs
pair selection only. Relation labels, directions, Evidence, and rationales are
evaluated by the frozen Relation protocol after candidate generation.

## Separation of Responsibilities

The pipeline stages are:

```text
Entity Extraction
    -> lecture-local predicted KO inventory
    -> Candidate Pair Generation
    -> frozen Relation Classification
```

The candidate generator may decide only whether an unordered pair is retained.
It must not predict Relation type or direction.

Experiment 002B-1 Oracle alignment is not a model-facing input. Experiment 002C
canonical IDs do not yet exist and must not be simulated in this experiment.

## Evaluation Universe

For each declared lecture inventory containing `n` valid predicted KOs, the
complete pair universe contains:

```text
n(n - 1) / 2
```

unordered pairs. A valid exhaustive benchmark must satisfy:

- every pair contains two distinct KOs from the same declared lecture;
- endpoint order is canonical and deterministic;
- no pair is duplicated;
- every mathematically possible unordered pair occurs exactly once;
- every pair has an annotation status;
- every KO occurs in exactly `n - 1` pairs for its lecture.

The checker must derive the expected pair set from the frozen KO inventory and
compare sets, not trust a declared count.

## Annotation States

Each exhaustive pair receives exactly one state:

- `positive`: one frozen graph Relation applies;
- `no_relation`: no graph Relation is supported by the material;
- `ambiguous`: the frozen guide permits more than one acceptable outcome;
- `schema_gap`: a meaningful relation exists but the frozen Relation schema
  cannot represent it.

Two predicted mentions that appear to denote the same educational object are
not silently removed. Until Experiment 002C provides canonical identity, their
pair remains in the exhaustive universe and is annotated as `schema_gap` with
an identity-or-duplicate reason. It is excluded from primary candidate scoring
and reported separately.

Primary candidate precision and recall use only `positive` and `no_relation`
pairs. `ambiguous` and `schema_gap` pairs are reported separately and never
silently converted to negatives.

Positive annotations must include Relation type, direction when applicable,
exact Evidence spans, and rationale under the existing Relation annotation
guide. Negative annotations must record a concise reason for `no_relation`.

## Existing Benchmark Limitation

`relations_holdout_v0_1.json` is a selected 40-pair classification benchmark.
It is not an exhaustive pair universe. Pairs absent from that file are
unlabelled, not negative. It cannot support candidate precision, all-pairs
reduction, or full candidate recall metrics.

## Frozen Input Inventory

The benchmark must bind to one exact predicted KO inventory using:

- inventory path and SHA-256;
- Entity prompt and model version;
- lecture IDs and lecture-text hashes;
- ordered fully qualified KO references;
- KO content hashes;
- structural normalization version.

Changing the inventory creates a new benchmark version and requires complete
pair regeneration and annotation review.

## Generator Contract

Every generator output records:

- generator ID and version;
- method configuration and hash;
- input inventory hash;
- generated pair count;
- deterministic ordered pair list;
- one or more non-gold candidate reasons;
- run timestamp and implementation hash.

The generator must not read:

- pair annotations;
- gold Relation labels or categories;
- gold Evidence or rationale;
- Relation model outputs;
- Oracle alignment records;
- holdout metrics.

## Candidate-Generation Metrics

Let:

- `P_pred` be primary positive pairs annotated over the frozen predicted-KO
  inventory;
- `N_pred` be primary `NO_RELATION` pairs over the same inventory;
- `U_primary = P_pred union N_pred`;
- `C` be all generated candidate pairs;
- `C_primary = C intersect U_primary`.

Report:

```text
candidate_recall = |C intersect P_pred| / |P_pred|
candidate_precision = |C intersect P_pred| / |C_primary|
retention_rate_primary = |C_primary| / |U_primary|
reduction_ratio_primary = 1 - retention_rate_primary
```

If `P_pred` is empty, candidate recall is `null`, not zero. If `C_primary` is
empty, candidate precision is `null`. If the benchmark is not exhaustive,
candidate precision and primary retention/reduction metrics are invalid and
must not be emitted as final values. Retention of `ambiguous` and `schema_gap`
pairs is reported as separate counts and must not alter the primary
denominator.

## Upstream and End-to-End Metrics

Endpoint recoverability is evaluated against the separate Oracle Relation
benchmark through the frozen 002B-1 alignment:

```text
endpoint_recoverability_oracle =
  recoverable Oracle positive edges / all Oracle positive edges
```

This is an upstream Entity/alignment metric, not a candidate-generator metric.
An Oracle edge and a predicted-inventory pair may be compared only through a
frozen, auditable alignment artifact; their identifiers must never be
intersected directly.

After candidate generation and Relation Classification, use that same mapping
to report end-to-end typed-edge recall over Oracle positive edges. Report
candidate recall over `P_pred` alongside it. The two figures answer different
questions and must not be substituted for each other.

After Relation Classification, also report:

- typed edge precision, recall, and F1;
- Relation type and direction errors;
- false-positive and false-negative edges;
- `NO_RELATION` workload;
- exact and semantically supported Evidence rates;
- request count, token usage, latency, and estimated cost.

## Baseline Comparability

All-Pairs and Rule-Filtered baselines must use:

- the same frozen predicted KO inventory;
- the same complete pair annotations;
- the same Relation classifier, prompt, schema, model, and parameters;
- the same Relation request-partitioning method;
- the same evaluator and adjudication rules.

Only the candidate-generation method may differ.

## Development and Holdout

Development lectures may be inspected to design deterministic rules and select
thresholds. The holdout must use different lectures. Before holdout execution,
freeze:

- predicted KO inventory generation;
- exhaustive annotation guide and ground truth;
- generator implementations and configurations;
- endpoint and pair matching;
- metric denominators and success criteria;
- Relation classifier and evaluator.

If holdout labels or outputs are inspected and the generator is changed, that
split becomes development data and a new holdout is required.

## Integrity Failures

Evaluation is invalid if:

- the pair universe is incomplete or duplicated;
- a pair references an unknown or repeated endpoint;
- pair ordering changes between compared generators;
- the generator reads gold-only fields;
- unlabelled pairs are counted as negatives;
- inventory hashes differ between generator runs;
- Relation methods differ between downstream comparisons;
- holdout rules are changed after outputs are inspected.

Invalid evaluations must not emit aggregate metrics that can be mistaken for a
final result.

## Current Status

This protocol defines the benchmark and metric boundary. No 002B-2 benchmark,
generator, evaluator result, or holdout claim has yet been completed.
