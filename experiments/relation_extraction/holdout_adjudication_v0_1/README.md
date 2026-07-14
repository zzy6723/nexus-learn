# Relation Holdout Evidence Adjudication

**Status:** Completed  
**Benchmark:** `relations_holdout_v0_1.json`  
**Freeze commit:** `5fd7e2b9ea02fad6a15f2a1a703193bd7d606c7d`  
**Completed:** 2026-07-13

---

# Scope

This adjudication asks only whether each complete predicted Evidence snapshot
semantically supports its predicted edge. It does not decide whether the edge is
the preferred gold edge, and it does not reinterpret the frozen ground truth.

Aggregate evaluation metrics were not inspected before the decisions were
completed. The two runs were reviewed as `Review A` and `Review B` under one
semantic-support standard. This is procedural single-reviewer blinding, not an
independent double-blind annotation study.

The run mapping is stored separately in `alias_mapping.json`. Human decisions
were mechanically bound to the exact pending snapshots before evaluator reuse.

---

# Decision Standard

Evidence is `supported` when the selected spans, read together, establish the
complete predicted Relation without relying on an unresolved reference to an
omitted sentence.

A mathematical expression may identify an object without repeating its name
when its notation and complete form make the predicted Relation unambiguous.
Generic formulas or unresolved phrases such as "this problem" and "it" are not
enough when they could refer to multiple objects or methods.

---

# Decisions

| Pair | Review A | Review B | Basis |
| --- | --- | --- | --- |
| `rel_holdout_003` | supported | supported | The span names path cost and gives its sum formula. |
| `rel_holdout_007` | not supported | not supported | "This problem" is not resolved to the shortest-path problem. |
| `rel_holdout_008` | supported | supported | The log-likelihood equation is unambiguous; Review B also names it. |
| `rel_holdout_011` | supported | supported | The root-finding condition and equation are directly connected. |
| `rel_holdout_015` | supported | supported | The explicit Euler update unambiguously expresses the method; Review B also names it. |
| `rel_holdout_017` | supported | supported | A minimum-cost path directly depends on path cost. |
| `rel_holdout_019` | supported | supported | The probability-product expression is the likelihood formula; Review B also names it. |
| `rel_holdout_023` | supported | supported | The Newton iteration is distinctive; Review B also names the method. |
| `rel_holdout_025` | supported | supported | The span explicitly identifies the relaxation update. |
| `rel_holdout_033` | supported | supported | The MLE argmax expression identifies and formalizes the method. |
| `rel_holdout_037` | supported | supported | The corrected predictor-corrector equation unambiguously gives the Heun update; Review B also names it. |
| `rel_holdout_039` | not supported | supported | Review A uses unresolved "It" plus a generic midpoint formula; Review B explicitly names bisection. |

---

# Outcome

Review A:

- pending snapshots: 12;
- supported: 10;
- not supported: 2;
- remaining pending: 0;
- evaluation status: `final`.

Review B:

- pending snapshots: 12;
- supported: 11;
- not supported: 1;
- remaining pending: 0;
- evaluation status: `final`.

These ratios describe only manually pending Evidence cases. They are not
all-Evidence semantic-support accuracy because exact gold-evidence matches can be
resolved automatically and other predictions may not enter this denominator.

No stale or unused adjudication decision was reported.
