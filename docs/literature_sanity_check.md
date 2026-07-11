# Literature Sanity Check

**Status:** Draft
**Version:** v0.1
**Last Updated:** 2026-07-11
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Purpose

This document evaluates whether the core technical assumptions behind the Learning Connection Engine are sufficiently supported by existing work to justify implementation experiments.

It is not intended to be:

* A systematic literature review
* A complete survey of educational AI
* A claim of academic novelty
* A substitute for empirical validation
* A final specification of the system architecture

The purpose of this sanity check is to identify which project assumptions are:

* Supported by existing evidence
* Challenged by existing evidence
* Still open and requiring project-specific validation

---

# Review Question

Do existing research results make the core technical assumptions behind the Learning Connection Engine sufficiently plausible to justify targeted implementation experiments?

More specifically:

> Can STEM learning materials be transformed into structured Knowledge Objects and used to propose typed, evidence-supported, learning-relevant Connections across courses and time?

---

# Design Assumptions

This sanity check evaluates five design assumptions.

## A1. Knowledge Extraction

STEM course materials can be transformed into sufficiently stable and structured Knowledge Objects.

The extraction process should identify meaningful educational entities rather than arbitrary text chunks.

---

## A2. Typed Relation Discovery

Educational relationships can be represented using a constrained Relation schema.

The system should distinguish meaningful relation types such as `REQUIRES`, `APPLIED_IN`, `EXTENDS`, and `CONTRASTS_WITH`, rather than relying primarily on semantic similarity or the fallback `RELATED_TO`.

---

## A3. Evidence Grounding

Proposed Connections can be supported by traceable Evidence from source materials.

A Connection should not be accepted solely because an LLM considers two Knowledge Objects related.

---

## A4. Learner-specific State

Learner State should be represented explicitly and should remain separable from general-purpose language-model reasoning.

The system should not assume that an LLM alone can reliably estimate or maintain a learner's knowledge state.

---

## A5. Cross-context Learning Relevance

Connections across courses, semesters, or disciplines can provide educational value beyond lexical or semantic similarity.

This is the central product-level assumption of the project and requires direct human evaluation.

---

# Scope

This sanity check covers six research directions:

1. Educational Knowledge Graphs and curriculum representation
2. Concept and Knowledge Object extraction
3. Prerequisite and typed Relation discovery
4. Evidence retrieval and grounded generation
5. Learner State and knowledge tracing
6. Long-term and graph-based memory

The following topics are outside the scope of this version:

* General-purpose AI tutoring
* User-interface design
* Quiz and flashcard generation
* Full learning-path recommendation
* Commercial product comparison
* Long-term pedagogical effectiveness
* Production-scale system architecture

These topics may be examined later if they become relevant to the validated core pipeline.

---

# Search Protocol

**Search cutoff:** 2026-07-11

## Sources

Publication venues and repositories considered include:

* arXiv
* ACM Digital Library
* ACL Anthology
* Journal of Educational Data Mining
* Educational Data Mining proceedings
* Artificial Intelligence in Education proceedings
* Learning Analytics and Knowledge proceedings
* SIGCSE proceedings

Discovery indexes may include:

* Google Scholar
* Semantic Scholar

---

## Representative Query Groups

* `"educational knowledge graph large language model"`
* `"curriculum knowledge graph benchmark"`
* `"course concept extraction LLM"`
* `"educational concept extraction course materials"`
* `"prerequisite relation extraction education"`
* `"typed relation extraction educational knowledge graph"`
* `"learner state knowledge tracing LLM"`
* `"long-term LLM memory"`
* `"retrieval augmented generation evidence grounding"`
* `"GraphRAG educational knowledge graph"`

---

## Inclusion Criteria

A work is included when it directly informs at least one Design Assumption and provides one or more of the following:

* A relevant system architecture
* An extraction or Relation-discovery method
* An educational dataset or benchmark
* An empirical evaluation
* A useful negative or failure result
* A reusable evaluation methodology
* A design pattern relevant to the MVP

---

## Exclusion Criteria

A work is excluded when it:

