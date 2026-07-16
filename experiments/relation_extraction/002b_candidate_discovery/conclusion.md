# Experiment 002B-2 Conclusion

**Decision:** Completed with partial feasibility.
**Candidate gate:** Rule-Filtered v0.1 failed.
**Selected fallback:** All-Pairs v0.1.
**Production readiness:** Not established.

## Candidate Discovery Result

The exhaustive development benchmark contains 39 predicted lecture-local KOs
and all 176 unordered within-lecture pairs. Its 171 primary pairs comprise 80
positive Relations and 91 hard negatives; five schema-gap pairs are diagnostic.

All-Pairs retained all 80 positives but performed no workload reduction.
Rule-Filtered v0.1 selected 127/176 pairs and reduced pair workload by 27.84%,
but recalled only 70/80 positive pairs. It failed the frozen requirements for
perfect aggregate recall, zero missed positives, and perfect per-lecture
recall.

## Downstream Consequence

The frozen Relation classifier was then run independently on both candidate
manifests. Over the full 171-pair primary universe:

- All-Pairs achieved 62/171 strict pipeline success and 40/80 positive
  typed-edge recall;
- Rule-Filtered achieved 84/171 strict pipeline success and 36/80 positive
  typed-edge recall;
- Rule-Filtered removed 39 hard negatives before classification, which raised
  overall strict accuracy and reduced false-positive exposure;
- its 10 candidate misses included four pairs that All-Pairs classified
  correctly, producing a real observed loss of four correct typed edges.

The higher Rule-Filtered full-universe strict score does not make it the
selected method. The Candidate gate is recall-first, and filtered-out positives
cannot be recovered by downstream improvements.

## What 002B-2 Established

- A complete predicted-KO pair universe can be constructed, annotated, and
  evaluated with explicit denominators.
- Candidate and classifier failures can be separated over one full universe.
- Deterministic local rules can reduce workload and false-positive exposure.
- The current v0.1 rules do not retain enough true Relations.
- The frozen Relation classifier itself remains a major bottleneck on the
  exhaustive workload.
- Exact Evidence reproduction remains unreliable when mathematical formatting
  is rewritten.

## Selected Technical-Validation Path

The current recall-preserving path is:

```text
lecture material
-> predicted lecture-local KOs
-> All-Pairs v0.1 candidate generation
-> frozen Relation classifier v0.1
```

This path is suitable only as a small-scale Technical Validation fallback.
All-Pairs grows as `n(n-1)/2`, and its false-positive Relation count is too high
for a production graph.

## Full Experiment 002B Closure

Experiment 002B is complete with partial feasibility:

- 002B-1 showed that predicted-KO representations can be passed to Relation
  Classification on recoverable pairs without an observed net strict-accuracy
  loss in the controlled diagnostics;
- missing KOs caused irrecoverable pairs and remain an upstream bottleneck;
- 002B-2 showed that Rule-Filtered v0.1 reduced workload but failed the frozen
  candidate-recall gate;
- All-Pairs v0.1 remains the lecture-local safety fallback;
- neither experiment establishes production readiness or broad generalization.

No further candidate-rule tuning should use this inspected 176-pair snapshot.
The next experiment is 002C, Knowledge Object Resolution / Canonicalization,
before cross-lecture Connection Discovery.

## Records

- Candidate-only comparison: `rule_filtered_v0_1_results.md`
- Downstream comparison: `downstream_relation_diagnostic.md`
- Pipeline metrics:
  `runs/downstream_diagnostic_v0_1/pipeline_evaluation/run_01/pipeline_metrics.json`
- Final pipeline marker:
  `runs/downstream_diagnostic_v0_1/pipeline_evaluation/run_01/pipeline_evaluation_complete.json`
