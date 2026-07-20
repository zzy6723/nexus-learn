# 002C-4 Development Results

## Scope

002C-4 tests an evidence-transport correction. Both datasets are development
evidence:

- the authored 002C-2 challenge was already used to select identity behavior;
- the locked-reuse diagnostic caused the Unicode/LaTeX remediation.

Neither dataset is an unseen holdout for v0.2 or v0.2.1.

## Formal Integrity

All four runs used `deepseek-v4-flash`, temperature `0`, top-p `1`, and one
candidate per request. Their formal metadata recorded a clean worktree, the
declared method commit, successful requests, valid JSON, valid prediction
schemas, and `finish_reason = stop`.

## Structural Results

| Run | Candidates | SAME precision | End-to-end SAME recall | B-cubed F1 | Exact clusters | Structural identity gates | Evidence semantic gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| v0.2 challenge | 11 | 1.000 | 1.000 | 1.000 | 13/13 | Passed | Failed, 10/11 |
| v0.2 locked-reuse diagnostic | 6 | 1.000 | 1.000 | 1.000 | 46/46 | Passed | Passed, 6/6 |
| v0.2.1 challenge | 11 | 1.000 | 1.000 | 1.000 | 13/13 | Passed | Passed, 11/11 |
| v0.2.1 locked-reuse diagnostic | 6 | 1.000 | 1.000 | 1.000 | 46/46 | Passed | Passed, 6/6 |

Every completed run had zero unresolved decisions, duplicate assignments,
orphan mentions, cross-type clusters, and lost-provenance mentions.

## Evidence Results

| Run | Materialized exact spans | Semantically supported candidate sets |
| --- | ---: | ---: |
| v0.2 challenge | 23/23 | 10/11 |
| v0.2 locked-reuse diagnostic | 14/14 | 6/6 |
| v0.2.1 challenge | 25/25 | 11/11 |
| v0.2.1 locked-reuse diagnostic | 12/12 | 6/6 |

v0.2 eliminated free-form evidence copying: the former Gradient failure
completed using IDs that materialized to exact LaTeX spans. Its challenge run
then exposed a deterministic catalog defect. Two Forward Euler formula blocks
at end of file were omitted because the source ended with a single trailing
newline. The Formula identity decision was correct, but its selected narrative
blocks were not self-contained.

v0.2.1 corrected the partitioner. The rerun made both formula blocks available,
and the model selected their IDs. All v0.2.1 evidence sets were exact and
semantically self-contained under the frozen review rule.

Semantic-support results come from finalized audit artifacts bound to each
run's `identity_decisions.json` hash. These development reviews were manual,
retrospective, and not blinded: the reviewer could see the candidate endpoints,
predicted decision, rationale, selected evidence, run identity, and benchmark
context. They did not use an embedding or another model as an automatic judge.
The reviews are suitable for development diagnosis, not independent evidence.
002C-5 uses the separate blind-review procedure in
`benchmark/ko_identity_evidence_review_protocol.md`.

## Interpretation

Opaque evidence IDs are operationally superior to free-form span copying on
the current development data. They preserve exact source bytes across
Unicode/LaTeX representations and keep model choice separate from deterministic
span materialization.

The result establishes development feasibility, not generalization. The
locked-reuse data influenced the interface, and the challenge influenced both
identity behavior and the v0.2.1 partitioner fix. A new source is required
before selecting a production canonicalizer.

The resolver directly saw only three development `DISTINCT_OBJECT` candidates:
one challenge homonym and two diagnostic containment cases. The full cluster
Ground Truth covers all pairwise distinct identities, but this does not amount
to broad context-resolver negative coverage. More same-name, same-type,
near-definition, shared-symbol, containment, and cross-course hard negatives
remain required.
