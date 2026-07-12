# Relation Extraction Evaluation

**Status:** final
**Ground truth:** `tests/fixtures/relation_extraction/synthetic_ground_truth.json`
**Predictions:** `tests/fixtures/relation_extraction/perfect_predictions.json`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | 1.000 |
| Relation type accuracy ignoring direction | 1.000 |
| Endpoint direction accuracy | 1.000 |
| Direction accuracy when type correct | 1.000 |
| Positive Relation accuracy | 1.000 |
| NO_RELATION accuracy | 1.000 |

Primary-scored pairs: 4 of 6.

## Grounding And Audit

| Metric | Value |
| --- | ---: |
| Exact evidence-span rate | 1.000 |
| Evidence outside candidate lectures | 0 |
| Missing evidence | 0 |
| Missing rationale | 0 |
| Pending adjudication | 0 |
| RELATED_TO overuse | 0 |

## Coverage Boundary

- `REQUIRES`: synthetic_test_coverage
- `APPLIED_IN`: ambiguous_only
- `EXTENDS`: not_covered
- `CONTRASTS_WITH`: not_covered
- `FORMALIZES`: synthetic_test_coverage
- `RELATED_TO`: schema_gap_only
- `NO_RELATION`: synthetic_test_coverage

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
