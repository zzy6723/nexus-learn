# Differential Equations Mini Lecture 001: Initial Value Methods

**Status:** Relation holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-13  
**Source:** Authored for this repository.

---

An ordinary differential equation relates an unknown function of one variable to its derivatives. A first-order equation can be written as

\[
y'(t) = F(t,y(t)).
\]

An initial value problem combines an ordinary differential equation with an initial condition such as \(y(t_0)=y_0\). The vector field \(F\) specifies the slope that the solution should follow at each state.

The forward Euler method is applied to an initial value problem by advancing from the current approximation along the current vector-field slope. Its update is

\[
y_{n+1} = y_n + hF(t_n,y_n).
\]

The step size \(h\) sets the spacing between consecutive numerical time points. Smaller steps usually reduce discretization error but require more updates over a fixed time interval.

Heun's method extends the forward Euler method with a predictor-corrector step. It first forms the Euler predictor

\[
\widetilde{y}_{n+1} = y_n + hF(t_n,y_n),
\]

then averages the slope at the current point with the slope at the predicted point. The corrected update is

\[
y_{n+1} = y_n + \frac{h}{2}\left(F(t_n,y_n)+F(t_n+h,\widetilde{y}_{n+1})\right).
\]
