# Probability Mini Lecture 001: Random Variables, Expectation, and Conditional Probability

**Status:** Holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-11  
**Source:** Authored for this repository.

---

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
