# Review Set 1

Pending items: 13

Decision for each item: `supported` or `not_supported`, with a short rationale.

## R1-01 - rel_dev_001

**Predicted edge:** Gradient (Concept) `REQUIRES` Partial Derivative (Concept)

**Candidate objects:**

- ko_a: Gradient (Concept)
- ko_b: Partial Derivative (Concept)

**Predicted evidence:**

- `calculus_001`: The gradient ∇f(x) collects these partial derivatives into a vector.

**Gold evidence reference:**

- `calculus_001`: The gradient \(\nabla f(x)\) collects these partial derivatives into a vector.

**KO source spans:**

- Gradient: The gradient ∇f(x) collects these partial derivatives into a vector.
- Partial Derivative: A partial derivative measures how f changes when one coordinate changes while the other coordinates are held fixed.

**Lecture context:**

### calculus_001

Let \(f:\mathbb{R}^n \to \mathbb{R}\) be a differentiable scalar-valued function. A partial derivative measures how \(f\) changes when one coordinate changes while the other coordinates are held fixed. The gradient \(\nabla f(x)\) collects these partial derivatives into a vector. For a unit direction \(u\), the directional derivative is \(\nabla f(x)\cdot u\), so the gradient points in the direction of steepest local increase. A point where the gradient is the zero vector is called a stationary point.

Taylor approximation describes the local behavior of a differentiable function near a point. The first-order Taylor approximation around \(a\) is

\[
f(a+h) \approx f(a) + \nabla f(a)\cdot h.
\]

For twice differentiable functions, a second-order approximation also includes the Hessian matrix, which describes local curvature. These approximations are useful because they turn a complicated function into a local linear or quadratic model. In optimization, this local model helps explain why the gradient gives a useful direction for changing the input.


**Your decision:**

- Decision: 
- Rationale: 

## R1-02 - rel_dev_002

**Predicted edge:** Directional Derivative (Concept) `REQUIRES` Gradient (Concept)

**Candidate objects:**

- ko_a: Directional Derivative (Concept)
- ko_b: Gradient (Concept)

**Predicted evidence:**

- `calculus_001`: For a unit direction u, the directional derivative is ∇f(x)·u, so the gradient points in the direction of steepest local increase.

**Gold evidence reference:**

- `calculus_001`: For a unit direction \(u\), the directional derivative is \(\nabla f(x)\cdot u\), so the gradient points in the direction of steepest local increase.

**KO source spans:**

- Directional Derivative: For a unit direction u, the directional derivative is ∇f(x)·u, so the gradient points in the direction of steepest local increase.
- Gradient: The gradient ∇f(x) collects these partial derivatives into a vector.

**Lecture context:**

### calculus_001

Let \(f:\mathbb{R}^n \to \mathbb{R}\) be a differentiable scalar-valued function. A partial derivative measures how \(f\) changes when one coordinate changes while the other coordinates are held fixed. The gradient \(\nabla f(x)\) collects these partial derivatives into a vector. For a unit direction \(u\), the directional derivative is \(\nabla f(x)\cdot u\), so the gradient points in the direction of steepest local increase. A point where the gradient is the zero vector is called a stationary point.

Taylor approximation describes the local behavior of a differentiable function near a point. The first-order Taylor approximation around \(a\) is

\[
f(a+h) \approx f(a) + \nabla f(a)\cdot h.
\]

For twice differentiable functions, a second-order approximation also includes the Hessian matrix, which describes local curvature. These approximations are useful because they turn a complicated function into a local linear or quadratic model. In optimization, this local model helps explain why the gradient gives a useful direction for changing the input.


**Your decision:**

- Decision: 
- Rationale: 

## R1-03 - rel_dev_004

**Predicted edge:** First-Order Taylor Approximation (Formula) `FORMALIZES` Taylor Approximation (Concept)

**Candidate objects:**

- ko_a: First-Order Taylor Approximation (Formula)
- ko_b: Taylor Approximation (Concept)

**Predicted evidence:**

- `calculus_001`: The first-order Taylor approximation around a is f(a+h) ≈ f(a) + ∇f(a)·h.
- `calculus_001`: Taylor approximation describes the local behavior of a differentiable function near a point.

**Gold evidence reference:**

- `calculus_001`: The first-order Taylor approximation around \(a\) is
- `calculus_001`: f(a+h) \approx f(a) + \nabla f(a)\cdot h.

**KO source spans:**

- First-Order Taylor Approximation: f(a+h) ≈ f(a) + ∇f(a)·h.
- Taylor Approximation: Taylor approximation describes the local behavior of a differentiable function near a point.

