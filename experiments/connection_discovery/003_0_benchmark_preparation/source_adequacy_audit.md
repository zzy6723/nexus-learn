# 003-0A Source Adequacy Audit

**Status:** Complete
**Decision:** Do not use the 002C-5 source unchanged as the primary 003
development benchmark.

## Audited Source

The audit covers the four authored Relation-holdout lectures reused by 002C-5:

- `differential_equations_001`
- `graph_algorithms_001`
- `numerical_root_finding_001`
- `statistics_estimation_001`

The canonical inventory is the frozen 002C-5 v0.2.1 output. This audit changes
neither that inventory nor the 002C conclusion.

## Structural Results

| Measure | Result |
| --- | ---: |
| Lectures | 4 |
| Canonical KOs | 38 |
| Mentions | 39 |
| Concepts / Methods / Formulas | 19 / 9 / 10 |
| Single-lecture canonical KOs | 37 |
| Multi-lecture canonical KOs | 1 |
| All unique unordered canonical pairs | 703 |
| Eligible cross-lecture pairs | 543 |
| Disjoint-provenance pairs | 527 |
| Overlap-bridge pairs | 16 |
| Same-lecture-only excluded pairs | 160 |
| Exact / nonexact upstream source spans | 34 / 5 |

`disjoint-provenance` means the endpoint lecture sets do not overlap.
`overlap-bridge` means the endpoints can be observed in different lectures but
also co-occur in at least one lecture. These strata must remain separate in
later reporting so a local co-occurrence is not presented as wholly
cross-document discovery.

The machine-readable counts are in `source_adequacy_audit.json` and can be
regenerated with `scripts/audit_connection_discovery_source.py`.

## Semantic Screening

The source has one clear cross-context bridge family:

- Newton's method appears in both numerical root finding and statistics;
- the statistics lecture explicitly applies it inside maximum likelihood
  estimation and in solving the score equation.

This supports useful development examples, but it does not provide a balanced
Connection Discovery benchmark. Preliminary screening suggests that the clear
in-schema cross-lecture positives concentrate in `APPLIED_IN`. The possible
link from a score equation to a root-finding problem also exposes an
`INSTANCE_OF`-like schema gap and must not be forced into `RELATED_TO` or
`EXTENDS`.

The differential-equations and graph-algorithms materials do not explicitly
establish comparable bridges to the other lectures. Consequently, most of the
527 disjoint-provenance pairs would be easy negatives produced by unrelated
topic blocks. That class balance would test refusal more than meaningful
Connection discovery.

This screening is an adequacy judgment, not Connection Ground Truth. No exact
positive count is frozen here.

## Metadata And Evidence Risks

The source manifest declares lecture IDs but not course or topic IDs. It cannot
support reliable `same_course_cross_lecture`, `cross_course`, and `cross_topic`
stratification without adding post hoc labels.

Five upstream Entity source spans are nonexact. This does not prevent a new
candidate-scoped Evidence catalog from using exact lecture blocks, but it must
remain visible as inherited provenance quality and cannot be silently repaired.

## Decision

The source is rejected only for use unchanged as the primary 003 development
benchmark. It remains suitable for a later sparse diagnostic after the 003
method is frozen on separate development data.

A new authored development bundle is required. It should deliberately place
old and new concepts across separate lectures while keeping each Relation
supported by frozen text. This is benchmark design, not data augmentation after
model output: the complete universe and labels must be frozen before any 003
model run.
