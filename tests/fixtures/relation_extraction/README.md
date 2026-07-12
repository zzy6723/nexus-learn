# Relation Evaluator Synthetic Fixtures

These fixtures test evaluator behavior independently of model quality.

They use `synthetic_ground_truth.json`, which contains six pairs:

- two primary positive directional Relations;
- two primary `NO_RELATION` pairs;
- one ambiguous pair with a predeclared alternative;
- one schema-gap pair excluded from primary scoring.

## Validation Status

**Protocol:** Relation Evaluation Protocol v0.1  
**Validated:** 2026-07-12  
**Report directory:** `tests/fixtures/relation_extraction/evaluation_v2/`  
**Status:** Synthetic evaluator validation passed

The latest evaluator behavior was confirmed across ten scenarios:

| Scenario | Status | Strict | Endpoint Direction | Direction When Type Correct | Key Result |
| --- | --- | ---: | ---: | ---: | --- |
| Perfect | `final` | 1.00 | 1.00 | 1.00 | All primary and grounding checks passed. |
| Wrong direction | `final` | 0.75 | 0.50 | 0.50 | One direction error; type accuracy remained 1.00. |
| Overconnection | `final` | 0.50 | 1.00 | 1.00 | `NO_RELATION` accuracy fell to 0.00. |
| All `RELATED_TO` | `final` | 0.00 | 1.00 | `null` | Type-conditioned direction denominator was zero. |
| Quality errors | `draft_pending_adjudication` | 1.00 | 1.00 | 1.00 | Four of six evidence spans were exact; two pairs require adjudication. |
| Invalid alignment | `invalid` | n/a | n/a | n/a | Fatal alignment errors suppressed aggregate metrics. |
| Empty evidence span | `invalid` | n/a | n/a | n/a | Empty span was rejected as a schema error. |
| Stale adjudication | `invalid` | n/a | n/a | n/a | Changed evidence snapshot was rejected. |
| Symmetric forward | `final` | 1.00 | `null` | `null` | Symmetric edge accepted without direction scoring. |
| Symmetric reverse | `final` | 1.00 | `null` | `null` | Reversed symmetric edge was also accepted. |

Expected behavior:

| Fixture | Expected Primary Metrics And Errors |
| --- | --- |
| `perfect_predictions.json` | Strict, type, direction, positive, and `NO_RELATION` accuracy are all `1.0`; ambiguous accuracy is `1.0`; schema-gap is excluded. |
| `wrong_direction_predictions.json` | Strict accuracy is `0.75`, type accuracy is `1.0`, direction accuracy is `0.5`, and exactly one `wrong_direction` error is produced. The ambiguous alternative is accepted. |
| `overconnection_predictions.json` | Strict and type accuracy are `0.5`, positive accuracy remains `1.0`, `NO_RELATION` accuracy becomes `0.0`, and two false positives plus two `overused_related_to` errors are produced. |
| `all_related_to_predictions.json` | Strict, type, positive, and `NO_RELATION` accuracy are `0.0`; primary `RELATED_TO` prediction rate is `1.0`; overuse count is `4`. |
| `quality_errors_predictions.json` | Evaluation remains nonfatal and produces complete metrics while recording missing evidence, invalid evidence, missing rationale, and unexpected evidence for `NO_RELATION`. |
| `invalid_alignment_predictions.json` | Evaluation status is `invalid`; duplicate, unknown, missing, and candidate-mismatch errors prevent valid aggregate metrics. |
| `empty_evidence_span_predictions.json` | An empty evidence span is a fatal schema error and must never count as an exact substring. |

`quality_errors_predictions.json` also includes an exact span copied from a lecture outside the candidate pair. It should produce `evidence_lecture_outside_candidate`, remain nonfatal, and exclude that span from the exact-span numerator.

## Adjudication Freshness

Use `stale_adjudication.json` with `quality_errors_predictions.json`. The adjudication snapshot intentionally contains evidence different from the current prediction. Evaluation should become `invalid` with `stale_or_unused_adjudication`, and runtime-error artifacts should replace any older valid report in the target directory.

Resolved adjudications must include the complete predicted edge and predicted evidence spans. A decision keyed only by `pair_id` is not valid.

## Symmetric Relation

The symmetric fixture uses:

- `symmetric_ground_truth.json`;
- `symmetric_knowledge_objects.json`;
- `symmetric_forward_predictions.json`;
- `symmetric_reverse_predictions.json`;
- `benchmark/lectures/synthetic/synthetic_relation_001.md`.

Both forward and reverse `CONTRASTS_WITH` predictions should be strict-edge correct. Neither should be eligible for endpoint or type-conditioned direction scoring, and neither should produce `wrong_direction`.

## Direction Metrics

`endpoint_direction_accuracy` preserves the original type-independent endpoint-order diagnostic. `direction_accuracy_when_type_correct` is the preferred standalone direction metric. The legacy `direction_accuracy` field remains an alias of `endpoint_direction_accuracy` for compatibility.

The automated regression harness is `tests/test_relation_evaluator.py` and uses only the Python standard library. It reproduces these scenarios in temporary directories so committed fixture reports are not overwritten.