**Lecture context:**

### calculus_001

Let \(f:\mathbb{R}^n \to \mathbb{R}\) be a differentiable scalar-valued function. A partial derivative measures how \(f\) changes when one coordinate changes while the other coordinates are held fixed. The gradient \(\nabla f(x)\) collects these partial derivatives into a vector. For a unit direction \(u\), the directional derivative is \(\nabla f(x)\cdot u\), so the gradient points in the direction of steepest local increase. A point where the gradient is the zero vector is called a stationary point.

Taylor approximation describes the local behavior of a differentiable function near a point. The first-order Taylor approximation around \(a\) is

\[
f(a+h) \approx f(a) + \nabla f(a)\cdot h.
\]

For twice differentiable functions, a second-order approximation also includes the Hessian matrix, which describes local curvature. These approximations are useful because they turn a complicated function into a local linear or quadratic model. In optimization, this local model helps explain why the gradient gives a useful direction for changing the input.


**Your decision:**

- Decision: 
- Rationale: 

## R1-04 - rel_dev_009

**Predicted edge:** Eigenvalue Equation (Formula) `FORMALIZES` Eigenvalue (Concept)

**Candidate objects:**

- ko_a: Eigenvalue (Concept)
- ko_b: Eigenvalue Equation (Formula)

**Predicted evidence:**

- `linear_algebra_001`: The corresponding eigenvalue λ satisfies Av = λ v.

**Gold evidence reference:**

- `linear_algebra_001`: The corresponding eigenvalue \(\lambda\) satisfies
- `linear_algebra_001`: Av = \lambda v.

**KO source spans:**

- Eigenvalue: The corresponding eigenvalue λ satisfies Av = λ v.
- Eigenvalue Equation: Av = λ v

**Lecture context:**

### linear_algebra_001

A vector space is a set of objects called vectors that can be added together and multiplied by scalars while satisfying the vector space axioms. A basis is a set of independent vectors that can represent every vector in the space through linear combinations. The number of vectors in a basis is the dimension of the vector space.

A matrix is a rectangular array of numbers that can represent a linear transformation once bases have been chosen for the input and output spaces. Matrix multiplication corresponds to composing linear transformations, and changing a basis changes the matrix representation without changing the underlying transformation.

For a square matrix \(A\), an eigenvector is a nonzero vector \(v\) whose direction is preserved by the transformation represented by \(A\). The corresponding eigenvalue \(\lambda\) satisfies

\[
Av = \lambda v.
\]

Eigenvalues are connected to the characteristic polynomial \(\det(\lambda I - A)\). They are important because they reveal directions in which a linear transformation acts by simple scaling.


**Your decision:**

- Decision: 
- Rationale: 

## R1-05 - rel_dev_011

**Predicted edge:** Unconstrained Minimisation Problem (Concept) `EXTENDS` Optimisation Problem (Concept)

**Candidate objects:**

- ko_a: Optimisation Problem (Concept)
- ko_b: Unconstrained Minimisation Problem (Concept)

**Predicted evidence:**

- `optimisation_001`: In an unconstrained minimisation problem, the feasible inputs are usually all points in a space such as ℝ^n, and the goal is to minimise a differentiable function f(x).

**Gold evidence reference:**

- `optimisation_001`: In an unconstrained minimisation problem, the feasible inputs are usually all points in a space such as \(\mathbb{R}^n\), and the goal is to minimise a differentiable function \(f(x)\).

**KO source spans:**

- Optimisation Problem: An optimisation problem asks for an input that makes the objective function as small or as large as possible
- Unconstrained Minimisation Problem: unconstrained minimisation problem

**Lecture context:**

### optimisation_001

In mathematical optimisation, an objective function assigns a real value to each feasible input. An optimisation problem asks for an input that makes the objective function as small or as large as possible. In an unconstrained minimisation problem, the feasible inputs are usually all points in a space such as \(\mathbb{R}^n\), and the goal is to minimise a differentiable function \(f(x)\).

If \(f\) is differentiable, the gradient \(\nabla f(x)\) describes local change. The negative gradient \(-\nabla f(x)\) is a descent direction because it points toward the direction of steepest local decrease. Gradient descent is a first-order iterative method that repeatedly moves in this direction:

\[
x_{k+1} = x_k - \alpha_k \nabla f(x_k).
\]

The scalar \(\alpha_k\) is the step size. It controls how far the method moves at iteration \(k\). A line search is a method for choosing a step size that gives sufficient decrease in the objective function.

For convex functions, every local minimum is also a global minimum. A stationary point is a point where the gradient is zero. In smooth optimisation, stationary points are important because they describe candidates for local optima.


