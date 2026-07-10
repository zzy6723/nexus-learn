# Prompt: optimisation_001

Extract Knowledge Objects from the following lecture snippet.

Allowed object types:

- `Concept`
- `Method`
- `Formula`

Return only valid JSON with this schema:

```json
{
  "lecture_id": "<lecture_id>",
  "knowledge_objects": [
    {
      "id": "lower_snake_case_stable_identifier",
      "name": "Canonical Name",
      "type": "Concept | Method | Formula",
      "aliases": ["optional alias"],
      "short_definition": "One sentence definition based only on the input.",
      "source_span": "Exact text span from the input that grounds the object."
    }
  ]
}
```

Rules:

1. Use only information present in the lecture snippet.
2. Prefer canonical mathematical names.
3. Merge duplicates into one object.
4. Keep `source_span` short but sufficient.
5. Do not output `RELATED_TO`, prerequisites, or any relation type.
6. If no valid Knowledge Objects exist, return an empty `knowledge_objects` list.

Lecture ID:

```text
optimisation_001
```

Lecture snippet:

```text
In mathematical optimisation, an objective function assigns a real value to each feasible input. An optimisation problem asks for an input that makes the objective function as small or as large as possible. In an unconstrained minimisation problem, the feasible inputs are usually all points in a space such as \(\mathbb{R}^n\), and the goal is to minimise a differentiable function \(f(x)\).

If \(f\) is differentiable, the gradient \(\nabla f(x)\) describes local change. The negative gradient \(-\nabla f(x)\) is a descent direction because it points toward the direction of steepest local decrease. Gradient descent is a first-order iterative method that repeatedly moves in this direction:

\[
x_{k+1} = x_k - \alpha_k \nabla f(x_k).
\]

The scalar \(\alpha_k\) is the step size. It controls how far the method moves at iteration \(k\). A line search is a method for choosing a step size that gives sufficient decrease in the objective function.

For convex functions, every local minimum is also a global minimum. A stationary point is a point where the gradient is zero. In smooth optimisation, stationary points are important because they describe candidates for local optima.
```
