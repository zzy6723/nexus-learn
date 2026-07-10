# Prompt: linear_algebra_001

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
linear_algebra_001
```

Lecture snippet:

```text
A vector space is a set of objects called vectors that can be added together and multiplied by scalars while satisfying the vector space axioms. A basis is a set of independent vectors that can represent every vector in the space through linear combinations. The number of vectors in a basis is the dimension of the vector space.

A matrix is a rectangular array of numbers that can represent a linear transformation once bases have been chosen for the input and output spaces. Matrix multiplication corresponds to composing linear transformations, and changing a basis changes the matrix representation without changing the underlying transformation.

For a square matrix \(A\), an eigenvector is a nonzero vector \(v\) whose direction is preserved by the transformation represented by \(A\). The corresponding eigenvalue \(\lambda\) satisfies

\[
Av = \lambda v.
\]

Eigenvalues are connected to the characteristic polynomial \(\det(\lambda I - A)\). They are important because they reveal directions in which a linear transformation acts by simple scaling.
```
