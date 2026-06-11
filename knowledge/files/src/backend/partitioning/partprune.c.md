# `src/backend/partitioning/partprune.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~3830
- **Source:** `source/src/backend/partitioning/partprune.c`

Heart of partition pruning: at **planning time**, compiles a list
of restriction clauses into a list of `PartitionPruneStep` nodes
that can be replayed at executor startup ("initial pruning") and
at each scan ("execution pruning"). Used by both the planner
(`prune_append_rel_partitions` → directly throws away child rels
of an Append) and the executor (`get_matching_partitions` against
the same step list, with Param values bound at runtime).
[from-comment, verified-by-code]

## Public API (only 3 externs)

- `make_partition_pruneinfo(root, parentrel, subpaths, prunequal)`
  (line 224) — builds a `PartitionPruneInfo` and registers it on
  `root->partPruneInfos`; returns the index, or `-1` if no useful
  runtime pruning steps were found. Called by
  `createplan.c::create_append_plan` / `create_merge_append_plan`.
  Skips partitions that cannot be pruned at runtime via either
  EXEC params or initial-pruning quals. [verified-by-code]
- `prune_append_rel_partitions(rel)` (line 779) — planner-side
  static pruning: returns the Bitmapset of partition indexes that
  survive after evaluating `rel->baserestrictinfo` under
  PARTTARGET_PLANNER. Honours `enable_partition_pruning` GUC.
  [verified-by-code]
- `get_matching_partitions(context, pruning_steps)` (line 845) —
  the step-replay engine. Walks each step in order, stashing
  `PruneStepResult` in a parallel array so combine-steps can refer
  back to earlier results by step id. Used at both planning and
  execution time. [verified-by-code]

## Internal data model

- `PartClauseInfo` — one clause × one partition key column.
  `{ keyno, opno, op_is_ne, expr, cmpfn, op_strategy }`. Built by
  `match_clause_to_partition_key` (line 161). [verified-by-code]
- `PartClauseMatchStatus` — enum: `NOMATCH`, `MATCH_CLAUSE`,
  `MATCH_NULLNESS`, `MATCH_STEPS`, `MATCH_CONTRADICT`,
  `UNSUPPORTED`. Drives the inner loop of step generation.
  [verified-by-code]
- `PartClauseTarget` — `PARTTARGET_PLANNER` (only immutable
  expressions), `PARTTARGET_INITIAL` (allow stable, no PARAM_EXEC),
  `PARTTARGET_EXEC` (allow PARAM_EXEC). Three passes can run per
  rel; the GeneratePruningStepsContext flags
  `has_mutable_op` / `has_mutable_arg` / `has_exec_param` let some
  passes be skipped. [verified-by-code]
- `GeneratePruningStepsContext` — accumulator: `rel`, `target`,
  output `steps` list, `next_step_id` counter, three "saw
  mutable/exec thing" flags, `contradictory` flag.
  [verified-by-code]
- `PruneStepResult` — `{ Bitmapset *bound_offsets, bool
  scan_default, bool scan_null }`. The output of every step.
  [verified-by-code]

## Planning-time flow

1. `gen_partprune_steps(rel, clauses, target, &ctx)` (line 743) —
   wraps `gen_partprune_steps_internal`, optionally augmenting
   `clauses` with `rel->partition_qual` if the rel is itself a
   sub-partition with a default partition (line 759-763). The
   only way to prune the **default partition** of a sub-partitioned
   table is to prove the sub-rel's partition constraint
   contradicts the new quals.
2. `gen_partprune_steps_internal` (line 989) — handles AND
   (clauses across), OR (BoolExpr arms), NOT (negate operator),
   and dispatches to:
   - `match_clause_to_partition_key` per `(clause, partkey)` pair,
   - `gen_prune_steps_from_opexps` (line 159 proto / body in section
     2451) for per-keynum combinations,
   - `match_boolean_partition_clause` (line 3713) for the IS [NOT]
     TRUE/FALSE/UNKNOWN special forms on bool partition columns,
   - `get_steps_using_prefix` / `_recurse` (line 165/172, body
     ~2521) for multi-column key combinations.
