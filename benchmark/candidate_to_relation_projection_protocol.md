# Candidate-to-Relation Downstream Diagnostic Protocol

**Version:** v0.1
**Status:** Frozen before downstream API execution
**Experiment:** 002B-2 Downstream Typed-Edge Diagnostic
**Split role:** Development diagnostic

## Purpose

This protocol evaluates how Candidate Pair Generation and the frozen Relation
classifier jointly affect typed-edge outcomes over the exhaustive predicted-KO
pair universe. It does not reopen Candidate Generator selection: a method that
fails the frozen Candidate recall gate remains failed regardless of downstream
classifier behavior.

## Frozen Source Universe

The diagnostic uses the existing 002B-2 development snapshot:

- 39 lecture-local predicted Knowledge Objects;
- 176 unordered, non-self candidate pairs;
- 80 `IN_SCHEMA_RELATION` primary positives;
- 91 `NO_IN_SCHEMA_RELATION` primary negatives;
- 5 `OUT_OF_SCHEMA_RELATION` diagnostic pairs;
- 0 unresolved or `AMBIGUOUS` pairs.

The source inventory, lecture inventory, pair universe, Candidate Ground Truth,
Candidate Generator selections, Relation prompt, Relation schema, and Relation
evaluator are hash-bound by the machine-readable diagnostic contract.

## Projection Unit

Each `cand_dev_NNN` candidate pair maps deterministically to
`rel_dev_NNN`. The numeric suffix and unordered endpoints must be preserved.
The mapping is structural and must not encode a label or Relation direction in
the model-facing pair ID.

The current Ground Truth contains no multi-relation pair. Every
`IN_SCHEMA_RELATION` annotation contains exactly one `gold_relations` item with
role `primary`. Projection fails closed if this ceases to be true. A future
benchmark with more than one valid Relation for a pair requires a separately
frozen primary/acceptable-alternative policy; the projector must not choose one
after seeing model output.

## Category Projection

Candidate annotations project as follows:

| Candidate label | Relation category | Relation target |
| --- | --- | --- |
| `IN_SCHEMA_RELATION` | `positive` | The single frozen primary gold Relation |
| `NO_IN_SCHEMA_RELATION` | `hard_negative` | `NO_RELATION` |
| `OUT_OF_SCHEMA_RELATION` | `schema_gap` | Diagnostic `RELATED_TO` placeholder |
| `AMBIGUOUS` | unsupported in v0.1 | Projection fails closed |

The `RELATED_TO` value for a schema-gap pair is a diagnostic placeholder, not a
claim that the frozen schema adequately represents the missing Relation. These
five pairs are excluded from primary strict accuracy, confusion matrices,
typed-edge precision, recall, and F1. Their model predictions are reported
separately as schema-forcing behavior.

## Candidate Conditions

Two candidate manifests are evaluated:

1. `all_pairs_v0_1`: all 176 pairs;
2. `rule_filtered_v0_1`: the frozen 127 selected pairs.

The conditions share the same KO representation, lecture text, Relation prompt,
schema, model, parameters, request partitioning, evaluator, and evidence rules.
Only Candidate Pair selection differs.

## Model-Facing Input

Each selected pair is rendered independently with:

- opaque `rel_dev_NNN` pair ID;
- unordered `ko_a` and `ko_b` references;
- the two predicted KOs with name, type, and source spans;
- the source lecture text;
- the frozen Relation schema and prompt.

The model must not receive Candidate labels, gold Relation type or direction,
evidence, rationale, schema-gap status, selection outcome, or evaluator data.
A leakage audit must reject these fields recursively.

## Execution Contract

The Relation method is the selected Experiment 002A refined prompt. Each pair is
one independent request under
`one_candidate_pair_per_request_v0_1`. This preserves the candidate-scoped
transport used by the completed 002B-1 locked-reuse run and avoids aggregate
endpoint substitution.

Both conditions use:

