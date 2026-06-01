# pathkeys.c — pathkey construction, comparison, and merge-clause matching

- **Source:** `source/src/backend/optimizer/path/pathkeys.c` (2299 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read
- **Canonical narrative:** `source/src/backend/optimizer/README` (PathKey section)

## 1. Purpose

PathKeys describe the *interesting* sort orders a Path produces (or would
produce, with a sort on top). Each PathKey is (`EquivalenceClass`,
opfamily collation, strategy, nulls_first). Two PathKeys with the same
canonical EC pointer are equal — that's the only allowed equality test.
[from-comment:295-302]

## 2. Public surface

### Construction
- `make_canonical_pathkey` (55) — must not be called before EC merging
  completes. [from-comment:50-54]
- `make_pathkeys_for_sortclauses` (1335) / `_extended` (1380) — used for
  ORDER BY / GROUP BY clauses. [from-comment:1325-1335]
- `build_index_pathkeys` (739) — pathkeys an index can produce; caller
  should follow up with `truncate_useless_pathkeys`. [from-comment:730-738]
- `build_partition_pathkeys` (918) — sort order delivered by an Append
  over an ordered partitioning. [from-comment:910-915]
- `build_expression_pathkey` (999) — pathkey for an arbitrary expression.
- `build_join_pathkeys` (1294) — sort order preserved through a join.
- `convert_subquery_pathkeys` (1053) — bridge child Query pathkeys to
  the parent's EC space.

### Comparison
- `compare_pathkeys` (303), `pathkeys_contained_in` (342),
  `pathkeys_count_contained_in` (557) — canonicalization means pointer
  equality is sufficient. [from-comment:300-302]
- `append_pathkeys` (106) — dedup-append.

### Cheapest selection
- `get_cheapest_path_for_pathkeys` (619) — picks cheapest path among
  candidates that satisfy a required ordering, parameterization, and
  parallel constraint. [from-comment:608-616]
- `get_cheapest_fractional_path_for_pathkeys` (665) — same but for
  LIMIT-style early-termination cost. [from-comment:656-662]
- `get_cheapest_parallel_safe_total_inner` (698) — used for inner side
  of parallel join.

### GROUP BY reordering
- `group_keys_reorder_by_pathkeys` (466) — keep two orderings of the
  GROUP BY clause: one matching ORDER BY, one matching path ordering.
  Gated by `enable_group_by_reordering` GUC. [from-comment:455-466]

### Mergejoin scaffolding
- `initialize_mergeclause_eclasses` (1462) — links a mergejoinable
  RestrictInfo to its left/right EC, but only tentatively (pre-EC-merge).
  [from-comment:1450-1457]
- `update_mergeclause_eclasses` (1509) — chase to canonical EC after
  merging. [from-comment:1500-1507]
- `find_mergeclauses_for_outer_pathkeys` (1543) — clauses usable for a
  mergejoin against a given outer ordering. [from-comment:1537-1543]
- `select_outer_pathkeys_for_merge`, `make_inner_pathkeys_for_merge`,
  `trim_mergeclauses_for_inner_pathkeys` (later in file).

## 3. Invariants

- **Canonical pathkeys are pointer-comparable.** Any code that constructs
  a PathKey *must* route through `make_canonical_pathkey`. [from-comment]
- **EC merging must be complete first.** `make_canonical_pathkey` will
  not find the right EC otherwise — hence the planner's strict ordering
  in `query_planner` (planmain.c). [from-comment:50-54]
- **Mergejoin eclass links can be stale.** Code that uses them must
  call `update_mergeclause_eclasses` first. [from-comment:1450-1505]

## 4. Tags
`[verified-by-code]` ×4, `[from-comment]` ×12
