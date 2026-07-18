# Experiment 002C-1: Controlled KO Canonicalization

**Status:** Benchmark frozen; deterministic baseline pending
**Stage:** Technical Validation
**Predecessor:** Experiment 002B completed with partial feasibility

## Question

Can a deterministic method assign predicted lecture-local KO mentions to
canonical identity clusters while preserving every mention and its provenance?

## Development Scope

The initial benchmark reuses the inspected Experiment 002B inventory:

- four authored lecture snippets;
- 39 predicted KO mentions;
- three KO types: `Concept`, `Method`, and `Formula`;
- cross-lecture and within-lecture identity resolution;
- cluster-level Ground Truth with explicit singleton records.

The source artifact still declares `split = holdout` because it originated in
the 002A Relation holdout. It has already been inspected repeatedly and is
therefore assigned the explicit 002C role `development_reuse`.

## Controlled Baselines

The planned deterministic sequence is:

1. exact normalized name plus identical KO type;
2. frozen alias rules plus a context guard;
3. context-aware or model-based resolution only if deterministic methods expose
   repeated, benchmark-supported limitations.

The first baseline must reuse the shared conservative `name_matching_key()`
implementation. It must not read canonical Ground Truth, special-case mention
IDs, or merge across KO types.

## Current Coverage Warning

The real 39-mention development inventory contains only one natural
multi-mention canonical object: Newton's Method across numerical root finding
and statistics estimation. It does not naturally cover alias-only matches or
same-name/different-object ambiguity.

Synthetic fixtures may validate checker and evaluator behavior for those edge
cases, but they do not count as real benchmark evidence. A later
lecture-disjoint benchmark must add natural identity diversity before any
generalization claim.

## Frozen Development Artifacts

The controlled benchmark is complete:

- mention inventory: `benchmark/ko_mentions/development_v0_1/mention_inventory.json`;
- mention completion marker:
  `benchmark/ko_mentions/development_v0_1/mention_inventory_complete.json`;
- cluster Ground Truth:
  `benchmark/ground_truth/ko_canonicalization_development_v0_1.json`;
- Ground Truth completion marker:
  `benchmark/ground_truth/ko_canonicalization_development_v0_1_complete.json`.

Derived counts:

- 39 mentions across four lectures;
- 38 canonical clusters;
- 37 singleton clusters;
- one two-mention cluster for Newton's Method;
- one `SAME_OBJECT` pair and 740 `DISTINCT_OBJECT` pairs;
- 565 cross-lecture pairs, including one cross-lecture identity match.

The mention inventory preserves all 39 source spans. Thirty-four are exact
lecture substrings and five are retained as non-exact source predictions. This
is provenance preservation, not silent source-span repair.

Strict validation:

```bash
python3 scripts/check_ko_canonicalization_ground_truth.py
python3 -m unittest tests.test_ko_canonicalization_ground_truth -v
```

## Initial Gates

1. Generate a deterministic mention inventory from frozen predicted-KO
   artifacts.
2. Bind the inventory to source and lecture hashes with a completion marker.
3. Freeze identity annotation and evaluation rules.
4. Annotate every mention into exactly one canonical cluster.
5. Include every singleton as a canonical record.
6. Validate Ground Truth with a strict checker and completion marker.
7. Implement and evaluate the exact-name baseline without API calls. Pending.

Gates 1-6 are complete. Gate 7 must run only after the benchmark and checker
milestone is frozen in repository history.

## Out Of Scope

- cross-course Relation extraction;
- learner-specific Connection ranking;
- ontology hierarchy or concept subsumption;
- merging a Concept with its Formula or Method;
- production-scale entity resolution;
- API-based resolution in the first baseline.
