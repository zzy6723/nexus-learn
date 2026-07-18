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
| 002C | Knowledge Object Resolution / Canonicalization | 002C-0 completed; 002C-1 formal runs pending |
| 003 | Learner-relevant Connection Discovery | Not started |
| 004 | Learner-facing Connection Explanation | Not started |

Experiment 002B is complete. The current lecture-local safety path uses
All-Pairs candidate generation because the deterministic Rule-Filtered v0.1
method reduced workload but failed its frozen positive-recall gate. This is a
Technical Validation fallback, not a scalable production design.

Experiment 002C-0 has a frozen 39-mention cluster-level development benchmark
and strict completion checks. The 002C-1 Exact and Alias-Aware deterministic
methods have passed synthetic implementation tests; their clean-state formal
development runs are the next gate. Learner-facing Connection discovery and
ranking remain Experiment 003.

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
