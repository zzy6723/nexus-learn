# 003-2b Development Results

**Status:** Final; execution completed and frozen quality gates failed
**Scope:** Two-stage Oracle-canonical Connection discovery on the frozen
development benchmark

## Experimental Control

The method used the same 125 candidates selected by `overlap_bridge_v0.1`, the
same canonical inventory, Evidence catalogs, Ground Truth, evaluator, success
criteria, model, and request parameters as 003-2. The intentional method change
was the decomposition of Connection discovery into:

1. a direct-edge gate over every selected pair; and
2. Relation typing over Stage-A positives only.

The completed v0.1.2 run started from a clean working tree at method commit
`d0c0dd3c02694646a816b2868fad3171051f877d`. It reused the strictly validated
125 Stage-A results and 37-result Stage-B prefix from the recorded v0.1.1
transport interruption, then completed the remaining Stage-B requests. The run
produced 125 unique, schema-valid predictions with `finish_reason = stop`.

The additive metadata finalizer at commit
`11b224e3e9b264f636bcb75ca498b0745a3ae2aa` added the evaluator-compatible
`completed_candidate_count = 125`. It preserved the original prediction hash
and recorded `prediction_content_changed = false`.

## Stage-A Direct-Edge Gate

| Metric | Result | Frozen diagnostic threshold | Passed |
| --- | ---: | ---: | --- |
| Direct-edge recall | 0.9024 | >= 0.80 | Yes |
| Direct-edge precision | 0.4805 | >= 0.70 | No |
| Direct-edge F1 | 0.6271 | Diagnostic | N/A |
| Primary-negative accuracy | 0.4872 | >= 0.80 | No |
| Semantic Evidence support | 0.6988 | >= 0.90 | No |
| Fatal alignment errors | 0 | = 0 | Yes |

Stage A found 37 of 41 positive pairs but also passed 40 of 78 selected primary
negatives. It therefore retained high direct-edge recall at the cost of severe
overconnection. Evidence adjudication resolved all 61 pending cases: 36 were
`supported` and 25 were `not_supported`.

## Final Typed Output

| Metric | Two-stage v0.1.2 | Frozen threshold | Passed |
| --- | ---: | ---: | --- |
| Positive typed-edge recall | 0.3171 | >= 0.75 | No |
| Positive edge precision | 0.1688 | >= 0.75 | No |
| `NO_RELATION` accuracy | 0.4872 | >= 0.90 | No |
| Conditional strict-edge accuracy | 0.4286 | Diagnostic | N/A |
| Relation type accuracy on positives | 0.5366 | Diagnostic | N/A |
| Direction accuracy when type correct | 0.5909 | Diagnostic | N/A |
| Exact Evidence materialization | 1.0000 | = 1.00 | Yes |
| Semantic Evidence support | 0.4096 | >= 0.90 | No |
| `RELATED_TO` prediction rate | 0.0840 | <= 0.05 | No |
| Full-universe precision | 0.1688 | >= 0.70 | No |
| Full-universe recall | 0.3171 | >= 0.70 | No |
| Full-universe F1 | 0.2203 | >= 0.70 | No |
| Pipeline strict accuracy | 0.8191 | Diagnostic | N/A |
| Cross-course Connection recall | 0.3214 | >= 0.65 | No |

The final output contained 13 correct positive edges, 38 correct selected
negatives, 40 edges on gold-negative pairs, 24 wrong typed or directed edges on
gold-positive pairs, and four gold-positive pairs predicted as `NO_RELATION`.
The 24 wrong positive edges comprise 15 wrong Relation types and nine wrong
directions. All 77 pending typed-Evidence cases were resolved: 28 were
`supported` and 49 were `not_supported`. Together with six exact-gold automatic
matches, this gives 34 supported Evidence cases among 83 positive predictions.

Per-relation recall remained uneven: `FORMALIZES` reached 0.75 and `APPLIED_IN`
0.3846, while `REQUIRES`, `EXTENDS`, and `CONTRASTS_WITH` each had zero strict
correct predictions on their small supports.

## Comparison With One-Stage Prompt 002

| Metric | One-stage Prompt 002 | Two-stage v0.1.2 | Change |
| --- | ---: | ---: | ---: |
| Positive typed-edge recall | 0.3171 | 0.3171 | 0.0000 |
| Positive edge precision | 0.1667 | 0.1688 | +0.0022 |
| `NO_RELATION` accuracy | 0.4872 | 0.4872 | 0.0000 |
| Conditional strict-edge accuracy | 0.4286 | 0.4286 | 0.0000 |
| Relation type accuracy | 0.5854 | 0.5366 | -0.0488 |
| Direction accuracy when type correct | 0.5417 | 0.5909 | +0.0492 |
| Exact Evidence materialization | 1.0000 | 1.0000 | 0.0000 |
| Semantic Evidence support | 0.4512 | 0.4096 | -0.0416 |
| `RELATED_TO` prediction rate | 0.0252 | 0.0840 | +0.0588 |
| Full-universe F1 | 0.2185 | 0.2203 | +0.0019 |
| Cross-course Connection recall | 0.2857 | 0.3214 | +0.0357 |

The decomposition did not materially improve Connection discovery. It retained
the same 13 correct positive edges and 40 false positives, introduced one
additional false negative and one additional wrong type, and reduced wrong
directions by two. The tiny F1 increase is not accompanied by gate progress and
does not offset worse type accuracy, semantic Evidence support, or
`RELATED_TO` control.

## Interpretation

The negative result localizes the dominant failure more clearly. Candidate
generation is not the limiting factor because all 41 primary positives reached
classification. Stage A can recover most positive pairs, but it cannot reliably
distinguish direct educational edges from thematic or mediated proximity.
Stage B cannot turn that permissive set into precise typed Connections and often
selects Evidence that does not semantically support its final edge.

The execution-reliability revisions succeeded: strict resume, bounded transport
retry, validator-guided schema repair, and additive metadata finalization all
produced an auditable final bundle without changing prediction content. Those
engineering successes do not change the failed model-quality outcome.

## Scope Limits

These results concern short, authored STEM snippets, Oracle canonical Knowledge
Objects, and one development benchmark that informed method design. They do not
establish independent generalization, production readiness, long-document
performance, parsed-PDF robustness, predicted-canonical behavior, or
run-to-run stability.
