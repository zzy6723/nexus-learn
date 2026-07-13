# Numerical Methods Mini Lecture 001: Root Finding

**Status:** Relation holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-13  
**Source:** Authored for this repository.

---

A root-finding problem asks for a value \(x^*\) at which a scalar function is zero:

\[
f(x^*) = 0.
\]

Newton's method uses the derivative to replace the function locally by its tangent line. Provided \(f'(x_k)\neq 0\), its update is

\[
x_{k+1} = x_k - \frac{f(x_k)}{f'(x_k)}.
\]

The damped Newton method extends Newton's method by scaling the Newton correction with a factor between zero and one. This extra control can prevent a full Newton step from moving too far when the current iterate is not yet near a root.

The bisection method begins with a sign-changing bracket \([a,b]\) satisfying \(f(a)f(b)<0\). It evaluates the midpoint

\[
m = \frac{a+b}{2}
\]

and retains the half-interval whose endpoints still have opposite signs.

Newton's method and the bisection method contrast in the information they use: Newton's method requires derivative values and can converge rapidly near a root, whereas bisection uses only function signs and preserves a bracket at every iteration.
