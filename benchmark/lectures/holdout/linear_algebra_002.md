# Linear Algebra Mini Lecture 002: Inner Products, Projections, and Least Squares

**Status:** Holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-11  
**Source:** Authored for this repository.

---

An inner product is an operation that takes two vectors and returns a scalar. In Euclidean space, the standard inner product is the dot product. Two vectors are orthogonal when their inner product is zero.

Orthogonal projection is a method for finding the closest point in a subspace to a given vector. If \(u\) is a nonzero vector, the projection of \(v\) onto the one-dimensional subspace spanned by \(u\) is

\[
\operatorname{proj}_u(v) = \frac{v \cdot u}{u \cdot u}u.
\]

Least squares problems use projection ideas to solve inconsistent systems. Given a matrix \(A\) and a vector \(b\), the least squares problem asks for a vector \(x\) that minimizes \(\|Ax-b\|^2\). When the columns of \(A\) are independent, the solution satisfies the normal equations

\[
A^\top A x = A^\top b.
\]
