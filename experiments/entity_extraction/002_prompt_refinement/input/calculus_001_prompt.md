# Prompt: calculus_001

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
calculus_001
```

Lecture snippet:

```text
Let \(f:\mathbb{R}^n \to \mathbb{R}\) be a differentiable scalar-valued function. A partial derivative measures how \(f\) changes when one coordinate changes while the other coordinates are held fixed. The gradient \(\nabla f(x)\) collects these partial derivatives into a vector. For a unit direction \(u\), the directional derivative is \(\nabla f(x)\cdot u\), so the gradient points in the direction of steepest local increase. A point where the gradient is the zero vector is called a stationary point.

Taylor approximation describes the local behavior of a differentiable function near a point. The first-order Taylor approximation around \(a\) is

\[
f(a+h) \approx f(a) + \nabla f(a)\cdot h.
\]

For twice differentiable functions, a second-order approximation also includes the Hessian matrix, which describes local curvature. These approximations are useful because they turn a complicated function into a local linear or quadratic model. In optimization, this local model helps explain why the gradient gives a useful direction for changing the input.
```
