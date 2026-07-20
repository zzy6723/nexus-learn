# 002C-5 Conclusion

## Decision

The frozen `ko_canonicalization_pipeline_v0_2_1` passed the complete
`independent_v0_1` evaluation and is selected as the canonicalization method
for the next Technical Validation stage.

The selected resolver is:

```text
candidate_scoped_context_resolution_evidence_ids_v0_2_1
```

## Basis

- all seven predeclared candidate decisions were correct;
- SAME_OBJECT precision and end-to-end recall were `1.0`;
- all six candidate hard negatives were correctly classified;
- all 38 canonical clusters matched Ground Truth exactly;
- integrity and provenance checks had no failures;
- all 15 selected Evidence spans materialized exactly;
- all seven Evidence sets passed independent blind semantic review;
- all five run-specific determinism checks passed.

## Boundary

Experiment 002C is complete with limited independent validation. The result
permits use of the selected pipeline in Experiment 003 Technical Validation.
It does not select a production canonicalizer or establish broad
generalization or stability.
