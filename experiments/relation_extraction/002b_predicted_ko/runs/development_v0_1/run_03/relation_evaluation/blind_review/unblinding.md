# Evidence Review Unblinding

Unblinding occurred only after both condition evaluation snapshots were final,
contained 36 evaluated pairs, had zero pending adjudications, and passed their
artifact-hash checks.

| Blinded review set | Condition | KO representation | Decisions |
| --- | --- | --- | --- |
| Review Set 1 | B_prime | Predicted Knowledge Objects | 13 supported, 0 not supported |
| Review Set 2 | A_prime | Oracle Knowledge Objects | 9 supported, 1 not supported |

The single `not_supported` decision is `R2-03 / rel_dev_012`. Its selected
evidence says Gradient Descent moves in "this direction" without including the
sentence that resolves the direction as the negative Gradient or an update
formula containing the Gradient.

