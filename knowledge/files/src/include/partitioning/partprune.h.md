# `src/include/partitioning/partprune.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~81
- **Source:** `source/src/include/partitioning/partprune.h`

Partition-pruning interface shared between planner (static pruning at
plan time) and executor (runtime/initial pruning at Append/MergeAppend).
Defines the `PartitionPruneContext` carrying everything needed to
evaluate pruning steps. [verified-by-code]

## API / declarations

### PartitionPruneContext

```
{
  char           strategy;       /* LIST/RANGE/HASH */
  int            partnatts;      /* partition key column count */
  int            nparts;
  PartitionBoundInfo boundinfo;
  Oid           *partcollation;  /* per-key */
  FmgrInfo      *partsupfunc;    /* per-key: '<' / hash */
  FmgrInfo      *stepcmpfuncs;   /* per (step, key) — flat array */
  MemoryContext  ppccontext;     /* owner of FmgrInfos etc. */
  PlanState     *planstate;      /* exec-time parent; NULL at plan time */
  ExprContext   *exprcontext;
  ExprState    **exprstates;     /* per (step, key); only at exec time */
}
```

- `PruneCxtStateIdx(partnatts, step_id, keyno) = partnatts*step_id +
  keyno` — indexes both `stepcmpfuncs[]` and `exprstates[]`. "Note:
  there is code that assumes the entries for a given step are
  sequential, so this is not chosen freely." [from-comment]

### Entry points

- `make_partition_pruneinfo(root, parentrel, subpaths, prunequal)` →
  int (index into root->partPruneInfos). Plan-time analysis that
  generates the `PartitionPruneInfo` consumed by Append/MergeAppend
  at execution.
- `prune_append_rel_partitions(rel)` → Bitmapset of surviving
  partition indexes (plan-time only, used for static pruning).
- `get_matching_partitions(context, pruning_steps)` → Bitmapset.
  Shared between plan-time and exec-time evaluation.

## Notable invariants / details

- `partsupfunc` points into the relation's `PartitionKey`
  (`source/src/include/utils/partcache.h`); `stepcmpfuncs` is
  step-specific and owned by `ppccontext`. The header makes that
  ownership distinction explicit. [from-comment]
- `planstate == NULL` discriminates plan-time from exec-time pruning;
  exec-time uses `exprcontext` + `exprstates` to evaluate
  Const/Param/Stable expressions in steps. [from-comment]
- The flat indexing scheme `partnatts*step+key` is relied on by the
  cmpfunc array allocator AND by the exprstate setup; both must
  agree on `partnatts`. [from-comment]

## Potential issues

- `PartitionPruneContext` uses `char strategy` (1 byte) but the
  underlying enum `PartitionStrategy` is wider — implicit narrowing
  on assignment, fine today but a reviewer should not widen the
  enum without auditing this struct. [ISSUE-undocumented-invariant:
  strategy stored as char (nit)]
- The "code that assumes the entries for a given step are
  sequential" warning is non-local: a reviewer modifying
  `PruneCxtStateIdx` must grep for raw `partnatts * step_id` math.
  [ISSUE-undocumented-invariant: PruneCxtStateIdx layout is
  load-bearing (likely)]
- `exprstates` is allocated only when `planstate != NULL`; the
  header says so in a comment but the struct doesn't enforce it
  (no NULL invariant). [ISSUE-doc-drift: exprstates nullity tied to
  planstate (nit)]
