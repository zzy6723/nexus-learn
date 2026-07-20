# v0.1.1 Transport Failure

## Status

The v0.1.1 formal `run_01` is incomplete and not eligible for evaluation.

## Failure

All 125 Stage-A requests completed successfully. Stage A selected 83 candidates
for Relation typing. Stage B completed an exact 37-pair prefix, including six
successful validator-guided schema repairs, before the next API response failed
with:

```text
TimeoutError: The read operation timed out
```

The next request in the frozen Stage-B order was:

```text
conn_dev_pair_9a51109c78e243ef
```

Runner v0.1.1 did not catch this transport exception and therefore did not write
aggregate failure metadata. It also did not write aggregate Stage-B or final
Connection predictions. No evaluator was run and no prediction quality was
inspected before defining recovery behavior.

## Interpretation

This is an execution-infrastructure failure. It is not evidence for or against
the two-stage Connection method. The partial source run must remain unchanged
and must never be evaluated as a complete run.

## Recovery Boundary

Runner v0.1.2 may reuse only the deterministic execution prefix after strict
local validation confirms:

- all 125 Stage-A rendered inputs, raw responses, outputs, and metadata;
- the Stage-A aggregate and its 83 positive decisions;
- all 83 deterministic Stage-B rendered inputs;
- an exact 37-pair Stage-B completion prefix;
- each original and repaired raw response against the unchanged validator;
- each saved output and pair metadata against the reconstructed response chain;
- absence of unbound Stage-B raw or repair artifacts.

The validated prefix is copied into a new run and bound by a generated resume
manifest. Execution continues from the first missing pair. Reuse is based only
on request order and artifact validity, never on prediction content or score.

## Local Preflight

The actual source artifacts passed the v0.1.2 local resume preflight:

```text
Stage-A reused:       125
Stage-A positives:     83
Stage-B reused:        37
Stage-B repairs:        6
Bound artifacts:      624
Artifact-set SHA-256: 84d6eaf9bb46d3d00343b7ea0af3762212cc04267903c32ed3b79659522a769a
```
