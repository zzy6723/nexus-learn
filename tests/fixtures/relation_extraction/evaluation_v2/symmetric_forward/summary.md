# Relation Extraction Evaluation

**Status:** final
**Ground truth:** `tests/fixtures/relation_extraction/symmetric_ground_truth.json`
**Predictions:** `tests/fixtures/relation_extraction/symmetric_forward_predictions.json`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | 1.000 |
| Relation type accuracy ignoring direction | 1.000 |
| Endpoint direction accuracy | n/a |
| Direction accuracy when type correct | n/a |
| Positive Relation accuracy | 1.000 |
| NO_RELATION accuracy | n/a |

Primary-scored pairs: 1 of 1.

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

- `REQUIRES`: not_covered
- `APPLIED_IN`: not_covered
- `EXTENDS`: not_covered
- `CONTRASTS_WITH`: synthetic_symmetric_test_coverage
- `FORMALIZES`: not_covered
- `RELATED_TO`: not_covered
- `NO_RELATION`: not_covered

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
