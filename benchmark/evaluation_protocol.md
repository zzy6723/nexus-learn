# Evaluation Protocol

**Status:** Frozen  
**Version:** v0.1 (Frozen)  
**Created:** 2026-07-11  
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Purpose

This protocol defines how Knowledge Object extraction outputs are evaluated.

It should be frozen before the first holdout run.

---

# Evaluation Unit

The evaluation unit is each predicted Knowledge Object.

Each prediction is compared against the ground truth for the same lecture.

---

# Benchmark Splits

## Development

The development split may be used for:

- prompt debugging;
- error analysis;
- ground-truth refinement;
- evaluation script development.

Results on the development split must not be interpreted as evidence of generalization.

## Holdout

The holdout split is used for unseen evaluation.

Before running models on holdout data, the following must be frozen:

- Knowledge Object schema;
- annotation guidelines;
- ground truth;
- object matching rules;
- required / optional / excluded scoring;
- success criteria;
- error taxonomy;
- evaluation code.

---

# Label Normalization

Before canonical-label and alias matching, labels are normalized using the following rules:

- Apply Unicode NFKC normalization.
- Convert Unicode apostrophes to the ASCII apostrophe.
- Convert Unicode dash variants to the ASCII hyphen.
- Remove leading and trailing whitespace.
- Collapse consecutive internal whitespace.
- Apply case-insensitive matching.

Normalization must not perform:

- stemming or lemmatization;
- automatic singularization;
- punctuation deletion;
- mathematical-symbol expansion;
- semantic similarity matching.

For example, `Bayes’ Rule`, `Bayes' Rule`, and `BAYES' RULE` may match automatically.

`Gradient Descent` and `First-order Iterative Method` must not match automatically only because they are semantically related.

---

# Matching Rules

Predictions are matched to ground truth in three levels.

## Level 1: Exact Canonical Match

The normalized predicted label exactly matches the ground-truth canonical label.

## Level 2: Alias Match

The normalized predicted label matches one of the predefined ground-truth aliases.

## Level 3: Manual Adjudication

Ambiguous cases are reviewed manually.

Predictions that do not match by exact canonical label or predefined alias are written to:

```text
adjudication_pending.json
```

The automatic evaluator may produce draft metrics while unresolved items exist, but those metrics must not be used as final holdout comparison results.

After manual review, decisions should be written to:

```text
adjudication_resolved.json
```

The evaluator should then be rerun with the resolved adjudication file.

Manual adjudication should record:

- predicted label;
- predicted type;
- candidate ground-truth object;
- match decision;
- match type;
- rationale.

Do not use embedding similarity as an automatic final judge for correctness.

Supported manual decisions are:

- `matched`;
- `not_matched`;
- `unsupported`;
- `granularity_error`.

`ambiguous_match` is a pending review state, not a resolved manual decision.

Manual adjudication decisions are keyed by `lecture_id` and `prediction_index`. Because prediction order can change between runs, the evaluator must validate that the adjudication `predicted_label` matches the prediction label after normalization. Stale or unused adjudication decisions must terminate evaluation.

`granularity_error` decisions must include a `ground_truth_id`.

---

# Scoring Categories

Ground-truth objects may be:

- `required`;
- `optional`;
- `excluded`.

Required objects count toward recall.

Optional objects do not count against precision if extracted correctly.

Excluded objects count as errors if extracted.

Unsupported predicted objects that are neither matched to required nor optional objects count against precision.

---

# Scoring Rules

Matching is one-to-one.

A ground-truth object may be matched to at most one prediction. Additional predictions referring to the same object are recorded as `duplicate_object`.

An identity match is determined independently from type correctness.

A prediction that correctly identifies a required object but assigns the wrong type:

- counts as a matched required object for object precision and recall;
- counts as an error for type accuracy;
- is recorded as `wrong_type`.

A prediction matched to an optional object with the wrong type:

- remains excluded from required-object precision and recall;
- is recorded as an optional type error;
- is not included in required-object type accuracy.

Correctly matched optional objects are excluded from both the numerator and denominator of required-object precision.

The main metrics are calculated as follows:

- Required True Positives: predictions matched to required objects.
- False Positives: unsupported predictions, excluded objects, and duplicate predictions.
- False Negatives: unmatched required objects.

