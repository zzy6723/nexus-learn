# Graph Algorithms Mini Lecture 001: Shortest Paths

**Status:** Relation holdout benchmark input  
**Version:** v0.1  
**Created:** 2026-07-13  
**Source:** Authored for this repository.

---

A weighted directed graph assigns a numerical weight \(w(u,v)\) to each directed edge \((u,v)\). A path is a sequence of compatible directed edges. Its path cost is the sum of their edge weights:

\[
C(v_0,\ldots,v_k) = \sum_{i=0}^{k-1} w(v_i,v_{i+1}).
\]

The single-source shortest-path problem asks for a minimum-cost path from a chosen source vertex to every reachable vertex. Dijkstra's algorithm is applied to this problem when all edge weights are nonnegative.

Dijkstra's algorithm stores tentative distance estimates in a priority queue. After removing a vertex \(u\) with the smallest tentative distance, it applies edge relaxation to each outgoing edge. Relaxation is formalized by the update

\[
d(v) \leftarrow \min\{d(v),\, d(u)+w(u,v)\}.
\]

A* search extends Dijkstra's algorithm by using a heuristic function \(h(v)\) to guide which vertex is explored next. Its queue priority combines the known path cost with the heuristic estimate, and setting \(h(v)=0\) recovers Dijkstra's ordering.
