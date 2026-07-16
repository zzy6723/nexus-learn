# Relation Extraction Evaluation

**Status:** final
**Ground truth:** `experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_2/run_01/projection/matched_relation_ground_truth.json`
**Predictions:** `experiments/relation_extraction/002b_predicted_ko/runs/locked_reuse_v0_2/run_01/A_prime/output/matched_relation_ground_truth.json`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | 0.758 |
| Relation type accuracy ignoring direction | 0.818 |
| Endpoint direction accuracy | 0.792 |
| Direction accuracy when type correct | 0.900 |
| Positive Relation accuracy | 0.760 |
| NO_RELATION accuracy | 0.750 |

Primary-scored pairs: 33 of 33.

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

- `APPLIED_IN`: covered_with_seven_primary_positives_including_one_cross_lecture_pair
- `CONTRASTS_WITH`: covered_with_one_symmetric_primary_positive
- `EXTENDS`: covered_with_three_primary_positives
- `FORMALIZES`: covered_with_ten_primary_positives
- `NO_RELATION`: covered_with_eleven_within_and_cross_lecture_hard_negatives
- `RELATED_TO`: no_primary_positive_support_overuse_only
- `REQUIRES`: covered_with_eight_primary_positives

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
