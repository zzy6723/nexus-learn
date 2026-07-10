# Calculus Mini Lecture 001: Gradients, Partial Derivatives, and Taylor Approximation

**Status:** Benchmark input  
**Version:** v0.1  
**Created:** 2026-07-10  
**Source:** Authored for this repository

---

Let \(f:\mathbb{R}^n \to \mathbb{R}\) be a differentiable scalar-valued function. A partial derivative measures how \(f\) changes when one coordinate changes while the other coordinates are held fixed. The gradient \(\nabla f(x)\) collects these partial derivatives into a vector. For a unit direction \(u\), the directional derivative is \(\nabla f(x)\cdot u\), so the gradient points in the direction of steepest local increase. A point where the gradient is the zero vector is called a stationary point.

Taylor approximation describes the local behavior of a differentiable function near a point. The first-order Taylor approximation around \(a\) is

\[
f(a+h) \approx f(a) + \nabla f(a)\cdot h.
\]

For twice differentiable functions, a second-order approximation also includes the Hessian matrix, which describes local curvature. These approximations are useful because they turn a complicated function into a local linear or quadratic model. In optimization, this local model helps explain why the gradient gives a useful direction for changing the input.
