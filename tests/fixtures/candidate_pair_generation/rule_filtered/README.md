# Rule-Filtered Candidate Fixtures

`rule_cases.json` is a model-visible feature fixture. It contains three
lectures and seven predicted Knowledge Objects, yielding exactly five
lecture-local unordered pairs:

- one pair selected by source proximity and lexical overlap;
- one pair selected by mathematical-symbol overlap;
- three pairs with no triggered rule.

The fixture contains no candidate labels, Relation labels, Evidence,
rationales, or pair-specific allowlists. Tests derive the normalized inventory,
lecture inventory, pair universe, decision audit, and selection artifacts in a
temporary directory.
