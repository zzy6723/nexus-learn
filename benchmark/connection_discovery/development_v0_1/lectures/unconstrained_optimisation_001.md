# Mathematical Optimisation 002: First- and Second-Order Methods

**Course:** Mathematical Optimisation
**Topic:** Unconstrained Optimisation
**Sequence:** 2
**Source:** Authored for this repository.

---

An objective function assigns a scalar value to each candidate parameter vector. Unconstrained optimisation seeks a parameter vector that minimizes this objective function.

Gradient descent requires the gradient of the objective function. With step size \(\alpha_k>0\), the method moves opposite to the gradient. The gradient descent update is

\[
x_{k+1}=x_k-\alpha_k\nabla f(x_k).
\]

For a small proposed displacement, the first-order Taylor approximation predicts the resulting objective change. This explains why a displacement opposite to the gradient is locally descending when the step size is sufficiently small.

The Newton optimisation method additionally requires the Hessian matrix to model local curvature. When the Hessian is invertible, the Newton optimisation update is

\[
x_{k+1}=x_k-H_f(x_k)^{-1}\nabla f(x_k).
\]

The Newton optimisation method can take a full curvature-adjusted step, whereas gradient descent controls movement through an explicit step size.
