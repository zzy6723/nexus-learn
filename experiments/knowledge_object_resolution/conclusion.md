# Experiment 002C Conclusion

## Result

Experiment 002C is complete with a validated development architecture and no
production canonicalizer selection.

- 002C-0 established a strict mention/identity/provenance contract.
- 002C-1 showed that Exact Name and frozen aliases can work on an easy but
  underpowered 39-mention benchmark.
- 002C-2 showed that candidate-scoped context resolution can perfectly resolve
  a 21-mention authored development challenge, including aliases,
  abbreviations, formula names, and a same-name homonym.
- 002C-3 showed that v0.1 cannot yet execute end to end on a previously
  inspected 49-mention bundle because its free-form exact-evidence output is
  brittle to Unicode/LaTeX differences inherited from upstream Entity spans.
- 002C-4 replaced copied spans with opaque evidence IDs. v0.2.1 passed the
  authored challenge and former failure diagnostic with perfect identity,
  cluster, integrity, exact-grounding, and semantic-evidence results.

## Product Decision

The canonical identity model, cluster-level Ground Truth, conservative
candidate generation, contradiction checks, and provenance-preserving cluster
format are retained.

Evidence-ID context resolution v0.2.1 is selected as the development candidate
for independent validation. No production canonicalization method is selected.
Exact Name is insufficient on the challenge, context v0.1 failed end-to-end
execution, and v0.2.1 has only been evaluated on data that influenced method
development. Experiment 003 should not assume that canonical KO endpoints are
generally ready.

## Next Validation

The next iteration is an independently frozen validation source that did not
drive candidate generation, identity behavior, evidence-ID transport, catalog
partitioning, or success criteria. The frozen v0.2.1 method must run unchanged.

This boundary prevents the successful development repair from being
misrepresented as evidence of generalization.

## Remediation Status

002C-4 implements this interface correction as a separate evidence-ID method
candidate. Candidate-scoped lecture blocks receive opaque IDs; the model
selects IDs, and the runner mechanically restores exact lecture spans.

Formal v0.2 development runs completed both the authored challenge and the
former 002C-3 failure bundle. Identity and cluster metrics passed, and the
Unicode/LaTeX copying failure disappeared. Post-run semantic evidence review
then found that the partitioner omitted final display-math blocks when a
lecture ended with a single trailing newline. One Formula identity decision
was correct but its available evidence could not be self-contained.

v0.2.1 fixed that defect in a new method commit and new run directories. Its
challenge run produced 13/13 exact clusters and 11/11 semantically supported
evidence sets. Its former-failure diagnostic produced 46/46 exact clusters and
6/6 supported evidence sets. Both frozen success criteria passed.

The earlier v0.2 runs remain diagnostic history and were not overwritten.
Production selection still requires a newly frozen source.
