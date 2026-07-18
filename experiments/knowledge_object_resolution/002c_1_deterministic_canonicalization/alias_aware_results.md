# Alias-Aware + Same Type v0.1 Results

## Setup

The Alias-Aware method used the same frozen benchmark, normalization contract,
runner, method commit, and evaluation protocol as the Exact method. Its only
additional input was `benchmark/ko_aliases_v0_1.json`.

## Results

All measured results were identical to the Exact method:

- 39/39 mention coverage;
- 38 predicted clusters;
- SAME_OBJECT precision, recall, and F1 of 1.0000;
- B-cubed precision, recall, and F1 of 1.0000;
- 38/38 exact gold-cluster matches;
- zero false merges, false splits, or provenance losses.

The alias resource changed no cluster membership in this benchmark. It
therefore provided no observed development benefit over the simpler Exact
method.

Synthetic diagnostics remain separate: the alias resource repaired the two
predeclared alias splits but could not disambiguate same-name `Degree` mentions.
