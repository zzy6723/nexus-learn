# Relation Extraction Evaluation

**Status:** final
**Ground truth:** `benchmark/ground_truth/relations_development_v0_1.json`
**Predictions:** `experiments/relation_extraction/002_prompt_refinement/runs/development_v0_1/run_01/output/relations_development_v0_1.json`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | 0.921 |
| Relation type accuracy ignoring direction | 0.974 |
| Endpoint direction accuracy | 0.893 |
| Direction accuracy when type correct | 0.926 |
| Positive Relation accuracy | 0.893 |
| NO_RELATION accuracy | 1.000 |

Primary-scored pairs: 38 of 41.

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

- `REQUIRES`: covered
- `APPLIED_IN`: covered
- `FORMALIZES`: covered
- `EXTENDS`: exploratory_single_positive
- `CONTRASTS_WITH`: not_covered
- `RELATED_TO`: no_primary_positive_support_overuse_only
- `NO_RELATION`: covered_with_cross_and_within_lecture_negatives

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
