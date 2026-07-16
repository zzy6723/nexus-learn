# All-Pairs Candidate Control

**Status:** Final
**Experiment:** 002B-2 Candidate Pair Generation under Predicted KOs
**Method:** `all_pairs_v0_1`
**Split role:** Development

## Purpose

The All-Pairs control mechanically retains every pair in the frozen exhaustive
predicted-KO pair universe. It validates Candidate Generation denominators,
diagnostic handling, artifact integrity, and the maximum Relation-classifier
workload. It is not a filtering method and is not evaluated against the frozen
20 percent workload-reduction gate.

## Frozen Inputs

- Pair universe: `benchmark/candidate_pairs/development_v0_1/pair_universe.json`
  (`d0c756b3e5533fac1e02c0aa5c1446cb78d206f21232e020ab0b5cb23b2bad84`)
- Candidate Ground Truth:
  `benchmark/ground_truth/candidate_pairs_development_v0_1.json`
  (`a25e5c9568b090fc97fd03ce0462fda608f62d88bd5b62f9b8d2db40530a133d`)
- Success criteria:
  `benchmark/candidate_pair_generation_success_criteria_v0_1.json`
  (`79c0f044c16077843ee74a07bf12c7e2638b10c2afd2fe05e96ca195105d4628`)
- Candidate output schema:
  `benchmark/schema/candidate_pair_generation_output.schema.json`

The generator reads the pair universe and its completion marker. It does not
read Candidate Ground Truth, Relation labels, Evidence, rationales, alignment
records, or Relation-classifier outputs.

## Expected And Observed Metrics

| Metric | Expected | Observed |
| --- | ---: | ---: |
| Total universe pairs | 176 | 176 |
| Selected pairs | 176 | 176 |
| Primary positive pairs selected | 80 | 80 |
| Primary negative pairs selected | 91 | 91 |
| Diagnostic pairs selected | 5 | 5 |
| Candidate recall | 1.000000 | 1.000000 |
| Primary candidate precision | 0.467836 | 0.467836 |
| Primary workload retained | 1.000000 | 1.000000 |
| Total workload retained | 1.000000 | 1.000000 |
| Total workload reduction | 0.000000 | 0.000000 |
| Actionable yield over total workload | 0.454545 | 0.454545 |

All four lectures achieved positive-pair recall `1.0`. All six supported
Relation types achieved pair recall and relation-instance coverage `1.0`.

## Integrity Checks

- Candidate generation status: `final`.
- Candidate evaluation status: `final`.
- Selected pair IDs: 176 unique IDs in frozen universe order.
- Endpoint mismatches: 0.
- Unknown or extra pairs: 0.
- Missing universe pairs: 0.
- Evaluation matches: 176 unique pair IDs.
- Primary denominator: `80 + 91 = 171`.
- Diagnostic denominator: `5 OUT_OF_SCHEMA_RELATION + 0 AMBIGUOUS = 5`.
- Total denominator: `171 + 5 = 176`.
- Generator metadata records `gold_artifacts_read = false`.
- Completion markers bind generator inputs, outputs, schema, implementation,
  evaluator, and final metrics by SHA-256.

`errors.json` contains 91 `retained_negative` and 5
`retained_out_of_schema` records. These are expected workload outcomes for an
All-Pairs control, not integrity failures.

## Decision

The All-Pairs control successfully reproduced the complete frozen candidate
universe and validated the Candidate Generation evaluator. It establishes the
maximum-workload reference for subsequent deterministic Rule-Filtered methods.

No Candidate Generation method is selected by this result. No Relation API was
called, and no downstream typed-edge claim is made.
