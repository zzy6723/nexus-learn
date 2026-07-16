# Experiment 002B-2: Candidate Pair Generation under Predicted KOs

**Status:** Completed with partial feasibility; All-Pairs v0.1 retained as the safety fallback
**Stage:** Technical Validation
**Predecessor:** Experiment 002B-1 completed

## Question

Given a predicted, lecture-local Knowledge Object inventory, can a frozen
candidate-generation method retain true typed-Relation pairs at high recall
while reducing the number of pairs sent to Relation Classification?

## Why This Is a Separate Experiment

Experiment 002B-1 received candidate pairs derived from an existing gold pair
universe. It measured endpoint recoverability and downstream Relation errors,
but it never asked the system to decide which pairs deserved classification.

Experiment 002B-2 introduces only that missing decision:

```text
predicted lecture-local KOs
        -> candidate generator
        -> unordered candidate pairs
        -> frozen Relation classifier
```

The candidate generator selects pairs. It does not assign Relation labels,
directions, evidence, or rationales.

## Scope Boundary

The v0.1 experiment is deliberately lecture-local and mention-level.

In scope:

- predicted KOs produced by the frozen Entity method;
- every unordered pair within each declared lecture inventory;
- deterministic candidate generation;
- candidate recall and workload reduction;
- downstream evaluation using the frozen Relation schema and classifier;
- separate accounting for missing endpoint KOs.

Out of scope:

- merging mentions across lectures or courses;
- canonical KO IDs;
- same-name disambiguation across contexts;
- learner history, novelty, or pedagogical-value ranking;
- learner-facing Connection explanations;
- free-form LLM pair proposal.

Cross-lecture canonicalization belongs to Experiment 002C. Learner-relevant
Connection discovery belongs to Experiment 003.

## Critical Benchmark Requirement

Candidate precision is meaningful only when the evaluation scope has a complete
pair universe. If a lecture has `n` KOs, the benchmark must enumerate and
annotate all `n(n-1)/2` unordered pairs.

The existing Relation holdout contains 40 deliberately selected pairs and is not
exhaustive. An unlisted pair may be a real Relation, a valid hard negative, or an
unreviewed case. It cannot automatically be counted as `NO_RELATION`.

Therefore 002B-2 must create a new versioned benchmark before implementing or
scoring a generator.

## Development Benchmark Status

The current development source is the inspected 002B-1 locked-reuse predicted
KO inventory. Although its source artifact records `split = holdout`, it is no
longer unseen and is intentionally assigned the 002B-2 development role.

Current deterministic universe:

| Lecture | Predicted KOs | Unordered pairs |
| --- | ---: | ---: |
| `differential_equations_001` | 11 | 55 |
| `graph_algorithms_001` | 10 | 45 |
| `numerical_root_finding_001` | 7 | 21 |
| `statistics_estimation_001` | 11 | 55 |
| **Total** | **39** | **176** |

Artifacts:

- `benchmark/candidate_pairs/development_v0_1/pair_universe.json`;
- `benchmark/candidate_pairs/development_v0_1/pair_universe_complete.json`;
- `benchmark/ground_truth/candidate_pairs_development_v0_1.json`;
- `benchmark/ground_truth/candidate_pairs_development_v0_1_complete.json`;
- `benchmark/candidate_pair_annotation_guidelines.md`;
- `benchmark/schema/candidate_pair_universe.schema.json`;
- `benchmark/schema/candidate_pair_ground_truth.schema.json`;
- `benchmark/candidate_pair_generation_success_criteria_v0_1.json`;
- `scripts/check_candidate_pair_ground_truth.py`;
- `tests/test_candidate_pair_ground_truth_checker.py`;
- `tests/fixtures/candidate_pair_ground_truth/`.

The pair universe is structurally complete and hash-bound. All 176 Ground Truth
annotations have been reviewed and finalized:

- 80 `IN_SCHEMA_RELATION`;
- 91 `NO_IN_SCHEMA_RELATION`;
- 5 `OUT_OF_SCHEMA_RELATION`;
- 0 `AMBIGUOUS`.

The checker passes the artifact in final mode, and the Ground Truth completion
marker binds the frozen snapshot. The deterministic All-Pairs and Rule-Filtered
generators are implemented and validated. Their formal development runs use the
same frozen 176-pair snapshot and Candidate Generation evaluator.

Current Candidate Generation infrastructure:

- `benchmark/schema/candidate_pair_generation_output.schema.json`;
- `scripts/generate_candidate_pairs.py`;
- `scripts/evaluate_candidate_pair_generation.py`;
- `tests/test_candidate_pair_generator.py`;
- `tests/test_candidate_pair_generation_evaluator.py`;
- `benchmark/candidate_pair_generation_rules_v0_1.json`;
- `benchmark/schema/candidate_pair_generation_rules.schema.json`;
- `benchmark/schema/candidate_pair_selection_decisions.schema.json`;
- `scripts/generate_rule_filtered_candidate_pairs.py`;
- `tests/test_rule_filtered_candidate_generator.py`;
- `tests/fixtures/candidate_pair_generation/`;
- `all_pairs_control.md`;
- `rule_filtered_design.md`;
- `rule_filtered_v0_1_results.md`;
- `runs/development_v0_1/all_pairs/run_01/`;
- `runs/development_v0_1/rule_filtered_v0_1/run_01/`.

