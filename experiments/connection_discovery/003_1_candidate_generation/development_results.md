# 003-1 Development Results

**Evaluation status:** Final
**Method commit:** `f8ba8291fdd9d71eb09ba3ab42f7b6198c64ccb7`
**API calls:** None

## Setup

Four deterministic generators consumed the same frozen Oracle canonical
inventory and 387-pair universe. Candidate generators did not read Connection
Ground Truth. Only the evaluator read the 387 frozen annotations.

## Aggregate Results

| Method | Selected | Primary recall | Missed | Primary precision | Workload reduction | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| All Pairs | 387 | 1.0000 | 0 | 0.1090 | 0.0000 | Control |
| Overlap Bridge | 125 | 1.0000 | 0 | 0.3445 | 0.6770 | Passed |
| Lexical Only | 309 | 0.9756 | 1 | 0.1338 | 0.2016 | Passed |
| Hybrid Provenance + Lexical | 309 | 1.0000 | 0 | 0.1367 | 0.2016 | Passed |

All methods had zero duplicate pairs, self-pairs, unknown endpoints, and
endpoint-alignment errors. Every supported Relation with at least four primary
examples met its frozen recall gate in each passing method.

## Scope Diagnostics

`overlap_bridge` retained all 41 primary positives because all primary
positives share endpoint provenance. It retained none of the five diagnostic
disjoint-provenance compositional positives.

`lexical_only` retained four of those five diagnostics but missed one primary
`REQUIRES` pair: Gradient with Newton Optimisation Update
(`conn_dev_pair_ef28d97312ee8970`). Its primary recall remained above the
frozen 0.95 threshold.

The hybrid restored that primary miss but retained only three of five
compositional diagnostics. At the fixed 80% retention budget it offered no
primary recall advantage over the much smaller overlap candidate set.

## Interpretation

The current benchmark establishes that explicit overlap-bridge candidates can
be reduced safely before Relation classification. It does not establish a
general solution to discovering Connections whose endpoint provenance is
fully disjoint. The lexical diagnostic is encouraging, but its workload is too
large and its diagnostic denominator too small for a broad claim.