- provider `deepseek`;
- model `deepseek-v4-flash`;
- temperature `0`;
- top-p `1`;
- max tokens `8192`;
- JSON response format;
- disabled thinking;
- All-Pairs first, Rule-Filtered second;
- independent no-overwrite run directories.

A formal run must start from the same clean frozen method commit. A failed
request, non-`stop` finish reason, parse failure, or prediction-schema failure
invalidates that attempt. Raw artifacts remain immutable; a permitted retry
uses a new attempt ID and reruns the complete condition.

## Conditional Relation Evaluation

The existing `evaluate_relation_extraction.py` evaluates only selected pairs.
It reports conditional strict accuracy, Relation type and direction behavior,
`NO_RELATION` accuracy, Evidence exactness, and semantic-support adjudication.
Each condition has an independent prediction-bound adjudication artifact and
must reach `evaluation_status = final` with zero pending items.

Exact Evidence span rate uses all submitted evidence spans as its denominator.
Manual support rate among pending cases is never presented as overall semantic
Evidence accuracy. The semantic-support pipeline metric uses accepted,
primary-scored graph edges only; schema-gap placeholder edges remain diagnostic.

Each final condition evaluation is copied into an independent, immutable
snapshot bundle. The snapshot binds the selected Ground Truth, formal run
completion marker, predictions, aggregate metadata, final metrics, pair-level
matches, errors, pending-adjudication artifact, summary, and any resolved
adjudication used by that condition. A final snapshot cannot be shared across
conditions, even when two pair predictions happen to be identical.

## Full-Universe Pipeline Evaluation

Primary pipeline scoring uses all 171 primary pairs.

For a selected pair, the pipeline outcome is the frozen Relation evaluator's
strict result. For an unselected pair:

- a primary positive is a candidate-induced false negative;
- a primary negative is a correct pipeline rejection;
- a diagnostic pair is unprocessed and remains outside primary scoring.

Report at least:

```text
pipeline_strict_accuracy
positive_typed_edge_precision
positive_typed_edge_recall
positive_typed_edge_f1
candidate_induced_false_negatives
classifier_no_relation_false_negatives
wrong_relation_type
wrong_direction_when_type_correct
false_positive_relations
selected_pair_count
API request count
token totals
Evidence exactness and semantic support on selected positive predictions
```

Positive typed-edge precision counts a true positive only when Relation type and
direction are strictly correct. Its denominator is all graph-Relation
predictions on primary pairs. Recall uses all 80 positive pairs, including
candidate misses.

Each primary pair receives one mutually exclusive failure locus in this order:

1. `candidate_induced_false_negative`;
2. `classifier_no_relation_false_negative`;
3. `wrong_relation_type`;
4. `wrong_direction`;
5. `false_positive_relation`;
6. `strict_success`.

The pipeline evaluator consumes only final condition snapshots. It emits:

- `pipeline_metrics.json`;
- `pipeline_errors.json`;
- `pair_transitions.json`;
- `summary.md`;
- `pipeline_evaluation_complete.json` written last as the validity boundary.

The transition artifact must report how many Rule-Filtered positive omissions
were strictly correct under the independently executed All-Pairs classifier.
This is an observed frozen-classifier diagnostic, not permission to override
the Candidate recall gate.

## Interpretation Boundary

Downstream results are diagnostic. In particular:

- small observed typed-edge loss cannot rescue Rule-Filtered v0.1 because a
  stronger future classifier could have recovered its 10 omitted positives;
- All-Pairs false positives demonstrate classifier exposure and quadratic
  workload, not that the failed filter is safe;
- no result is a fresh holdout claim;
- no current result establishes long-document, cross-lecture, or production
  scalability.

## Closure Rule

After both evaluations are final, write one downstream comparison and update the
002B conclusions. The expected project-level status is `completed with partial
feasibility`, not a binary pass:

- predicted-KO representation coupling is feasible on recoverable pairs;
- missing KOs remain an upstream bottleneck;
- Rule-Filtered v0.1 failed the Candidate recall gate;
- All-Pairs v0.1 remains the current lecture-local safety fallback;
- production readiness is not established.
