# Learning Explanation Evaluator Fixtures

These fixtures validate the frozen Experiment 004 evaluation boundary without
calling an API.

The canonical fixture contains four Oracle-conditioned explanation instances
and a perfect Evidence-grounded prediction/review bundle. Unit tests derive
isolated mutations for:

- semantic direction reversal;
- unsupported claims;
- endpoint drift;
- pedagogically empty output;
- unresolved claim adjudication;
- invalid Evidence references;
- stale review snapshots;
- missing prediction alignment;
- no-Evidence baseline behavior.

Semantic failures remain evaluable and produce final or draft metrics.
Transport, Evidence-reference, snapshot, and alignment failures are fatal and
must not produce aggregate metrics.