**Your decision:**

- Decision: 
- Rationale: 

## R1-06 - rel_dev_013

**Predicted edge:** Gradient Descent Update (Formula) `FORMALIZES` Gradient Descent (Method)

**Candidate objects:**

- ko_a: Gradient Descent (Method)
- ko_b: Gradient Descent Update (Formula)

**Predicted evidence:**

- `optimisation_001`: x_{k+1} = x_k - α_k ∇f(x_k).

**Gold evidence reference:**

- `optimisation_001`: x_{k+1} = x_k - \alpha_k \nabla f(x_k).

**KO source spans:**

- Gradient Descent: Gradient descent is a first-order iterative method that repeatedly moves in this direction
- Gradient Descent Update: \[ x_{k+1} = x_k - \alpha_k \nabla f(x_k). \]

**Lecture context:**

### optimisation_001

In mathematical optimisation, an objective function assigns a real value to each feasible input. An optimisation problem asks for an input that makes the objective function as small or as large as possible. In an unconstrained minimisation problem, the feasible inputs are usually all points in a space such as \(\mathbb{R}^n\), and the goal is to minimise a differentiable function \(f(x)\).

If \(f\) is differentiable, the gradient \(\nabla f(x)\) describes local change. The negative gradient \(-\nabla f(x)\) is a descent direction because it points toward the direction of steepest local decrease. Gradient descent is a first-order iterative method that repeatedly moves in this direction:

\[
x_{k+1} = x_k - \alpha_k \nabla f(x_k).
\]

The scalar \(\alpha_k\) is the step size. It controls how far the method moves at iteration \(k\). A line search is a method for choosing a step size that gives sufficient decrease in the objective function.

For convex functions, every local minimum is also a global minimum. A stationary point is a point where the gradient is zero. In smooth optimisation, stationary points are important because they describe candidates for local optima.


**Your decision:**

- Decision: 
- Rationale: 

## R1-07 - rel_dev_015

**Predicted edge:** Chain Rule (Method) `REQUIRES` Composite Function (Concept)

**Candidate objects:**

- ko_a: Chain Rule (Method)
- ko_b: Composite Function (Concept)

**Predicted evidence:**

- `calculus_002`: The chain rule describes how the derivative of the composite function depends on the derivatives of f and g.

**Gold evidence reference:**

- `calculus_002`: The chain rule describes how the derivative of the composite function depends on the derivatives of \(f\) and \(g\).

**KO source spans:**

- Chain Rule: The chain rule describes how the derivative of the composite function depends on the derivatives of f and g.
- Composite Function: The composite function h = f ∘ g maps an input x ∈ ℝ^m to f(g(x)).

**Lecture context:**

### calculus_002

Let \(g:\mathbb{R}^m \to \mathbb{R}^n\) and \(f:\mathbb{R}^n \to \mathbb{R}\) be differentiable functions. The composite function \(h = f \circ g\) maps an input \(x \in \mathbb{R}^m\) to \(f(g(x))\). The chain rule describes how the derivative of the composite function depends on the derivatives of \(f\) and \(g\).

For a differentiable vector-valued function \(g\), the Jacobian matrix \(J_g(x)\) collects all first-order partial derivatives of the output components of \(g\). It gives the best local linear approximation to \(g\) near \(x\).

For the scalar-valued composite function \(h(x)=f(g(x))\), the multivariable chain rule can be written as

\[
\nabla h(x) = J_g(x)^\top \nabla f(g(x)).
\]

This formula shows how gradients and Jacobian matrices work together. The Jacobian transfers local changes in the input space of \(g\) into local changes in the input space of \(f\).


**Your decision:**

- Decision: 
- Rationale: 

## R1-08 - rel_dev_016

**Predicted edge:** Multivariable Chain Rule Formula (Formula) `FORMALIZES` Chain Rule (Method)

**Candidate objects:**

- ko_a: Chain Rule (Method)
- ko_b: Multivariable Chain Rule Formula (Formula)

**Predicted evidence:**

- `calculus_002`: ∇h(x) = J_g(x)^⊤ ∇f(g(x)).

**Gold evidence reference:**

- `calculus_002`: the multivariable chain rule can be written as
- `calculus_002`: \nabla h(x) = J_g(x)^\top \nabla f(g(x)).

**KO source spans:**

- Chain Rule: The chain rule describes how the derivative of the composite function depends on the derivatives of f and g.
- Multivariable Chain Rule Formula: ∇h(x) = J_g(x)^⊤ ∇f(g(x)).

**Lecture context:**

