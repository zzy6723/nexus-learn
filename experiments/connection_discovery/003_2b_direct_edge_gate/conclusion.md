# 003-2b Conclusion

**Status:** Development method completed; frozen success gates failed

The two-stage direct-edge architecture is not operationally viable under the
current Oracle-canonical development benchmark and frozen success criteria.

Stage A achieved high direct-edge recall (`0.9024`) but admitted 40 false
positives, yielding only `0.4805` precision and `0.4872` primary-negative
accuracy. Stage B did not recover the required precision: the final method
retained 40 false-positive Relations, achieved `0.3171` positive typed-edge
recall and `0.1688` precision, and semantically supported only `0.4096` of its
positive Evidence sets.

Compared with one-stage Prompt 002, the two-stage method has identical strict
accuracy and positive recall. Its small direction and cross-course gains are
offset by worse Relation type accuracy, semantic Evidence support, false
negatives, and `RELATED_TO` control. The full-universe F1 change from `0.2185`
to `0.2203` is not a meaningful validation improvement.

The run remains valuable as a clean negative result. It shows that separating
edge existence from Relation typing is insufficient when the first-stage gate
still treats thematic or mediated proximity as a direct edge. It also confirms
that execution reliability can be handled without weakening schema validation
or altering model outputs.

No validated Connection Discovery default is selected. Candidate generation
from 003-1 remains accepted, but Oracle-canonical Connection classification
remains unresolved. Predicted-canonical propagation and learner-facing ranking
must remain diagnostic-only while this gate is failed.

Further pair-specific prompt tuning on the same 125 development candidates is
not justified. A future method version should change the decision evidence or
learning formulation, freeze that change before execution, and use fresh data
for any generalization claim.
