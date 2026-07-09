# Product Definition

**Version:** v1.0 (Frozen)

> Terminology follows `docs/glossary.md`.

---

# Mission

Enable learning continuity by helping STEM students continuously reconnect knowledge across time, courses, and disciplines.

The project treats learning as a continuous process rather than a sequence of isolated interactions with individual documents or courses.

---

# Problem

Knowledge acquired over months or years gradually becomes disconnected.

As learners progress through increasingly advanced subjects, previously learned concepts fade from active memory, making it difficult to understand how new knowledge relates to existing understanding.

This fragmentation reduces learning efficiency and weakens long-term knowledge integration.

---

# Opportunity

Recent advances in large language models make it increasingly feasible to extract structured knowledge, reason over relationships, and generate evidence-supported explanations.

Rather than replacing human learning, AI can assist learners by making meaningful learning connections explicit.

---

# Core Value Proposition

The system supports **Learning Continuity** by reconstructing meaningful learning connections instead of simply retrieving documents.

Rather than answering isolated questions, the system continuously reconnects newly acquired knowledge with previously learned concepts and explains why those connections matter.

Learning Connections are represented internally as typed Relations.

---

# Product Scope

## In Scope

- Cross-course knowledge connection
- Cross-semester learning continuity
- Knowledge object extraction
- Typed relation discovery
- Evidence-supported learning explanation
- Long-term learning memory

## Out of Scope

### Now

- User interface optimization
- Personalized learning recommendation
- Agent workflows
- Flashcards
- Quiz generation

### Later

- Adaptive review scheduling
- Learning path recommendation
- Multi-modal learning resources
- Personalized tutoring

### Never

This project is not intended to become:

- A document retrieval system
- A note-taking application
- A general-purpose chatbot
- A generic educational content generator

---

# Design Boundary

The system augments human learning.

It does not replace human reasoning, judgment, or understanding.

---

# Minimum Viable Product

The first MVP validates the core AI pipeline.

Capabilities include:

1. Parse course materials.
2. Extract Knowledge Objects.
3. Propose evidence-supported learning connections, represented internally as Connection Hypotheses.
4. Generate evidence-supported learning explanations.

The MVP intentionally focuses on understanding knowledge rather than generating educational content.

---

# Success Criteria

The MVP is considered successful if it can consistently produce:

- Typed knowledge relations
- Evidence-supported explanations
- Cross-course learning connections that are considered useful by human evaluators

Specific evaluation metrics are defined in `evaluation_plan.md`.

## Failure Indicators

- Most proposed connections collapse into fallback `RELATED_TO` relations.
- Evidence cannot justify proposed connections.
- Human reviewers consider connections educationally meaningless.

---

# Product Principles

- Learning before retrieval.
- Continuity before memorization.
- Explain before recommend.
- Evidence before confidence.
- Connection quality over graph size.

---

# Long-term Vision

**Immediate Product Goal**

> Enable Learning Continuity.

**Long-term System Vision**

> Support Knowledge Evolution throughout a learner's educational journey.

Learning Continuity is the immediate objective.

Knowledge Evolution is the long-term capability the system aims to enable.

---

> The system does not attempt to replace human learning. It aims to augment human understanding by making meaningful learning connections explicit.
