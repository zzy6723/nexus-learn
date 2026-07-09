# Glossary

**Version:** v1.0 (Frozen)

> This document defines the canonical terminology used throughout the repository.

> This document is normative. If definitions conflict across documents, Glossary takes precedence.

---

# Product Concepts

## Learning Continuity

The ability to continuously reconnect newly acquired knowledge with previously learned concepts across time, courses, and disciplines.

Learning Continuity is the primary product objective.

---

## Knowledge Evolution

The gradual development and refinement of a learner's knowledge structure throughout an extended learning journey.

Knowledge Evolution is the long-term vision enabled by Learning Continuity.

---

# Core Objects

## Knowledge Object

A structured representation of a meaningful educational entity.

Knowledge Objects may participate in Relations and Connections.

Canonical object types are defined in ADR-003.

Evidence belongs to the Connection layer, not to individual Knowledge Objects.

---

## Connection

A user-facing learning link that explains how two or more Knowledge Objects are meaningfully related.

A Connection is presented to learners to improve understanding.

A meaningful Connection must satisfy three conditions:

- Typed
- Evidence-supported
- Learning-relevant

---

## Relation

A typed machine-readable representation of a Connection.

Relations define the system's internal knowledge graph.

Examples include:

- REQUIRES
- APPLIED_IN
- EXTENDS
- CONTRASTS_WITH

`RELATED_TO` is treated as a fallback relation and is not considered a high-quality learning connection.

Canonical relation types are defined in ADR-004.

---

## Evidence

Supporting information used to justify why a Connection exists.

Evidence may include:

- Lecture content
- Mathematical definitions
- Logical dependencies
- Textbook explanations
- Explicit prerequisite relationships

Evidence belongs to the Connection layer.

---

# Learner Concepts

## Learner

The individual whose accumulated knowledge is modeled by the system.

The term "Learner" is used throughout technical documentation, while "Student" is primarily used in product-facing descriptions.

---

## Learner State

The learner-specific representation describing accumulated knowledge and associated states for individual Knowledge Objects.

The exact implementation may evolve as the project develops.

---

## Long-term Learning Memory

A persistent learner-specific representation of Knowledge Objects, Relations, and Learner State.

Rather than storing raw documents, Long-term Learning Memory models how knowledge evolves throughout a learner's educational journey.

---

# Core Capabilities

## Knowledge Extraction

The process of identifying structured Knowledge Objects from educational materials.

---

## Connection Hypothesis

A candidate Connection proposed by the system before validation.

Connection Hypotheses are supported by Evidence and may subsequently be accepted, rejected, or refined through automated evaluation or human review.

---

## Connection Discovery

The process of proposing evidence-supported Connection Hypotheses between Knowledge Objects.

Connection Discovery is the central AI capability of this project.

---

## Learning Explanation

The generation of human-readable explanations describing why a proposed Connection exists and why it matters for learning.

---

# Evaluation Terms

## Ground Truth

Human-annotated reference data used to evaluate extraction quality and connection quality.

---

## Benchmark

A standardized collection of datasets, annotations, evaluation procedures, and evaluation metrics.

---

## Evaluation Protocol

The predefined methodology used to compare experimental results consistently across different iterations.
