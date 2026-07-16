# 002B-2 Downstream Typed-Edge Diagnostic

**Status:** Final
**Split role:** Inspected development diagnostic
**Method freeze:** `78e47b8dc792dd970e72c0040f045c8d1cc1035c`
**Selected safety fallback:** `all_pairs_v0_1`

## Question

How do the completed All-Pairs and Rule-Filtered candidate methods affect
typed-edge quality, Evidence grounding, and Relation-classification workload
when both use the same frozen Relation method?

This diagnostic does not reopen the Candidate Generation decision. The frozen
Rule-Filtered recall gate had already failed because 10 of 80 positive pairs
were omitted.

## Experimental Integrity

Both conditions used:

- the same 39 predicted KOs and four authored lecture snippets;
- the same frozen Relation prompt, schema, model, and request parameters;
- one candidate pair per API request;
- identical model-facing payloads for all 127 shared candidate pairs;
- independent API requests and independent prediction artifacts;
- the same Relation evaluator and Evidence-support protocol;
- separate snapshot-bound adjudication files and final evaluation snapshots.

The All-Pairs run completed 176/176 requests. The Rule-Filtered run completed
127/127 requests. Every request returned `finish_reason = stop`, passed JSON and
prediction-schema validation, preserved its candidate endpoints, and required
no retry. Both runs began from the frozen method commit with
`git_dirty_at_start = false`.

The full evaluation universe contains:

| Category | Count | Primary-scored |
| --- | ---: | --- |
| Positive Relation | 80 | Yes |
| Hard negative | 91 | Yes |
| Schema gap | 5 | No |
| **Total** | **176** | **171 primary** |

## Results

| Metric | All-Pairs v0.1 | Rule-Filtered v0.1 |
| --- | ---: | ---: |
| Candidates selected | 176 | 127 |
| Candidate positive recall | 80/80 = 1.0000 | 70/80 = 0.8750 |
| Candidate primary precision | 80/171 = 0.4678 | 70/122 = 0.5738 |
| Pair workload reduction | 0/176 = 0.0000 | 49/176 = 0.2784 |
| Conditional Relation strict accuracy | 62/171 = 0.3626 | 45/122 = 0.3689 |
| Conditional positive Relation accuracy | 40/80 = 0.5000 | 36/70 = 0.5143 |
| Conditional `NO_RELATION` accuracy | 22/91 = 0.2418 | 9/52 = 0.1731 |
| Full-universe pipeline strict accuracy | 62/171 = 0.3626 | 84/171 = 0.4912 |
| Positive typed-edge precision | 40/148 = 0.2703 | 36/112 = 0.3214 |
| Positive typed-edge recall | 40/80 = 0.5000 | 36/80 = 0.4500 |
| Positive typed-edge F1 | 0.3509 | 0.3750 |
| Candidate-induced false negatives | 0 | 10 |
| Classifier `NO_RELATION` false negatives | 1 | 1 |
| Wrong Relation type | 35 | 30 |
| Wrong direction when type correct | 4 | 3 |
| False-positive Relations | 69 | 43 |
| Exact Evidence-span rate | 162/209 = 0.7751 | 126/160 = 0.7875 |
| Semantic support on accepted primary graph edges | 31/40 = 0.7750 | 31/36 = 0.8611 |
| API requests | 176 | 127 |
| Total tokens | 444,705 | 321,692 |
| Aggregate latency | 544,699 ms | 407,175 ms |

The Rule-Filtered full-universe strict score includes 39 hard negatives that
were correctly rejected before Relation Classification. It must not be read as
the classifier achieving 84/171 on selected pairs. Its conditional classifier
score is 45/122.

## Candidate-Miss Recoverability

Rule-Filtered omitted 10 positive pairs. Under the frozen All-Pairs classifier:

- four omitted pairs were strictly correct;
- six omitted pairs were already classified incorrectly.

The observed positive typed-edge recall therefore fell from 40/80 to 36/80,
rather than by all 10 candidate misses. This does not make the other six misses
safe: a candidate that is filtered out remains unavailable to a future, better
Relation classifier.

The 176 pair transitions reconcile as follows:

| Transition | Count |
| --- | ---: |
| Diagnostic, excluded from primary | 5 |
| Filtered missed positive, All-Pairs correct | 4 |
| Filtered missed positive, All-Pairs incorrect | 6 |
| Filtered rejected hard negative | 39 |
| Shared correct to correct | 44 |
| Shared correct to incorrect | 1 |
| Shared incorrect to correct | 1 |
| Shared incorrect to incorrect | 76 |

The two opposite shared strict transitions cancel in aggregate. There were
three shared-pair prediction disagreements, which is a reminder that separate
temperature-zero API calls are not guaranteed to be identical.

## Evidence Adjudication

The two conditions were adjudicated independently against their own frozen
prediction snapshots:

- All-Pairs: 32 manual decisions, 23 `supported`, 9 `not_supported`;
- Rule-Filtered: 27 manual decisions, 22 `supported`, 5 `not_supported`;
- pending decisions after final evaluation: 0 in both conditions.

Those manual totals include one schema-gap pair in each condition. The semantic
support rates in the results table use accepted primary graph edges and combine
automatic gold-Evidence matches with resolved manual decisions.

Exactness remains a separate quality problem. The model frequently preserved
the mathematical content while removing Markdown or LaTeX delimiters, so 47
of 209 submitted All-Pairs spans and 34 of 160 Rule-Filtered spans were not
exact lecture substrings.

## Decision

Rule-Filtered v0.1 remains a valid failed development baseline. Its 27.84%
workload reduction and improved full-universe negative rejection do not reverse
the frozen Candidate recall failure or recover the four typed edges that the
All-Pairs classifier correctly found among the omitted candidates.

`all_pairs_v0_1` remains the selected lecture-local safety fallback for the
current Technical Validation stage. This is a recall-preservation decision, not
a production recommendation. All-Pairs exposed substantial false-positive
Relation risk and retains quadratic pair growth.

No Rule-Filtered v0.2 is created on this inspected 176-pair development set.

## Interpretation Boundary

This result is limited to four short authored lectures and one formal run per
condition. It does not establish:

- unseen-data generalization or run-to-run stability;
- long-document, parsed-PDF, or noisy-input performance;
- scalable candidate discovery for large KO inventories;
- cross-lecture canonical KO identity;
- production readiness;
- learner relevance or Connection quality.

The frozen pipeline artifacts are under
`runs/downstream_diagnostic_v0_1/`. The machine-readable final comparison is in
`pipeline_evaluation/run_01/pipeline_metrics.json`, with all 176 transitions in
`pair_transitions.json`.
