# Relation Extraction 001 Baseline Conclusion

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Development run:** `runs/development_v0_1/run_02`  
**Holdout run:** `runs/holdout_v0_1/run_01`  
**Status:** Completed control for development and unseen holdout comparison  
**Evaluation status:** Both `final`

---

# Scope

The baseline evaluates typed Relation classification, endpoint direction,
`NO_RELATION`, and evidence grounding with human-annotated Knowledge Objects and
preselected unordered candidate pairs.

The development result was used for prompt diagnosis. The later holdout result
uses 40 unseen pairs, 36 model-facing oracle Knowledge Objects, and 4 new short
authored lectures. Neither result measures automatic Knowledge Object extraction,
candidate generation, long-document processing, or end-to-end performance.

---

# Development Result

| Metric | Result |
| --- | ---: |
| Strict edge accuracy | 0.8421 (32/38) |
| Relation type accuracy, ignoring direction | 0.8947 (34/38) |
| Endpoint direction accuracy | 0.9286 (26/28) |
| Direction accuracy when type correct | 0.9259 (25/27) |
| Positive Relation accuracy | 0.8929 (25/28) |
| `NO_RELATION` accuracy | 0.7000 (7/10) |
| Exact evidence-span rate | 1.0000 |

The development baseline produced three false-positive Relations, including two
uses of `RELATED_TO` as a fallback. Its error analysis supported the six minimal
changes tested by Prompt 002. Full pair-level diagnosis remains in
`error_analysis.md` and `../development_comparison.md`.

Development evidence adjudication resolved 13 pending cases: 12 were supported,
1 was not supported, and 0 remain pending. The unsupported `rel_dev_014` evidence
does not identify Gradient Descent inside the selected spans.

---

# Holdout Result

The formal holdout run started from frozen commit
`5fd7e2b9ea02fad6a15f2a1a703193bd7d606c7d` with a clean working tree. The
request completed with successful JSON parsing, schema validation, 40 aligned
results, and `finish_reason = stop`.

| Metric | Result |
| --- | ---: |
| Strict edge accuracy | 0.9000 (36/40) |
| Relation type accuracy, ignoring direction | 0.9000 (36/40) |
| Endpoint direction accuracy | 0.8571 (24/28) |
| Direction accuracy when type correct | 1.0000 (24/24) |
| Positive Relation accuracy | 0.8621 (25/29) |
| `NO_RELATION` accuracy | 1.0000 (11/11) |
| Macro F1 over supported labels | 0.9000 |
| `RELATED_TO` prediction rate | 0.0000 (0/40) |
| Exact evidence-span rate | 1.0000 (29/29) |
| Pending-case manual evidence support | 10/12 |

All four primary strict-edge errors are gold `APPLIED_IN` pairs predicted as
`REQUIRES` with reversed endpoints:

- `rel_holdout_013`;
- `rel_holdout_030`;
- `rel_holdout_032`;
- `rel_holdout_036`.

The `1.0000` direction-when-type-correct value is denominator-sensitive: these
four pairs are excluded because their labels are also wrong. Endpoint direction
accuracy, which scores all 28 directional pairs, is the comparable direction
measure.

Holdout evidence adjudication resolved 12 pending cases: 10 were supported and 2
were not supported. `rel_holdout_007` contains an unresolved "this problem", and
`rel_holdout_039` contains an unresolved "It" plus a generic midpoint formula.

---

# Final Role

The baseline is a valid control, not a failed prompt. It establishes the point of
comparison needed to show that Prompt 002's type-boundary improvement generalizes
to unseen data. It also shows that strong hard-negative and exact-span results on
this holdout are not unique to Prompt 002.

Prompt 002 is selected for subsequent Technical Validation because it improves
holdout type accuracy and evidence support without reducing strict edge,
direction, positive, or hard-negative performance. The complete selection logic
is recorded in `../holdout_comparison.md`.

The baseline prompt and all formal artifacts remain preserved for future
regression comparisons.
