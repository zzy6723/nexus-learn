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
