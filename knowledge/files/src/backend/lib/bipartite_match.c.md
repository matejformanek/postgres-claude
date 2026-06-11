# `src/backend/lib/bipartite_match.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~180
- **Source:** `source/src/backend/lib/bipartite_match.c`

Hopcroft-Karp maximum-cardinality bipartite matching, used by the
extended-statistics MCV-list selection logic in the planner. Sets U
and V are indexed 1..size; adjacency is caller-supplied (an array
where `adjacency[u][0]` is the count and `adjacency[u][1..]` are V
neighbors). [verified-by-code §bipartite_match.c:36-50]

## API / entry points

- `BipartiteMatchState *BipartiteMatch(int u_size, int v_size, short **adjacency)`
  — `u_size`/`v_size` must each be `< SHRT_MAX` (enforced with `elog
  ERROR`). Returns palloc'd state holding `matching` (size of the
  matching) and `pair_uv`/`pair_vu` (pairings). [verified-by-code §bipartite_match.c:38-46]
- `BipartiteMatchFree(BipartiteMatchState *)` — frees state fields
  but NOT the adjacency array (caller-owned). [from-comment §bipartite_match.c:74-77]

## Notable invariants / details

- Uses `SHRT_MAX` as the "infinity" distance marker, which is safe
  because BFS distances are bounded by `u_size < SHRT_MAX`.
  [from-comment §bipartite_match.c:24-29]
- BFS queue is sized `u_size + 2` and never wraps (`qhead` only
  monotonically grows because each node is enqueued at most once).
  [from-comment §bipartite_match.c:98-99]
- DFS calls `check_stack_depth()` per level — recursion depth is
  bounded by the BFS depth which is bounded by `u_size`. [verified-by-code §bipartite_match.c:161]
- `CHECK_FOR_INTERRUPTS()` between each BFS+DFS phase, defensively.
  [verified-by-code §bipartite_match.c:67]

## Potential issues

- None.
