# Experiment 003 Persistent Error Analysis

**Status:** Final development analysis
**Scope:** Four Oracle-canonical development methods on the same selected
125-pair benchmark

## Purpose

This report compares the one-stage baseline, one-stage Prompt 002, two-stage
direct-edge gate, and endpoint-linked verifier. It identifies failures that
persisted across method changes and separates them from errors recovered or
introduced by the endpoint-linked method.

The benchmark is exhausted development data. These observations may motivate a
future v0.3 method, but they do not support further pair-specific tuning or an
independent generalization claim.

## Persistent Gold-Negative Overconnections

Nineteen primary-negative pairs received an edge under all four methods:

| Pair | Endpoint A | Endpoint B |
| --- | --- | --- |
| `conn_dev_pair_222c986cd9853739` | Gradient Descent | Least Squares Objective |
| `conn_dev_pair_263db2f07078bcd1` | First-Order Taylor Approximation | Initial Value Problem |
| `conn_dev_pair_31fa9b658289ed76` | Maximum Likelihood Estimation | Root-Finding Problem |
| `conn_dev_pair_3b005c7a79510244` | Gradient Descent | Mean Squared Error Formula |
| `conn_dev_pair_3c1d300edac20859` | Score Function | Root-Finding Problem |
| `conn_dev_pair_56bf2cab52cf025c` | Gradient | Score Equation |
| `conn_dev_pair_7ae886fbc9be7241` | Objective Function | Mean Squared Error Formula |
| `conn_dev_pair_8fae4bf3dd480f71` | Gradient | Log-Likelihood |
| `conn_dev_pair_a1e6b8f76fd16f4d` | Root-Finding Problem | Newton Root Update |
| `conn_dev_pair_ad73d420644fe99f` | First-Order Taylor Approximation | Objective Function |
| `conn_dev_pair_be2636a5d8bc8b4c` | Linear Regression | Mean Squared Error Formula |
| `conn_dev_pair_be5dff9ee6b32e1a` | Objective Function | Ridge Regression |
| `conn_dev_pair_c02b6a5def080df9` | First-Order Taylor Approximation | Forward Euler Update |
| `conn_dev_pair_c9da9f7c5ff3c1f6` | Log-Likelihood | Newton's Root-Finding Method |
| `conn_dev_pair_da1c18bdf793236f` | Log-Likelihood | Root-Finding Problem |
| `conn_dev_pair_dcf07ffb792c61d7` | Score Function | Newton's Root-Finding Method |
| `conn_dev_pair_e1603fa09ad3fd48` | Objective Function | Root-Finding Problem |
| `conn_dev_pair_f04767c63a30f18a` | First-Order Taylor Approximation | Gradient Descent Update |
| `conn_dev_pair_fa0a79a76255633a` | Gradient | Root-Finding Problem |

These pairs repeatedly expose the same boundary: the model promotes shared
derivations, participation in one wider method, and mediated chains into direct
edges between the exact endpoints. Narrower Evidence transport did not remove
that semantic overconnection tendency.

## Persistent Wrong Edges On Gold Positives

Twelve primary-positive pairs received a positive edge with the wrong Relation
type or direction under all four methods:

| Pair | Endpoint A | Endpoint B |
| --- | --- | --- |
| `conn_dev_pair_225420587c4177f5` | Gradient Descent | Gradient Descent Update |
| `conn_dev_pair_654033881f94fbf0` | Gradient Descent Update | Step Size |
| `conn_dev_pair_7f5ac4c6e2fe5268` | Gradient | Gradient Descent Update |
| `conn_dev_pair_8404187bbee08589` | Statistical Model | Maximum Likelihood Estimation |
| `conn_dev_pair_855fc91eae345c72` | Hessian Matrix | Newton Optimisation Method |
| `conn_dev_pair_9a51109c78e243ef` | Newton's Root-Finding Method | Derivative |
| `conn_dev_pair_9f008ddde3e426f0` | Maximum Likelihood Estimation | Score Equation |
| `conn_dev_pair_a1259045b6b2d2c7` | Gradient | First-Order Taylor Formula |
| `conn_dev_pair_c9d185b1eedd2c21` | First-Order Taylor Approximation | Local Truncation Error |
| `conn_dev_pair_e848f855de939343` | Ordinary Least Squares | Ridge Regression |
| `conn_dev_pair_ef28d97312ee8970` | Gradient | Newton Optimisation Update |
| `conn_dev_pair_fac1350d8eb9227e` | Score Equation | Newton's Root-Finding Method |

These are not candidate-recall failures. Every method recognized some positive
association but failed the exact typed and directed graph contract. Formula,
method, and concept role boundaries recur, especially around `FORMALIZES`,
`APPLIED_IN`, and `REQUIRES`.

## Prompt 002 To Endpoint-Linked Transitions

The endpoint-linked method did not simply make the earlier output more
conservative:

- it recovered 18 Prompt 002 gold-negative overconnections;
- it introduced 14 new gold-negative overconnections;
- 22 negative overconnections persisted across Prompt 002, two-stage, and
  endpoint-linked methods;
- it corrected three Prompt 002 wrong edges on gold positives;
- it regressed three Prompt 002 strict-correct positive edges;
- it newly rejected nine gold positives as `NO_RELATION`.

The three corrected wrong-positive edges were:

- `conn_dev_pair_623dc620447526e3`;
- `conn_dev_pair_799174f17022eacc`;
- `conn_dev_pair_ea10f05ebcebff54`.

The three regressed Prompt 002 strict-correct positives were:

- `conn_dev_pair_63bb993a9e7b1d30`, wrong direction;
- `conn_dev_pair_bfce59cf0247f59a`, wrong direction;
- `conn_dev_pair_d64d8e658f6dafd8`, rejected after window conflict.

This turnover shows that the v0.2 improvement is not a monotonic repair of a
fixed error set. Local Evidence views change which pairs fail.

## Aggregation Instability

The endpoint-linked method generated 17 conflicting aggregations:

- seven on primary positives, directly reducing recall under fail-closed
  aggregation;
- eight on primary negatives, correctly preventing overconnection;
- two on out-of-schema diagnostic pairs.

Ten conflicts were Relation-type-only disagreements, four were
direction-only, and three involved both type and direction. The conflict rate
was `17/125` (`13.6%`) overall and `17/88` (`19.3%`) among pairs for which at
least one window asserted a direct edge.

The fail-closed aggregator remains the defensible policy because no
window-level Ground Truth supports majority voting, confidence selection, or a
second LLM judge. The conflict rate therefore diagnoses the verifier, not the
deterministic aggregator.

## Research Boundary

Across the ablations, candidate coverage within the overlap-bridge primary
scope and exact Evidence transport were not the dominant bottlenecks. The
persistent failure is deciding whether the exact endpoint pair supports one
direct Relation, then serializing its semantic roles consistently.

A future v0.3 method should separate:

1. direct versus mediated edge classification;
2. semantic endpoint-role prediction;
3. deterministic source/target serialization;
4. exact Evidence materialization.

It should use fresh contrastive supervision and reserve an independent source.
The existing 125 pairs should remain regression and forensic-analysis data
only.
