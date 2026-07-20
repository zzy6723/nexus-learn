# 003-2 Baseline Error Analysis

**Run:** `formal/run_01`
**Method commit:** `4ae39785c447b7dc68f854a5314ab00a4451ac52`
**Evaluation status:** Final; conditional and full-universe gates failed

## Result

The baseline predicted 115 positive edges among 125 high-recall candidates.
Only 14 of 41 primary positives had the correct type and direction, while 68 of
78 primary negatives became false-positive graph edges.

| Metric | Result | Gate |
| --- | ---: | ---: |
| Positive typed-edge recall | 0.3415 | 0.75 |
| Positive edge precision | 0.1284 | 0.75 |
| `NO_RELATION` accuracy | 0.1282 | 0.90 |
| Exact Evidence materialization | 1.0000 | 1.00 |
| Semantic Evidence support | 0.1217 | 0.90 |
| Full-universe F1 | 0.1867 | 0.70 |

Evidence adjudication resolved 106 pending cases: 5 were supported and 101 were
not supported. Transport worked; semantic selection did not.

## Error Structure

- 45 hard negatives were labelled `APPLIED_IN`;
- 13 hard negatives were labelled `FORMALIZES`;
- 10/78 hard negatives were correctly rejected;
- primary positives contained 18 wrong-type and 9 wrong-direction errors;
- `APPLIED_IN` was often inferred from shared workflow or co-occurrence;
- `FORMALIZES` was assigned without an explicit Formula-source definition or
  characterization statement;
- `REQUIRES` and `APPLIED_IN` roles were not separated consistently.

## Refinement Targets

Prompt 002 may strengthen only rules supported by these errors:

1. treat the selected candidate set as recall-oriented and mostly negative;
2. require an explicit relational predicate, not two endpoint descriptions;
3. require direct use language for `APPLIED_IN`;
4. require a Formula source and explicit formalization language for
   `FORMALIZES`;
5. require explicit necessity for `REQUIRES` and verify direction;
6. prefer `NO_RELATION` whenever the selected Evidence cannot state the full
   edge without an unstated bridge.

The benchmark, candidate selection, Ground Truth, evaluator, Evidence catalogs,
and success criteria remain unchanged.
