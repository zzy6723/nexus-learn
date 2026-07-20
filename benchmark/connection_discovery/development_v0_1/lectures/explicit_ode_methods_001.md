# Numerical Methods 002: Explicit ODE Integration

**Course:** Numerical Methods
**Topic:** Explicit ODE Methods
**Sequence:** 2
**Source:** Authored for this repository.

---

An initial value problem combines a differential equation \(y'(t)=F(t,y(t))\) with an initial value \(y(t_0)=y_0\).

Applying the first-order Taylor approximation over a step of length \(h\) gives the Forward Euler method. Its Forward Euler update is

\[
y_{n+1}=y_n+hF(t_n,y_n).
\]

The step size \(h\) sets the spacing between consecutive numerical time points. The Forward Euler update formalizes how the Forward Euler method advances one step from the current approximation.

The local truncation error is the one-step error obtained when the exact current solution value is inserted into the numerical update. For the Forward Euler method, this error is governed by the terms omitted after the first-order Taylor approximation.
