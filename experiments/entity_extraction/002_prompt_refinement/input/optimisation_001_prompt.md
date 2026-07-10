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
      "source_span": "Exact text span copied from the input."
    }
  ]
}
```

Object inclusion rules:

1. Extract named or clearly defined educational entities that could later participate in typed learning relations.
2. Include central objects and useful supporting objects if they are explicitly named or explained in the text.
3. Do not extract broad domains, section headings, historical people, isolated variables, or ordinary words.
4. Merge duplicates into one canonical object.

Type rules:

1. Use `Concept` for mathematical objects, properties, structures, and named constructs.
2. Use `Method` for procedures, algorithms, or techniques.
3. Use `Formula` only for symbolic equations, update rules, or displayed mathematical expressions.
4. If a named mathematical construct is mentioned together with a formula, the named construct is usually a `Concept`; the equation itself may be a separate `Formula` only if it defines or updates something important.
5. Displayed equations should usually be extracted as `Formula` objects when they define, characterize, or update a concept or method.

Grounding rules:

1. `source_span` must be an exact substring copied from the lecture snippet.
2. Do not normalize LaTeX into Unicode inside `source_span`.
3. Keep `source_span` short but sufficient.
4. If no exact grounding span exists, do not extract the object.

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