Required Precision:

`required_true_positives / (required_true_positives + false_positives)`

Required Recall:

`required_true_positives / total_required_objects`

Required F1:

The harmonic mean of required precision and required recall.

Type Accuracy:

`correctly_typed_required_matches / all_required_matches`

Unresolved manual adjudication items are treated as unsupported objects in automatic draft metrics and are also counted as `unresolved_adjudications`.

Final holdout metrics require either:

- zero unresolved adjudication items; or
- a documented decision to treat the unresolved items as unsupported.

## Granularity Errors

A prediction that is substantially broader or narrower than the ground-truth object is not automatically treated as a match.

It should enter manual adjudication.

If it is judged not equivalent:

- the prediction counts as a false positive;
- the unmatched required object counts as a false negative;
- the error is recorded as `granularity_error`.

---

# Metrics

Report at least:

- required-object precision;
- required-object recall;
- required-object F1;
- type accuracy on matched required objects;
- total prediction count;
- required match count;
- optional object count;
- unsupported object count;
- duplicate object count;
- unresolved adjudication count;
- evaluation status (`final` or `draft_pending_adjudication`);
- exact source-span validity;
- invalid source-span count.

Small holdout results should be described as technical validation, not statistical proof.

---

# Error Taxonomy

Use the following error categories:

- `missing_required_object`;
- `unsupported_object`;
- `wrong_type`;
- `duplicate_object`;
- `granularity_error`;
- `invalid_source_span`;
- `invalid_prediction_schema`;
- `missing_output_file`;
- `insufficient_source_span`;
- `excluded_object_extracted`;
- `ambiguous_match`.

Missing output files must terminate evaluation before aggregate metrics are generated.

Invalid prediction schemas must be recorded as `invalid_prediction_schema` and terminate evaluation before aggregate metrics are generated.

Prediction output must be a JSON object with:

- a non-empty string `lecture_id`;
- a `knowledge_objects` list;
- one object per predicted Knowledge Object.

Each predicted object must contain:

- non-empty string `id`;
- non-empty string `name`;
- `type` in `Concept`, `Method`, or `Formula`;
- string `source_span`;
- no duplicate `id` within the same lecture output.

---

# Comparing Baseline and Refined Prompts

The baseline and refined prompts should both be run on the same holdout split with:

- the same model;
- the same parameters;
- the same evaluation script;
- the same number of runs.

The refined prompt is considered preferable only if it improves required-object coverage or type accuracy without materially increasing unsupported objects or invalid source spans.

Improvement should not be claimed solely because the refined prompt extracts more optional objects.

The evaluator reports metric differences but does not automatically declare a winning prompt.

The final comparison conclusion must document all improvements and regressions. A prompt should not be preferred if an improvement in one metric is achieved through an unexplained degradation in unsupported-object count or source-span validity.

---

# Runner Integrity

Runner outputs must not reuse stale artifacts from previous runs.

Before running a lecture, the runner must fail if any target artifact already exists unless `--overwrite` is explicitly provided:

- rendered input payload;
- raw API response;
- parsed output JSON;
- raw parse-failure text;
- metadata JSON.

When `--overwrite` is provided, the runner must delete stale artifacts for that lecture before making the API request. This prevents old successful outputs from being reused if the new API call or JSON parse fails.

The runner must validate that the selected ground-truth file declares the same split as the `--split` argument.

Metadata should record:

- provider;
- requested and returned model;
- temperature;
- top_p;
- max_tokens;
- timestamp;
- prompt hash;
- input hash;
- rendered request hash;
- git commit at run start;
- git dirty status at run start;
- request success;
- API error, if any;
- finish reason, if available;
- JSON parse success;
- prediction schema validity, if checked;
- repair status;
- retry count.

---

# Manual Adjudication Rule

When possible, ambiguous predictions should be reviewed without showing whether they came from the baseline or refined prompt.

This lightweight prompt-blind review reduces bias during manual matching.

---

# Stability Evaluation

Stability evaluation is optional until the first holdout comparison is complete.

If performed, evaluate:

- object extraction stability;
- type stability;
- source grounding stability.

Do not summarize stability with a single number when object identity, type, and grounding behave differently.
