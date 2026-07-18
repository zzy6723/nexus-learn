# 002C-1 Development Comparison

## Reproducibility

Both formal runs:

- started from commit `645e3cfa415f1f53aa1dd668ac84663c32830c7d`;
- recorded `git_dirty_at_start = false`;
- used the same frozen 39-mention inventory;
- used the same normalization config and runner;
- reached final evaluation status;
- passed every frozen success criterion.

The only intended difference was whether the frozen alias resource was active.

## Aggregate Comparison

| Metric | Exact | Alias-Aware |
| --- | ---: | ---: |
| Predicted clusters | 38 | 38 |
| SAME_OBJECT precision | 1.0000 | 1.0000 |
| SAME_OBJECT recall | 1.0000 | 1.0000 |
| SAME_OBJECT F1 | 1.0000 | 1.0000 |
| B-cubed F1 | 1.0000 | 1.0000 |
| Exact gold-cluster matches | 38/38 | 38/38 |
| False merges | 0 | 0 |
| False splits | 0 | 0 |
| Lost provenance | 0 | 0 |

The two methods produced the same mention partition and assignment mapping.

## Decision

`exact_name_same_type_v0_1` is selected as the deterministic candidate entering
002C-2 because the frozen selection policy prefers the simpler method when
formal metrics tie.

This is not the final production canonicalizer. The synthetic diagnostic shows
that deterministic name methods can false-merge same-name, same-type homonyms,
and the real benchmark lacks that identity boundary.
