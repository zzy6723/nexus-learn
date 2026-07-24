# 004-1: Oracle-Connection Explanation Baselines

**Status:** Not started; blocked on 004-0 repository freeze

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

No execution is authorized until a clean repository commit freezes 004-0.
