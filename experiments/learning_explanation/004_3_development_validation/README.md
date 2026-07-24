# 004-3: Development Validation And Method Selection

**Status:** Not started

Development validation compares:

- deterministic paraphrase lower bound;
- Relation-only LLM no-Evidence control;
- Evidence-grounded LLM method.

Review is snapshot-bound, randomized, and method-blinded. Claim faithfulness is
evaluated before learning value. Only faithfulness-passing explanations receive
learning-value scores.

Method 002 may be selected only if it passes every frozen hard gate, improves
the paired learning-value composite over Baseline 001A, and does not trade
unsupported claims or direction errors for fluent prose. Baseline 001B remains
diagnostic regardless of its score.
