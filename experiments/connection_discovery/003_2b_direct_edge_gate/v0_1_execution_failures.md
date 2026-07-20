# 003-2b v0.1 Execution Failures

**Status:** Closed after the repeated-failure ceiling

Two clean-state formal attempts used method commit
`7fe5eab9f8f1b8b3e63c2931208c02fea9ed1b66` with identical model parameters.

| Attempt | Stage A | Stage-A positives | Stage B before failure | Failure |
| --- | ---: | ---: | ---: | --- |
| `run_01` | 125/125 | 82 | 6 completed | `conn_dev_pair_225420587c4177f5`: `FORMALIZES` source was not a Formula |
| `run_02` | 125/125 | 82 | 6 completed | Same candidate and same schema violation |

The candidate endpoints were Gradient Descent (`Method`) and Gradient Descent
Update (`Formula`). The model selected `FORMALIZES` but serialized Gradient
Descent as source. ADR-004 requires the Formula endpoint to be source.

Both failed attempts are retained as execution-reliability evidence. They are
not experiment results and do not enter any metric denominator. No raw response,
endpoint, or prediction was edited. Repeating the unchanged full run again is
not permitted; the next execution must use the separately committed v0.1.1
bounded schema-repair policy.