### calculus_002

Let \(g:\mathbb{R}^m \to \mathbb{R}^n\) and \(f:\mathbb{R}^n \to \mathbb{R}\) be differentiable functions. The composite function \(h = f \circ g\) maps an input \(x \in \mathbb{R}^m\) to \(f(g(x))\). The chain rule describes how the derivative of the composite function depends on the derivatives of \(f\) and \(g\).

For a differentiable vector-valued function \(g\), the Jacobian matrix \(J_g(x)\) collects all first-order partial derivatives of the output components of \(g\). It gives the best local linear approximation to \(g\) near \(x\).

For the scalar-valued composite function \(h(x)=f(g(x))\), the multivariable chain rule can be written as

\[
\nabla h(x) = J_g(x)^\top \nabla f(g(x)).
\]

This formula shows how gradients and Jacobian matrices work together. The Jacobian transfers local changes in the input space of \(g\) into local changes in the input space of \(f\).


**Your decision:**

- Decision: 
- Rationale: 

## R1-09 - rel_dev_019

**Predicted edge:** Projection Formula (Formula) `FORMALIZES` Orthogonal Projection (Method)

**Candidate objects:**

- ko_a: Orthogonal Projection (Method)
- ko_b: Projection Formula (Formula)

**Predicted evidence:**

- `linear_algebra_002`: proj_u(v) = (v·u)/(u·u) u.

**Gold evidence reference:**

- `linear_algebra_002`: \operatorname{proj}_u(v) = \frac{v \cdot u}{u \cdot u}u.

**KO source spans:**

- Orthogonal Projection: Orthogonal projection is a method for finding the closest point in a subspace to a given vector.
- Projection Formula: \operatorname{proj}_u(v) = \frac{v \cdot u}{u \cdot u}u.

**Lecture context:**

### linear_algebra_002

An inner product is an operation that takes two vectors and returns a scalar. In Euclidean space, the standard inner product is the dot product. Two vectors are orthogonal when their inner product is zero.

Orthogonal projection is a method for finding the closest point in a subspace to a given vector. If \(u\) is a nonzero vector, the projection of \(v\) onto the one-dimensional subspace spanned by \(u\) is

\[
\operatorname{proj}_u(v) = \frac{v \cdot u}{u \cdot u}u.
\]

Least squares problems use projection ideas to solve inconsistent systems. Given a matrix \(A\) and a vector \(b\), the least squares problem asks for a vector \(x\) that minimizes \(\|Ax-b\|^2\). When the columns of \(A\) are independent, the solution satisfies the normal equations

\[
A^\top A x = A^\top b.
\]


**Your decision:**

- Decision: 
- Rationale: 

## R1-10 - rel_dev_021

**Predicted edge:** Normal Equations (Formula) `FORMALIZES` Least Squares Problem (Concept)

**Candidate objects:**

- ko_a: Least Squares Problem (Concept)
- ko_b: Normal Equations (Formula)

**Predicted evidence:**

- `linear_algebra_002`: A^⊤ A x = A^⊤ b.

**Gold evidence reference:**

- `linear_algebra_002`: the solution satisfies the normal equations
- `linear_algebra_002`: A^\top A x = A^\top b.

**KO source spans:**

- Least Squares Problem: Least squares problems use projection ideas to solve inconsistent systems.
- Normal Equations: A^\top A x = A^\top b.

**Lecture context:**

### linear_algebra_002

An inner product is an operation that takes two vectors and returns a scalar. In Euclidean space, the standard inner product is the dot product. Two vectors are orthogonal when their inner product is zero.

Orthogonal projection is a method for finding the closest point in a subspace to a given vector. If \(u\) is a nonzero vector, the projection of \(v\) onto the one-dimensional subspace spanned by \(u\) is

\[
\operatorname{proj}_u(v) = \frac{v \cdot u}{u \cdot u}u.
\]

Least squares problems use projection ideas to solve inconsistent systems. Given a matrix \(A\) and a vector \(b\), the least squares problem asks for a vector \(x\) that minimizes \(\|Ax-b\|^2\). When the columns of \(A\) are independent, the solution satisfies the normal equations

\[
A^\top A x = A^\top b.
\]


**Your decision:**

- Decision: 
- Rationale: 

## R1-11 - rel_dev_024

**Predicted edge:** Expected Value Formula (Formula) `FORMALIZES` Expected Value (Concept)

**Candidate objects:**

- ko_a: Expected Value (Concept)
- ko_b: Expected Value Formula (Formula)

**Predicted evidence:**

- `probability_001`: E[X] = ∑_x x P(X=x).

