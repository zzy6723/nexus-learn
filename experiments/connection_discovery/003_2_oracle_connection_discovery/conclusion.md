# 003-2 Conclusion

**Status:** Development comparison completed; frozen success gates failed

Oracle-canonical Connection classification is not operationally viable under the
current v0.1 method and benchmark criteria.

The baseline overconnected heavily. Prompt 002 is a real but insufficient
development improvement: false-positive Relations fall from 68 to 40,
`NO_RELATION` accuracy rises from 0.1282 to 0.4872, semantic Evidence support
rises from 0.1217 to 0.4512, and full-universe F1 rises from 0.1867 to 0.2185.

Those gains do not satisfy the frozen gates and do not preserve all positive
behavior. Positive typed-edge recall falls from 0.3415 to 0.3171, three false
negatives appear, direction accuracy falls from 0.6087 to 0.5417, and
cross-course recall falls from 0.3214 to 0.2857.

Prompt 002 is retained as the stronger development diagnostic condition, not as
a validated default or production method. The observed error pattern points to
a method-level problem: the classifier needs a stricter direct-edge decision
gate and more reliable endpoint-role serialization, rather than another
pair-specific prompt patch.

Experiment 003 must therefore not claim successful Connection Discovery.
Subsequent predicted-canonical or ranking work may be performed only as clearly
labelled diagnostics, or deferred until a revised Oracle-canonical method passes
the frozen classification and full-universe gates.
