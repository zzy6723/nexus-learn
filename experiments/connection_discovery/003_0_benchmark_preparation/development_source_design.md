# 003-0B Development Source Design

**Status:** Structurally complete; pending repository freeze before annotation
**Source:** `benchmark/connection_discovery/development_v0_1`

## Design

The development source contains six authored lectures arranged as three
two-lecture course sequences:

| Course | Earlier lecture | Later lecture |
| --- | --- | --- |
| Mathematical Optimisation | Multivariable Derivatives | Unconstrained Optimisation |
| Statistical Learning | Maximum Likelihood | Least Squares and Regularisation |
| Numerical Methods | Nonlinear Root Finding | Explicit ODE Integration |

This structure supports both same-course cross-lecture and cross-course
Connections. Course, topic, and sequence values are explicit source metadata;
they are not inferred from filenames during evaluation.

## Canonical Inventory

The Oracle inventory contains:

- 29 canonical Knowledge Objects;
- 44 exact mention records;
- all three frozen KO types;
- repeated canonical objects across lectures and courses;
- distinct Newton root-finding and Newton optimisation methods;
- formula objects kept separate from the methods or concepts they formalize.

The inventory is authored Oracle input for 003-1 and 003-2. It is not the
output of canonicalization v0.2.1. Predicted-canonical behavior remains a
separate 003-3 condition.

## Pair Universe

The deterministic generator produced:

| Measure | Count |
| --- | ---: |
| All unique unordered canonical pairs | 406 |
| Eligible cross-lecture pairs | 387 |
| Excluded same-lecture-only pairs | 19 |
| Disjoint-provenance pairs | 262 |
| Overlap-bridge pairs | 125 |
| Same-course cross-lecture pairs | 139 |
| Pairs with a cross-course combination | 330 |

Scope flags are not mutually exclusive when a canonical object appears in
multiple courses. For example, a pair can share a course through one mention
combination and also have a cross-course combination through another. The
exclusive provenance stratum remains either `disjoint_provenance` or
`overlap_bridge`.

## Intended Semantic Coverage

The authored material contains explicit bridge families suitable for later
annotation:

- derivative objects used by first- and second-order optimisation;
- Taylor approximation used in optimisation reasoning and Forward Euler;
- Gradient Descent used in least-squares learning;
- Newton root finding used inside maximum likelihood estimation;
- score equations viewed as root-finding problems;
- formula-to-method and formula-to-concept formalization;
- Damped Newton and Ridge Regression extension relations.

It also intentionally contains schema-gap candidates:

- conditional equivalence between ordinary least squares and maximum
  likelihood estimation;
- instance-like relationships between a score equation and a root-finding
  problem;
- model-instance relationships around Gaussian linear regression.

These must be annotated as schema gaps when the current Relation schema cannot
state them faithfully. They must not be forced into `RELATED_TO`.

## Boundary

The bridge list is a source-design audit, not exhaustive Connection Ground
Truth. Every one of the 387 pairs still requires a frozen category decision in
003-0C. No model output has been generated or inspected.

## Decision

The source meets the structural 003-0B targets and is selected for development
annotation after repository freeze. It is not an independent validation source.
