# Statistics Mini Lecture 001: Likelihood and Parameter Estimation

**Status:** Relation holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-13  
**Source:** Authored for this repository.

---

A statistical model is a family of probability distributions indexed by an unknown parameter \(\theta\). The likelihood is defined from this statistical model by treating the observations as fixed and comparing possible parameter values. For independent observations \(x_1,\ldots,x_n\), it is

\[
L(\theta; x_{1:n}) = \prod_{i=1}^{n} p(x_i \mid \theta).
\]

The log-likelihood is obtained by taking the logarithm of the likelihood. Independence turns the product into a sum:

\[
\ell(\theta) = \log L(\theta; x_{1:n}) = \sum_{i=1}^{n} \log p(x_i \mid \theta).
\]

Maximum likelihood estimation uses the log-likelihood as its objective and selects a parameter value that maximizes it:

\[
\widehat{\theta}_{\mathrm{MLE}} = \operatorname*{arg\,max}_{\theta}\, \ell(\theta).
\]

The score function is the derivative of the log-likelihood with respect to the parameter,

\[
s(\theta) = \nabla_{\theta}\ell(\theta).
\]

At an interior differentiable optimum, an MLE candidate satisfies the score equation \(s(\theta)=0\). When this equation has no closed-form solution, Newton's method can be applied within maximum likelihood estimation to compute a candidate numerically.
