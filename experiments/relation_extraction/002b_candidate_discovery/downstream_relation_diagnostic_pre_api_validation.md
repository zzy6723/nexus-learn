# 002B-2 Downstream Diagnostic Pre-API Validation

**Date:** 2026-07-17
**Status:** Passed; formal execution subsequently completed
**API calls performed:** 0

This document records the pre-API gate only. Formal execution, independent
Evidence adjudication, final snapshots, and the full-universe comparison are
reported in `downstream_relation_diagnostic.md`.

## Frozen Scope

The diagnostic compares the already completed Candidate methods:

- `all_pairs_v0_1`;
- `rule_filtered_v0_1`.

It uses the selected Relation prompt v0.2, the existing strict Relation
evaluator, one candidate pair per request, and the inspected 002B-2 development
universe. Downstream results cannot override the failed Rule-Filtered Candidate
recall gate.

## Contract Validation

The machine contract validates 20 hash-bound artifacts covering:

- source pair universe and Candidate Ground Truth;
- predicted KO and lecture inventories;
- both Candidate selections and completion markers;
- Relation prompt, schema, base runner, and base evaluator;
- projection, preparation, execution, evaluation-finalization, and pipeline
  implementations.

The contract, projection protocol, and all bindings passed strict validation.

## Projection Validation

The canonical Candidate-to-Relation projection is complete and immutable by
default:

| Category | Count | Primary-scored |
| --- | ---: | --- |
| Positive | 80 | Yes |
| Hard negative | 91 | Yes |
| Schema gap | 5 | No |
| **Total** | **176** | **171 primary** |

Each `cand_dev_NNN` maps to `rel_dev_NNN`. Every positive has exactly one
predeclared primary Relation. Multi-relation positives, endpoint changes,
unknown pairs, ambiguous annotations, and stale source hashes fail closed.

The existing strict Relation Ground Truth checker accepted the projected
artifact. Primary Relation counts are:

| Relation | Count |
| --- | ---: |
| `REQUIRES` | 39 |
| `APPLIED_IN` | 23 |
| `FORMALIZES` | 10 |
| `EXTENDS` | 5 |
| `RELATED_TO` | 2 |
| `CONTRASTS_WITH` | 1 |
| `NO_RELATION` | 91 |

The five schema-gap placeholders are reported separately and do not enter these
primary Relation counts.

## Preparation Validation

| Condition | Selected | Positive | Negative | Diagnostic | Requests |
| --- | ---: | ---: | ---: | ---: | ---: |
| All-Pairs | 176 | 80 | 91 | 5 | 176 |
| Rule-Filtered v0.1 | 127 | 70 | 52 | 5 | 127 |

For both conditions:

- pair IDs are unique and preserve Candidate selection order;
- candidate endpoints match the canonical projection;
- one independent request is rendered per selected pair;
- 39 predicted KOs and four lecture texts are drawn from the same frozen input;
- the structured gold-leakage audit passes;
- no Candidate label, Relation label/direction, category, gold Evidence,
  rationale, symmetry flag, acceptable alternative, or scoring status appears
  in model-facing input.

## Evaluation Validation

Seventy non-Git regression tests passed across the relevant existing and new
suites. The new 14-test downstream suite covers:

- frozen denominators and deterministic ID projection;
- multi-relation and endpoint mismatch rejection;
- 176/127 gold-free preparation;
- perfect full-universe scoring;
- candidate-induced false negatives;
- correct rejection of unselected negatives;
- schema-gap exclusion;
- mutually exclusive classifier failure loci;
- empty selection behavior;
- duplicate/unknown alignment rejection;
- Evidence denominator reconciliation;
- stale snapshot rejection;
- an end-to-end synthetic path through the existing Relation evaluator,
  independent condition snapshots, and the final pipeline evaluator.

The synthetic full-pipeline control produced 171/171 strict success for
All-Pairs. With a perfect classifier on selected pairs, Rule-Filtered produced
161/171 because its 10 known positive omissions remained candidate-induced
false negatives. This confirms the intended denominator and error-attribution
behavior.

## Remaining Gates

No formal runner or API call has been made. The remaining sequence is:

1. user-managed repository freeze;
2. user-run clean-state dry runs for 176 and 127 requests;
3. formal All-Pairs execution;
4. formal Rule-Filtered execution bound to the preceding All-Pairs metadata;
5. independent base evaluation and Evidence adjudication;
6. independent final evaluation snapshots;
7. full-universe pipeline evaluation and 002B closure documents.

Exact commands are in `downstream_relation_diagnostic_runbook.md`.
