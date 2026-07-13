# Relation Extraction 002 Prompt Refinement Conclusion

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Run:** `runs/development_v0_1/run_01`  
**Status:** Selected for unseen holdout evaluation; development method frozen  
**Evaluation status:** `final`

---

# Result

Prompt v0.2 completed a clean-state formal development run. Request execution,
JSON parsing, and prediction-schema validation succeeded with 41 aligned results.
All 13 pending evidence cases were independently adjudicated: 12 were supported,
1 was not supported, and 0 remain pending.

| Metric | Baseline | Prompt 002 |
| --- | ---: | ---: |
| Strict edge accuracy | 0.8421 | 0.9211 |
| Relation type accuracy | 0.8947 | 0.9737 |
| Endpoint direction accuracy | 0.9286 | 0.8929 |
| Positive Relation accuracy | 0.8929 | 0.8929 |
| `NO_RELATION` accuracy | 0.7000 | 1.0000 |
| False-positive Relations | 3 | 0 |
| Positive-to-`NO_RELATION` false negatives | 0 | 0 |
| Exact evidence-span rate | 1.0000 | 1.0000 |
| Pending-case evidence support | 12/13 | 12/13 |

---

# Interpretation

Prompt 002 fixes four baseline failures and introduces one new positive-pair
regression. It eliminates all observed hard-negative false positives without
becoming over-conservative, but it does not fix the two original direction errors
or the unsupported `rel_dev_014` evidence. Raw endpoint direction accuracy falls
because `rel_dev_017` changes from a correct `APPLIED_IN` edge to an incorrectly
oriented `REQUIRES` edge.

Prompt 002 is selected as the Relation development prompt candidate for unseen
holdout evaluation. This selection is based on the multi-metric improvement and
absence of positive-to-`NO_RELATION` regression, not strict accuracy alone.

The selected prompt content is locked at SHA-256
`e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`.
It is not yet a production prompt. The development method was frozen at commit
`18e687d5cd7909531918b51e2d6bef38cb64a053`, and the completed holdout now awaits
its separate benchmark freeze commit.

The complete analysis and limitations are recorded in
`experiments/relation_extraction/development_comparison.md`. The 13 pair-level
evidence decisions are recorded in the run evaluation directory.

No Prompt 003 should be created from the remaining development errors alone. A
further refinement requires the same failure pattern to recur on unseen holdout
data.
