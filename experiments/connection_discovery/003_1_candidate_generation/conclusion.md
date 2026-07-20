# 003-1 Conclusion

Experiment 003-1 development validation is complete with a material scope
limitation.

`overlap_bridge_v0.1` is selected for the Experiment 003-2 primary route. It
retained all 41 primary positive candidates while reducing the 387-pair
classification workload to 125 pairs, a 67.70% reduction. It also produced the
highest primary candidate precision among the passing non-control methods.

This is an engineering decision for the v0.1 explicit overlap-bridge benchmark,
not a claim that provenance overlap solves Connection Discovery. The method
retrieved zero of five disjoint-provenance compositional diagnostics.
`lexical_only_v0.1` is retained as the diagnostic starting point for a later
benchmark with primary disjoint-provenance positives.

The next stage is 003-2 Oracle-Canonical Connection Discovery. It will classify
the 125 selected primary-route candidates using candidate-scoped Evidence IDs
and evaluate typed edge correctness, direction, `NO_RELATION`, and Evidence
support. The five compositional positives remain diagnostic and are not
silently added to the selected primary route.
