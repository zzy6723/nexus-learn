# Knowledge Object Resolution Experiments

This directory validates how lecture-local predicted Knowledge Object mentions
become stable canonical Knowledge Objects without losing source provenance.

Knowledge Object Resolution is separate from Relation Extraction:

- identity asks whether two mentions denote the same educational object;
- a Relation asks how two distinct Knowledge Objects are connected.

## Final Status

Experiment 002C-0 has frozen its controlled canonicalization benchmark and
strict artifact checks. The first benchmark reuses the inspected four-lecture,
39-mention inventory from Experiment 002B as development data. It is not unseen
evidence. Experiment 002C-1 completed its clean-state formal comparison; both
deterministic methods passed, and Exact Name was selected by the frozen
simplicity tie-breaker.

```text
predicted lecture-local KO mentions
-> canonical identity clusters
-> stable canonical KO records
-> provenance-preserving mention membership
```

The completed preparation milestone is documented in
`002c_controlled_canonicalization/README.md`. The formal validation sequence is:

- `002c_1_deterministic_canonicalization/`;
- `002c_2_context_aware_resolution/`;
- `002c_3_pipeline_validation/`;
- `002c_4_evidence_id_resolution/`;
- `002c_5_independent_validation/`.

The authored 002C-2 challenge selected context-aware identity resolution after
it achieved perfect candidate, resolver, cluster, and provenance metrics. The
Exact baseline produced one false merge and nine false splits.

The selected v0.1 method then failed the 002C-3 locked-reuse execution gate in
two attempts. A nonexact Unicode Entity span was not an exact substring of the
LaTeX lecture text, and the model repeatedly copied that span as evidence. The
strict runner rejected both attempts before cluster generation.

Experiment 002C is complete with limited independent validation. The identity
architecture is retained, and evidence-ID context resolution v0.2.1 is
selected as the canonicalization method for the next Technical Validation
stage. No production canonicalizer is selected.

The remediation is documented in `002c_4_evidence_id_resolution/`. v0.2 fixed
the original Unicode/LaTeX copying failure but exposed a trailing display-math
catalog defect. v0.2.1 corrected that defect and passed the authored challenge
and former failure bundle, including manual semantic-evidence review. Both are
development datasets; the subsequent 002C-5 source provides the limited
independent result.

The final stage is complete:

```text
002C-5 Independent Canonicalization Validation: Passed
```

002C-5 froze a pre-existing four-lecture Entity bundle that did not
participate in 002C method development. It contains 39 mentions, one positive
identity pair, and six selected hard negatives. Every candidate, resolver,
cluster, integrity, exact-Evidence, blind semantic-Evidence, and determinism
gate passed. This supports limited independent locked reuse on this source,
not production readiness or broad generalization.

Experiment 003 Technical Validation may now use the selected canonicalization
pipeline under this limited evidence boundary.

## Programme Boundary

Experiment 002C does not classify typed Relations, generate candidate edges, or
rank learner-facing Connections. Cross-lecture Relation discovery begins only
after identity resolution has a validated contract.
