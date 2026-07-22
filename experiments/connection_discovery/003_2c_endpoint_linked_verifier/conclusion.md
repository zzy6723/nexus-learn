# 003-2c Conclusion

**Status:** Development method completed; frozen criteria failed

Endpoint-linked Evidence verification v0.1.1 is not selected as a validated
Connection Discovery method.

The method completed its full execution contract and improved several
development diagnostics relative to the one-stage and two-stage methods. It
raised positive edge precision to `0.2206`, positive typed-edge recall to
`0.3659`, `NO_RELATION` accuracy to `0.5385`, and full-universe F1 to `0.2752`.
It also eliminated `RELATED_TO` fallback and reduced false-positive Relations
from 40 to 36.

Those gains are not operationally sufficient. Five of eight predeclared 003-2c
criteria failed. The verifier produced 17 conflicting direct-edge decisions,
nine false negatives, and 42 semantically unsupported Evidence sets. Semantic
Evidence support remained `0.4085`, effectively unchanged from the two-stage
method and below the `0.90` threshold.

The result narrows the research problem: deterministic endpoint-linked windows
improve input scope and Evidence materialization, but an unsupervised LLM
verifier still does not reliably distinguish direct typed graph edges from
mediated, contextual, or abstraction-shifted connections. The remaining
failure is semantic classification rather than candidate coverage or Evidence
transport.

No further prompt or pair-specific architecture tuning on this development
benchmark is authorized. The current 125 pairs have informed three classifier
designs and are no longer suitable for an independent claim. A future cycle
must introduce a materially different learning signal, such as frozen
contrastive direct-versus-mediated examples or calibrated supervised
classification, and reserve a fresh source for independent validation.

Predicted-canonical discovery, learner-facing ranking, and Experiment 004
product validation remain blocked. Experiment 003 may be closed as a complete
negative Technical Validation programme with useful infrastructure and a
localized unresolved semantic boundary.
