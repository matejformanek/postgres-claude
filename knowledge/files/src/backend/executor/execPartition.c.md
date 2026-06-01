# execPartition.c

- **Source:** `source/src/backend/executor/execPartition.c` (2804 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (routing + pruning entry points)

## Purpose

Two big jobs:

1. **Tuple routing** for INSERT/COPY/UPDATE into partitioned tables — given
   a row, figure out which leaf partition it belongs to and lazily open +
   prep that partition's ResultRelInfo.
2. **Runtime partition pruning** — given quals that include Params (e.g.
   `partkey = $1` or join keys from above), prune the set of Append/MergeAppend
   subplans before opening / during execution.

## Tuple routing

### `ExecSetupPartitionTupleRouting(estate, rel)` `:221`

Allocates a `PartitionTupleRouting` for the top-level partitioned root. Sets
up the initial PartitionDispatch for the root only — the rest is built
lazily as rows actually need them.

### `ExecFindPartition(mtstate, rootResultRelInfo, proute, slot, estate)` `:268`

Routes one row to its leaf partition. Walks down `proute->partition_dispatch_info`
applying each level's `PartitionKey` to the slot, looking up the matching
child via `get_partition_for_tuple` (in partitioning/partbounds.c). For the
matched leaf:
- If we've never seen it: `ExecInitPartitionInfo` `:564` opens the partition,
  builds its ResultRelInfo, child-vs-parent **TupleConversionMap**, indexes,
  trigger info, RETURNING projection, ON CONFLICT helpers, FDW state if
  foreign, then caches it in `proute->partitions[]`.
- If conversion is needed (column reordering / dropped cols), converts the
  slot via `execute_attr_map_slot`.

Returns the ResultRelInfo for the leaf so caller (`ExecInsert`/`ExecUpdate`)
can run triggers + heap_insert against it.

### `ExecInitPartitionDispatchInfo` `:1275`

Builds one level of dispatch (PartitionDesc + key extraction ExprState).

### `ExecCleanupTupleRouting` `:1412`

Walks the cached partitions, closes them, runs FDW EndForeignModify, drops
TupleConversionMaps.

## Runtime pruning

### `ExecCreatePartitionPruneState` (called from Append/MergeAppend init)

Compiles the planner-produced `PartitionPruneInfo` (which holds one
`PartitionedRelPruneInfo` per partitioned RTE involved) into a
`PartitionPruneState`. Each `PartitionedRelPruneInfo` contains lists of
"pruning steps" (`PartitionPruneStep` nodes) — these are essentially
mini-expressions over partition key vs. quals that may reference Params.

### `ExecDoInitialPruning(estate)` `:1995`

Runs the **initial** pruning pass (before workers launch) using only
*external* params known at ExecutorStart. This is what lets PG skip opening
relations for partitions that are statically pruned away.

### `ExecFindMatchingSubPlans(prunestate, initial_prune)` `:2667`

The **execution-time** pruning pass run by Append/MergeAppend on each
ReScan when a relevant `chgParam` fires (e.g. nested-loop join driving
partition key from outer side). Returns a bitmapset of subplan indexes
that survive pruning.

## Notable details

- Routing is lazy because COPY into a 1000-partition table that only
  receives rows for 3 partitions should only ever open 3.
- Pruning steps are **interpreted**, not compiled to ExprStates — they have
  their own tiny VM described in partprune.c. execPartition just drives it.
- Conversion maps survive across rows for the same partition; built once
  per partition open.
- Updates that move a row across partitions: ModifyTable detects this in
  `ExecCrossPartitionUpdate` and turns the UPDATE into a DELETE+INSERT,
  which routes through ExecFindPartition again — but the trigger semantics
  fire UPDATE row triggers on the old partition only (see nodeModifyTable.c).

## Tags

- [verified-by-code] entry point line numbers.
- [from-comment] lazy-partition-open rationale (file header + per-function).
- [inferred] interpretation vs compilation of pruning steps (consistent with
  partprune.c code but not re-verified here).