**Gold evidence reference:**

- `probability_001`: \mathbb{E}[X] = \sum_x x P(X=x).

**KO source spans:**

- Expected Value: The expected value of a random variable is a weighted average of its possible values.
- Expected Value Formula: \mathbb{E}[X] = \sum_x x P(X=x).

**Lecture context:**

### probability_001

A random variable is a function that assigns a numerical value to each outcome of a random experiment. The probability distribution of a random variable describes how probability is assigned to its possible values.

The expected value of a random variable is a weighted average of its possible values. For a discrete random variable \(X\), the expected value is

\[
\mathbb{E}[X] = \sum_x x P(X=x).
\]

Variance measures how far a random variable typically is from its expected value. It can be defined as

\[
\operatorname{Var}(X) = \mathbb{E}[(X-\mathbb{E}[X])^2].
\]

Conditional probability measures the probability of an event given that another event has occurred. If \(P(B)>0\), then

\[
P(A \mid B) = \frac{P(A \cap B)}{P(B)}.
\]

Bayes' rule rewrites conditional probability in a form that is useful for updating beliefs:

\[
P(A \mid B) = \frac{P(B \mid A)P(A)}{P(B)}.
\]


**Your decision:**

- Decision: 
- Rationale: 

## R1-12 - rel_dev_026

**Predicted edge:** Variance Formula (Formula) `FORMALIZES` Variance (Concept)

**Candidate objects:**

- ko_a: Variance (Concept)
- ko_b: Variance Formula (Formula)

**Predicted evidence:**

- `probability_001`: Var(X) = E[(X-E[X])^2].

**Gold evidence reference:**

- `probability_001`: \operatorname{Var}(X) = \mathbb{E}[(X-\mathbb{E}[X])^2].

**KO source spans:**

- Variance: Variance measures how far a random variable typically is from its expected value.
- Variance Formula: \operatorname{Var}(X) = \mathbb{E}[(X-\mathbb{E}[X])^2].

**Lecture context:**

### probability_001

A random variable is a function that assigns a numerical value to each outcome of a random experiment. The probability distribution of a random variable describes how probability is assigned to its possible values.

The expected value of a random variable is a weighted average of its possible values. For a discrete random variable \(X\), the expected value is

\[
\mathbb{E}[X] = \sum_x x P(X=x).
\]

Variance measures how far a random variable typically is from its expected value. It can be defined as

\[
\operatorname{Var}(X) = \mathbb{E}[(X-\mathbb{E}[X])^2].
\]

Conditional probability measures the probability of an event given that another event has occurred. If \(P(B)>0\), then

\[
P(A \mid B) = \frac{P(A \cap B)}{P(B)}.
\]

Bayes' rule rewrites conditional probability in a form that is useful for updating beliefs:

\[
P(A \mid B) = \frac{P(B \mid A)P(A)}{P(B)}.
\]


**Your decision:**

- Decision: 
- Rationale: 

## R1-13 - rel_dev_027

**Predicted edge:** Conditional Probability Formula (Formula) `FORMALIZES` Conditional Probability (Concept)

**Candidate objects:**

- ko_a: Conditional Probability (Concept)
- ko_b: Conditional Probability Formula (Formula)

**Predicted evidence:**

- `probability_001`: P(A|B) = P(A∩B)/P(B).

**Gold evidence reference:**

- `probability_001`: P(A \mid B) = \frac{P(A \cap B)}{P(B)}.

**KO source spans:**

- Conditional Probability: Conditional probability measures the probability of an event given that another event has occurred.
- Conditional Probability Formula: P(A \mid B) = \frac{P(A \cap B)}{P(B)}.

**Lecture context:**

### probability_001

A random variable is a function that assigns a numerical value to each outcome of a random experiment. The probability distribution of a random variable describes how probability is assigned to its possible values.

The expected value of a random variable is a weighted average of its possible values. For a discrete random variable \(X\), the expected value is

\[
\mathbb{E}[X] = \sum_x x P(X=x).
\]

Variance measures how far a random variable typically is from its expected value. It can be defined as

\[
\operatorname{Var}(X) = \mathbb{E}[(X-\mathbb{E}[X])^2].
\]

Conditional probability measures the probability of an event given that another event has occurred. If \(P(B)>0\), then

\[
P(A \mid B) = \frac{P(A \cap B)}{P(B)}.
\]

Bayes' rule rewrites conditional probability in a form that is useful for updating beliefs:

\[
P(A \mid B) = \frac{P(B \mid A)P(A)}{P(B)}.
\]


**Your decision:**

- Decision: 
- Rationale: 
