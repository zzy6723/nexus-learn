# Experiment 003 v0.1 Conclusion

**Status:** Completed with a negative Technical Validation result

## Result

Experiment 003 v0.1 established a frozen canonical-pair benchmark, selected a
candidate-generation method, and evaluated two Oracle-canonical Connection
classification architectures. Candidate generation was feasible, but neither
classification architecture passed the frozen quality gates. No validated
Connection Discovery method is selected.

The selected `overlap_bridge_v0.1` candidate generator retained all 41 primary
positive pairs while reducing the classifier workload from 387 to 125 pairs.
This result isolates classification, rather than candidate recall, as the main
failure in the current pipeline.

The stronger one-stage Prompt 002 diagnostic produced 13 correct positive
edges, 40 false-positive Relations, three false negatives, and a full-universe
F1 of `0.2185`. Its positive-edge precision was `0.1667`, positive typed-edge
recall was `0.3171`, and semantic Evidence support was `0.4512`.

The two-stage v0.1.2 method separated direct-edge detection from Relation
typing. Stage A recovered 37 of 41 positive pairs, but also passed 40 of 78
selected negatives. The final typed output retained the same 13 correct
positive edges and 40 false positives as Prompt 002. Its full-universe F1 was
`0.2203`, semantic Evidence support was `0.4096`, and both frozen gates failed.
The architecture therefore did not produce a material improvement.

## Stage Decisions

- 003-0 completed benchmark, protocol, Evidence, and success-criteria freeze.
- 003-1 completed candidate-generation validation and selected
  `overlap_bridge_v0.1` for the v0.1 benchmark.
- 003-2 completed one-stage Oracle-canonical evaluation; frozen gates failed.
- 003-2b completed two-stage Oracle-canonical evaluation; frozen gates failed.
- 003-3 was not executed because the predicted-canonical pipeline cannot
  validate a classifier that already fails with Oracle endpoints.
- 003-4 was not executed because ranking unvalidated Connection predictions
  would confound discovery correctness with educational usefulness.
- 003-5 was not executed because no complete method qualified for independent
  validation.

The unexecuted stages are gate-respecting outcomes, not missing work. Their
preconditions were declared before the model runs and were not satisfied.

## Product Decision

Connection Discovery is not operationally viable for the MVP under the current
v0.1 method and benchmark criteria. Experiment 004 must not begin as product
validation because the system cannot yet produce a sufficiently precise,
typed, and semantically grounded Connection set.

The accepted outputs are limited to:

- the canonical Connection benchmark and evaluator;
- `overlap_bridge_v0.1` as a development candidate generator;
- the execution, Evidence-ID, adjudication, and failure-lifecycle
  infrastructure;
- the negative evidence that prompt-only and simple two-stage decomposition do
  not solve direct-edge discrimination.

No one-stage or two-stage Connection classifier is selected as a default.

## Next Research Direction

A future Connection Discovery v0.2 should be a new method cycle, not Prompt 003
on the same 125 pairs. It should first redefine how direct educational support
is represented and verified, then freeze the method before evaluation on fresh
data. Useful directions include explicit endpoint-linked Evidence verification,
contrastive direct-versus-mediated supervision, or a deterministic retrieval
stage followed by a calibrated verifier.

Any v0.2 claim must distinguish method-development data from independent
validation data. Predicted-canonical propagation, ranking, and learner-facing
explanations remain blocked as product validation until an Oracle-canonical
method passes its frozen gates.

## Scope Limits

The result concerns 31 Oracle canonical Knowledge Objects, 387 eligible pairs,
125 selected candidates, and short authored STEM lectures. It does not establish
performance on long documents, parsed PDFs, noisy Entity outputs, broad STEM
coverage, learner-specific usefulness, or run-to-run stability.
