# Learning Explanation Evaluation Protocol

**Status:** Ready for 004-0 review
**Version:** v0.1

## Scope

This protocol evaluates Oracle-conditioned Learning Explanations. It does not
evaluate Connection Discovery or an end-to-end product pipeline.

## Methods

### Baseline 001: Deterministic Relation Paraphrase

Produce a fixed template from source name, Relation, and target name. It uses no
LLM and establishes a faithful but intentionally shallow lower bound. It
receives immutable Connection fields and copies supplied Evidence IDs for
schema consistency, but it does not receive or use Evidence text.

### Method 002: Evidence-Grounded Learning Explanation

Provide Oracle endpoints, Relation, and supplied Evidence entries. Require the
structured output defined in `benchmark/learning_explanation_contract.md`.

The first development comparison may also report a Relation-only ablation, but
it is diagnostic and must not replace Baseline 001.

## Evaluation Sequence

1. Validate JSON schema and immutable transport fields.
2. Validate that every Evidence ID belongs to the supplied catalog.
3. Materialize Evidence IDs deterministically.
4. Blind method identity and randomize review items.
5. Segment substantive claims.
6. Label claim support.
7. Evaluate explanation-level faithfulness.
8. Score learning value only for faithfulness-passing explanations.
9. Resolve `UNRESOLVED` claim decisions.
10. Produce machine-readable metrics, errors, matches, and reviewer artifacts.

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

## Secondary Metrics

Only faithfulness-passing explanations enter:

- mean Conceptual Mechanism score;
- mean Learning Relevance score;
- mean Specificity score;
- mean Clarity score;
- pedagogically non-empty rate;
- paired learning-value composite improvement over Baseline 001.

The learning-value composite for one output is the mean of its Conceptual
Mechanism and Learning Relevance scores. Paired improvement is computed per
Connection instance before averaging.

The denominator for every secondary metric must be reported explicitly.

## Comparison Rules

- The same Connection instances, model, parameters, and output contract must be
  used across learned methods.
- Baseline 001 is deterministic and does not receive Evidence.
- Review bundles must hide method identity.
- A usefulness gain cannot compensate for a hard-gate regression.
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
