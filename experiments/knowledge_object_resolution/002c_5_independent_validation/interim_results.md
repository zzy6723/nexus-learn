# 002C-5 Interim Results

## Status

Independent structural validation passed. The predeclared blind semantic
Evidence gate remains pending, so the complete 002C-5 result is not final.

## Execution Integrity

The seven candidate-scoped requests ran from freeze commit
`7ab00e00a7ba64b8ce906eb31ee6512983e82a3b` with a clean worktree. All
requests completed with valid JSON, valid prediction schemas, exact candidate
alignment, and `finish_reason = stop`.

## Structural Results

| Metric | Result |
| --- | ---: |
| Gold SAME_OBJECT candidate recall | 1.000 |
| SAME_OBJECT precision | 1.000 |
| SAME_OBJECT end-to-end recall | 1.000 |
| DISTINCT_OBJECT candidate accuracy | 1.000 |
| Unresolved rate | 0.000 |
| B-cubed precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Exact gold-cluster match | 38/38 |
| Singleton precision / recall | 1.000 / 1.000 |
| Mention coverage | 1.000 |
| False merges / false splits | 0 / 0 |
| Duplicate / orphan assignments | 0 / 0 |
| Cross-type clusters | 0 |
| Lost-provenance mentions | 0 |

All seven predeclared candidate decisions passed: one SAME_OBJECT identity and
six hard-negative DISTINCT_OBJECT cases.

## Evidence

All 15 selected Evidence IDs materialized to exact lecture substrings. An
unblinded semantic review judged all seven candidate-level Evidence sets
supported, and the project owner concurred.

That review is diagnostic rather than protocol-compliant blind Evidence. The
reviewer had prior exposure to Ground Truth and method-development context.
The project therefore does not claim that the frozen blind Evidence gate has
passed.

## Determinism

The stored output matched recomputed semantics. Canonical assignments and IDs
were invariant to mention order; cluster identity was invariant to candidate
decision order and candidate-manifest order.

The first direct-file checker invocation failed before writing output because
the project namespace was not available under that invocation form. Running
the same frozen checker bytes through the Python module entry point completed
successfully. No method or checker file was changed.

## Interpretation

The result independently supports the structural viability of the frozen
canonicalization pipeline on this four-lecture source. It does not establish
broad generalization, run-to-run stability, or production readiness: the
source contains only one positive identity pair and six selected hard
negatives.
