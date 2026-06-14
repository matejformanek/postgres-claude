# Partition runtime pruning — PARAM-driven scan elimination

The planner does **static** partition pruning during planning
(eliminating subplans whose bounds can't satisfy WHERE
constants). For PARAM_EXEC-bound predicates — values that
aren't known until runtime — the planner sets up
**`PartitionPruneInfo`** so the executor can prune again at
each rescan or per execution. `find_matching_subplans_recurse`
walks the pruning step tree, comparing PARAM values to
partition bounds, and returns the bitmap of subplans that
actually need to run.

Anchors:
- `source/src/backend/executor/execPartition.c:2410` —
  InitPartitionPruneContext [verified-by-code]
- `source/src/backend/executor/execPartition.c:2700-2740` —
  find_matching_subplans_recurse [verified-by-code]
- `knowledge/idioms/partition-tuple-routing.md` — companion
- `knowledge/idioms/partition-attach-detach.md` — companion
- `knowledge/idioms/partition-bound-comparison.md` —
  companion (compare-step uses these)
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The two pruning regimes

| Regime | When | Driven by |
|---|---|---|
| **Plan-time** | During planner's path generation | Const + immutable expression values |
| **Init-time** | At ExecInitNode (first call) | PARAM_EXEC values set by InitPlans |
| **Execution-time** | Per ExecReScan / per tuple in nested-loop | PARAM_EXEC values that change per parent tuple |

The first is `static`; the latter two are `runtime`. The
planner emits a `PartitionPruneInfo` containing pruning steps
designed for runtime use.

## PartitionPruneInfo + the step tree

```c
typedef struct PartitionPruneInfo
{
    NodeTag    type;
    Bitmapset *other_subplans;       /* subplans that aren't partitions */
    List      *prune_infos;           /* per-partition-hierarchy data */
} PartitionPruneInfo;

typedef struct PartitionedRelPruneInfo
{
    /* the partition rel + its bounds */
    Oid              parent_relid;
    int              nparts;
    int              relid_subplan_map[];  /* RT-index → subplan index */

    /* The "do this at init time" steps */
    List            *initial_pruning_steps;
    /* The "do this on each exec / rescan" steps */
    List            *exec_pruning_steps;

    /* All PARAM_EXEC IDs the steps depend on */
    Bitmapset       *execparamids;
} PartitionedRelPruneInfo;
```

(simplified from `partprune.h` + planner output)

The planner classifies each pruning step:
- **`initial`** — depends on Params known at executor start
  (typically InitPlan outputs); can be evaluated once.
- **`exec`** — depends on Params that change per parent tuple
  (e.g., nested-loop join keys); re-evaluated.

## The pruning step types

Each `PartitionPruneStep` is one of:

- `OPSTEP` — compare a partition key column to a PARAM value
  using a btree opfamily.
- `COMBINESTEP` — combine results from sub-steps (UNION,
  INTERSECT for OR / AND).

Composed into a tree mirroring the qual structure. The result
of evaluation: a Bitmapset of partition indices that may
contain matching rows.

## InitPartitionPruneContext

[verified-by-code `execPartition.c:2410`]

```c
void
InitPartitionPruneContext(PartitionPruneContext *context,
                          List *pruning_steps,
                          PartitionDesc partdesc,
                          PartitionKey partkey,
                          PlanState *planstate);
```

Sets up the context for one run of pruning:
- The list of steps to evaluate.
- The partition descriptor (partition list + bounds).
- The partition key (column types + comparators).
- The PlanState (for ExprState evaluation of PARAM values).

Created at ExecInitNode time per partitioned scan;
re-used across pruning calls.

## find_matching_subplans

[verified-by-code `execPartition.c:2700-2740`]

```c
Bitmapset *
find_matching_subplans(PartitionPruneState *pps,
                       bool initial_prune);
```

Driver function:
1. Calls `find_matching_subplans_recurse` walking the hierarchy.
2. Per-partition: evaluate the step tree, compute matching
   bitmap.
3. Recurse into sub-partitions if any (nested partitioning).
4. Return the union of matched subplan indices.

`initial_prune = true` → only run initial steps. False → run
exec steps (or both).

