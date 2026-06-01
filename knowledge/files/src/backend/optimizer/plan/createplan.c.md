# createplan.c — Path → Plan conversion

- **Source:** `source/src/backend/optimizer/plan/createplan.c` (7316 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

"Routines to create the desired plan for processing a query. Planning is
complete, we just need to convert the selected Path into a Plan."
[from-comment:3-6]

Given the cheapest `Path` tree chosen from `(UPPERREL_FINAL, NULL)`,
recurse top-down emitting `Plan` nodes. Vars in tlists/quals at this
point still use the parser's numbering; `setrefs.c` runs afterwards to
rewrite them. [from-comment:330-332]

## 2. Entry points

| Line | Function | Role |
|---|---|---|
| 339 | `create_plan` | Public entry. Resets `root->curOuterRels`/`curOuterParams`, calls `create_plan_recurse(best_path, CP_EXACT_TLIST)`, runs `apply_tlist_labeling`, `SS_attach_initplans`, asserts all NestLoopParams got assigned [verified-by-code:339-383] |
| 390 | `create_plan_recurse` | Switch on `best_path->pathtype` → one of the `create_*_plan` helpers. `check_stack_depth()` guards [verified-by-code:390-544] |
| 1991 | `change_plan_targetlist` | Public: replace a finished Plan's tlist, possibly inserting a Result above [verified-by-code:1991] |
| 6396 | `make_sort_from_pathkeys` | Public (used outside file too) [verified-by-code:6396] |
| 6508 | `materialize_finished_plan` | Public — used by SS_make_initplan_output_param etc. [verified-by-code:6508] |
| 7231 | `is_projection_capable_path` | Public predicate: can this Path's exec node project? Used by upper layers deciding whether a Result is needed [verified-by-code:7231] |
| 7281 | `is_projection_capable_plan` | Same predicate on a Plan [verified-by-code:7281] |

## 3. The CP_* flag system (line 47-72)

`create_plan_recurse(root, best_path, flags)` accepts an OR-ed `int flags`
that constrains the child's tlist. **Every per-node helper must respect
these.** [from-comment:47-72]

| Flag | Meaning |
|---|---|
| `CP_EXACT_TLIST` (0x01) | Plan node must emit exactly path's pathtarget; overrides CP_SMALL/CP_LABEL |
| `CP_SMALL_TLIST` (0x02) | Prefer narrow tlist; passed by Sort/Hash which spool tuples |
| `CP_LABEL_TLIST` (0x04) | Tlist columns matching `sortgrouprefs` must carry the label; passed by Sort/Group needing sortgroup info |
| `CP_IGNORE_TLIST` (0x08) | Caller will replace tlist; helper can emit whatever |

`use_physical_tlist` (line 857) is the helper that decides — given these
flags — whether to use the rel's full `reltarget` vs the path's narrow
target.

## 4. Dispatch table — `create_plan_recurse` pathtype → helper

Scan/base paths funnel through `create_scan_plan` (line 551):

| Pathtype | Helper | Line |
|---|---|---|
| `T_SeqScan` | `create_seqscan_plan` | 2755 |
| `T_SampleScan` | `create_samplescan_plan` | 2793 |
| `T_IndexScan` / `T_IndexOnlyScan` | `create_indexscan_plan` | 2844 |
| `T_BitmapHeapScan` | `create_bitmap_scan_plan` + `create_bitmap_subplan` | 3040, 3170 |
| `T_TidScan` | `create_tidscan_plan` | 3378 |
| `T_TidRangeScan` | `create_tidrangescan_plan` | 3475 |
| `T_SubqueryScan` | `create_subqueryscan_plan` | 3540 |
| `T_FunctionScan` | `create_functionscan_plan` | 3599 |
| `T_TableFuncScan` | `create_tablefuncscan_plan` | 3642 |
| `T_ValuesScan` | `create_valuesscan_plan` | 3685 |
| `T_CteScan` | `create_ctescan_plan` | 3729 |
| `T_NamedTuplestoreScan` | `create_namedtuplestorescan_plan` | 3824 |
| `T_WorkTableScan` | `create_worktablescan_plan` | 3901 |
| `T_Result` (RTE_RESULT) | `create_resultscan_plan` | 3863 |
| `T_ForeignScan` | `create_foreignscan_plan` | 3961 |
| `T_CustomScan` | `create_customscan_plan` | 4116 |

Join paths through `create_join_plan` (line 1073):
- `T_NestLoop` → `create_nestloop_plan` (line 4187)
- `T_MergeJoin` → `create_mergejoin_plan` (line 4339)
- `T_HashJoin` → `create_hashjoin_plan` (line 4693)

Upper-rel paths:
- `T_Append` → `create_append_plan` (line 1208) — also marks async-capable
  via `mark_async_capable_plan` (line 1132)
- `T_MergeAppend` → `create_merge_append_plan` (line 1455)
- `T_Result` flavors → `create_group_result_plan` (1632) /
  `create_projection_plan` (1859) / `create_minmaxagg_plan` (2398)
- `T_ProjectSet` → `create_project_set_plan` (1657)
- `T_Material` → `create_material_plan` (1683)
- `T_Memoize` → `create_memoize_plan` (1711)
- `T_Sort` / `T_IncrementalSort` → `create_sort_plan` (2020) /
  `create_incrementalsort_plan` (2054)
- `T_Group` / `T_Unique` / `T_Agg` → 2081 / 2120 / 2156
- `T_Agg` may be `GroupingSetsPath` → `create_groupingsets_plan` (2240)
- `T_WindowAgg` → `create_windowagg_plan` (2467)
- `T_SetOp` → `create_setop_plan` (2562)
- `T_RecursiveUnion` → `create_recursiveunion_plan` (2598)
- `T_LockRows` → `create_lockrows_plan` (2630)
- `T_ModifyTable` → `create_modifytable_plan` (2653)
- `T_Limit` → `create_limit_plan` (2694)
- `T_Gather` / `T_GatherMerge` → `create_gather_plan` (1765) /
  `create_gather_merge_plan` (1803)

Default case `elog(ERROR, "unrecognized node type")` at line 536.

## 5. Scan-plan template (`create_seqscan_plan`, line 2754)

The canonical 4-step pattern every scan helper follows
[verified-by-code:2754-2784]:

1. `order_qual_clauses(root, scan_clauses)` — sort quals into cheapest-first
   evaluation order
2. `extract_actual_clauses(scan_clauses, false)` — strip RestrictInfo
   wrappers; ignore pseudoconstants (they've gone to a gating Result above)
3. `replace_nestloop_params(root, scan_clauses)` — if this path is
   parameterized, rewrite outer-Vars to NestLoopParams (line 4882)
4. `make_<plan>(...)` constructor + `copy_generic_path_info` to copy
   rows/cost/tlist/etc from the Path

## 6. Gating Result nodes

`get_gating_quals` (line 994) extracts pseudoconstant quals from a list.
If any exist, `create_gating_plan` (line 1014) wraps the child in a Result
node whose `resconstantqual` enforces them once (vs once per tuple).
[verified-by-code:1014, from-comment:1099-1107]

## 7. Index-scan plumbing

`fix_indexqual_references` (line 4967) / `fix_indexorderby_references`
(line 5008) / `fix_indexqual_clause` (line 5037) / `fix_indexqual_operand`
(line 5109) rewrite IndexClauses' operands into the form executor wants:
`(Var → IndexVar)` on the indexed side, RHS replaced where needed.

## 8. NestLoop parameter handover

- `create_nestloop_plan` (line 4187):
  - Calls `reparameterize_path_by_child` (in pathnode.c) on
    `innerjoinpath` if it's parameterized by the outer's topmost parent
    [verified-by-code:4205-4218]
  - Adds outer relids to `root->curOuterRels` before planning inner
  - Inner-side `replace_nestloop_params` adds entries to
    `root->curOuterParams` (line 4882)
  - Extracts those NestLoopParams from `curOuterParams` keyed by
    outerrelids → `nestParams` of the NestLoop node
- `create_plan` checks at the end that `curOuterParams == NIL`
  ("failed to assign all NestLoopParams to plan nodes")
  [verified-by-code:372-374]

## 9. Sort/IncrementalSort cost-labelling

`label_sort_with_costsize` (line 5399) and
`label_incrementalsort_with_costsize` (line 5427) re-cost a finished Sort
plan node after its child plan tree is built — used when the sort is
inserted explicitly (not as part of a SortPath cost-already-set chain).

## 10. Async-aware Append

`mark_async_capable_plan` (line 1132): an Append child Plan is marked
`async_capable` if its FDW returns `IsForeignPathAsyncCapable` and the
parent Append uses `parallel_aware==false`. Used by parallel-async exec.

## 11. Invariants & gotchas

- **Top-level only:** `apply_tlist_labeling` runs at exactly one place —
  on the topmost plan that isn't a ModifyTable [verified-by-code:360-361].
- **plan_params discipline:** `create_plan` asserts `plan_params == NIL`
  at entry and resets to NIL at exit, so param-id space isn't poisoned
  across calls [verified-by-code:344, 380].
- **InitPlans attach high:** `SS_attach_initplans` puts all initplans on
  the topmost node of this query level. In principle they could go lower;
  see SS_finalize_plan comments [from-comment:363-369].
- **`use_physical_tlist` may downgrade CP_EXACT_TLIST:** if the path's
  pathtarget equals the rel's reltarget (modulo decoration), we save the
  ProjectionPath. The function checks `is_projection_capable_path` for
  the node type.
- **Bitmap subplan tree shape:** `create_bitmap_subplan` (line 3170) is
  the recursive constructor that turns a `BitmapAndPath` /
  `BitmapOrPath` / `IndexPath` chain into `BitmapAnd` / `BitmapOr` /
  `BitmapIndexScan` plan nodes. The recursive structure mirrors the path
  tree exactly. `bitmap_subplan_mark_shared` (line 5459) marks every
  BitmapIndexScan beneath a parallel-aware BitmapHeapScan as
  `isshared=true`.

## 12. `make_*` constructors (lines 5488-7228)

A second-level layer of pure-allocator helpers (one per Plan node type)
sits below the `create_*_plan` functions. They are simple: makeNode +
field assignment, no cost computation. Examples: `make_seqscan` (5489),
`make_indexscan` (5525), `make_nestloop` (5929), `make_hashjoin` (5954),
`make_sort` (6049), `make_agg` (6583), `make_modifytable` (7005). Most
are static; a handful (`make_foreignscan` at 5803, `make_sort_from_pathkeys`
at 6328, `materialize_finished_plan` at 6509) are public.

## 13. Cross-refs

- Path constructors: `knowledge/files/src/backend/optimizer/util/pathnode.c.md`
- Cost calculations these helpers rely on: `knowledge/files/src/backend/optimizer/path/costsize.c.md`
- Var renumbering pass that runs after: `knowledge/files/src/backend/optimizer/plan/setrefs.c.md`
- Subsystem overview: `knowledge/subsystems/optimizer.md`
- Path/Plan boundary architecture: `knowledge/architecture/planner.md`

## 14. Tags
`[verified-by-code]` ×17, `[from-comment]` ×6
