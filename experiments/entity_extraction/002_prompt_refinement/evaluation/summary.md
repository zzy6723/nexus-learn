# Entity Extraction Evaluation Summary

**Experiment:** `002_prompt_refinement`
**Ground Truth:** `benchmark/ground_truth/development_v0_1.json`
**Predictions:** `experiments/entity_extraction/002_prompt_refinement/output`
**Adjudication:** `experiments/entity_extraction/002_prompt_refinement/evaluation/adjudication_resolved.json`
**Evaluation Status:** `final`

# Aggregate Metrics

| Metric | Value |
| --- | --- |
| `required_precision` | 1.000 |
| `required_recall` | 1.000 |
| `required_f1` | 1.000 |
| `type_accuracy_required` | 1.000 |
| `required_true_positives` | 26 |
| `false_positives` | 0 |
| `false_negatives` | 0 |
| `matched_optional` | 2 |
| `optional_type_errors` | 1 |
| `unsupported_objects` | 0 |
| `duplicate_objects` | 0 |
| `manual_matches` | 1 |
| `unresolved_adjudications` | 0 |
| `exact_source_span_rate` | 0.786 |
| `exact_source_spans` | 22 |
| `invalid_source_spans` | 6 |

# Per-Lecture Metrics

| Lecture | Required Precision | Required Recall | Type Accuracy | Exact Span Rate | Unsupported | Optional Matched | Pending |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `calculus_001` | 1.000 | 1.000 | 1.000 | 0.429 | 0 | 0 | 0 |
| `linear_algebra_001` | 1.000 | 1.000 | 1.000 | 0.800 | 0 | 1 | 0 |
| `optimisation_001` | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1 | 0 |

# Notes

The evaluator reports metrics only. It does not declare a winning prompt.
Exact and alias matches are automatic. Other semantic matches require manual adjudication.
