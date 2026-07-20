# 003-1: Oracle-Canonical Candidate Generation

**Status:** Implementation ready; method commit pending
**API calls:** None required

## Question

Can a gold-blind deterministic candidate generator retain at least 95% of the
41 primary positive canonical pairs while removing at least 20% of the 387-pair
classification workload?

## Frozen Inputs

- benchmark freeze commit: `11f7696ba829e9f3c51eb2fcac04757fdcdfd2a3`;
- freeze manifest: `../003_0_benchmark_preparation/benchmark_freeze_manifest_v0_1.json`;
- Oracle canonical inventory and exhaustive pair universe from
  `benchmark/connection_discovery/development_v0_1/`;
- success criteria from
  `benchmark/connection_discovery_success_criteria_v0_1.json`.

Candidate generators must not read Connection Ground Truth. The evaluator is
the only 003-1 component authorized to read `ground_truth.json`.

## Methods

1. `all_pairs` is a recall upper-bound control and cannot pass the workload
   reduction gate.
2. `overlap_bridge` selects every pair whose endpoint provenance overlaps. It
   intentionally tests whether v0.1 can be solved by a provenance shortcut.
3. `lexical_only` ranks all pairs using frozen KO names, aliases, mention spans,
   type diversity, and IDF-weighted lexical overlap. It retains a fixed 80% of
   the universe.
4. `hybrid_provenance_lexical` adds an explicit shared-provenance feature to
   the same lexical score and retains the same fixed 80%. Comparing methods 3
   and 4 isolates the contribution of the benchmark's provenance shortcut.

All methods are deterministic. Scores are diagnostic retrieval signals, not
Connection probabilities.

## Scope Warning

All 41 primary positives are `overlap_bridge`. Five disjoint-provenance
compositional positives are diagnostic only. A passing result therefore
establishes candidate recall for explicit overlap bridges, not general implicit
cross-document discovery.

## Formal Run Rule

The generator and evaluator must be committed before formal artifacts are
created. Each formal run records the operator-supplied method commit, the
freeze-manifest hash, all input hashes, method configuration, and a no-gold-read
integrity declaration. Existing run artifacts are never overwritten.
