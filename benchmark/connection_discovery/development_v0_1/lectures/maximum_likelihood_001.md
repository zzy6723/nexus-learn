# Statistical Learning 001: Maximum Likelihood

**Course:** Statistical Learning
**Topic:** Maximum Likelihood
**Sequence:** 1
**Source:** Authored for this repository.

---

A statistical model is a family of probability distributions indexed by an unknown parameter \(\theta\). For observed data, the log-likelihood measures how the assumed parameter value supports those observations.

Maximum likelihood estimation treats the log-likelihood as an objective function and selects a parameter value that maximizes it. The score function is the gradient of the log-likelihood with respect to the parameter,

\[
s(\theta)=\nabla_{\theta}\ell(\theta).
\]

At an interior differentiable maximum, a candidate satisfies the score equation \(s(\theta)=0\). Finding such a candidate is a root-finding problem. When the score equation has no closed-form solution, Newton's root-finding method can be applied within maximum likelihood estimation.

For a Gaussian linear regression model with constant variance, maximizing the log-likelihood is equivalent to minimizing the least squares objective. Under this assumption, ordinary least squares and maximum likelihood estimation select the same coefficient vector.
