# Experiment 002B-2: Candidate Pair Generation under Predicted KOs

**Status:** Pair universe and strict checker complete; exhaustive annotation pending
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
- `benchmark/candidate_pair_annotation_guidelines.md`;
- `benchmark/schema/candidate_pair_universe.schema.json`;
- `benchmark/schema/candidate_pair_ground_truth.schema.json`;
- `benchmark/candidate_pair_generation_success_criteria_v0_1.json`.
- `scripts/check_candidate_pair_ground_truth.py`;
- `tests/test_candidate_pair_ground_truth_checker.py`;
- `tests/fixtures/candidate_pair_ground_truth/`.

The pair universe is structurally complete and hash-bound. The ground-truth
artifact is intentionally still a draft: all 176 labels require manual review.
The checker passes this artifact in draft mode and rejects it in final mode.
Seventeen pair-universe and checker regression tests pass. No Candidate Generator
has been implemented or scored.

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
  "artifact_type": "candidate_pair_manifest",
  "version": "v0.1",
  "generator_id": "all_pairs_v0_1",
  "inventory_sha256": "...",
  "pairs": [
    {
      "candidate_pair_id": "cand_dev_001",
      "ko_a": {
        "lecture_id": "lecture_001",
        "ko_id": "pred_ko_001"
      },
      "ko_b": {
        "lecture_id": "lecture_001",
        "ko_id": "pred_ko_004"
      },
      "candidate_reasons": ["same_lecture"],
      "generator_version": "v0.1"
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

## Immediate Next Gate

Annotate one lecture at a time without inspecting Candidate Generator outputs.
After each batch, run:

```bash
python3 scripts/check_candidate_pair_ground_truth.py \
  --pair-universe benchmark/candidate_pairs/development_v0_1/pair_universe.json \
  --ground-truth benchmark/ground_truth/candidate_pairs_development_v0_1.json \
  --allow-draft
```

After all annotations and reviews are final, change top-level `status` to
`frozen`, run the checker without `--allow-draft`, and write the completion
marker. Do not implement or score a Candidate Generator before that final gate.
