# Learning Connection Engine

> Helping STEM students continuously connect knowledge across time, courses, and disciplines.

An AI engineering project that builds a long-term learning memory to discover and explain meaningful knowledge connections rather than simply retrieving documents.

---

## Why

Learning does not happen within a single lecture or a single course.

Students often understand individual concepts but struggle to connect new knowledge with what they learned months—or even years—earlier. As a result, prerequisite knowledge gradually disappears from active memory, making advanced topics increasingly difficult to understand.

This project explores how AI can reconstruct those long-term learning connections instead of acting as another document retrieval system.

---

## What

The Learning Connection Engine focuses on **learning continuity** rather than document retrieval.

Instead of answering:

> "What does this lecture say?"

it aims to answer:

> "How does this concept relate to what I learned before?"

The goal is to continuously build meaningful knowledge connections across:

- Time
- Courses
- Disciplines

---

## How

```text
Course Materials
        │
        ▼
Knowledge Extraction
        │
        ▼
Knowledge Objects
        │
        ▼
Connection Discovery
        │
        ▼
Evidence Generation
        │
        ▼
Learning Explanation
```

The current MVP focuses on validating whether LLMs can reliably discover meaningful learning connections with supporting evidence.

---

## Current Status

Technical Validation currently has the following experiment status:

| Experiment | Capability | Status |
| --- | --- | --- |
| 001 | Knowledge Object Extraction | Completed |
| 002A | Oracle-KO Typed Relation Extraction | Completed |
| 002B-1 | Controlled predicted-KO pipeline coupling | Completed |
| 002B-2 | Candidate Pair Generation under predicted KOs | Completed with partial feasibility |
| 002C | Knowledge Object Resolution / Canonicalization | Completed with limited independent validation |
| 003 | Learner-relevant Connection Discovery | Closed with negative development Technical Validation results |
| 004 | Oracle-conditioned Learning Explanation | 004-0 freeze candidate prepared; downstream product validation remains blocked |

Experiment 002B is complete. The current lecture-local safety path uses
All-Pairs candidate generation because the deterministic Rule-Filtered v0.1
method reduced workload but failed its frozen positive-recall gate. This is a
Technical Validation fallback, not a scalable production design.

Experiment 002C selected Evidence-ID context resolution v0.2.1 for subsequent
Technical Validation after limited independent validation. It is not a
production canonicalizer.

Experiment 003 v0.1 completed candidate-generation and Oracle-canonical
Connection classification validation. Candidate generation retained all 41
overlap-bridge primary positive pairs, but both the one-stage and two-stage
classifiers failed the frozen quality gates. The five disjoint-provenance
compositional positives were diagnostic-only. No validated Connection
Discovery default is selected, and downstream ranking or explanation is not
authorized as product validation.

Experiment 003 v0.2 then evaluated minimal endpoint-linked Evidence windows and
an explicit direct-versus-mediated support contract. The method produced modest
development gains but still failed five of eight frozen criteria: positive
precision was `0.2206`, typed-edge recall was `0.3659`, and semantic Evidence
support was `0.4085`. Experiment 003 is therefore closed without a validated
Connection classifier. This is a scoped negative development result, not a
claim that Connection Discovery is generally impossible. Experiment 004
remains blocked as product validation.

Experiment 004 has begun only as Oracle-conditioned component validation. Its
development input fixes human-validated endpoints, Relation direction, and
Evidence before asking whether a model can produce a faithful and educationally
useful explanation. This work does not unblock the failed Connection Discovery
pipeline.

The user interface is intentionally postponed until the core AI pipeline has been validated.

---

## Repository Structure

```text
docs/
Why was the system designed this way?

experiments/
What engineering assumptions are we validating?

benchmark/
How do we evaluate the system?

src/
How is the system implemented?

assets/
Images and diagrams used throughout the project.
```

---

## Engineering Principles

This repository follows four principles.

1. Product-driven development.
2. Engineering decisions supported by evidence.
3. Validate before scaling.
4. Build reusable AI infrastructure rather than isolated features.

---

## Roadmap

✅ Project Definition

🚧 Technical Validation

⬜ Core Engineering

⬜ MVP

⬜ Evaluation

---

## Vision

The long-term goal is to move beyond AI tools that simply retrieve information.

Instead, this project explores how AI can model the evolution of a learner's knowledge and continuously reconstruct meaningful connections throughout an entire learning journey.
