# Literature Sanity Check

**Status:** Draft  
**Version:** v0.1  
**Last Updated:** 2026-07-10  
**Owner:** Project

Terminology follows `docs/glossary.md`.

---

# Purpose

This document checks whether the core design direction of the project is technically and academically plausible.

It is not a complete literature review. Its purpose is to test whether existing work supports, challenges, or leaves open the design assumptions behind the Learning Connection Engine.

The document should remain concise. It should guide engineering decisions rather than become a general paper summary.

---

# Review Question

Can current AI systems extract and structure STEM learning knowledge in a way that supports typed, evidence-supported, cross-course learning connections over time?

---

# Scope

This sanity check focuses on five research directions.

1. Educational Knowledge Graphs
2. Concept and Knowledge Object Extraction
3. Prerequisite and Relation Discovery
4. Learner State and Knowledge Tracing
5. Long-term Memory, RAG, and Graph-based Retrieval

The goal is not to prove that the project is unique. The goal is to understand which parts of the system are supported by existing work and which assumptions still require validation.

---

# Search Protocol

**Search cutoff:** 2026-07-10

Primary source types targeted in this first pass:

- arXiv
- ACM Digital Library
- ACL Anthology
- Journal of Educational Data Mining
- AIED / EDM / LAK / SIGCSE proceedings where relevant
- Project pages and released datasets associated with papers

Representative query groups:

- `educational knowledge graph large language models`
- `course concept extraction LLM`
- `prerequisite relation extraction education`
- `learner state knowledge tracing LLM`
- `LLM memory graph retrieval`
- `GraphRAG education knowledge graph`
- `curriculum knowledge graph educational LLM benchmark`

This is a living search protocol rather than a claim of exhaustive coverage. New papers should be added when they change the project position, affect the benchmark design, or challenge an engineering assumption.

---

# Evaluation Matrix

| Work | Direction | Supports Which Module | What We Borrow | Limitation for This Project |
| --- | --- | --- | --- | --- |
| [K12-KGraph: A Curriculum-Aligned Knowledge Graph for Benchmarking and Training Educational LLMs](https://arxiv.org/abs/2605.09635) | Educational KG / Benchmark | Knowledge Objects, Relations, Benchmark | Curriculum-aligned node and relation schema; graph-derived benchmark families | K-12 focused; not centered on long-term learner continuity across university STEM courses |
| [Hey Chat, Can You Teach Me? Structuring Socratic Dialogue for Human Learning in the Wild](https://arxiv.org/abs/2606.11744) | AI tutoring / Curriculum sequencing | Learner State, prerequisite graph, sequencing | Explicit curriculum structure separated from dialogue generation | Tutor-centered; the main product goal is not Learning Continuity memory |
| [Dynamic Knowledge Expansion via LLM-Automated Graph Construction](https://arxiv.org/html/2602.00020v1) | Educational KG + learner-aware GraphRAG | KG construction, learner-aware retrieval | Schema-constrained graph construction and learner-aware reasoning | Optimized for exercise generation, not connection explanation across prior learning |
| [Faster, Cheaper, More Accurate: Specialised Knowledge Tracing Models Outperform LLMs](https://arxiv.org/abs/2603.02830) | Knowledge Tracing | Learner State | Warning that learner modeling should not be delegated blindly to general LLMs | Focuses on response prediction rather than learning connection explanation |
| [ACE: AI-Assisted Construction of Educational Knowledge Graphs with Prerequisite Relations](https://jedm.educationaldatamining.org/index.php/JEDM/article/view/737) | Educational KG | Prerequisite relation discovery | Human-in-the-loop validation for prerequisite relations | Focuses primarily on prerequisite relations, while this project needs a broader relation schema |
| [Examining GPT's Capability to Generate and Map Course Concepts and Their Relationship](https://arxiv.org/abs/2504.08856) | Course concept extraction | Knowledge Extraction, Relation Extraction | Prompt-based concept and relation generation from course information | Course-selection oriented; not designed as a learner-specific long-term memory |
| [Concept Extraction and Prerequisite Relation Learning from Educational Data](https://ojs.aaai.org/index.php/AAAI/article/view/5033) | Concept extraction / Prerequisite learning | Knowledge Extraction, Relation Extraction | Separating concept extraction from prerequisite relation learning | Earlier non-LLM pipeline; does not directly address evidence-supported explanations |
| [Deep Knowledge Tracing](https://arxiv.org/abs/1506.05908) | Knowledge Tracing | Learner State | Sequential modeling of learner knowledge over time | Models performance prediction, not explicit knowledge connections |
| [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) | Long-term memory | Long-term Learning Memory | Memory tiering and context management for long-running interactions | Not education-specific; memory is conversation/document oriented rather than knowledge-connection oriented |
| [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) | Agent memory / Reflection | Long-term Memory | Observation, memory, reflection, and retrieval as separate components | Simulates agents rather than modeling a learner's knowledge structure |
| [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) | Retrieval / Grounding | Evidence Retrieval | External non-parametric memory and provenance-aware generation | Retrieves documents or passages; does not itself reconstruct learning connections |

---

# Preliminary Findings

Existing work supports several building blocks of this project.

- LLMs can assist with concept extraction and course-level relation generation.
- Educational Knowledge Graphs are a mature representation for concepts, prerequisites, curriculum structure, and learning resources.
- Explicit curriculum or graph structure improves educational AI systems compared with unstructured chat alone.
- Learner State should be modeled carefully; current evidence suggests that general LLMs are not a universal replacement for specialized learner modeling.
- RAG and memory systems provide useful patterns for grounding and long-term context, but retrieval alone does not solve Learning Continuity.

Existing work also highlights the main risk.

- A system can easily become a document retrieval tool, a generic tutoring chatbot, or a graph construction project without actually producing useful learning connections.

---

# Design Implications

The project should not begin with a general chatbot, a flashcard generator, or a document retrieval interface.

The first technical validation should test whether STEM learning materials can be converted into stable Knowledge Objects that are useful for later Connection Discovery.

Connection Discovery should be treated as hypothesis generation, not truth generation.

Evidence and human evaluation should be introduced early, even if the first experiment is small.

---

# Implications for Experiment 001

Experiment 001 should validate Knowledge Object extraction before relation discovery.

The experiment should test whether a baseline LLM prompt can extract:

- Meaningful educational entities rather than chunks or headings
- Stable object names and aliases
- A small controlled set of object types
- Source spans that ground each extracted object in the input material

Experiment 001 should not attempt to generate Relations, Connections, or Connection Hypotheses.

---

# Open Questions

1. Which Knowledge Object types are stable enough for ADR-003?
2. Can LLM extraction remain consistent across calculus, linear algebra, and optimisation materials?
3. What source grounding is sufficient before Relation Discovery?
4. Which relation types are reliably distinguishable from fallback `RELATED_TO`?
5. How should Learner State be represented without prematurely committing to a specific mastery model?

---

# Maintenance Rules

- Add a paper only if it changes a design assumption, supports a module, or challenges the project boundary.
- Prefer tables over long paper summaries.
- Avoid claiming that no prior work exists.
- Use this document to inform experiments, ADRs, and the evaluation plan.
