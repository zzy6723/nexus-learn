# Experiment 002B-1 Development Results

**Status:** Final  
**Run:** `development_v0_1/run_03`  
**Evaluation type:** Single-run controlled paired diagnostic  
**Dataset:** Relation development set  
**Primary pair universe:** 38  
**Completed:** 2026-07-16

---

## Research Question

When Relation Classification is run on the same recoverable candidate pairs,
lectures, neutral KO slots, prompt, model, parameters, and batch plan, does
replacing Oracle KO representations with real predicted KO representations
reduce Relation Extraction performance?

The experiment also measures the end-to-end loss introduced by unrecoverable
upstream Knowledge Objects.

The two result levels are distinct:

- A-prime versus B-prime compares KO representations on the matched,
  recoverable subset.
- B-prime strict-correct pairs divided by all 38 primary pairs measures
  end-to-end pipeline success.

## Claim Boundary

This result is a single-run controlled paired diagnostic on the development
set.

It does not establish:

- run-to-run stability;
- an average causal effect of individual KO fields;
- holdout generalisation;
- complete-graph extraction quality;
- production-level performance.

## Experimental Conditions

| Condition | Pair universe | KO representation | Purpose |
| --- | ---: | --- | --- |
| A0 | Historical full development set | Oracle KO | Historical reference |
| A-prime | 36 recoverable primary pairs | Oracle KO in neutral slots | Matched control |
| B-prime | Same 36 primary pairs | Predicted KO in the same slots | Predicted representation |

A-prime and B-prime used the same:

- pair IDs, order, and pair-to-slot incidence;
- neutral KO slots;
- lecture text;
- Relation prompt and schema;
- model and request parameters;
- batch plan;
- method commit, `6295652ceee8c30a84808363b0c85e87322e1b36`.

Only KO `name`, `type`, and `source_spans`, plus hashes derived from that
content, were allowed to differ. Both formal runs used `deepseek-v4-flash`,
temperature `0`, top-p `1`, and maximum output tokens `8192`.

A0 covered 41 total pairs: 38 primary and 3 diagnostic. Its historical strict
result was 35/38 (92.11%). A0 is not a representation-only control because its
pair and batch composition differ from A-prime and B-prime.

## Upstream KO Summary

| Measure | Result |
| --- | ---: |
| Oracle KOs | 53 |
| Predicted KOs | 49 |
| One-to-one aligned predicted KOs | 49 |
| Exact identity alignments | 48 |
| Manual identity alignments | 1 |
| Unmatched predicted extras | 0 |
| Missing Oracle KOs | 4 |
| Pending alignment decisions | 0 |

The four missing Oracle KOs were:

- required: `Bayes' Rule Formula`;
- optional: `Local Linear Approximation`;
- optional: `Subspace`;
- optional: `Event`.

`First-order Taylor Approximation Formula` was manually aligned one-to-one with
the predicted `First-Order Taylor Approximation` Formula. The labels and source
spans denoted the same educational object.

Four type mismatches occurred in the complete aligned inventory. Within the
primary-pair endpoint universe, 43 of 45 unique endpoints were recovered, and
40 of the 43 recovered endpoints matched the Oracle type. Four missing KOs do
not imply four unrecoverable primary pairs because not every missing KO appears
in a primary pair.

## Pair Recoverability

| Measure | Result |
| --- | ---: |
| Original primary pairs | 38 |
| Recoverable primary pairs | 36 |
| Unrecoverable primary pairs | 2 |
| Overall recoverability | 36/38 = 94.74% |
| Positive-pair recoverability | 27/28 = 96.43% |
| Hard-negative recoverability | 9/10 = 90.00% |
| Cross-lecture recoverability | 4/4 = 100% |

The two unrecoverable pairs were:

| Pair | Category | Missing endpoint |
| --- | --- | --- |
| `rel_dev_029` | Positive | `Bayes' Rule Formula` |
| `rel_dev_037` | Hard negative | `Local Linear Approximation` |

The primary accounting identity is:

