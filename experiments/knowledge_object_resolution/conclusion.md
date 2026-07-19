# Experiment 002C Conclusion

## Result

Experiment 002C is complete with partial feasibility and a failed locked-reuse
gate.

- 002C-0 established a strict mention/identity/provenance contract.
- 002C-1 showed that Exact Name and frozen aliases can work on an easy but
  underpowered 39-mention benchmark.
- 002C-2 showed that candidate-scoped context resolution can perfectly resolve
  a 21-mention authored development challenge, including aliases,
  abbreviations, formula names, and a same-name homonym.
- 002C-3 showed that v0.1 cannot yet execute end to end on a previously
  inspected 49-mention bundle because its free-form exact-evidence output is
  brittle to Unicode/LaTeX differences inherited from upstream Entity spans.

## Product Decision

The canonical identity model, cluster-level Ground Truth, conservative
candidate generation, contradiction checks, and provenance-preserving cluster
format are retained.

No production canonicalization method is selected. Exact Name is insufficient
on the challenge, while context v0.1 passed development but failed locked
reuse. Experiment 003 should not assume that canonical KO endpoints are ready.

## Next Validation

The next iteration should be narrowly scoped to evidence transport:

1. deterministically enumerate exact lecture spans or sentences;
2. give each span an opaque evidence ID;
3. require the resolver to return evidence IDs rather than copied text;
4. preserve the original Entity span and exactness flag separately;
5. rerun the development challenge without changing its identity labels;
6. validate on a newly frozen source that did not drive the remediation.

This is an engineering interface correction, not a reason to weaken source
grounding or reinterpret the failed run as a semantic success.

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

v0.2.1 fixes that implementation defect and is pending a new formal
development run. The earlier runs remain diagnostic history and must not be
overwritten. Even after development passes, production selection requires a
newly frozen source.
