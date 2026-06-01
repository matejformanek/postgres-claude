# pathnode.c — add_path dominance + every Path constructor

- **Source:** `source/src/backend/optimizer/util/pathnode.c` (4556 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## 1. Purpose

"Routines to manipulate pathlists and create path nodes"
[from-comment:3-4]. Two concerns under one roof:

1. **Tournament logic:** `add_path` / `add_partial_path` /
   `add_path_precheck` / `add_partial_path_precheck` / `set_cheapest`
   — the gatekeepers that decide which Paths survive on a RelOptInfo's
   pathlist.
2. **Path constructors:** every `create_*_path` factory called from
   `allpaths.c`, `indxpath.c`, `joinpath.c`, `planner.c`. Each pairs
   `makeNode(<PathType>)` + `cost_*` from `costsize.c`.

## 2. The five comparator/cheapest routines

| Line | Function | Use |
|---|---|---|
| 68 | `compare_path_costs(p1, p2, criterion)` | Exact compare on STARTUP_COST or TOTAL_COST; disabled_nodes lex-trumps cost; tie on chosen field falls through to the other [verified-by-code:67-111] |
| 123 | `compare_fractional_path_costs(p1, p2, fraction)` | For LIMIT-ish fetches; linear interpolation between startup and total [verified-by-code:122-149] |
| 181 | `compare_path_costs_fuzzily(p1, p2, fuzz_factor)` | Returns COSTS_EQUAL/BETTER1/BETTER2/DIFFERENT with `STD_FUZZ_FACTOR = 1.01` (1% slop). Disabled_nodes still trumps. DIFFERENT means each wins on one of startup/total [verified-by-code:180-238, from-comment:152-178] |
| 268 | `set_cheapest(parent_rel)` | After all add_path calls: scan pathlist, set `cheapest_startup_path`, `cheapest_total_path`, `cheapest_unique_path` (NULL stub), `cheapest_parameterized_paths` list [from-comment:241-265] |
| 1483 / 1506 | `append_total_cost_compare` / `append_startup_cost_compare` | list_sort callbacks for parallel Append child ordering [verified-by-code:1484, 1506] |

### `STD_FUZZ_FACTOR = 1.01` (line 47)
"It provides a tradeoff between planner runtime and the accuracy of path
cost comparisons" [from-comment:43-46]. Used everywhere outside the
inner second-pass compare which uses `1.0000000001` (line 565, 851).

## 3. `add_path` — the tournament (line 459)

[verified-by-code:458-666, from-comment:438-457]

Loop over existing pathlist; for each old path:

1. **Disabled_nodes lex compare first** (in `compare_path_costs_fuzzily`)
   — fewer disabled wins outright [verified-by-code:186-193]
2. **Fuzzy cost compare** with `STD_FUZZ_FACTOR`
3. If cost differs and pathkeys+param compatible → loser eliminated
4. If cost ties **and** pathkeys tie **and** param relids equal:
   - parallel_safe wins over not-safe
   - else rows wins (lower)
   - else tighter fuzzy compare (`1.0000000001`)
   - else **arbitrarily keep old** [from-comment:550-554]
5. Subset comparisons on `PATH_REQ_OUTER`: a path with strictly fewer
   parameterization rels can still dominate one with more, but only if
   rows ≤ and parallel_safe ≥ [verified-by-code:589-606]

### The pfree-on-reject safety rule

"deleting a previously-accepted Path is safe because we know that Paths
of this rel cannot yet be referenced from any other rel" — but
**IndexPath is excluded** from pfree because BitmapHeapPath references
IndexPaths as bitmap leaves. [from-comment:438-452, verified-by-code:630,
663]

### Insertion ordering

Paths are inserted **sorted by (disabled_nodes, total_cost) ascending**,
which lets later iteration short-circuit [verified-by-code:639-642].
`insert_at` is recomputed as the loop progresses.

## 4. `add_path_precheck` (line 686)

Cheap "can this possibly survive?" check before paying for a full Path
construction (esp. before `cost_index` on huge index lists).
[from-comment:669-684] Takes bare cost+pathkeys+req_outer numbers — no
Path needed yet. Conservative: assumes rowcount cannot dominate
(parametrization-superset paths get fewer rows by assumption
[from-comment:674-680]).

## 5. `add_partial_path` (line 793) + precheck (line 912)

**Different rules from `add_path`:**

- Paths must be `parallel_safe` (asserted) [verified-by-code:803]
- Partial paths ignore parameterization (always unparameterized)
- All partial paths produce the same number of rows (no row-count
  dominance) [from-comment:780-784]
- IndexPath **not** excluded from pfree on reject — partial bitmap heap
  paths can't reference partial IndexPaths [from-comment:786-790]
- Caller must finish all partial paths before constructing any
  GatherPath that consumes them — otherwise `add_partial_path` could
  pfree a path the Gather already references [from-comment:786-789]

`add_partial_path_precheck` differs from `add_path_precheck` in: never
exits early ("we expect partial_pathlist to be very short")
[from-comment:919-925].

## 6. Path constructors — by category

Each constructor: `makeNode(<Path>)` → fill struct fields → call
matching `cost_*` from costsize.c → return.

### Base-rel scan paths

| Line | Constructor |
|---|---|
| 1026 | `create_seqscan_path` |
| 1051 | `create_samplescan_path` |
| 1092 | `create_index_path` |
| 1149 | `create_bitmap_heap_path` |
| 1182 | `create_bitmap_and_path` |
| 1234 | `create_bitmap_or_path` |
| 1286 | `create_tidscan_path` |
| 1315 | `create_tidrangescan_path` |
| 1909 | `create_subqueryscan_path` |
| 1939 | `create_functionscan_path` |
| 1965 | `create_tablefuncscan_path` |
| 1991 | `create_valuesscan_path` |
| 2017 | `create_ctescan_path` |
| 2043 | `create_namedtuplestorescan_path` |
| 2069 | `create_resultscan_path` |
| 2095 | `create_worktablescan_path` |
| 2128 | `create_foreignscan_path` |
| 2176 | `create_foreign_join_path` |
| 2229 | `create_foreign_upper_path` |

Canonical template (`create_seqscan_path`) [verified-by-code:1025-1044]:
sets pathtype, parent, pathtarget=`rel->reltarget`, param_info via
`get_baserel_parampathinfo`, parallel flags, pathkeys=NIL, then
`cost_seqscan`.

### Append/MergeAppend

| Line | Constructor |
|---|---|
| 1351 | `create_append_path` — sorts non-partial children by descending total cost for parallel append [from-comment:1393-1401] |
| 1523 | `create_merge_append_path` |
| 1664 | `create_group_result_path` |

`create_append_path` is unusual: it accepts an `AppendPathInput input`
struct (not just a subpath list) and may call **either** `get_baserel_
parampathinfo` (when this is a base-rel appendrel) **or**
`get_appendrel_parampathinfo` (otherwise) [verified-by-code:1380-1386].

### Material / Memoize / Gather

| Line | Constructor |
|---|---|
| 1711 | `create_material_path` |
| 1745 | `create_memoize_path` |
| 1812 | `create_gather_merge_path` |
| 1864 | `create_gather_path` |

### Join paths

`calc_nestloop_required_outer` (line 2276) and
`calc_non_nestloop_required_outer` (line 2303) compute the joinrel's
`required_outer` Relids from outer+inner paths.

| Line | Constructor |
|---|---|
| 2355 | `create_nestloop_path` |
| 2452 | `create_mergejoin_path` |
| 2520 | `create_hashjoin_path` |

### Upper-rel / wrapper paths

| Line | Constructor |
|---|---|
| 2586 | `create_projection_path` |
| 2695 | `apply_projection_to_path` — *mutates* a Path's tlist in place if possible (avoids ProjectionPath wrap) |
| 2784 | `create_set_projection_path` — for tlists with SRFs |
| 2854 | `create_incremental_sort_path` |
| 2903 | `create_sort_path` |
| 2947 | `create_group_path` |
| 3004 | `create_unique_path` |
| 3056 | `create_agg_path` |
| 3138 | `create_groupingsets_path` |
| 3301 | `create_minmaxagg_path` |
| 3392 | `create_windowagg_path` |
| 3465 | `create_setop_path` |
| 3584 | `create_recursiveunion_path` |
| 3629 | `create_lockrows_path` |
| 3691 | `create_modifytable_path` |
| 3792 | `create_limit_path` |
| 3848 | `adjust_limit_rows_costs` — helper used by createplan to recompute LIMIT rows under a Limit plan |

## 7. Reparameterization

Used by partition-wise join / appendrel where children must share a
common parameterization:

| Line | Function |
|---|---|
| 3917 | `reparameterize_path(root, path, required_outer, loop_count)` — supports only a few pathtypes (SeqScan, Index, BitmapHeap, SubqueryScan, RTE_RESULT, Append). Returns NULL if can't. **Does NOT call `add_path`** (would risk pfree of the source path) [from-comment:3910-3914, verified-by-code:3916-4085] |
| 4087 | `reparameterize_path_by_child(root, path, child_rel)` — covers many more pathtypes recursively; rewrites required_outer to swap parent-rel for child-rel relids; used by partition-wise join |
| 4383 | `path_is_reparameterizable_by_child(path, child_rel)` — predicate; must stay in sync with `reparameterize_path_by_child` (createplan.c asserts) |
| 4514 | `reparameterize_pathlist_by_child` (static) |
| 4542 | `pathlist_is_reparameterizable_by_child` (static) |

## 8. Invariants

- **`add_path` rejects parameterized-path pathkeys.** Comment:
  "Pretend parameterized paths have no pathkeys" — line 472-473. So
  pathkeys-based ordering only matters for unparameterized paths
  [verified-by-code:472-473].
- **disabled_nodes is the lexicographic primary key everywhere.** Both
  `add_path` and `add_partial_path` and the precheck variants
  short-circuit on it [verified-by-code:71-77, 186-193, 942-948].
- **`set_cheapest` must run exactly once per rel** after all paths
  added. Pathlist mutation after `set_cheapest` is a planner bug —
  `cheapest_*_path` would dangle [from-comment:264-265].
- **`add_partial_path` mismatched-startup-vs-total `COSTS_DIFFERENT`
  case yields `continue`** (line 977) — partial pathlist may contain
  both Pareto-front points for use by Gather and GatherMerge
  respectively [verified-by-code:973-977].
- **`STD_FUZZ_FACTOR`** is duplicated in `add_partial_path_precheck`
  by manual arithmetic (line 949) — must stay in sync with
  `compare_path_costs_fuzzily`.
- **Recycling IndexPaths:** the comment at 438-452 is the only
  authoritative source for why IndexPaths are leaked when rejected;
  removing this exception silently breaks bitmap planning.
- **`apply_projection_to_path`** is the planner's main "don't add
  another node, just edit the existing one" optimization — but it
  bails out and returns a ProjectionPath wrap if the underlying node
  isn't `is_projection_capable_path()`.

## 9. Cross-refs

- The cost functions every constructor calls: `knowledge/files/src/backend/optimizer/path/costsize.c.md`
- Where these get called from: `knowledge/files/src/backend/optimizer/path/allpaths.c.md`, `joinpath.c.md`, `indxpath.c.md`
- Path→Plan downstream: `knowledge/files/src/backend/optimizer/plan/createplan.c.md`
- Architecture (Path/Plan model, dominance pruning): `knowledge/architecture/planner.md`, `knowledge/subsystems/optimizer.md`
- The README that explains why discarding is safe:
  `source/src/backend/optimizer/README` (paragraph on path comparison)

## 10. Tags
`[verified-by-code]` ×20, `[from-comment]` ×15

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