The existing pair-universe, Ground Truth, All-Pairs, and evaluator regression
tests are supplemented by 11 Rule-Filtered generator tests covering individual
rules, full decision auditing, determinism, leakage rejection, stale bindings,
and no-overwrite behavior.

## Inputs

- authored lecture snippets;
- predicted lecture-local KO inventories from the frozen Entity prompt;
- KO names, types, and source spans;
- the frozen Relation schema;
- an exhaustive pair annotation for evaluation only.

The generator must not receive:

- gold Relation labels or directions;
- gold evidence or rationales;
- Oracle-to-predicted alignment decisions;
- benchmark categories;
- canonical IDs from a future 002C system;
- outputs from the Relation classifier.

## Candidate Output

```json
{
  "artifact_type": "candidate_pair_selection",
  "version": "v0.1",
  "benchmark_split": "development",
  "scope": "lecture_local_unordered_nonself",
  "selection_order": "pair_universe_order",
  "generator": {
    "id": "all_pairs_v0_1",
    "name": "all_pairs",
    "version": "v0.1",
    "implementation": {
      "path": "scripts/generate_candidate_pairs.py",
      "sha256": "..."
    },
    "config": {
      "strategy": "all_pairs",
      "selection_scope": "complete_pair_universe",
      "candidate_reasons": ["all_pairs_control"]
    },
    "config_sha256": "..."
  },
  "pair_universe": {
    "path": "benchmark/candidate_pairs/development_v0_1/pair_universe.json",
    "sha256": "..."
  },
  "source_inventory": {
    "path": "...",
    "sha256": "...",
    "normalized_content_sha256": "..."
  },
  "selected_pair_count": 176,
  "selected_pairs": [
    {
      "pair_id": "cand_dev_001",
      "lecture_id": "lecture_001",
      "ko_a": {
        "lecture_id": "lecture_001",
        "ko_id": "pred_ko_001"
      },
      "ko_b": {
        "lecture_id": "lecture_001",
        "ko_id": "pred_ko_004"
      },
      "candidate_reasons": ["all_pairs_control"]
    }
  ]
}
```

Endpoint order is structural only. Each pair is unordered, unique, and sorted
deterministically from fully qualified KO references.

## Baselines

### Baseline A: All Pairs

Emit every unordered pair in the declared lecture-local inventory.

This establishes:

- the maximum candidate recall conditional on endpoint availability;
- the full Relation-classification workload;
- a reference for downstream edge precision, recall, and cost.

### Baseline B: Rule-Filtered Pairs

Apply deterministic, predeclared rules using only model-visible KO fields and
lecture text. Candidate feature families may include:

- KO type combination;
- source-span proximity in the lecture;
- normalized token overlap;
- shared mathematical symbols or terms.

Exact rules and thresholds must be chosen on development data, recorded in a
versioned method file, and frozen before holdout execution. A rule may not be
added because it preserves a known holdout edge.

### Deferred Baseline C: Retrieval Ranked

Lexical or embedding ranking may be added only after A and B establish the
benchmark and evaluator. It must report recall at a fixed pair budget or top-k,
not only an unconstrained ranking score.

## Evaluation Layers

### Layer 1: Endpoint Availability

Using the frozen 002B-1 alignment, measure whether both endpoints of each Oracle
gold edge exist in the predicted KO inventory. This is an upstream
recoverability gate, not part of candidate-generator precision or recall.

### Layer 2: Candidate Generation

Measure recall and precision against the exhaustive annotations over the
predicted-KO pair universe, plus retained-pair count and reduction versus All
Pairs. Do not intersect Oracle pair IDs directly with predicted pair IDs.

### Layer 3: Relation Classification

Run the frozen Relation classifier only on generated pairs, then measure typed
edge precision, recall, F1, `NO_RELATION` workload, grounding quality, token
usage, and API request count.

### Layer 4: End-to-End

Through the frozen alignment artifact, report typed edge recall over all Oracle
gold positive edges, including losses from missing KOs, candidate filtering,
Relation classification, and grounding.

## Primary Metrics

- endpoint-recoverable positive pairs / all positive pairs;
- candidate recall over positive pairs in the predicted-KO pair universe;
- candidate precision over the exhaustive pair universe;
- pairs retained / all possible pairs;
- reduction ratio;
- positive Relation recall after classification;
- typed edge precision, recall, and F1;
- `NO_RELATION` calls;
- request, token, latency, and estimated-cost totals.

Candidate recall is the primary generator metric. Precision improvements do not
justify silently losing positive Relations.

Endpoint recoverability and end-to-end Oracle edge recall are reported
separately through the frozen alignment artifact. They must not share the
candidate metric denominator.

