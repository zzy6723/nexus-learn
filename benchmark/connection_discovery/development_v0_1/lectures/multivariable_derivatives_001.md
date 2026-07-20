# Mathematical Optimisation 001: Multivariable Derivatives

**Course:** Mathematical Optimisation
**Topic:** Multivariable Derivatives
**Sequence:** 1
**Source:** Authored for this repository.

---

For a differentiable scalar function \(f:\mathbb{R}^d\to\mathbb{R}\), the gradient is the vector of first partial derivatives,

\[
\nabla f(x)=\left(\frac{\partial f}{\partial x_1},\ldots,\frac{\partial f}{\partial x_d}\right)^\top.
\]

The Hessian matrix collects the second partial derivatives of \(f\). At a point \(x\), its \((i,j)\) entry is

\[
[H_f(x)]_{ij}=\frac{\partial^2 f}{\partial x_i\partial x_j}(x).
\]

The first-order Taylor approximation uses the function value and gradient at \(x\) to approximate the value after a small displacement \(\Delta x\). It is formalized by the first-order Taylor formula

\[
T_1(x+\Delta x;x)=f(x)+\nabla f(x)^\top\Delta x.
\]

The gradient supplies the local linear term, while the Hessian matrix supplies the curvature term used by a second-order approximation.
