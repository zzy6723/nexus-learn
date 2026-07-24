# Experiments

This directory contains reproducible technical validation experiments.

Each experiment should document:

- Hypothesis
- Inputs
- Prompt or method
- Outputs
- Evaluation
- Conclusion

Experiments should support engineering decisions rather than exist as isolated demos.

---

# Experiment Areas

## `entity_extraction/`

Validates whether STEM learning materials can be converted into structured Knowledge Objects.

## `relation_extraction/`

Validates whether typed Relations can be extracted or inferred from Knowledge Objects and source materials.

## `connection_discovery/`

Validates whether the system can propose evidence-supported Connection Hypotheses across courses, time, or disciplines.

Connection Discovery is the central AI capability of the project.

---

# Technical Validation Sequence

| Experiment | Boundary | Status |
| --- | --- | --- |
| 001 | Extract structured Knowledge Objects | Completed |
| 002A | Classify typed Relations for supplied Oracle-KO pairs | Completed |
| 002B-1 | Measure predicted-KO error propagation on supplied gold pair candidates | Completed |
| 002B-2 | Generate Relation candidate pairs from predicted KOs | Completed with partial feasibility |
| 002C | Resolve lecture-local KO mentions into canonical objects | Completed with limited independent validation |
| 003 | Discover and rank learner-relevant Connections | Closed with negative development Technical Validation results |
| 004 | Oracle-conditioned evidence-supported explanations | 004-0 preparation; downstream product validation remains blocked |

Experiment 002B is complete. Predicted-KO Relation coupling was feasible on
recoverable pairs, but missing KOs remained an upstream bottleneck and the
Rule-Filtered v0.1 candidate method failed its frozen recall gate. All-Pairs
v0.1 remains the current lecture-local safety fallback.

The alignment used in Experiment 002B-1 is an evaluation scaffold against an
Oracle inventory. It is not the product canonicalization layer planned for
Experiment 002C.

Experiment 002C selected Evidence-ID context resolution v0.2.1 for subsequent
Technical Validation after limited independent validation. It is not a
production canonicalizer.

Experiment 003 v0.1 retained all 41 primary positive pairs with its selected
candidate generator within the overlap-bridge primary scope, but both tested
Oracle-canonical Connection classifiers failed the frozen quality gates. The
five disjoint-provenance compositional positives were diagnostic-only.
Predicted-canonical propagation, ranking, independent validation, and
learner-facing explanation were not executed because their preconditions were
not met. The subsequent v0.2 cycle therefore used a materially revised method.

Experiment 003 v0.2 evaluated endpoint-linked Evidence windows and an explicit
direct-versus-mediated support contract. It improved some development
diagnostics but failed five of eight frozen criteria, including precision,
recall, negative accuracy, conflict control, and semantic Evidence support.
No Connection classifier is selected, and the existing 125-pair benchmark is
now development-only for all three tested architectures. This is a scoped
negative development result, not evidence that Connection Discovery is
generally impossible.

Experiment 004 has entered benchmark and evaluation preparation only as an
Oracle-conditioned component experiment. It fixes human-validated Connections
and Evidence and does not evaluate predicted-Connection explanations or the
end-to-end product pipeline.
