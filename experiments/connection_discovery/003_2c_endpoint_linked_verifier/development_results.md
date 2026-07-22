# 003-2c Development Results

**Status:** Final; execution completed and frozen development gates failed  
**Scope:** Endpoint-linked Oracle-canonical Connection verification on the
existing 125-pair development benchmark

## Experimental Control

The method reused the selected `overlap_bridge_v0.1` candidate set, Oracle
canonical endpoints, Evidence catalogs, Ground Truth, evaluator, and global
success criteria. Its intentional method change was to replace catalog-wide
edge generation with deterministic minimal Evidence windows that cover both
endpoints, followed by candidate-scoped window classification and deterministic
aggregation.

This benchmark is development-only for 003-2c because errors from the earlier
one-stage and two-stage runs informed the endpoint-linking method. The result
cannot support a generalization claim.

The completed v0.1.1 run started from clean method commit
`02a618358301d1e4f87488198e71c8d9dc232fbc`. It processed all 173 windows for
125 candidates. Three schema-invalid responses were repaired once under the
frozen generic validator-guided repair contract. There were no transport
retries, all 125 predictions were schema-valid, and `finish_reason = stop`.

## Preprocessor And Aggregation

- selected candidates: 125;
- generated minimal windows: 173;
- candidates with at least one window: 111;
- deterministic no-window candidates: 14;
- primary-positive window coverage: 41/41 (`1.0000`);
- window decisions marked `DIRECT_IN_SCHEMA`: 128;
- window decisions marked `MEDIATED_OR_CONTEXTUAL`: 37;
- window decisions marked `INSUFFICIENT`: 8;
- window decisions marked `DIRECT_OUT_OF_SCHEMA`: 0;
- unique-edge aggregations: 71;
- no-direct-edge aggregations: 37;
- conflicting-edge aggregations: 17.

The 17 aggregation conflicts exceed the predeclared maximum of 2. Although the
aggregator failed closed to `NO_RELATION`, this also contributed to nine false
negatives.

## Final Metrics

| Metric | Result | Frozen 003-2c threshold | Passed |
| --- | ---: | ---: | --- |
| Primary-positive window coverage | 1.0000 | >= 0.95 | Yes |
| Fatal alignment errors | 0 | = 0 | Yes |
| Aggregation conflicts | 17 | <= 2 | No |
| Positive edge precision | 0.2206 | >= 0.70 | No |
| Positive typed-edge recall | 0.3659 | >= 0.70 | No |
| `NO_RELATION` accuracy | 0.5385 | >= 0.85 | No |
| Semantic Evidence support | 0.4085 | >= 0.90 | No |
| `RELATED_TO` prediction rate | 0.0000 | <= 0.05 | Yes |

The global v0.1 evaluator also reports exact Evidence materialization of
`1.0000`, strict edge accuracy of `0.4790`, full-universe F1 of `0.2752`, and
cross-course Connection recall of `0.3571`. The run produced 15 correct
positive edges, 42 correct selected negatives, 36 false-positive Relations,
9 false negatives, 11 wrong types, and 6 wrong directions.

All 65 pending Evidence cases were manually adjudicated against the frozen
semantic-support rule. Twenty-three were `supported` and 42 were
`not_supported`. Together with six automatic exact-gold matches, 29 of 71
positive predictions had semantically supported Evidence (`0.4085`).

## Comparison

| Metric | One-stage Prompt 002 | Two-stage v0.1.2 | Endpoint-linked v0.1.1 |
| --- | ---: | ---: | ---: |
| Correct positive edges | 13 | 13 | 15 |
| False-positive Relations | 40 | 40 | 36 |
| False negatives | 3 | 4 | 9 |
| Positive typed-edge recall | 0.3171 | 0.3171 | 0.3659 |
| Positive edge precision | 0.1667 | 0.1688 | 0.2206 |
| `NO_RELATION` accuracy | 0.4872 | 0.4872 | 0.5385 |
| Strict edge accuracy | 0.4286 | 0.4286 | 0.4790 |
| Relation type accuracy | 0.5854 | 0.5366 | 0.5122 |
| Direction accuracy when type correct | 0.5417 | 0.5909 | 0.7143 |
| Semantic Evidence support | 0.4512 | 0.4096 | 0.4085 |
| `RELATED_TO` prediction rate | 0.0252 | 0.0840 | 0.0000 |
| Full-universe F1 | 0.2185 | 0.2203 | 0.2752 |
| Cross-course Connection recall | 0.2857 | 0.3214 | 0.3571 |

Endpoint linking yields modest gains in correct edges, false-positive control,
direction, and full-universe F1. The gains are not sufficient for selection:
precision remains far below threshold, semantic Evidence support does not
improve, Relation type accuracy falls, and conflict-driven false negatives more
than double relative to the previous methods.

## Error Interpretation

The method successfully prevents `RELATED_TO` fallback and guarantees exact
Evidence transport. It does not solve the semantic decision boundary. The
window classifier still treats co-occurrence in a derivation, a shared method,
or a nearby contrast as a direct edge between the exact endpoints. It also
drifts between concepts, formulas, methods, and their associated objects.

The absence of any `DIRECT_OUT_OF_SCHEMA` decisions is itself diagnostic. The
four-way verifier uses `DIRECT_IN_SCHEMA` too readily and does not reliably
separate a direct but unrepresentable connection from mediated context or an
in-schema edge.

## Scope Limits

These results concern short authored STEM snippets, Oracle canonical Knowledge
Objects, one model configuration, and development data that informed the
method. They do not establish independent generalization, predicted-canonical
performance, long-document robustness, learner usefulness, or run-to-run
stability.
