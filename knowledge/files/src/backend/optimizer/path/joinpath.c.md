# joinpath.c — per-pair join path enumeration

- **Source:** `source/src/backend/optimizer/path/joinpath.c` (2526 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

Given a join rel and its two component rels, generate every plausible
NestLoop / MergeJoin / HashJoin path (serial + parallel variants) and
feed each through `add_path`. [from-comment:101-105]

## 2. Sole public entry

`void add_paths_to_joinrel(root, joinrel, outerrel, innerrel, jointype,
sjinfo, restrictlist)` at line 122. [verified-by-code]

## 3. Internal dispatch

Path generation is split across (all static):

- `sort_inner_and_outer` — explicitly sort *both* sides for a mergejoin
- `match_unsorted_outer` — exploit any pre-existing outer ordering
  (mergejoin or nestloop, parameterized inner)
- `hash_inner_and_outer` — Hash join (only when hashable equijoin
  clauses exist)
- `consider_parallel_nestloop`, `consider_parallel_mergejoin` — partial
  variants for Gather above
- `try_partial_mergejoin_path`, `generate_mergejoin_paths` — internal
  helpers
- `select_mergejoin_clauses` — pick which restrict clauses are eligible
  for mergejoining; also returns `mergejoin_allowed` (FALSE for some
  outer-join cases) [verified-by-code]

## 4. JoinType subtleties

- `jointype` passed in may be *flipped* relative to `sjinfo->jointype`
  (when we're trying the other join direction). [from-comment:110-112]
- `JOIN_UNIQUE_OUTER` and `JOIN_UNIQUE_INNER` are local-only signals
  that one side has been unique-ified; outside this routine they appear
  as `JOIN_INNER` plus `sjinfo->jointype == JOIN_SEMI`. [from-comment:114-120]

## 5. Parameterization helpers

`PATH_PARAM_BY_PARENT`, `PATH_PARAM_BY_REL_SELF`, `PATH_PARAM_BY_REL`
macros (line 39-46) — paths parameterized by a parent rel count as
parameterized by any child rel during partitionwise join consideration.
[verified-by-code]

## 6. Tags
`[verified-by-code]` ×4, `[from-comment]` ×3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
