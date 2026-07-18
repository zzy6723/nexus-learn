# 002C-2 Authored Development Challenge

This challenge was created after 002C-1 exposed that the original 39-mention
benchmark contained only one positive identity pair. It is development data,
not an unseen holdout.

## Frozen Counts

- 9 lectures;
- 21 mentions;
- 13 canonical clusters;
- 7 singleton and 6 multi-mention clusters;
- 10 SAME_OBJECT and 200 DISTINCT_OBJECT pairs;
- 21 exact source spans.

The benchmark is generated from authored Markdown and source-prediction
artifacts through the existing structural normalization and mention-inventory
pipeline. Ground Truth remains cluster-level and every singleton is explicit.

The challenge must be frozen before any context-aware formal API run. Resolver
outputs may not modify these artifacts or their completion markers.
