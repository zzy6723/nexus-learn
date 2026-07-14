# Relation Extraction 002 Prompt Refinement

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Status:** Selected for subsequent Technical Validation; Experiment 002A complete  
**Prompt version:** v0.2  
**Created:** 2026-07-13

---

# Purpose

This experiment tests a minimal prompt refinement derived from the finalized
`001_baseline` development error analysis. It uses the same model-facing task,
Relation schema, development benchmark, candidate pairs, runner, evaluator, and
request parameters as the baseline.

Development results were used for prompt diagnosis. The frozen holdout comparison
completed the generalization check for this experiment.

---

# Frozen Inputs

The following remain unchanged:

- `benchmark/ground_truth/relations_development_v0_1.json`;
- `benchmark/relation_annotation_guidelines.md`;
- `benchmark/relation_evaluation_protocol.md`;
- `docs/decisions/004-relation-schema.md`;
- `scripts/run_relation_extraction.py`;
- `scripts/evaluate_relation_extraction.py`;
- the 41 candidate pairs, 46 Knowledge Objects, and 6 lecture snippets;
- model and request parameters used by the baseline formal run.

---

# Changes From Baseline

Prompt v0.2 preserves the baseline task and I/O contract. It adds only the six
targets supported by `001_baseline/error_analysis.md`:

1. determine semantic roles before serializing endpoints;
2. prefer `FORMALIZES` over `APPLIED_IN` for an explicitly formalizing Formula;
3. require direct supplied evidence before assigning a positive Relation;
4. use `NO_RELATION` for weak, indirect, contextual, or external inference;
5. prevent `RELATED_TO` from acting as an uncertainty fallback;
6. require a self-contained evidence set and evidence-consistent rationale.

No development pair or object is named in the added rules.

---

# Baseline Reference

Formal baseline run:

- `experiments/relation_extraction/001_baseline/runs/development_v0_1/run_02/`

| Metric | Baseline |
| --- | ---: |
| Strict edge accuracy | 0.8421 |
| Relation type accuracy ignoring direction | 0.8947 |
| Endpoint direction accuracy | 0.9286 |
| Direction accuracy when type correct | 0.9259 |
| Positive Relation accuracy | 0.8929 |
| `NO_RELATION` accuracy | 0.7000 |
| Exact evidence-span rate | 1.0000 |
| False-positive Relations | 3 |
| `RELATED_TO` overuse | 2 |
| Positive-to-`NO_RELATION` false negatives | 0 |

---

# Comparison Criteria

Prompt v0.2 should be judged as a multi-metric refinement, not by strict-edge
accuracy alone.

Desired development effects:

- strict edge accuracy improves or does not regress;
- Relation type accuracy does not regress, with the observed `FORMALIZES`
  confusion removed if possible;
- direction accuracy improves;
- `NO_RELATION` accuracy improves;
- false-positive Relations decrease;
- `RELATED_TO` overuse decreases, ideally to zero;
- exact evidence-span performance remains high;
- unsupported evidence does not increase.

Over-conservatism guardrails:

- positive Relation accuracy must be inspected alongside hard-negative accuracy;
- positive-to-`NO_RELATION` false negatives must be counted explicitly;
- a reduction in false positives is not sufficient if supported positive edges
  are suppressed;
- manual evidence support rates are comparable only with their pending-case
  denominators and must not be treated as all-evidence accuracy.

---

# Run Plan

1. Run the existing evaluator and runner regression suites.
2. Create an isolated `dry_run_01` and inspect rendered inputs and metadata.
3. Confirm identical benchmark, lecture, and Knowledge Object hashes against the
   baseline, and confirm a different prompt hash.
4. Preserve or remove the dry-run artifacts before the formal run as an explicit
   workspace decision.
5. Only after the refined setup is committed and the working tree is clean, run a
   new formal API request without `--overwrite`.
6. Evaluate predictions and resolve any evidence adjudication before comparison.

This plan is historical. The formal development and holdout runs are complete;
the resulting comparison is recorded in `../holdout_comparison.md`.

The formal run is complete under `runs/development_v0_1/run_01/`. Its evaluation
status is `final` after 13 independent semantic-support adjudications.

---

# Dry-Run Validation

Validated dry run:

- `runs/development_v0_1/dry_run_01/`

Regression and dry-run checks completed on 2026-07-13:

- Python compilation passed;
- 18 evaluator and runner regression tests passed;
- candidate pairs: 41;
- Knowledge Objects: 46;
- lectures: 6;
- gold-leakage audit: passed;
- model and request parameters: identical to the formal baseline;
- ground-truth hash: identical to the formal baseline;
- Knowledge Object ground-truth hashes: identical to the formal baseline;
- lecture hashes: identical to the formal baseline;
- model-input hash: identical to the formal baseline;
- prompt hash: different from the baseline, as expected.

The dry run recorded `git_dirty_at_start = true` because the refinement setup was
not committed. This is acceptable for input validation but not for the future
formal API run. The dry-run artifacts must not be represented as a clean-state
experimental result.

---

# Final Development Result

- strict edge accuracy: `0.9211`;
- Relation type accuracy: `0.9737`;
- endpoint direction accuracy: `0.8929`;
- positive Relation accuracy: `0.8929`;
- `NO_RELATION` accuracy: `1.0000`;
- false-positive Relations: `0`;
- positive-to-`NO_RELATION` false negatives: `0`;
- exact evidence-span rate: `1.0000`;
- pending-case evidence support: `12/13`;
- remaining pending adjudications: `0`.

Prompt 002 is the stronger current development candidate, with documented
direction and evidence limitations. See:

- `conclusion.md`;
- `../development_comparison.md`;
- `runs/development_v0_1/run_01/evaluation/adjudication_analysis.md`.

---

# Selection and Content Lock

Selected method:

- experiment: `002_prompt_refinement`;
- prompt version: `v0.2`;
- prompt SHA-256: `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`;
- engineering role: Relation Extraction prompt v0.1 for subsequent Technical
  Validation.

Development selection basis:

- strict-edge accuracy increased from `0.8421` to `0.9211`;
- Relation type accuracy increased from `0.8947` to `0.9737`;
- all three observed hard-negative false positives were eliminated;
- `RELATED_TO` overuse decreased from 2 to 0;
- positive Relation accuracy did not decrease;
- no positive pair was changed to `NO_RELATION`;
- exact grounding and pending-case semantic support did not decrease.

The unseen holdout confirmed the selection because Prompt 002 improved Relation
type accuracy from `36/40` to `40/40` while preserving strict edge accuracy,
endpoint direction accuracy, positive Relation accuracy, hard-negative accuracy,
and exact evidence grounding. It also improved pending-case evidence support from
`10/12` to `11/12`. The full selection argument is recorded in
`../holdout_comparison.md`.

This is an engineering default for subsequent Technical Validation, not a
production-prompt decision. Endpoint direction and evidence self-containment
remain documented cross-split limitations.

The prompt content remains locked at the SHA-256 above. The development method
was frozen at commit `18e687d5cd7909531918b51e2d6bef38cb64a053` before any unseen
holdout lecture or gold label was authored. The completed holdout benchmark was
then frozen at commit `5fd7e2b9ea02fad6a15f2a1a703193bd7d606c7d`; both formal
holdout runs started clean from that commit. No Prompt 003 refinement may use the
inspected holdout and then report performance on the same split as unseen.
