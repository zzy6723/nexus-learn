# Candidate Pair Generation Fixtures

`selection_scenarios.json` is a compact scoring fixture for the Candidate
Generation evaluator. Its five primary denominator-guard pairs contain:

- two `IN_SCHEMA_RELATION` positives;
- two `NO_IN_SCHEMA_RELATION` negatives;
- one `OUT_OF_SCHEMA_RELATION` diagnostic.

Selecting all five must produce recall `2/2`, primary precision `2/4`, primary
retention `4/4`, total workload retention `5/5`, and diagnostic selection
`1/1`. The separate ambiguous item tests finalized diagnostics without changing
the primary denominator. One positive pair carries two Relation instances so
pair recall and relation-instance coverage are tested independently.

These records are test specifications rather than benchmark Ground Truth. The
integration tests construct fully hash-bound v0.1 artifacts in temporary
directories using the repository's strict checker and completion-marker code.
