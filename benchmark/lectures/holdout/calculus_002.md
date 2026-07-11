# Calculus Mini Lecture 002: Chain Rule and Jacobian Matrices

**Status:** Holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-11  
**Source:** Authored for this repository.

---

Let \(g:\mathbb{R}^m \to \mathbb{R}^n\) and \(f:\mathbb{R}^n \to \mathbb{R}\) be differentiable functions. The composite function \(h = f \circ g\) maps an input \(x \in \mathbb{R}^m\) to \(f(g(x))\). The chain rule describes how the derivative of the composite function depends on the derivatives of \(f\) and \(g\).

For a differentiable vector-valued function \(g\), the Jacobian matrix \(J_g(x)\) collects all first-order partial derivatives of the output components of \(g\). It gives the best local linear approximation to \(g\) near \(x\).

For the scalar-valued composite function \(h(x)=f(g(x))\), the multivariable chain rule can be written as

\[
\nabla h(x) = J_g(x)^\top \nabla f(g(x)).
\]

This formula shows how gradients and Jacobian matrices work together. The Jacobian transfers local changes in the input space of \(g\) into local changes in the input space of \(f\).
