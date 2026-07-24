# 004-2: Evidence-Grounded Learning Explanation

**Status:** Not started; blocked on 004-0 repository freeze

`002_evidence_grounded` receives one Oracle Connection and its supplied
Evidence catalog. It must preserve immutable endpoints, Relation type, and
direction while generating:

- Connection Summary;
- Why Connected;
- Learning Value.

Every output field has its own `evidence_refs`. `why_connected` must cite at
least one supplied Evidence ID. The method may not retrieve Evidence,
reclassify the Connection, infer Learner State, or personalize advice.

This is the only selectable Experiment 004 method. At most one minimal,
error-analysis-driven development refinement is permitted.
