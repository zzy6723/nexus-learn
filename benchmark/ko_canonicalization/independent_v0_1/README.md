# 002C-5 Independent Canonicalization Benchmark v0.1

**Status:** Prepared before resolver execution

## Source Boundary

This benchmark reuses a four-lecture Entity bundle frozen during Experiment
002B before Knowledge Object canonicalization was designed. The lectures were
previously inspected for Relation work, but no 002C-0 through 002C-4 method or
run consumed this bundle.

It is therefore independent with respect to canonicalization method
development, not a universally unseen source or a broad real-course benchmark.

## Coverage

- 4 lectures;
- 39 predicted KO mentions;
- 1 cross-lecture SAME_OBJECT pair;
- 740 DISTINCT_OBJECT pairs;
- 7 deterministic resolver candidates;
- 1 positive candidate;
- 6 name-containment hard negatives;
- 34 exact and 5 non-exact upstream Entity source spans.

The low positive count is a pre-existing property of the source. It limits the
strength of any passing recall claim and must not be repaired by adding authored
examples after method freeze.

## Independence Rule

Ground Truth, candidates, success criteria, and Evidence review rules are
frozen before the v0.2.1 resolver is called. A failure converts this benchmark
to development data; the method may then change only for a future source.
