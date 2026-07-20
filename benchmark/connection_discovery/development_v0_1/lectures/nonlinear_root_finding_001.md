# Numerical Methods 001: Nonlinear Root Finding

**Course:** Numerical Methods
**Topic:** Nonlinear Root Finding
**Sequence:** 1
**Source:** Authored for this repository.

---

A root-finding problem asks for a point \(x^*\) satisfying \(g(x^*)=0\). Newton's root-finding method requires the derivative of \(g\) and replaces the function locally by its tangent line.

Provided \(g'(x_k)\neq 0\), the Newton root update is

\[
x_{k+1}=x_k-\frac{g(x_k)}{g'(x_k)}.
\]

The Newton root update formalizes Newton's root-finding method in one dimension. Near a simple root, the derivative controls the tangent correction.

The damped Newton method extends Newton's root-finding method by multiplying the correction by a factor \(\lambda_k\in(0,1]\). Damping can prevent a full Newton correction from moving too far when the current iterate is not yet near a root.
