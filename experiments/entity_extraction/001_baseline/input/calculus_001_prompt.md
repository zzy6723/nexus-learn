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
