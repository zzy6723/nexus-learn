# Optimisation Mini Lecture 001: Objective Functions and Gradient Descent

**Status:** Benchmark input  
**Version:** v0.1  
**Created:** 2026-07-10  
**Source:** Authored for this repository.

---

In mathematical optimisation, an objective function assigns a real value to each feasible input. An optimisation problem asks for an input that makes the objective function as small or as large as possible. In an unconstrained minimisation problem, the feasible inputs are usually all points in a space such as \(\mathbb{R}^n\), and the goal is to minimise a differentiable function \(f(x)\).

If \(f\) is differentiable, the gradient \(\nabla f(x)\) describes local change. The negative gradient \(-\nabla f(x)\) is a descent direction because it points toward the direction of steepest local decrease. Gradient descent is a first-order iterative method that repeatedly moves in this direction:

\[
x_{k+1} = x_k - \alpha_k \nabla f(x_k).
\]

The scalar \(\alpha_k\) is the step size. It controls how far the method moves at iteration \(k\). A line search is a method for choosing a step size that gives sufficient decrease in the objective function.

For convex functions, every local minimum is also a global minimum. A stationary point is a point where the gradient is zero. In smooth optimisation, stationary points are important because they describe candidates for local optima.
