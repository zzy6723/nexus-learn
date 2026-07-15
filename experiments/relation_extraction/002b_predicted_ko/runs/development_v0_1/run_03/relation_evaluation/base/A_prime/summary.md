# Relation Extraction Evaluation

**Status:** final
**Ground truth:** `experiments/relation_extraction/002b_predicted_ko/runs/development_v0_1/run_03/projection/matched_relation_ground_truth.json`
**Predictions:** `experiments/relation_extraction/002b_predicted_ko/runs/development_v0_1/run_03/A_prime/output/matched_relation_ground_truth.json`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | 0.833 |
| Relation type accuracy ignoring direction | 0.889 |
| Endpoint direction accuracy | 0.815 |
| Direction accuracy when type correct | 0.913 |
| Positive Relation accuracy | 0.778 |
| NO_RELATION accuracy | 1.000 |

Primary-scored pairs: 36 of 36.

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

- `APPLIED_IN`: covered
- `CONTRASTS_WITH`: not_covered
- `EXTENDS`: exploratory_single_positive
- `FORMALIZES`: covered
- `NO_RELATION`: covered_with_cross_and_within_lecture_negatives
- `RELATED_TO`: no_primary_positive_support_overuse_only
- `REQUIRES`: covered

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