3. If 2+ steps result and clauses are mutually ANDed,
   `gen_prune_step_combine(... PARTPRUNE_COMBINE_INTERSECT)`
   bundles them. For BoolExpr OR, the bundle is `_UNION`.
4. `prune_append_rel_partitions` then sets up a minimal
   `PartitionPruneContext` (no planstate, no exprcontext) and
   calls `get_matching_partitions`. [verified-by-code]

## Executor-side flow

(The executor's side lives in `executor/execPartition.c` —
`ExecInitPartitionPruning`, `ExecFindMatchingSubPlans`,
`ExecInitPartitionDispatchInfo`, etc. partprune.c provides only
the engine.)

- `make_partition_pruneinfo` (planning time) produces a
  `PartitionPruneInfo` containing `prune_infos` (a list of
  `PartitionedRelPruneInfo` per partitioned rel) plus
  `other_subplans` (subplans that can never be pruned, like
  the always-scanned default partition once we've established
  we can't prune it). [verified-by-code]
- `PartitionedRelPruneInfo` carries TWO step lists:
  `initial_pruning_steps` (PARTTARGET_INITIAL: usable once per
  query before any rescan) and `exec_pruning_steps` (PARTTARGET
  _EXEC: re-evaluated per parameter-changed rescan).
  [verified-by-code]
- The Bitmapset returned by `get_matching_partitions` is interpreted
  by the executor against `subplan_map[]` / `subpart_map[]` to map
  partition index → Append's subplan index. [verified-by-code]

## Per-strategy bound matching

`get_matching_partitions` calls a strategy-specific helper per
operator step:

- `get_matching_hash_bounds(context, opstrategy, values, nvalues,
  partsupfunc, nullkeys)` (line ~3050) — only equality
  (BTEqualStrategyNumber) is supported for HASH; computes
  `hashfn(values) % modulus`. [verified-by-code]
- `get_matching_list_bounds(context, opstrategy, value, nvalues,
  partsupfunc, nullkeys)` — for LIST: equality picks one; `<`/`<=`
  picks a prefix; `>`/`>=` picks a suffix; `<>` punches a single
  hole; NULL keys steer to `null_index`. [verified-by-code]
- `get_matching_range_bounds(context, opstrategy, values, nvalues,
  partsupfunc, nullkeys)` — for RANGE: `partition_range_datum_bsearch`
  gives the lower bound index, then strategy-specific endpoint
  adjustment. Supports multi-column partial-prefix matching.
  [verified-by-code]

## Run-time param plumbing

- `pull_exec_paramids(expr)` / `pull_exec_paramids_walker`
  (line 3387/3397) — walk an expression collecting `PARAM_EXEC`
  paramids. [verified-by-code]
- `get_partkey_exec_paramids(steps)` (line 3420) — union of all
  exec-param ids referenced from the step list; used to know
  when a rescan must re-prune. [verified-by-code]
- `partkey_datum_from_expr(context, expr, stateidx, *value,
  *isnull)` (line 3802) — at execution time, evaluates an expr to
  a Datum/null. Const fast path; otherwise consults
  `context->exprstates[stateidx]` under `context->exprcontext`.
  Note the warning: **the evaluated Datum may live in the per-tuple
  memory context** of `exprcontext`, so the caller in
  `execPartition.c` must reset the context after a pruning round.
  [from-comment]

## Notable invariants / details

- **Three-target generation invariant:** `make_partition_pruneinfo`
  runs `gen_partprune_steps` up to twice — once with
  `PARTTARGET_INITIAL`, once with `PARTTARGET_EXEC`. The latter
  pass is skipped if the first pass saw no mutable / no exec-param
  clauses. The `has_mutable_op`/`has_mutable_arg`/`has_exec_param`
  flags exist solely to enable that optimisation.
  [from-comment L106-109]
- **Contradiction handling.** If clauses prove contradictory
  (planner side: literal `false`, mutually exclusive ranges,
  contradicts partition constraint of sub-partitioned table), the
  caller treats EVERY partition as pruned. Implemented by
  `context->contradictory = true; return NIL`.
  [verified-by-code]
- **Default partition is special:** it is only prunable if we can
  prove the OTHER quals refute its negative-space constraint.
  `partition_bound_has_default` + `partition_qual` augmentation at
  line 759 is the entry point. [verified-by-code]
- **Collation matching** is required: `IndexCollMatchesExprColl`-
  style check at line 1782/comment. If a clause uses a different
  collation than the partition key, pruning is skipped — failure
  would otherwise produce wrong results for ICU-locale-sensitive
  data. [from-comment]
- **Param refs are stored as step ids**, not direct pointers: a
  combine step references previous steps by `source_stepids` array
  of ints. This means the step list can be serialised into a Plan
  and copied around without pointer surgery. [verified-by-code]
- **No catalog access at execution time:** the planner records
  every Oid/cmpfn needed in the step itself. Execution-side
  pruning is pure arithmetic on the pre-built `PartitionBoundInfo`.
  [from-comment]
- **`stepcmpfuncs` array** (lazy fmgr lookups for runtime
  comparison) is allocated as `partnatts * list_length(steps)` —
  one per (step, key) pair — and populated on demand by
  `perform_pruning_base_step`. The `pgrepack`-style retention
  pattern. [verified-by-code]

## Potential issues

- Line 3713 — `match_boolean_partition_clause` only handles
  built-in bool opfamily (`IsBuiltinBooleanOpfamily`). Any
  user-defined bool opfamily — e.g. extensions that define their
  own bool order — silently misses the special-case pruning and
  falls back to generic operator matching. The comment notes
  "Partitioning currently can only use built-in AMs, so checking
  for built-in boolean opfamilies is good enough." If that ever
  changes, the check becomes a bug. [ISSUE-undocumented-invariant:
  built-in-bool-opfamily check assumes partitioning AMs are built-in
  (maybe)]
- Line 3797-3800 — comment about per-tuple memory context retention
  ("This memory must be recovered by resetting that ExprContext
  after we're done"). The contract crosses files into
  execPartition.c; if a future caller forgets, this leaks per-row
  during a long Append scan. There's no Assert backing this.
  [ISSUE-undocumented-invariant: exprcontext-reset contract is
  cross-file and unenforced (likely)]
- File complexity: 3830 lines, ~25 internal helpers, 5+ separate
  state structs, three pruning targets, three partition strategies.
  Several known bug surfaces have been fixed over the years
  (CF#XXXX FALSE-strict operator, CF#YYYY collation; not cited
  here). New behaviour additions are extremely high-risk; the
  test corpus in `src/test/regress/sql/partition_prune.sql` is
  the only practical guard. [ISSUE-question: would benefit from
  module-level invariant doc (maybe)]
- Line 952-988 — the gen_partprune_steps_internal comment is the
  single best reference for partition pruning semantics, but it
  lives in a static function. A user looking up "what clauses can
  prune partitions?" via grep on the header won't find it.
  [ISSUE-doc-drift: best architectural comment is on a static
  helper (nit)]
- `pull_exec_paramids` walks every step's `exprs` list with a
  full `expression_tree_walker`, including for Const args
  (it short-circuits `IsA(expr, Const)` first at line 3438, but
  re-runs per step). On extremely complex pruning step lists this
  is O(steps × tree). In practice tiny but worth noting.
  [ISSUE-style: pull_exec_paramids re-walks per step (nit)]
- The line 3429 cast `(PartitionPruneStepOp *) lfirst(lc)` is
  guarded by an `IsA(step, PartitionPruneStepOp) continue` for
  combine steps — but the cast is performed BEFORE the IsA check
  reads the tag. In practice safe because PartitionPruneStep nodes
  share a tag-prefix layout, but the order looks fragile.
  [ISSUE-style: cast-before-IsA-tag-check in get_partkey_exec_paramids
  (nit)]
