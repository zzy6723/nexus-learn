# Relation Extraction 002 Prompt Refinement Conclusion

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Development run:** `runs/development_v0_1/run_01`  
**Holdout run:** `runs/holdout_v0_1/run_01`  
**Status:** Selected Relation Extraction prompt v0.1 for subsequent Technical Validation  
**Evaluation status:** Both `final`

---

# Development Result

Prompt v0.2 was created as one minimal refinement of the baseline. It targets
endpoint serialization, the `FORMALIZES` boundary, direct evidence gating,
`NO_RELATION` under insufficient support, `RELATED_TO` fallback prevention, and
self-contained evidence.

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

Prompt 002 removes all three observed hard-negative false positives without
suppressing supported positive edges. It does not fix the development direction
errors or the unsupported evidence at `rel_dev_014`, and it introduces one new
type-and-direction regression at `rel_dev_017`. These development findings are
recorded in `../development_comparison.md`.

---

# Unseen Holdout Result

Both holdout runs used the same frozen benchmark, model inputs, model, request
parameters, runner, evaluator, and clean-start commit. The only intended method
difference was prompt content.

| Metric | Baseline | Prompt 002 |
| --- | ---: | ---: |
| Strict edge accuracy | 0.9000 (36/40) | 0.9000 (36/40) |
| Relation type accuracy | 0.9000 (36/40) | 1.0000 (40/40) |
| Endpoint direction accuracy | 0.8571 (24/28) | 0.8571 (24/28) |
| Direction accuracy when type correct | 1.0000 (24/24) | 0.8571 (24/28) |
| Positive Relation accuracy | 0.8621 (25/29) | 0.8621 (25/29) |
| `NO_RELATION` accuracy | 1.0000 (11/11) | 1.0000 (11/11) |
| Macro F1 over supported labels | 0.9000 | 1.0000 |
| False-positive Relations | 0 | 0 |
| Positive-to-`NO_RELATION` false negatives | 0 | 0 |
| `RELATED_TO` overuse | 0 | 0 |
| Exact evidence-span rate | 1.0000 (29/29) | 1.0000 (29/29) |
| Pending-case evidence support | 10/12 | 11/12 |

Prompt 002 fixes all four unseen `APPLIED_IN -> REQUIRES` label confusions. It
does not improve strict edge accuracy because the same four pairs retain reversed
endpoints. The lower type-conditioned direction value is caused by the corrected
type labels adding those four pairs to Prompt 002's denominator; the common
28-pair endpoint direction metric is identical for both prompts.

Prompt 002 does not become over-conservative. It preserves all 29 positive-edge
decisions, rejects all 11 hard negatives, and never uses `RELATED_TO` as an
uncertainty fallback. Evidence remains exact, while one baseline semantic-support
failure at `rel_holdout_039` is corrected. The unresolved-reference failure at
`rel_holdout_007` remains.

---

# Selection

Prompt 002 is selected as the **Relation Extraction prompt v0.1 for subsequent
Technical Validation**.

The selection is based on improved unseen Relation type classification and
pending-case evidence support with no observed regression in strict edge,
endpoint direction, positive Relation, hard-negative, or exact-span outcomes.
It is not based on a holdout strict-accuracy gain, because no such gain occurred.

Selected prompt content:

- experiment: `002_prompt_refinement`;
- prompt version: `v0.2`;
- prompt SHA-256:
  `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`;
- engineering role: Relation Extraction prompt v0.1 for the next Technical
  Validation stage.

Experiment 002A is now complete. This is not a production-prompt decision and
does not establish broad STEM performance. The benchmark consists of short
authored snippets, oracle Knowledge Objects, preselected pairs, and one run per
prompt. `RELATED_TO` recall, run-to-run stability, long-document behavior, and
end-to-end error propagation remain untested.

Endpoint direction and evidence self-containment remain explicit limitations.
Prompt 003 must not be tuned on the inspected holdout and then evaluated against
that same split as unseen data. A future refinement using these errors requires a
new holdout for a fresh generalization claim.

The complete aggregate and pair-level analysis is recorded in
`../holdout_comparison.md`.
