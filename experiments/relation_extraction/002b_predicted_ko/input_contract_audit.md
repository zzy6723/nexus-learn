# Experiment 002B-1 Input Contract Audit

**Status:** Completed before implementation  
**Date:** 2026-07-14  
**Experiment:** Predicted-KO Relation Classification

---

# Purpose

This audit determines whether the completed Experiment 002A Oracle-KO runs can
serve as a fair reference for Experiment 002B-1, where Relation classification
receives Knowledge Objects produced by the frozen Entity Extraction prompt.

The audit covers only model-facing input structure. It does not run Entity
Extraction or Relation Classification and does not inspect future 002B-1
predictions.

---

# Audited Artifacts

Oracle Relation input:

- `scripts/run_relation_extraction.py`;
- `experiments/relation_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/rendered_inputs/relations_holdout_v0_1.json`;
- `experiments/relation_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/metadata/relations_holdout_v0_1.json`.

Predicted Knowledge Object output:

- `experiments/entity_extraction/002_prompt_refinement/prompt.md`;
- `experiments/entity_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/output/`;
- `benchmark/evaluation_protocol.md`.

Selected prompt hashes:

- Entity Extraction prompt: `12d85ea9b3ed66b751b637d7ce2e459c69368b9685bbc39c4713c24ff69feeeb`;
- Relation Extraction prompt: `e3b0e53f3ceed60c60d082fa9c4a67f9497e64d50664118227cd9bea9fbc12af`.

---

# Oracle KO View in Experiment 002A

The Relation runner exposes exactly these fields for each Oracle Knowledge
Object:

```json
{
  "lecture_id": "differential_equations_001",
  "ko_id": "euler_update",
  "name": "Forward Euler Update Formula",
  "type": "Formula",
  "source_spans": [
    "y_{n+1} = y_n + hF(t_n,y_n)."
  ]
}
```

It does not expose:

- aliases;
- a short definition;
- required/optional category;
- gold Relation type or direction;
- gold Relation evidence or rationale;
- primary-scoring status.

The runner includes only Knowledge Objects referenced by the rendered candidate
pairs. It sorts the referenced fully qualified KO identities deterministically.

---

# Entity Prediction View

The frozen Entity Extraction output contract is:

```json
{
  "id": "composite_function",
  "name": "Composite Function",
  "type": "Concept",
  "aliases": [],
  "short_definition": "A function formed by applying one function to the result of another.",
  "source_span": "The composite function h = f o g maps an input x to f(g(x))."
}
```

The surrounding output supplies the `lecture_id` once per lecture.

---

# Common Normalized Relation Input KO View

Both matched conditions will use:

```json
{
  "lecture_id": "string",
  "ko_id": "ko_slot_NNN",
  "name": "string",
  "type": "Concept | Method | Formula",
  "source_spans": ["string"]
}
```

Predicted outputs are normalized only by:

1. copying the enclosing `lecture_id` onto each object;
2. assigning the neutral `ko_slot_NNN` identifier frozen in the KO manifest;
3. wrapping the original `source_span` as a one-item `source_spans` list;
4. dropping `aliases`;
5. dropping `short_definition`.

No name, type, or source span may be corrected, canonicalized, or replaced with
an Oracle value. Original Oracle and predicted IDs remain unchanged in the
non-model-facing manifest, but both requests use the same neutral slot ID. This
is a content-preserving normalization of educational content, not manual repair.

Neutral IDs intentionally remove local identifier wording from the conditional
representation comparison. Experiment 002B-1 measures changes in `name`, `type`,
and source grounding; raw predicted-ID quality remains an upstream diagnostic.

---

# Inventory Behavior

The existing Relation runner derives its KO inventory from the candidate pairs.
Therefore Experiment 002B-1 must freeze two linked manifests:

- `recoverable_pair_manifest.json` defines the candidate-pair subset and order;
- `recoverable_ko_manifest.json` is deterministically derived from the pair
  manifest and the one-to-one alignment.

The KO manifest records one structural slot for every distinct referenced
endpoint, its Oracle and predicted identities, deterministic order, and the pair
IDs that reference it.

The KO manifest is an integrity artifact, not an independent selection surface.
It must not be manually expanded with unmatched predicted KOs or reduced after
the pair manifest has been fixed.

Matched Oracle and Predicted requests must have:

- the same number of KO slots;
- the same slot order;
- the same pair-to-slot incidence pattern;
- the same number and order of candidate pairs;
- the same lecture inventory and lecture order.

Only the KO content placed in each slot differs between conditions.

Slot IDs are assigned deterministically by sorting the recoverable Oracle fully
qualified references, independently of gold Relation type and direction. The
same slot ID is used for the aligned Oracle and predicted object.

---

# Historical Oracle Control Decision

The Experiment 002A Oracle input already uses the common normalized KO fields.
No Oracle rerun is required merely to remove aliases or definitions because
neither was present in the historical Relation request.

However, A0 is not reused as A-prime:

- matched requests use neutral KO slot IDs while A0 uses original Oracle IDs;
- the development A0 request contains 41 pairs, including 38 primary pairs, 2
  ambiguous pairs, and 1 schema-gap pair;
- the holdout A0 request contains 40 pairs, all of which are primary-scored;
- the primary A-prime/B-prime experiment contains only primary-scored recoverable
  pairs;
- pair recoverability may reduce the matched request further.

A new A-prime request is therefore always rendered and run from the same primary
pair manifest, KO-slot manifest, matched ground truth, and batching plan as
B-prime. A0 remains a historical Oracle-condition reference only.

Recovery and pipeline denominators come from the frozen primary gold
candidate-pair set, never from A0 output completeness or correctness.

No sentinel or invented Knowledge Object may be inserted for a missing endpoint
solely to preserve the full batch.

---

# Conclusion

Experiment 002B-1 can use a shared model-facing KO contract without changing the
semantic content of either condition. The selected Entity output contains extra
fields, but Experiment 002A did not use corresponding Oracle-only information.

The remaining controls are alignment, recoverable pair selection, KO-slot
composition, neutral ID assignment, deterministic matched-ground-truth
derivation, batching, and matched execution. These are defined in:

- `benchmark/predicted_ko_alignment_protocol.md`;
- `benchmark/predicted_ko_relation_evaluation_protocol.md`.
