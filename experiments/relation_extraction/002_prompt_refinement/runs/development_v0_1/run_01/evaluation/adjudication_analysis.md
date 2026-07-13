# Prompt 002 Evidence Adjudication Analysis

**Run:** `002_prompt_refinement/runs/development_v0_1/run_01`  
**Evaluation status:** `final`  
**Pending snapshots reviewed:** 13  
**Supported:** 12  
**Not supported:** 1  
**Remaining pending:** 0

---

# Decision Boundary

Each decision asks only whether the complete predicted evidence snapshot
semantically supports the corresponding predicted edge. It does not re-evaluate
whether that edge is the preferred gold label, and it does not use aggregate
scores or baseline adjudication decisions.

The exact snapshot bindings and auditable rationales are stored in
`adjudication_resolved.json`.

---

# Pair-Level Decisions

| Pair | Predicted edge | Decision | Analysis |
| --- | --- | --- | --- |
| `rel_dev_004` | First-order Taylor Formula `FORMALIZES` Taylor Approximation | `supported` | The span names the approximation and immediately gives the equation that expresses it. |
| `rel_dev_009` | Eigenvalue Equation `FORMALIZES` Eigenvalue | `supported` | The span states that the corresponding eigenvalue satisfies the displayed equation. |
| `rel_dev_012` | Gradient Descent `REQUIRES` Gradient | `supported` | Gradient Descent is named and its update explicitly contains the gradient, establishing the dependency. |
| `rel_dev_013` | Gradient Descent Update `FORMALIZES` Gradient Descent | `supported` | The method is named directly before its update equation. |
| `rel_dev_014` | Step Size `APPLIED_IN` Gradient Descent | `not_supported` | The span describes step size but refers only to "the method"; no selected span resolves that phrase to Gradient Descent. |
| `rel_dev_016` | Multivariable Chain Rule Formula `FORMALIZES` Chain Rule | `supported` | The text explicitly says the multivariable chain rule can be written as the displayed equation. |
| `rel_dev_019` | Projection Formula `FORMALIZES` Orthogonal Projection | `supported` | The projection operation is described and immediately expressed by the displayed formula. |
| `rel_dev_021` | Normal Equations `FORMALIZES` Least Squares Problem | `supported` | The span states that the least-squares solution satisfies the displayed normal equations, making them a formal solution condition. |
| `rel_dev_024` | Expected Value Formula `FORMALIZES` Expected Value | `supported` | Expected value is named and immediately followed by its discrete formula. |
| `rel_dev_026` | Variance Formula `FORMALIZES` Variance | `supported` | Although the span begins with "It", the displayed `Var(X)` equation unambiguously identifies and defines Variance. |
| `rel_dev_027` | Conditional Probability Formula `FORMALIZES` Conditional Probability | `supported` | The condition and equation provide the defining formula for conditional probability. |
| `rel_dev_029` | Bayes Rule Formula `FORMALIZES` Bayes Rule | `supported` | Bayes' Rule is explicitly named and directly connected to its equation. |
| `rel_dev_041` | Gradient `APPLIED_IN` Gradient Descent | `supported` | The span names Gradient Descent and its update explicitly uses the gradient; one candidate lecture is sufficient under the current cross-lecture evidence protocol. |

---

# Interpretation

The manual adjudication support rate among pending evidence cases is `12/13`
(`0.923`). This is not an all-evidence semantic-support accuracy because exact
gold-evidence matches are auto-resolved and incorrect predicted edges do not enter
this pending set.

Prompt 002 did not fix the self-contained-evidence failure at `rel_dev_014`.
`rel_dev_017` is absent from this adjudication set because its refined predicted
edge is incorrect; that absence must not be interpreted as evidence improvement.
