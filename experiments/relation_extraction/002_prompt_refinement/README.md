# Relation Extraction 002 Prompt Refinement

**Stage:** Experiment 002A: Oracle-KO Typed Relation Extraction  
**Status:** Selected for unseen holdout evaluation; freeze commit pending  
**Prompt version:** v0.2  
**Created:** 2026-07-13

---

# Purpose

This experiment tests a minimal prompt refinement derived from the finalized
`001_baseline` development error analysis. It uses the same model-facing task,
Relation schema, development benchmark, candidate pairs, runner, evaluator, and
request parameters as the baseline.

Development results can show whether the refinement addresses known errors on the
data used to design it. They cannot establish generalization; that requires a
later frozen holdout comparison.

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

Selected development prompt:

- experiment: `002_prompt_refinement`;
- prompt version: `v0.2`;
- prompt SHA-256: `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`;
- selected purpose: unseen Relation holdout evaluation.

Selection basis:

- strict-edge accuracy increased from `0.8421` to `0.9211`;
- Relation type accuracy increased from `0.8947` to `0.9737`;
- all three observed hard-negative false positives were eliminated;
- `RELATED_TO` overuse decreased from 2 to 0;
- positive Relation accuracy did not decrease;
- no positive pair was changed to `NO_RELATION`;
- exact grounding and pending-case semantic support did not decrease.

This is a development selection, not a production-prompt decision. Direction
errors at `rel_dev_010` and `rel_dev_020`, the new `rel_dev_017` type regression,
and the `rel_dev_014` evidence self-containment error remain documented
limitations.

The prompt content is now locked at the SHA-256 above. `prompt.md` must not be
changed during holdout construction or evaluation. The repository freeze commit
must be created and recorded by the user before any unseen holdout lecture or gold
label is authored.