## When pruning fires

[from `execAppend.c` + `execMergeAppend.c`]

For an `Append` / `MergeAppend` node over partitions:
1. `ExecInitAppend` — calls `find_matching_subplans` with
   `initial_prune = true`. If a subplan is pruned, it's not
   initialized at all (saves InitPlan / catalog lookups).
2. Per ExecReScan / per parent tuple of nested-loop —
   `find_matching_subplans` with `initial_prune = false`.
   Subplans no longer matching are skipped.

The Append node maintains a "matching subplans" bitmap;
elements outside the bitmap are dead for this scan.

## EXPLAIN visibility

```sql
EXPLAIN (ANALYZE, VERBOSE) SELECT * FROM t WHERE col = $1;
```

Output includes:
- "Subplans Removed: N" — N subplans pruned during init.
- "Workers: M filtered: K" — parallel-runtime pruning.

For static pruning, removed subplans don't appear at all.

## Optimization heuristics

- **Range partitioning** — bsearch for the right subplan;
  O(log n) per probe.
- **Hash partitioning** — modular arithmetic; O(1) per probe.
- **List partitioning** — bsearch on sorted lists; O(log n).

Each pruning step uses the corresponding lookup function from
`partbounds.c`.

## PARAM_EXEC dependence

[via `execparamids` Bitmapset]

The planner records which PARAM_EXEC slots each pruning step
depends on. At runtime:
- Initial pruning runs only if its slots are set (or set to
  invalid, in which case no pruning happens).
- Exec pruning runs whenever its slots' values change.

The Bitmapset is consulted in `ExecReScan` to decide if
re-pruning is needed.

## Interaction with parallel execution

In parallel queries with `Append` over partitions:
- Initial pruning is done once by the leader BEFORE spawning
  workers.
- Exec pruning happens in each worker as the parameters
  change.
- The pruning result is communicated via shared bitmap.

This means workers don't waste effort opening partitions that
won't be queried.

## Common review-time concerns

- **PARAM_EXEC dependence** drives the init/exec
  classification; understand which slots are set when.
- **Exec pruning per tuple is hot** — keep step trees shallow
  for nested-loop scans.
- **Multi-key partitioning** widens the step tree — each
  partition key needs its own evaluation.
- **Default partition** is always included unless explicitly
  pruned out.
- **Pruning bitmap must be consistent** across workers in
  parallel scans.
- **Adding a new partition-key operator** requires the
  opfamily to be registered for pruning.

## Invariants

- **[INV-1]** Initial steps run once at ExecInitNode; exec
  steps may run per-tuple.
- **[INV-2]** PartitionPruneInfo carries execparamids
  Bitmapset; pruning re-runs if any slot changes.
- **[INV-3]** Pruned subplans aren't initialized (saves
  setup).
- **[INV-4]** Default partition included unless explicitly
  pruned.
- **[INV-5]** Range/hash/list use specialized bsearch /
  mod arithmetic per partition kind.

## Useful greps

- The init + find:
  `grep -n 'InitPartitionPruneContext\|find_matching_subplans' source/src/backend/executor/execPartition.c | head -10`
- Step types:
  `grep -RIn 'PartitionPruneStepOp\|PartitionPruneStepCombine' source/src/include | head -10`
- Append/MergeAppend pruning calls:
  `grep -RIn 'find_matching_subplans' source/src/backend/executor/nodeAppend.c | head -10`

## Cross-references

- `knowledge/idioms/partition-tuple-routing.md` —
  insertion side uses the same bounds.
- `knowledge/idioms/partition-attach-detach.md` —
  changing bounds invalidates plans.
- `knowledge/idioms/partition-bound-comparison.md` —
  the comparison primitives.
- `knowledge/idioms/parallel-worker-coordination.md` —
  pruning bitmap in parallel scans.
- `knowledge/idioms/subplan-and-initplan.md` —
  PARAM_EXEC slots drive the dependence.
- `knowledge/data-structures/plannerinfo.md` —
  planner emits PartitionPruneInfo into PlannedStmt.
- `knowledge/subsystems/partitioning.md` —
  partitioning overview.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/executor/execPartition.c` — full
  module.
