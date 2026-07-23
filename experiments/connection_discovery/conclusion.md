# Experiment 003 Conclusion

**Status:** v0.1 and v0.2 development completed with negative Technical Validation results

## Result

Experiment 003 v0.1 established a frozen canonical-pair benchmark, selected a
candidate-generation method, and evaluated two Oracle-canonical Connection
classification architectures. Candidate generation was feasible, but neither
classification architecture passed the frozen quality gates. No validated
Connection Discovery method is selected.

The selected `overlap_bridge_v0.1` candidate generator retained all 41 primary
positive pairs while reducing the classifier workload from 387 to 125 pairs.
All 41 primary positives are `overlap_bridge` cases. Within that frozen primary
scope, this result isolates classification, rather than candidate recall, as
the main failure in the current pipeline. It does not establish candidate
recall for truly disjoint-provenance Connections.

The stronger one-stage Prompt 002 diagnostic produced 13 correct positive
edges, 25 wrong typed or directed edges on gold-positive pairs, three
gold-positive pairs predicted as `NO_RELATION`, 40 edges on gold-negative
pairs, and 38 correctly rejected gold negatives. Its full-universe F1 was
`0.2185`, positive-edge precision was `0.1667`, positive typed-edge recall was
`0.3171`, and semantic Evidence support was `37/82` (`0.4512`).

The two-stage v0.1.2 method separated direct-edge detection from Relation
typing. Stage A recovered 37 of 41 positive pairs, but also passed 40 of 78
selected negatives. The final typed output retained the same 13 correct
positive edges and 40 gold-negative overconnections as Prompt 002, while 24
gold-positive pairs received a wrong typed or directed edge and four were
predicted as `NO_RELATION`. Its full-universe F1 was `0.2203`, semantic
Evidence support was `34/83` (`0.4096`), and both frozen gates failed. The
architecture therefore did not produce a material improvement.

## Stage Decisions

- 003-0 completed benchmark, protocol, Evidence, and success-criteria freeze.
- 003-1 completed candidate-generation validation and selected
  `overlap_bridge_v0.1` for the v0.1 benchmark.
- 003-2 completed one-stage Oracle-canonical evaluation; frozen gates failed.
- 003-2b completed two-stage Oracle-canonical evaluation; frozen gates failed.
- 003-2c completed endpoint-linked Oracle-canonical development evaluation;
  five of eight frozen criteria failed.
- 003-3 was not executed because the predicted-canonical pipeline cannot
  validate a classifier that already fails with Oracle endpoints.
- 003-4 was not executed because ranking unvalidated Connection predictions
  would confound discovery correctness with educational usefulness.
- 003-5 was not executed because no complete method qualified for independent
  validation.

The unexecuted stages are gate-respecting outcomes, not missing work. Their
preconditions were declared before the model runs and were not satisfied.

## Product Decision

No tested v0.1 or v0.2 development method established operationally viable
Connection Discovery for the MVP under the frozen benchmark criteria.
Experiment 004 must not begin as downstream product validation because the
system cannot yet produce a sufficiently precise, typed, and semantically
grounded Connection set. Oracle-conditioned explanation research remains a
scientifically separate question, but it cannot be presented as validation of
the discovery pipeline.

The accepted outputs are limited to:

- the canonical Connection benchmark and evaluator;
- `overlap_bridge_v0.1` as a development candidate generator;
- the execution, Evidence-ID, adjudication, and failure-lifecycle
  infrastructure;
- the negative evidence that prompt-only and simple two-stage decomposition do
  not solve direct-edge discrimination.

No one-stage or two-stage Connection classifier is selected as a default.

## Next Research Direction

A future Connection Discovery research cycle, v0.3 or later, should be a new
method cycle, not another prompt iteration on the same 125 pairs. It should
first redefine how direct educational support is represented and verified,
then freeze the method before evaluation on fresh data. Useful directions
include contrastive direct-versus-mediated supervision, a deterministic
symbolic verifier for a narrow Relation subset, or calibrated supervised edge
classification. Directional methods should separate semantic role prediction
from deterministic source/target serialization.

Any future-cycle claim must distinguish method-development data from independent
validation data. Predicted-canonical propagation, ranking, and learner-facing
explanations remain blocked as product validation until an Oracle-canonical
method passes its frozen gates.

## Scope Limits

The result concerns 29 Oracle canonical Knowledge Objects, 387 eligible pairs,
125 selected candidates, and short authored STEM lectures. It does not establish
performance on long documents, parsed PDFs, noisy Entity outputs, broad STEM
coverage, learner-specific usefulness, or run-to-run stability.

All 41 primary positive pairs are `overlap_bridge` cases. The five annotated
`disjoint_provenance` compositional positives are diagnostic-only and excluded
from the primary validation gates. The reported `41/41` candidate recall
therefore does not establish general disjoint-provenance cross-document
Connection discovery.

## v0.2 Development Addendum

The v0.2 endpoint-linked Evidence verifier tested a materially different input
and decision contract on the same development benchmark. Deterministic
preprocessing generated 173 minimal windows, retained coverage for all 41
primary positives, and guaranteed exact Evidence materialization. A completed
candidate-scoped run produced 15 strict-correct positive edges, 17 wrong typed
or directed edges on gold-positive pairs, nine gold-positive pairs predicted
as `NO_RELATION`, 36 edges on gold-negative pairs, and 42 correctly rejected
gold negatives.

Compared with v0.1, positive precision rose to `0.2206`, typed-edge recall to
`0.3659`, `NO_RELATION` accuracy to `0.5385`, and full-universe F1 to `0.2752`.
These are modest diagnostic improvements, not validation success. The method
generated 17 aggregation conflicts and only `29/71` (`0.4085`) semantic
Evidence support. Of those 29 supported cases, six matched frozen gold Evidence
automatically and 23 were supported through manual adjudication. Five of eight
frozen 003-2c criteria failed.

The 17 aggregation conflicts are distinct from the 17 final wrong typed or
directed positive edges. Conflicts are disagreements among local windows for
one pair and fail closed to `NO_RELATION`; final wrong edges are accepted
positive predictions whose type or direction is incorrect.

The v0.2 result confirms that endpoint-scoped retrieval and exact Evidence
transport do not by themselves solve direct-edge semantics. The unresolved
problem is distinguishing exact typed educational edges from mediated context,
shared derivations, and endpoint abstraction drift.

No validated Connection Discovery method is selected after either development
cycle. Further tuning on this benchmark is stopped. Any future research must
use a materially different learning signal and reserve fresh explicitly
annotated data for independent validation. Predicted-canonical propagation,
learner-facing ranking, and Experiment 004 product validation remain blocked.