* Discusses educational AI only at a general conceptual level
* Focuses exclusively on educational content generation
* Provides no technical or empirical detail
* Duplicates a more complete version of the same work
* Has no clear implication for the core pipeline

---

## Selection Policy

This document uses representative works rather than exhaustive coverage.

Preference is given to:

1. Work directly aligned with the MVP
2. Work containing empirical evaluation
3. Work with available datasets, code, or evaluation procedures
4. Peer-reviewed work where suitable
5. Recent preprints when they address emerging system designs not yet represented in established literature

A work appearing in this document should not be interpreted as an endorsement of all its claims or methods.

---

# Representative Evidence Matrix

| Work                                                                                                                       | Status                       | Assumptions | Relevant Evidence                                                                                                                            | Design Implication                                                                                      | Limitation for This Project                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| K12-KGraph: A Curriculum-Aligned Knowledge Graph for Benchmarking and Training Educational LLMs [1]                        | Preprint, 2026               | A1, A2, A3  | Presents a curriculum-aligned graph with explicit node and Relation types and constructs graph-derived benchmark tasks                       | Reuse ideas for typed curriculum representation, source-linked Evidence, and benchmark construction     | Focuses on K–12 textbooks rather than heterogeneous university STEM materials or learner-specific continuity      |
| ACE: AI-Assisted Construction of Educational Knowledge Graphs with Prerequisite Relations [2]                              | Peer-reviewed, 2024          | A2, A3      | Ranks candidate prerequisite relations for expert review and updates the graph iteratively from accepted labels                              | Treat proposed Relations as hypotheses, rank candidates, and include human validation                   | Concentrates mainly on prerequisite relations rather than a broader Relation schema                               |
| Examining GPT's Capability to Generate and Map Course Concepts and Their Relationship [3]                                  | Preprint, 2025               | A1, A2      | Evaluates prompt-based generation of course concepts and prerequisite relationships using course information with different levels of detail | Supports a controlled LLM baseline for concept and Relation extraction                                  | Does not establish stable, source-grounded extraction from heterogeneous full-length STEM materials               |
| Beyond Static Question Banks: Dynamic Knowledge Expansion via LLM-Automated Graph Construction and Adaptive Generation [4] | Preprint, 2026               | A1, A2, A4  | Uses schema-constrained LLM extraction, automated hierarchical graph construction, learner mastery information, and graph-based retrieval    | Borrow modular separation between graph construction, learner state, retrieval, and generation          | Optimized for personalized exercise generation rather than persistent cross-course learning Connections           |
| Hey Chat, Can You Teach Me? Structuring Socratic Dialogue for Human Learning in the Wild [5]                               | Preprint, 2026               | A2, A4      | Separates curriculum sequencing, dialogue generation, and learner-state inference; uses an explicit prerequisite graph                       | Avoid assigning curriculum structure, learner modeling, and explanation to one monolithic LLM component | Tutor-centered and session-oriented rather than focused on Long-term Learning Memory                              |
| Faster, Cheaper, More Accurate: Specialised Knowledge Tracing Models Outperform LLMs [6]                                   | Preprint, 2026               | A4          | Reports that specialized knowledge-tracing models outperform evaluated LLMs on student-response prediction while being faster and cheaper    | Keep Learner State modular and do not use the LLM as a universal learner model                          | Evaluates response prediction, not Knowledge Object extraction or Connection quality                              |
| Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks [7]                                                       | Peer-reviewed, 2020          | A3          | Demonstrates generation supported by retrieved external, non-parametric knowledge                                                            | Reuse retrieval and provenance patterns for locating Evidence                                           | Retrieves information for generation but does not construct educational Connections or model learning continuity  |
| From Local to Global: A Graph RAG Approach to Query-Focused Summarization [8]                                              | Preprint, 2024               | A2, A3      | Constructs an entity graph and community summaries to support corpus-level sensemaking                                                       | Graph-based organization may help retrieve multi-source Evidence and reason across materials            | The graph is a document-retrieval index, not a learner-centered knowledge representation                          |
| MemGPT: Towards LLMs as Operating Systems [9]                                                                              | Preprint, 2023; revised 2024 | A4          | Introduces hierarchical memory management for long documents and multi-session conversations                                                 | Borrow separation between active context and persistent memory                                          | Provides memory management but does not define learner-specific knowledge semantics or educational memory quality |

