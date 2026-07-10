# Linear Algebra Mini Lecture 001: Vector Spaces, Matrices, and Eigenvalues

**Status:** Benchmark input  
**Version:** v0.1  
**Created:** 2026-07-10  
**Source:** Authored for this repository.

---

A vector space is a set of objects called vectors that can be added together and multiplied by scalars while satisfying the vector space axioms. A basis is a set of independent vectors that can represent every vector in the space through linear combinations. The number of vectors in a basis is the dimension of the vector space.

A matrix is a rectangular array of numbers that can represent a linear transformation once bases have been chosen for the input and output spaces. Matrix multiplication corresponds to composing linear transformations, and changing a basis changes the matrix representation without changing the underlying transformation.

For a square matrix \(A\), an eigenvector is a nonzero vector \(v\) whose direction is preserved by the transformation represented by \(A\). The corresponding eigenvalue \(\lambda\) satisfies

\[
Av = \lambda v.
\]

Eigenvalues are connected to the characteristic polynomial \(\det(\lambda I - A)\). They are important because they reveal directions in which a linear transformation acts by simple scaling.
