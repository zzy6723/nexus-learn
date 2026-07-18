# Exact Name + Same Type v0.1 Results

## Setup

- benchmark role: inspected `development_reuse`;
- mentions: 39;
- gold canonical clusters: 38;
- gold `SAME_OBJECT` pairs: 1;
- method commit: `645e3cfa415f1f53aa1dd668ac84663c32830c7d`;
- launch worktree: clean;
- API calls: none.

## Results

| Metric | Result |
| --- | ---: |
| Mention coverage | 1.0000 |
| SAME_OBJECT precision | 1.0000 |
| SAME_OBJECT recall | 1.0000 |
| SAME_OBJECT F1 | 1.0000 |
| B-cubed precision | 1.0000 |
| B-cubed recall | 1.0000 |
| B-cubed F1 | 1.0000 |
| Exact gold-cluster match | 38/38 |
| Singleton precision | 1.0000 |
| Singleton recall | 1.0000 |
| False merges | 0 |
| False splits | 0 |
| Lost provenance mentions | 0 |

The method recovered the sole cross-lecture identity cluster, Newton's Method,
and retained the remaining 37 mentions as correct singleton clusters.

## Limit

The benchmark contains only one positive identity pair and no natural alias or
same-name/different-referent case. These results establish operational behavior
only for the represented identities.
