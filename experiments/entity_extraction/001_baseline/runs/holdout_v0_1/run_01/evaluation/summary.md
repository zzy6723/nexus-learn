# Entity Extraction Evaluation Summary

**Experiment:** `001_baseline`
**Ground Truth:** `benchmark/ground_truth/holdout_v0_1.json`
**Predictions:** `experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01/output`
**Adjudication:** `experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01/evaluation/adjudication_resolved.json`
**Evaluation Status:** `final`

# Aggregate Metrics

| Metric | Value |
| --- | --- |
| `required_precision` | 1.000 |
| `required_recall` | 0.950 |
| `required_f1` | 0.974 |
| `type_accuracy_required` | 0.895 |
| `required_true_positives` | 19 |
| `false_positives` | 0 |
| `false_negatives` | 1 |
| `matched_optional` | 2 |
| `optional_type_errors` | 0 |
| `unsupported_objects` | 0 |
| `duplicate_objects` | 0 |
| `manual_matches` | 1 |
| `unresolved_adjudications` | 0 |
| `exact_source_span_rate` | 0.476 |
| `exact_source_spans` | 10 |
| `invalid_source_spans` | 11 |

# Per-Lecture Metrics

| Lecture | Required Precision | Required Recall | Type Accuracy | Exact Span Rate | Unsupported | Optional Matched | Pending |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `calculus_002` | 1.000 | 1.000 | 0.750 | 0.000 | 0 | 1 | 0 |
| `linear_algebra_002` | 1.000 | 1.000 | 1.000 | 0.714 | 0 | 1 | 0 |
| `probability_001` | 1.000 | 0.900 | 0.889 | 0.556 | 0 | 0 | 0 |

# Notes

The evaluator reports metrics only. It does not declare a winning prompt.
Exact and alias matches are automatic. Other semantic matches require manual adjudication.
