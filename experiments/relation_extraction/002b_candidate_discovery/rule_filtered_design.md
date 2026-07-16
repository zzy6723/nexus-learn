# Rule-Filtered Candidate Generator v0.1

**Status:** Frozen for the first development baseline
**Method ID:** `rule_filtered_v0_1`
**Scope:** Lecture-local, unordered, non-self predicted-KO pairs

## Question

Can a deterministic and auditable union of high-recall signals reduce the
number of pairs sent to Relation Classification without missing any primary
positive pair on the frozen development benchmark?

This is a Candidate Generation experiment. It does not assign Relation labels,
directions, Evidence, or rationales, and it does not call a model API.

## Historical Integrity Boundary

The completed All-Pairs control hash-binds
`scripts/generate_candidate_pairs.py` and
`scripts/evaluate_candidate_pair_generation.py`. Those files remain unchanged
so the historical control stays locally verifiable. Rule-Filtered v0.1 uses a
separate versioned runner while emitting the same candidate selection contract
and using the existing evaluator unchanged.

## Allowed Inputs

The method reads only:

- the frozen pair universe and completion marker;
- predicted KO `lecture_id`, `predicted_ko_id`, `name`, `type`, and
  `source_spans`;
- lecture `lecture_id` and text;
- the frozen Rule-Filtered configuration.

It does not accept a Ground Truth path. Candidate labels, gold Relations,
Evidence, rationales, evaluator errors, Oracle alignment, Relation outputs,
and pair-specific allowlists are forbidden.

## Semantic Blocks

Lecture text is split on one or more blank lines. A display-math block is
attached to the immediately preceding prose block. Text matching uses NFKC,
case folding, removed LaTeX display/inline delimiters, and collapsed
whitespace. A KO is located using its normalized source spans; its normalized
name is a deterministic fallback when an extracted span joins prose and math
slightly differently from the source.

## Rule Union

A pair is selected when any enabled rule matches. Triggered reasons are emitted
in the frozen order below.

1. `source_proximity`: the nearest located source blocks differ by at most one.
2. `lexical_overlap`: endpoint names share at least one normalized non-stopword
   token using the existing Entity name-normalization implementation.
3. `symbol_overlap`: endpoint source spans share at least one nontrivial LaTeX
   command or mathematical identifier after frozen stop-symbol removal.
4. `explicit_reference`: one semantic block contains a frozen relation cue and
   identifies both endpoints by normalized name tokens or located source span.
5. `type_compatibility`: disabled in v0.1 because type alone is not a reliable
   filter under the broad frozen Relation schema.

The rules form a union, not a score. Multiple triggers select one pair once.
No rule may inspect `pair_id` except to copy the frozen identifier into output.

## Audit Artifacts

`candidate_pairs.json` contains only selected pairs with stable string rule
IDs in `candidate_reasons`. `selection_decisions.json` contains one record for
every universe pair, including structured trigger details or
`no_rule_triggered`. The candidate generator config binds the decision audit by
path and SHA-256, and metadata binds the rules and source artifacts.

## Development Gate

Rule-Filtered v0.1 is a baseline, not a selected product method. It must be
evaluated against the existing frozen criteria:

- candidate recall `1.0`;
- missed primary positives `0`;
- per-lecture positive recall `1.0`;
- total workload reduction at least `0.2`.

Passing these Candidate-layer gates leaves downstream typed-edge evaluation
pending. Failing any recall gate cannot be offset by better precision or cost.

At most one controlled v0.2 refinement should follow the v0.1 error analysis.
It must be a general rule change, never a pair-specific patch.