---

# Findings

## Supported

The reviewed work provides support for the following conclusions.

### Structured educational knowledge representation is feasible

Educational concepts, skills, prerequisites, curricular locations, and other educational entities can be represented using typed graph structures.

Existing systems and benchmarks provide useful examples of:

* Explicit node types
* Explicit Relation types
* Curriculum alignment
* Prerequisite structure
* Graph-derived evaluation tasks
* Human-assisted graph construction

This supports proceeding with a constrained Knowledge Object and Relation schema.

---

### LLM-assisted Knowledge Extraction warrants direct experimentation

Existing work indicates that LLMs can assist with:

* Generating course concepts
* Extracting structured educational entities
* Proposing prerequisite relationships
* Producing schema-constrained graph outputs

However, the quality of these outputs depends on:

* Available source information
* Prompt structure
* Schema constraints
* Domain complexity
* Evaluation methodology

The literature therefore supports experimentation, but not an assumption of reliable extraction.

---

### Candidate Relations should be validated rather than accepted as truth

Human-assisted graph-construction work demonstrates the value of:

* Ranking candidate Relations
* Reviewing high-value candidates
* Updating the graph from accepted decisions
* Using existing graph structure to reduce later review effort

This aligns with the project's definition of a `Connection Hypothesis`.

Connection Discovery should remain hypothesis generation rather than truth generation.

---

### Explicit structure can outperform monolithic LLM behavior

Recent educational systems suggest that curriculum modeling, learner-state estimation, sequencing, dialogue, and generation should not automatically be assigned to a single general-purpose LLM.

This supports a modular pipeline in which:

* LLMs assist with extraction and explanation
* Relations are constrained by a schema
* Learner State remains a separate component
* Human or automated validation is applied before acceptance

---

### Retrieval and memory systems provide reusable infrastructure patterns

RAG, GraphRAG, and long-term memory systems provide relevant patterns for:

* External Evidence retrieval
* Provenance
* Persistent information storage
* Context management
* Cross-document aggregation

These methods can support the project infrastructure.

They do not, by themselves, solve Learning Continuity.

---

## Challenged

The reviewed work challenges several potentially unsafe assumptions.

### An LLM should not be treated as a universal learner model

Specialized knowledge-tracing models may be more suitable than general-purpose LLMs for prediction-based learner modeling.

The project should therefore avoid embedding learner-state estimation irreversibly inside an LLM prompt or generation pipeline.

---

### Semantic similarity is insufficient for Connection quality

Two Knowledge Objects may be textually or semantically similar without having a meaningful learning relationship.

The project must distinguish:

* Topic similarity
* General relatedness
* Prerequisite dependency
* Application
* Extension
* Contrast
* Genuine learning relevance

A large graph with many weak `RELATED_TO` edges would not demonstrate success.

---

### Long-term conversational memory is not Long-term Learning Memory

Remembering prior messages, facts, or documents does not automatically represent:

* What a learner understands
* How Knowledge Objects relate
* Which Connections have been validated
* How knowledge changes over time
* Which prior concepts are useful for current learning

Long-term Learning Memory requires project-specific semantics beyond generic memory storage.

---

### More retrieval does not establish educational usefulness

Evidence retrieval may improve grounding, but retrieved Evidence does not prove that a proposed Connection is useful for learning.

Evidence quality and learning relevance must be evaluated separately.

---

# Open Assumptions

The selected literature does not directly validate the following assumptions.

## Stable extraction across university STEM subjects

It remains unknown whether a shared Knowledge Object schema can be applied consistently across materials from domains such as:

* Calculus
* Linear algebra
* Probability
* Optimization
* Machine learning
* Physics

Different subjects may require different object types or extraction granularity.

---

## Reliable distinction between Relation types

It remains unknown whether the proposed Relation types can be separated consistently.

Potential confusion includes:

