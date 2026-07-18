# KO Canonicalization Fixtures

`semantic_identity_cases.json` is a synthetic semantic fixture, not benchmark
evidence. It covers identity boundaries that occur too rarely or not at all in
the initial 39-mention development-reuse set:

- different-name aliases that denote one Method;
- an abbreviation and its expanded name;
- equal names with different mathematical referents;
- a Method and its related Formula remaining distinct.

The frozen real Ground Truth remains authoritative for 002C-1 development
evaluation. These cases test checker and method behavior only and must not be
combined with the real benchmark metrics.
