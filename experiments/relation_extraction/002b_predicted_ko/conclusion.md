# Experiment 002B-1 Conclusion

**Development decision:** Pass the development feasibility gate with an
Evidence exact-span compliance caveat.

**Execution update:** The original `locked_reuse_v0_1` Relation stage closed
after two repeated schema-invalid A-prime responses. The versioned
`locked_reuse_v0_2` candidate-scoped execution subsequently completed. It is a
method-revision diagnostic, not an untouched locked-reuse or unseen-holdout
result.

---

## Basis for the Decision

1. Primary pair recoverability was 36/38 (94.74%).
2. On the matched recoverable subset, strict edge accuracy did not decrease:
   A-prime = 30/36 and B-prime = 30/36.
3. The complete predicted-KO pipeline achieved 30/38 (78.95%) strict success.
   All nine recoverable hard-negative pairs were correctly classified as
   `NO_RELATION`, with no `RELATED_TO` fallback use.

Experiment 002B-1 therefore passed its development feasibility gate.

## Evidence Caveat

Exact Evidence-span compliance fell from 27/27 in A-prime to 12/28 in B-prime.

This grounding failure does not change strict edge correctness under the
current frozen metric, but it shows that the B-prime pipeline path is not yet
reliable for strict verbatim Evidence reproduction. Non-exact predicted KO
source spans are a leading observed risk, but this experiment does not isolate
them as the cause. The decline is the principal development caveat and must
remain visible in any downstream product claim.

Semantic support remained high on acceptable positive graph edges, but that
metric has a different denominator and does not offset the exact-span failure.

## Interpretation

The development result supports the feasibility of passing predicted Knowledge
Objects into Relation Classification without an observed net strict-accuracy
loss on recoverable pairs in this single paired run.

The gap between conditional strict accuracy, 30/36, and end-to-end pipeline
success, 30/38, is explained by two upstream unrecoverable pairs.

The result does not show that predicted and Oracle KO representations are
equivalent. Relation-type and direction error patterns changed, one strict
error was introduced while one was corrected, and exact Evidence grounding
deteriorated substantially.

No field-level causal claim is supported. The experiment is a descriptive,
single-run development diagnostic.

## Frozen Method Scope

The locked reuse evaluation must preserve the development method without
result-driven changes to:

- Entity prompt and model parameters;
- structural normalization and name-matching behavior;
- alignment protocol and manual adjudication rules;
- recoverability definition;
- neutral slot assignment and pair projection;
- Relation prompt, schema, model parameters, and execution order;
- Relation evaluator and Evidence-support adjudication protocol;
- pipeline metrics and failure-locus precedence.

## Locked Reuse Rule

After the repository-level method freeze:

- no alignment, projection, evaluation, or scoring rule may be changed in
  response to locked reuse results;
- A-prime and B-prime must use the frozen model, parameters, prompt, schema,
  batching, and execution order;
- any method change requires a new experiment version and invalidates the
  current locked reuse claim;
- the result must be described as locked reuse of previously seen 002A
  materials, not as a fresh unseen 002B holdout.

## Decision Boundary

This decision authorizes the locked reuse preflight only after the user-managed
repository freeze is complete and the working tree is clean. It does not
authorize a production claim, a stability claim, or immediate product
integration.

Detailed results and denominators are in `development_results.md`.

## Locked-Reuse v0.2 Outcome

The candidate-scoped revision completed all 33 recoverable pair requests in
both matched conditions without retries or endpoint substitutions. Conditional
strict edge accuracy was 25/33 for A-prime and 26/33 for B-prime. No pair moved
from an A-prime strict success to a B-prime strict failure.

Five missing endpoint KOs made seven of the 40 original pairs unrecoverable.
The complete B-prime pipeline therefore achieved 26/40 strict success. Exact
Relation Evidence grounding was 32/35 under B-prime, with three non-exact spans.

This supports conditional predicted-KO representation viability for the current
single paired run, while rejecting any production-readiness, stability, or
generalization claim. Full results are in `locked_reuse_v0_2_results.md`.