* `REQUIRES` versus `APPLIED_IN`
* `EXTENDS` versus general relatedness
* `CONTRASTS_WITH` versus simple difference
* High-quality typed Relations versus `RELATED_TO`

This must be tested directly.

---

## Evidence sufficiency

It remains unknown what amount and type of Evidence is sufficient to justify a Connection Hypothesis.

Possible Evidence requirements include:

* A source document identifier
* Page, slide, section, or timestamp
* A directly quoted source span
* Evidence from both connected Knowledge Objects
* A logical explanation linking the Evidence to the proposed Relation

The Evidence protocol should be defined before Relation experiments are evaluated.

---

## Cross-course learning relevance

The selected literature does not establish that automatically generated cross-course Connections consistently help learners understand new material.

This cannot be inferred from:

* Extraction accuracy
* Graph completeness
* Embedding similarity
* Relation classification accuracy
* Retrieval relevance alone

It requires direct human judgment of educational usefulness.

---

## Longitudinal learner value

The selected literature does not establish that maintaining Connections over months or years produces Learning Continuity.

This remains a long-term product hypothesis and is outside the first technical-validation cycle.

---

# Design Implications

| Finding                                                            | Current Design Decision                                         | Required Validation                                                               |
| ------------------------------------------------------------------ | --------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| LLM-assisted concept extraction is plausible but input-sensitive   | Begin with a constrained Knowledge Object schema                | Compare extraction quality across multiple STEM courses                           |
| Educational graph construction benefits from expert feedback       | Represent outputs as Connection Hypotheses                      | Record human acceptance, rejection, and refinement                                |
| Unrestricted relation generation may create weak graphs            | Use a small Relation whitelist                                  | Evaluate confusion between Relation types and fallback frequency                  |
| Source retrieval can support grounding                             | Store traceable Evidence separately from generated explanations | Evaluate Evidence correctness, coverage, and sufficiency                          |
| General-purpose LLMs are not universal learner models              | Keep Learner State modular                                      | Postpone full learner modeling until the core Connection pipeline is validated    |
| Long-term memory infrastructure does not define learning semantics | Separate memory storage from the conceptual model               | Define what is persisted only after Knowledge Objects and Relations are validated |
| Semantic similarity does not establish learning value              | Evaluate learning relevance independently                       | Conduct human review of cross-course Connection usefulness                        |
| Existing work does not validate the full Learning Continuity claim | Limit the MVP claim to technical feasibility                    | Do not claim improved long-term learning during the initial validation phase      |

---

# Decisions for Technical Validation

Based on this sanity check, the project should proceed with the following decisions.

## 1. Begin with Knowledge Object Extraction

The first experiment should test whether heterogeneous STEM materials can be transformed into stable Knowledge Objects.

It should evaluate:

* Missing objects
* Unsupported objects
* Duplicate objects
* Type errors
* Boundary and granularity inconsistency
* Variation across subjects
* Variation across repeated runs

---

## 2. Use a constrained schema

The project should not begin with unrestricted graph generation.

Initial experiments should use:

* A limited set of Knowledge Object types
* A limited Relation whitelist
* Explicit JSON output schemas
* Source anchors
* Validation rules

Schema changes should be recorded through the relevant ADR.

---

## 3. Separate extraction from Connection Discovery

Knowledge Object Extraction and Connection Discovery should be evaluated as separate stages.

This allows the project to distinguish:

* Object extraction failure
* Candidate-generation failure
* Relation-typing failure
* Evidence failure
* Explanation failure

---

## 4. Treat every generated Connection as a hypothesis

Generated Connections should not be added directly to the accepted knowledge structure.

Each proposal should retain:

* Source and target Knowledge Objects
* Proposed Relation type
* Supporting Evidence
* Generated explanation
* Confidence or ranking information, if used
* Validation status

---

## 5. Evaluate Evidence separately from explanation quality

A fluent explanation may still rely on insufficient or incorrect Evidence.

The evaluation should distinguish:

* Whether the Evidence exists
* Whether it is correctly attributed
* Whether it supports the proposed Relation
* Whether the explanation accurately represents that Evidence
* Whether the Connection matters for learning

---

