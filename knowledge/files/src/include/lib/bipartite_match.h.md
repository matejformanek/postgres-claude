# `src/include/lib/bipartite_match.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 46

## Role

Maximum-cardinality bipartite matching (Hopcroft-Karp). Sole
internal user is the planner's GROUPING SETS chain-decomposition
via Dilworth's theorem
(`source/src/backend/optimizer/plan/planner.c`). Polynomial-time
minimization of sort operations for grouping-set plans.
[from-comment] `source/src/include/lib/bipartite_match.h:20-25`

## Public API

- `BipartiteMatch(u_size, v_size, adjacency)` →
  `BipartiteMatchState*`
- `BipartiteMatchFree(state)`

## Invariants

- INV-1: `adjacency[u]` is `[k, v1, v2, …, vk]` (first short is
  count). [from-comment]
  `source/src/include/lib/bipartite_match.h:14`
- INV-2: `short`-sized indices — implicit cap at INT16_MAX edges
  per side. [verified-by-code] line 32-39.

## Trust boundary (Phase D)

None — internal planner data.

## Cross-refs

- `knowledge/subsystems/optimizer-planner.md` (if exists)
- A SQL-level user can influence `u_size`/`v_size` only via the
  shape of GROUPING SETS in their query; the short cap is an
  implicit safety limit.

## Issues

- ISSUE-DESIGN: `short` indices give a hard cap of ~32k grouping
  columns; well above any realistic query. (None — fine.)
