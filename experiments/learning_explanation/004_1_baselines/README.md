# 004-1: Oracle-Connection Explanation Baselines

**Status:** Implementation validated; pending repository freeze and execution

## Baseline 001A

`001a_deterministic_paraphrase` is a deterministic Relation-template lower
bound. It receives only immutable Connection fields, makes no API request, and
uses no Evidence IDs or text.

## Baseline 001B

`001b_relation_only_llm` receives the same immutable Connection fields but no
Evidence IDs or text. It is a no-Evidence hallucination control and cannot be
selected as the Experiment 004 method.

Both baselines use the v0.2 structured output contract with empty
`evidence_refs` arrays. Baseline 001B and Method 002 must later use the same
model and generation parameters.

Formal execution is not authorized until a clean repository commit freezes
this 004-1 implementation.

## Implementation

The shared runner is:

`scripts/run_learning_explanation_baselines.py`

It enforces:

- the 004-0 freeze-manifest and benchmark hash chain;
- a clean repository at the supplied method commit;
- one explanation instance per request for Baseline 001B;
- exact immutable transport fields;
- empty Evidence catalogs and empty output `evidence_refs`;
- no-overwrite behavior;
- raw and parsed failure retention;
- per-instance and aggregate metadata.

The offline suite contains eight tests. It generated the full deterministic
21-instance output and the full 21-request Relation-only dry-run under mocked
repository state, without an external API call.

Formal artifacts have not been created. `implementation_validation.json`
records the validated implementation bindings and keeps
`formal_execution_authorized = false` until the implementation is
repository-frozen.
