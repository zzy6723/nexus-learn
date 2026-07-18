# Experiment 002C-1: Deterministic KO Canonicalization

**Status:** Implementation and synthetic validation passed; formal development runs pending
**API usage:** None
**Frozen input:** 002C-0 development-reuse mention inventory v0.1

## Question

How much KO identity resolution is possible using only conservative name
normalization, a frozen type-scoped alias resource, and KO type?

## Compared Methods

### Exact Normalized Name + Same Type v0.1

Merge mentions if and only if their normalized names and KO types are equal.

### Frozen Alias Map + Same Type v0.1

Apply the same normalization contract, map names through the frozen alias
resource, then merge if and only if the resulting identity keys and KO types
are equal.

Neither method reads Ground Truth, mention-specific exceptions, semantic
embeddings, Relation outputs, or LLM responses.

## Method Artifacts

- `benchmark/ko_name_normalization_protocol.md`;
- `benchmark/ko_name_normalization_v0_1.json`;
- `benchmark/ko_aliases_v0_1.json`;
- `benchmark/ko_canonicalization_success_criteria_v0_1.json`;
- `scripts/run_deterministic_ko_canonicalization.py`;
- `scripts/evaluate_ko_canonicalization.py`.

## Formal Run Layout

```text
runs/development_v0_1/
├── exact_name_same_type_v0_1/run_01/
│   ├── canonical_clusters.json
│   ├── mention_assignments.json
│   ├── normalization_audit.json
│   ├── metadata.json
│   ├── generation_complete.json
│   └── evaluation/
└── alias_aware_same_type_v0_1/run_01/
    └── ...
```

The formal runner performs read-only Git checks when launched by the project
owner. It rejects a dirty worktree or a commit different from the declared
method commit. Generated artifacts are no-overwrite by default.

## Synthetic Diagnostic

The predeclared semantic fixture intentionally includes:

- two alias-based same-object clusters;
- two `Degree` mentions with the same name and type but different referents;
- a related Method and Formula that must remain distinct.

Observed unit behavior:

- Exact Name exposes one same-name false merge and two alias false splits;
- Alias-Aware repairs the two alias splits but retains the same-name false
  merge;
- neither method merges across KO types;
- all provenance snapshots are retained exactly;
- repeated generation is byte deterministic.

Synthetic results validate behavior and limitations. They are not combined
with real benchmark metrics.

## Interpretation Boundary

The real 39-mention benchmark contains only one positive identity pair and no
natural homonym case. Even a perfect formal result can establish only that the
method handles identities represented in that development benchmark. It cannot
establish general alias resolution or contextual disambiguation.

## Next Gate

Freeze this method milestone, then run both methods from the same clean commit
and evaluate them with the frozen evaluator. If both tie on the real benchmark,
the simpler method is preferred there, while the synthetic homonym failure
still motivates an independent 002C-2 challenge evaluation.
