# Statistical Learning 002: Least Squares and Regularisation

**Course:** Statistical Learning
**Topic:** Least Squares Learning
**Sequence:** 2
**Source:** Authored for this repository.

---

Linear regression models a response using a linear function of the input features. Ordinary least squares fits a linear regression model by minimizing the least squares objective over the coefficient vector \(\beta\).

For observations \((x_i,y_i)\), the mean squared error formula is

\[
\operatorname{MSE}(\beta)=\frac{1}{n}\sum_{i=1}^{n}(y_i-x_i^\top\beta)^2.
\]

This formula formalizes the least squares objective up to a positive constant scaling. Gradient descent can be applied to ordinary least squares by using the gradient of this objective function.

Ridge regression extends ordinary least squares by adding a squared-coefficient penalty to the objective. The penalty can improve numerical stability and reduce sensitivity to highly correlated features.

Under a Gaussian noise model, ordinary least squares also has a maximum likelihood estimation interpretation. That equivalence depends on the statistical assumptions and is not an identity between the two methods in every model.
