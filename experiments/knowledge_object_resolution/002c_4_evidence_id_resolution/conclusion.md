# 002C-4 Conclusion

## Decision

`candidate_scoped_context_resolution_evidence_ids_v0_2_1` is selected as the
Knowledge Object resolution **development candidate for future independent
validation**.

It retains the candidate-scoped identity architecture and replaces model-copied
evidence with candidate-scoped opaque IDs. The runner resolves selected IDs to
exact lecture substrings and preserves upstream Entity provenance separately.

## Basis

- all 17 v0.2.1 candidate decisions were correct across the challenge and
  locked-reuse diagnostic;
- SAME_OBJECT precision, end-to-end recall, and B-cubed F1 were all `1.0`;
- exact cluster matches were `13/13` and `46/46`;
- all 37 selected evidence IDs materialized to exact source spans;
- all 17 candidate-level evidence sets passed semantic-support review;
- no unresolved decisions, integrity failures, or provenance loss occurred.

## Boundary

This selection is not a production decision. Both datasets are development
data, the sample is small, and the method has not been tested on a newly frozen
source, long parsed documents, noisy extraction output, or broader STEM
domains. Run-to-run stability is also not established.

The two development resolver runs contain only 17 decisions and three direct
`DISTINCT_OBJECT` candidates. Perfect metrics on this small candidate-scoped
sample do not establish stability, generalization, or complete ambiguity
resolution.

Experiment 003 must not treat canonical KO endpoints as generally validated
until v0.2.1 passes an independently frozen evaluation source.