```text
36 recoverable + 2 unrecoverable = 38 primary pairs
```

## Conditional Matched Comparison

| Metric | A-prime | B-prime |
| --- | ---: | ---: |
| Strict edge accuracy | 30/36 = 83.33% | 30/36 = 83.33% |
| Relation type accuracy | 32/36 = 88.89% | 31/36 = 86.11% |
| Endpoint direction accuracy | 22/27 = 81.48% | 24/27 = 88.89% |
| Direction accuracy when type correct | 21/23 = 91.30% | 21/22 = 95.45% |
| Positive Relation accuracy | 21/27 = 77.78% | 21/27 = 77.78% |
| `NO_RELATION` accuracy | 9/9 = 100% | 9/9 = 100% |
| Exact Evidence-span rate | 27/27 = 100% | 12/28 = 42.86% |
| Semantic Evidence-support rate | 20/21 = 95.24% | 21/21 = 100% |

### Denominator Definitions

- `36` is the frozen recoverable primary-pair set.
- `27` and `9` are its gold-positive and hard-negative subsets.
- Endpoint direction is scored on direction-eligible positive edges.
- Direction when type correct further restricts the denominator to predictions
  with the correct Relation type.
- The exact-Evidence denominator counts submitted Evidence spans, not positive
  predictions. Both conditions predicted a graph Relation on 27 pairs.
  A-prime submitted 27 spans; B-prime submitted 28 because one prediction used
  two spans.
- Semantic Evidence support is scored on acceptable positive graph-edge
  predictions for which the evaluator assigned a support status. The 21 cases
  in each condition include both automatic gold-Evidence matches and manually
  adjudicated cases. A-prime required 10 manual decisions; B-prime required 13.

A-prime and B-prime achieved identical strict edge accuracy: 30/36. B-prime
had one fewer correct Relation type classification and two more correct
endpoint directions. These changes offset at the strict-edge level.

This single matched run therefore provides no evidence of a net strict-accuracy
degradation after replacing Oracle KO representations with predicted KO
representations. It does not establish that the two representations are
equivalent.

Neither condition produced a false-positive Relation, a false-negative
Relation, or a `RELATED_TO` prediction on the matched set.

## Evidence Grounding

Exact Evidence-span compliance changed from:

- A-prime: 27/27 = 100%;
- B-prime: 12/28 = 42.86%.

Semantic support on acceptable positive graph edges was:

- A-prime: 20/21 = 95.24%;
- B-prime: 21/21 = 100%.

The B-prime run contained 16 non-exact Evidence spans. The exact-span decline is
consistent with non-exact source spans present in predicted KO representations.
This is a descriptive association, not a causal attribution.

The semantic-support result does not imply that B-prime had better overall
grounding. It excludes incorrect edges, combines automatic and manual support
decisions, and uses a different denominator from span exactness. In particular,
the one unsupported A-prime Evidence case was `rel_dev_012`; B-prime predicted
the wrong Relation type for that pair, so its Evidence did not enter the
semantic-support denominator.

## End-to-End Pipeline Result

| Metric | Result |
| --- | ---: |
| B-prime conditional strict accuracy | 30/36 = 83.33% |
| Pair recoverability | 36/38 = 94.74% |
| Pipeline strict success | 30/38 = 78.95% |
| Positive pipeline success | 21/28 = 75.00% |
| Hard-negative pipeline success | 9/10 = 90.00% |

The integer decomposition is:

```text
Pipeline strict success
= pair recoverability x B-prime conditional strict accuracy
= (36/38) x (30/36)
= 30/38
= 78.95%
```

All nine recoverable hard negatives were correctly classified as
`NO_RELATION`. Pipeline hard-negative success is 9/10 because `rel_dev_037`
was unrecoverable upstream. Similarly, conditional positive success is 21/27,
while pipeline positive success is 21/28 because `rel_dev_029` was
unrecoverable upstream.

## Pair Transitions

