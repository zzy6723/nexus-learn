# Learning Explanation Evaluation Protocol

**Status:** Ready for 004-0 freeze review
**Version:** v0.2

## Scope

This protocol evaluates Oracle-conditioned Learning Explanations. It does not
evaluate Connection Discovery or an end-to-end product pipeline.

## Methods

### Baseline 001A: Deterministic Relation Paraphrase

Produce a fixed template from source name, Relation, and target name. It uses no
LLM and establishes a faithful but intentionally shallow lower bound. It
receives immutable Connection fields but no Evidence IDs or Evidence text. All
field-level Evidence references are empty.

### Baseline 001B: Relation-Only LLM

Provide the same immutable Connection fields but no Evidence IDs or Evidence
text. Require the same structured prose fields and empty field-level Evidence
references. This method measures how much plausible explanation and
hallucination arise from Relation semantics and model prior knowledge alone.
It is a diagnostic control and cannot be selected.

### Method 002: Evidence-Grounded Learning Explanation

Provide Oracle endpoints, Relation, and supplied Evidence entries. Require the
structured output defined in `benchmark/learning_explanation_contract.md`.
This is the only selectable Experiment 004 method.

## Evaluation Sequence

1. Validate JSON schema and immutable transport fields.
2. Apply the method-specific Evidence-reference contract.
3. Validate that every cited Evidence ID belongs to the supplied catalog.
4. Materialize Evidence IDs deterministically for Method 002.
5. Blind method identity and randomize review items.
6. Segment substantive claims.
7. Label claim support.
8. Evaluate explanation-level faithfulness.
9. Score learning value only for faithfulness-passing explanations.
10. Resolve `UNRESOLVED` claim decisions.
11. Produce machine-readable metrics, errors, matches, and reviewer artifacts.

## Hard-Gate Metrics

- schema-valid output rate;
- immutable-field accuracy;
- Relation faithfulness rate;
- direction faithfulness rate;
- endpoint faithfulness rate;
- explanation-level Evidence faithfulness rate;
- unsupported claim rate;
- contradiction count;
- exact Evidence-ID validity rate;
- faithfulness-pass rate.

Unsupported claim rate is:

```text
UNSUPPORTED + CONTRADICTED substantive claims
------------------------------------------------
all resolved substantive claims
```

`UNRESOLVED` claims prevent final evaluation until adjudicated.
Evidence-faithfulness metrics are `not_applicable` for Baselines 001A and 001B,
which receive no Evidence. They must not receive an artificial perfect score.

## Secondary Metrics

Only faithfulness-passing explanations enter:

- mean Conceptual Mechanism score;
- mean Learning Relevance score;
- mean Specificity score;
- mean Clarity score;
- pedagogically non-empty rate;
- paired learning-value composite improvement over Baseline 001A.

The learning-value composite for one output is the mean of its Conceptual
Mechanism and Learning Relevance scores. Paired improvement is computed per
Connection instance before averaging.

The denominator for every secondary metric must be reported explicitly.

## Comparison Rules

- The same Connection instances and output contract must be used across all
  methods.
- Baselines 001A and 001B receive no Evidence.
- Baseline 001B and Method 002 use the same model and generation parameters.
- Only Method 002 is eligible for selection.
- Review bundles must hide method identity.
- A usefulness gain cannot compensate for a hard-gate regression.
- At most one minimal, error-analysis-driven prompt refinement is allowed on
  the development benchmark.
- No benchmark, rubric, claim rule, or threshold may change after formal
  development execution without a new version and rerunning all compared
  methods.

## Required Artifacts

Each evaluated method must retain:

- rendered inputs;
- raw responses, when an API is used;
- parsed structured outputs;
- exact Evidence materialization;
- metadata and input hashes;
- claim segmentation;
- blinded reviewer bundle;
- raw review decisions;
- adjudication;
- final metrics, errors, matches, and summary.

## Independent Validation Gate

Independent validation is authorized only after a development method passes the
frozen hard and secondary gates. Before the independent source is viewed:

- freeze prompt, model, parameters, schema, rubric, claim protocol, evaluator,
  and thresholds;
- annotate the independent Connection instances without model outputs;
- keep method identity and aggregate outcomes hidden from the reviewer.

Passing independent Oracle-conditioned validation does not validate predicted
Connection Explanation or unblock Connection Discovery.