## Split and Freeze Rules

- development and holdout must be lecture-disjoint;
- all holdout pair labels must be completed before any generator is run;
- generator rules, thresholds, matching rules, metrics, and success criteria
  must be frozen before holdout;
- the All-Pairs and selected filtered generator must run on the same holdout;
- Entity and Relation methods remain frozen during the comparison;
- inspected 002B-1 materials may be used only as development data, never as a
  fresh candidate-discovery holdout.

## Execution Plan

1. Select a deliberately small development lecture set.
2. Freeze the predicted KO inventory used as generator input.
3. Enumerate every lecture-local unordered KO pair.
4. Annotate every pair as `IN_SCHEMA_RELATION`, `NO_IN_SCHEMA_RELATION`,
   `AMBIGUOUS`, or `OUT_OF_SCHEMA_RELATION` under a frozen guide.
5. Validate pair-universe completeness and endpoint integrity.
6. Implement the All-Pairs generator and evaluator fixtures.
7. Implement one deterministic Rule-Filtered generator.
8. Compare candidate metrics without calling the Relation API.
9. Run the frozen Relation classifier on both candidate manifests.
10. Freeze the selected generator and evaluation protocol.
11. Construct and annotate a lecture-disjoint holdout.
12. Run both generators and produce the final comparison.

## All-Pairs Control Result

The formal control is final and hash-bound:

- selected pairs: `176 / 176`;
- candidate recall: `80 / 80 = 1.0`;
- primary candidate precision: `80 / 171 = 0.4678362573`;
- primary retention: `171 / 171 = 1.0`;
- total workload retention: `176 / 176 = 1.0`;
- total workload reduction: `0.0`;
- diagnostics selected: `5 / 5`.

This validates the Candidate Generation evaluator and establishes the maximum
workload control. The control alone did not select a final method. After the
Rule-Filtered comparison failed the frozen recall gates, All Pairs was retained
as the current safe fallback. This still does not constitute downstream
Relation Classification evidence. See `all_pairs_control.md` for the formal
control record.

## Rule-Filtered v0.1 Result

The formal Rule-Filtered run is final and hash-bound:

- selected pairs: `127 / 176`;
- selected positive pairs: `70 / 80`;
- missed positive pairs: `10`;
- candidate recall: `0.875`;
- primary candidate precision: `70 / 122 = 0.5737704918`;
- total workload reduction: `49 / 176 = 0.2784090909`;
- diagnostics selected: `5 / 5`.

The method reduced workload but failed candidate recall, missed-positive, and
per-lecture recall gates. Seven missed pairs were `REQUIRES` and three were
`APPLIED_IN`; no endpoint, order, or alignment failure occurred. See
`rule_filtered_v0_1_results.md` for the comparison and false-negative analysis.

## Downstream Typed-Edge Diagnostic Result

The frozen downstream diagnostic is complete. Both conditions used the same
Relation prompt, model, parameters, evaluator, and one-pair-per-request
partitioning under method commit
`78e47b8dc792dd970e72c0040f045c8d1cc1035c`.

| Metric | All-Pairs | Rule-Filtered v0.1 |
| --- | ---: | ---: |
| Candidate requests | 176 | 127 |
| Candidate positive recall | 80/80 | 70/80 |
| Conditional Relation strict | 62/171 | 45/122 |
| Full-universe strict | 62/171 | 84/171 |
| Positive typed-edge recall | 40/80 | 36/80 |
| Positive typed-edge precision | 40/148 | 36/112 |
| Candidate-induced false negatives | 0 | 10 |
| False-positive Relations | 69 | 43 |
| Exact Evidence spans | 162/209 | 126/160 |

Rule-Filtered rejected 39 hard negatives before classification, so its
full-universe strict accuracy improved. It nevertheless lost four correct typed
edges: the All-Pairs classifier was strictly correct on four of the 10 positive
pairs omitted by Rule-Filtered. The other six omitted positives were classified
incorrectly by the current All-Pairs run, but remain irrecoverable to any future
classifier once filtered out.

Both Relation evaluations are final with zero pending adjudications. Their
independent snapshots and the 176-pair pipeline comparison are hash-bound by
`pipeline_evaluation_complete.json`.

See `downstream_relation_diagnostic.md` for the complete comparison and
`conclusion.md` for the experiment decision.

## Decision And Next Stage

Rule-Filtered v0.1 remains a failed development baseline. Its downstream cost
and negative-rejection benefits do not override the frozen recall-first
Candidate gate.

`all_pairs_v0_1` remains the current lecture-local safety fallback. This is not
a production scalability claim: pair workload grows quadratically, the frozen
Relation classifier produced many false-positive edges, and exact Evidence
grounding remained below 0.8 in both conditions.

Experiment 002B is now complete with partial feasibility. No further candidate
rule is tuned on this inspected 176-pair development snapshot. The next stage is
Experiment 002C, Knowledge Object Resolution / Canonicalization.
