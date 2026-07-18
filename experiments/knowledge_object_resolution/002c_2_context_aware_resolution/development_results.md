# 002C-2 Development Challenge Results

## Scope

The authored development challenge contains 21 mentions in 13 gold clusters,
with 10 `SAME_OBJECT` and 200 `DISTINCT_OBJECT` pairs. It is development data,
not unseen evidence.

Both formal runs started clean at method commit:

```text
98ddd710cd4dd1f4c1034dc4a05dd24034676ac2
```

## Candidate Generation

The deterministic rules selected 11 of 210 unordered pairs, a reduction of
94.76%. The set contained all 10 gold identity pairs and the predeclared
same-name, same-type `Degree` hard negative.

```text
gold SAME_OBJECT candidate recall: 10/10 = 1.000
selected hard negatives:           1
```

## Comparison

| Metric | Exact Name | Context v0.1 |
|---|---:|---:|
| SAME_OBJECT precision | 0.500 | 1.000 |
| SAME_OBJECT recall | 0.100 | 1.000 |
| SAME_OBJECT F1 | 0.167 | 1.000 |
| B-cubed precision | 0.952 | 1.000 |
| B-cubed recall | 0.651 | 1.000 |
| B-cubed F1 | 0.773 | 1.000 |
| Exact gold clusters | 5/13 | 13/13 |
| False merges | 1 | 0 |
| False splits | 9 | 0 |
| Unresolved decisions | N/A | 0 |
| Inconsistent components | N/A | 0 |

Exact Name merged the graph-theoretic and polynomial senses of `Degree` and
split nine alias or naming-variant identity pairs. Its generic evaluation used
the existing strict canonicalization gates only to materialize metrics; method
selection follows the challenge-specific frozen criteria.

The context resolver correctly classified all ten positive candidates and the
`Degree` negative. All 11 evidence sets were exact and semantically adequate
under manual review. No adjudication was required, all mentions retained full
provenance, and no cross-type cluster was produced.

## Decision

`candidate_scoped_context_resolution_v0_1` passes every 002C-2 challenge gate
and is selected for the predeclared 002C-3 locked-reuse execution. This is a
development selection, not a production or generalization claim.
