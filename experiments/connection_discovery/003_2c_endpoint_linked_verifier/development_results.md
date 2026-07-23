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

Of the 14 zero-window pairs, 13 are primary negatives and one is a diagnostic
`OUT_OF_SCHEMA_CONNECTION`; no primary positive has zero windows. Of the 17
aggregation conflicts, seven are primary positives, eight are primary
negatives, and two are diagnostic out-of-schema pairs.

The 17 aggregation conflicts exceed the predeclared maximum of 2. The
fail-closed policy directly rejected seven gold-positive pairs and correctly
protected eight gold-negative pairs; the two diagnostic pairs are excluded
from primary scoring. Conflict patterns comprise 10 type-only disagreements,
four direction-only disagreements, and three disagreements involving both
type and direction.

Conflict rates are:

- `17/125` (`0.1360`) across all selected pairs;
- `17/111` (`0.1532`) among window-covered pairs;
- `17/88` (`0.1932`) among pairs with at least one `DIRECT_IN_SCHEMA` window.

The last denominator shows that nearly one in five pairs with at least one
locally asserted direct edge failed to produce one unique graph edge across
Evidence views. This is window-level semantic instability, not an aggregation
policy defect; without window-level gold labels, majority voting or confidence
tie-breaking would be ungrounded.

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
positive edges, 17 wrong typed or directed edges on gold-positive pairs, nine
gold-positive pairs predicted as `NO_RELATION`, 36 edges on gold-negative
pairs, and 42 correctly rejected gold negatives. The 17 wrong final positive
edges comprise 11 wrong Relation types and six wrong directions.

All 65 pending Evidence cases were manually adjudicated against the frozen
semantic-support rule. Twenty-three were `supported` and 42 were
`not_supported`. Together with six automatic exact-gold matches, 29 of 71
positive predictions had semantically supported Evidence (`0.4085`).

## Comparison

| Primary outcome | One-stage Prompt 002 | Two-stage v0.1.2 | Endpoint-linked v0.1.1 |
| --- | ---: | ---: | ---: |
| Strict-correct gold-positive edge | 13 | 13 | 15 |
| Wrong typed/directed edge on gold positive | 25 | 24 | 17 |
| Gold positive predicted `NO_RELATION` | 3 | 4 | 9 |
| Edge predicted on gold negative | 40 | 40 | 36 |
| Correct `NO_RELATION` on gold negative | 38 | 38 | 42 |

| Metric | One-stage Prompt 002 | Two-stage v0.1.2 | Endpoint-linked v0.1.1 |
| --- | ---: | ---: | ---: |
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
| Semantic Evidence support count | 37/82 | 34/83 | 29/71 |

Endpoint linking yields modest gains in correct edges, false-positive control,
direction, and full-universe F1. The gains are not sufficient for selection:
precision remains far below threshold, semantic Evidence support does not
improve, Relation type accuracy falls, and gold-positive rejection rises from
three or four cases to nine. The method is more conservative, but the reduction
in negative overconnection is not enough to offset low precision and recall.

The identical integer `17` appears in two unrelated diagnostics:

- 17 final positive predictions have the wrong Relation type or direction;
- 17 canonical pairs contain conflicting direct-edge window decisions.

The first is a final graph error class. The second is a pre-aggregation
consistency failure that produces fail-closed `NO_RELATION`.

## Uncertainty

Counts and Wilson 95% intervals are reported to avoid overstating precision
from this small development benchmark:

- primary-positive window coverage: `41/41` (`1.0000`), interval
  `[0.9143, 1.0000]`;
- positive edge precision: `15/68` (`0.2206`), interval
  `[0.1385, 0.3326]`;
- positive typed-edge recall: `15/41` (`0.3659`), interval
  `[0.2359, 0.5188]`;
- `NO_RELATION` accuracy: `42/78` (`0.5385`), interval
  `[0.4286, 0.6447]`;
- semantic Evidence support: `29/71` (`0.4085`), interval
  `[0.3017, 0.5246]`;
- all-pair aggregation conflict rate: `17/125` (`0.1360`), interval
  `[0.0867, 0.2070]`.

These intervals are descriptive uncertainty bounds, not statistical
significance tests between methods.

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

## Execution Reliability

Execution failures were retained separately from semantic quality:

- one-stage execution required no retries;
- two-stage execution resumed after a transport timeout, reused 125 completed
  Stage-A decisions, completed 37 Stage-B requests, and used 13 bounded schema
  repairs;
- endpoint-linked execution completed 173 windows using 176 API attempts, with
  three bounded schema repairs and no transport retries.

Schema repair and resume counts are execution-reliability measurements. They
are not evidence of semantic quality improvement.

## Scope Limits

These results concern short authored STEM snippets, Oracle canonical Knowledge
Objects, one model configuration, and development data that informed the
method. They do not establish independent generalization, predicted-canonical
performance, long-document robustness, learner usefulness, or run-to-run
stability.

All 41 primary positives are `overlap_bridge` cases. The five
`disjoint_provenance` compositional positives are diagnostic-only. Because this
method requires one same-lecture window to cover both endpoints, it cannot
directly verify a truly disjoint-provenance pair with no shared lecture
Evidence.