| A-prime to B-prime transition | Count |
| --- | ---: |
| Correct to correct | 29 |
| Wrong to correct | 1 |
| Correct to wrong | 1 |
| Wrong to same error class | 5 |
| Upstream unrecoverable | 2 |
| **Total** | **38** |

Key transitions were:

- `rel_dev_005`: A-prime wrong direction to B-prime correct;
- `rel_dev_012`: A-prime correct to B-prime wrong Relation type;
- `rel_dev_029`: upstream unrecoverable;
- `rel_dev_037`: upstream unrecoverable.

For `rel_dev_028`, "same error class" means that both conditions were
classified as `wrong_relation_type`. A-prime predicted `EXTENDS`, while B-prime
predicted `FORMALIZES`; the predicted labels were not the same.

Every original primary pair has exactly one transition record: 36 contain both
matched outcomes and 2 record upstream unrecoverability.

## Descriptive Failure Decomposition

Primary failure loci are mutually exclusive:

| Primary locus | Pair count |
| --- | ---: |
| No strict pipeline failure | 30 |
| Strict error already present in A-prime | 5 |
| New B-prime Relation-type error | 1 |
| Upstream unrecoverable | 2 |

Secondary quality flags may overlap:

| Secondary flag | Exposed pair count |
| --- | ---: |
| Non-exact predicted KO source span | 11 |
| Non-exact B-prime Relation grounding | 16 |
| KO type mismatch | 6 |
| KO name change | 1 |
| Manual identity alignment | 1 |

Secondary flags record exposure or co-occurrence. They do not prove that a KO
property caused a downstream Relation outcome.

## Limitations

1. This is a development-set result, not a new holdout result.
2. A-prime and B-prime were each run once; run-to-run stability is unknown.
3. The primary universe contains only 38 pairs.
4. Semantic Evidence support is scored only for acceptable positive graph
   edges, not all pairs or all submitted spans.
5. A0 has different pair and batch composition and is historical context, not
   the matched representation control.
6. Field-level changes and secondary flags cannot be interpreted causally.
7. Two unrecoverable pairs directly reduce the end-to-end denominator while
   remaining outside the conditional A-prime/B-prime denominator.
8. Candidate pairs remain human-authored, so this experiment does not evaluate
   candidate discovery or complete-graph precision and recall.

## Final Artifacts

All completion-marker dependency hashes were validated. Fatal errors: `0`.
Pending items: `0`.

| Artifact | SHA-256 |
| --- | --- |
| `runs/development_v0_1/run_03/entity_predictions/entity_predictions_complete.json` | `477e5c8fed5af204c6a81252df3835ea04694f5b8f0669c599b0f8ac46b2a1ed` |
| `runs/development_v0_1/run_03/alignment/final/alignment_bundle_complete.json` | `b2cceef24daad185347582fa0e93e9bae972f4c218fe5fe8b8f036008e08e898` |
| `runs/development_v0_1/run_03/projection/projection_bundle_complete.json` | `cbb93eeed950c6e42d5b33a6b18a24f9cec8b73efab0571415c71d0bf84cb62c` |
| `runs/development_v0_1/run_03/relation_evaluation/A0/evaluation_snapshot.json` | `1f2e3236f490f8e878eeb85a3dee3a8de53ca0394fe8571f3c272adbaa86efc9` |
| `runs/development_v0_1/run_03/relation_evaluation/A_prime/evaluation_snapshot.json` | `7c3cf042b10c87b87d01ac9e915604df6100b497aceca279ca52623ac2c9ac11` |
| `runs/development_v0_1/run_03/relation_evaluation/B_prime/evaluation_snapshot.json` | `e9c6cf36bae5f99bdec8b8dd855130e78417ced6fbaca6e59e8d643182190ce4` |
| `runs/development_v0_1/run_03/pipeline_evaluation/pipeline_evaluation_complete.json` | `4fa3f189bbee5a4f55412ea82aa72b1758856f465deb9d0564a6a0f2092bfc9e` |

The authoritative aggregate values are stored in
`runs/development_v0_1/run_03/pipeline_evaluation/pipeline_metrics.json`.