## 6. Postpone full Learner State implementation

Learner State is relevant to the long-term vision but is not required to validate the initial Knowledge Extraction and Connection Discovery pipeline.

The first technical-validation cycle should define interfaces for future Learner State integration without committing to a detailed implementation.

---

# Open Questions

1. Which Knowledge Object types are sufficiently stable for `ADR-003`?

2. Can a shared extraction schema work across calculus, linear algebra, probability, optimization, machine learning, and physics?

3. What extraction granularity produces useful Connections without creating excessive duplication?

4. Which Relations are reliably distinguishable from the fallback `RELATED_TO`?

5. What minimum source information must be stored for Evidence to be considered traceable?

6. Must valid Connection Evidence reference both Knowledge Objects, or can one source establish the Relation?

7. Can learning relevance be evaluated independently from semantic similarity?

8. How should human reviewers distinguish an interesting Connection from an educationally useful Connection?

9. How should disagreements between human reviewers be recorded?

10. Which components should remain deterministic, and which should use LLM generation?

11. When should accepted Knowledge Objects and Connections be merged across different courses?

12. What information, if any, should enter Long-term Learning Memory during the MVP?

---

# Sanity Check Outcome

**Outcome:** Conditional Go

The reviewed work provides sufficient evidence that the individual building blocks of the proposed system are technically plausible.

In particular:

* Structured educational knowledge representations are feasible.
* LLM-assisted concept and Relation extraction warrants controlled experimentation.
* Schema constraints and human review are appropriate for educational graph construction.
* Retrieval systems provide reusable patterns for Evidence grounding.
* Long-term memory systems provide reusable context-management patterns.
* Learner State should remain modular rather than being delegated entirely to a general-purpose LLM.

However, the central product assumption remains unvalidated:

> Automatically proposed cross-course Connections are not yet known to be consistently useful for supporting Learning Continuity.

The project should therefore proceed to Technical Validation, beginning with:

1. Knowledge Object extraction across heterogeneous STEM materials
2. Typed Connection Hypothesis generation
3. Evidence traceability
4. Human evaluation of learning relevance

This sanity check supports experimentation.

It does not justify:

* Freezing a production architecture
* Claiming that the full system is technically solved
* Claiming academic novelty
* Claiming improved learning outcomes
* Claiming that Learning Continuity has already been validated

---

# References

[1] Liang, H., Lin, Q., Han, Z., Ma, X., Wong, Z. H., Qiang, M., Sun, L., and Zhang, W. (2026). *K12-KGraph: A Curriculum-Aligned Knowledge Graph for Benchmarking and Training Educational LLMs*. arXiv:2605.09635.

[2] Aytekin, M. C., and Saygın, Y. (2024). *ACE: AI-Assisted Construction of Educational Knowledge Graphs with Prerequisite Relations*. Journal of Educational Data Mining, 16(2), 85–114.

[3] Yang, T., Ren, B., Gu, C., He, T., Ma, B., and Konomi, S. (2025). *Examining GPT's Capability to Generate and Map Course Concepts and Their Relationship*. arXiv:2504.08856.

[4] Wang, Y., Wei, T., Li, Q., and Zeng, L. (2026). *Beyond Static Question Banks: Dynamic Knowledge Expansion via LLM-Automated Graph Construction and Adaptive Generation*. arXiv:2602.00020.

[5] Tio, S., Sinha, A., and Varakantham, P. (2026). *Hey Chat, Can You Teach Me? Structuring Socratic Dialogue for Human Learning in the Wild*. arXiv:2606.11744.

[6] Bhattacharyya, P., Mitton, J., Abboud, R., and Woodhead, S. (2026). *Faster, Cheaper, More Accurate: Specialised Knowledge Tracing Models Outperform LLMs*. arXiv:2603.02830.

[7] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., and Kiela, D. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. Advances in Neural Information Processing Systems, 33.

[8] Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A., Truitt, S., and Larson, J. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*. arXiv:2404.16130.

[9] Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., and Gonzalez, J. E. (2023). *MemGPT: Towards LLMs as Operating Systems*. arXiv:2310.08560.
