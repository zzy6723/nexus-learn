# Relation Extraction Evaluation

**Status:** final
**Ground truth:** `experiments/relation_extraction/002b_candidate_discovery/runs/downstream_diagnostic_v0_1/preparation/all_pairs/selected_relation_ground_truth.json`
**Predictions:** `experiments/relation_extraction/002b_candidate_discovery/runs/downstream_diagnostic_v0_1/formal/all_pairs/run_01/output/selected_relation_ground_truth.json`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | 0.363 |
| Relation type accuracy ignoring direction | 0.386 |
| Endpoint direction accuracy | 0.846 |
| Direction accuracy when type correct | 0.907 |
| Positive Relation accuracy | 0.500 |
| NO_RELATION accuracy | 0.242 |

Primary-scored pairs: 171 of 176.

## Grounding And Audit

| Metric | Value |
| --- | ---: |
| Exact evidence-span rate | 0.775 |
| Evidence outside candidate lectures | 0 |
| Missing evidence | 0 |
| Missing rationale | 0 |
| Pending adjudication | 0 |
| RELATED_TO overuse | 1 |

## Coverage Boundary

- `REQUIRES`: covered_with_39_primary_instances
- `APPLIED_IN`: covered_with_23_primary_instances
- `EXTENDS`: covered_with_5_primary_instances
- `CONTRASTS_WITH`: covered_with_1_primary_instances
- `FORMALIZES`: covered_with_10_primary_instances
- `RELATED_TO`: covered_with_2_primary_instances
- `NO_RELATION`: covered_with_91_primary_instances

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
