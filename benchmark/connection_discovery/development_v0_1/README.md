# Connection Discovery Development Source v0.1

**Status:** Draft before Connection annotation
**Role:** Experiment 003 development

This authored source is designed for canonical-level cross-lecture Connection
Discovery. It contains six lectures in three course sequences. Repeated
Knowledge Objects are intentional and are represented once in the Oracle
canonical inventory with multiple mention records.

The source is development data. It must not later be presented as an
independent validation source.

## Course Sequences

- `mathematical_optimisation`: multivariable derivatives, then unconstrained
  optimisation;
- `statistical_learning`: maximum likelihood, then least-squares learning;
- `numerical_methods`: nonlinear root finding, then explicit ODE methods.

## Artifact Boundary

- `source_manifest.json` declares course, topic, and temporal metadata.
- `oracle_canonical_inventory.json` defines canonical endpoints and exact
  mention provenance.
- `pair_universe.json` is generated deterministically and contains no gold
  Connection labels.

Connection Ground Truth and Evidence catalogs are added only in 003-0C after
the source and universe pass structural review.
