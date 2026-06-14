# Partition tuple routing — PartitionTupleRouting flow

PG partitioned tables route INSERT and UPDATE tuples to the
correct partition based on the partition key. The routing
machinery (`PartitionTupleRouting` struct +
`ExecLocateResultPartition`) walks the partition hierarchy
to find the leaf partition for each tuple, allocates per-
partition state lazily, and handles cross-partition UPDATEs
(when an UPDATE moves a row to a different partition).

Anchors:
- `source/src/include/executor/execPartition.h:23-33` —
  public API [verified-by-code]
- `source/src/backend/executor/execPartition.c` —
  implementation
- `knowledge/subsystems/partitioning.md` — surrounding
  subsystem
- `.claude/skills/executor-and-planner/SKILL.md` — executor
  context

## The PartitionTupleRouting struct

```c
typedef struct PartitionTupleRouting PartitionTupleRouting;
```

[verified-by-code `execPartition.h:23`]

The struct is opaque to callers. Internally it carries:
- The partition tree's PartitionDispatch nodes (per
  internal level).
- A lazy-allocated array of ResultRelInfo per leaf
  partition.
- Per-partition tuple-conversion maps (when partition's
  TupleDesc differs from root's).

## The 3 entry points

```c
extern PartitionTupleRouting *
ExecSetupPartitionTupleRouting(EState *estate, Relation rel);

extern ResultRelInfo *
ExecFindPartition(/* slot, proute, ... */);

extern void
ExecCleanupTupleRouting(PartitionTupleRouting *proute);
```

[verified-by-code `execPartition.h:25-33`]

- **`ExecSetupPartitionTupleRouting`** — at INSERT/UPDATE
  query setup, build the routing struct.
- **`ExecFindPartition`** — per tuple, find the leaf
  partition's `ResultRelInfo` (which holds open relation,
  indices, triggers).
- **`ExecCleanupTupleRouting`** — at end-of-query, release
  any per-partition state.

## The routing tree walk

PG partitions form a tree:

```
root (partitioned table)
├── partition_A (still partitioned by sub-key)
│   ├── leaf_A1
│   └── leaf_A2
└── partition_B (leaf)
```

Per-INSERT row, `ExecFindPartition`:

1. Start at root's PartitionDispatch.
2. Apply the partition-key function to the tuple.
3. Look up which child partition matches.
4. If child is leaf → return its `ResultRelInfo`.
5. If child is partitioned → recurse to step 2.

The traversal is O(depth) — typically 1-3 levels.

## Lazy partition allocation

`PartitionTupleRouting` defers opening partitions until they
receive a tuple. For an INSERT that touches only 1 out of 100
partitions, only that 1 gets opened. This is critical for
hash-partitioned tables with many empty partitions — no per-
partition setup cost for unused leaves.

State allocated per leaf on first hit:
- Open the relation (`heap_open`).
- Build index info for all indexes.
- Build triggers list.
- Build tuple-conversion map (if partition's TupleDesc differs
  from root's).

## TupleDesc mismatch

Child partitions can have **dropped columns** that the root
doesn't, or have columns in different physical positions.
When this happens, the per-partition ResultRelInfo carries a
**tuple-conversion map** that rewrites the slot before
insertion.

The mismatch is detected at setup; the map is built once
and reused per tuple.

## Cross-partition UPDATE

An UPDATE that changes the partition key may move a row to a
different partition:

```sql
UPDATE sales SET region = 'EU' WHERE id = 42;
-- if 'EU' is in a different partition than the old region
```

The executor:
1. DELETE from the old partition.
2. INSERT into the new partition.
3. Wraps both in the same transaction.

The semantic is **atomic** — readers see either the old or
new state, never both. But this is more expensive than an
in-partition UPDATE; consider whether your partitioning
allows update-in-place.

## The ON CONFLICT problem

`INSERT ... ON CONFLICT` on a partitioned table has subtle
semantics:

- The conflict resolution is checked **per-partition**, not
  globally.
- A UNIQUE constraint declared on a partitioned table is
  enforced via **per-partition** unique indexes.
- If the partition key DOESN'T include the UNIQUE columns,
  the global uniqueness CAN'T be enforced.

This is the "you can't have a globally-unique non-key column
on a partitioned table" limitation.

## Per-partition triggers

BEFORE / AFTER INSERT triggers on the root partitioned table
fire for every tuple. Triggers declared on a specific
partition fire only for tuples landing in THAT partition.

Both fire if both exist. Order: root's BEFORE → child's
BEFORE → INSERT → child's AFTER → root's AFTER. The walk
follows the partition tree.

## Default-partition routing

If a partitioned table has a DEFAULT partition, tuples that
don't match any explicit partition's bound go there. Default
partition is the "catch-all" — useful for unexpected
inputs, but can grow unboundedly if explicit partitions don't
cover well.

`ExecFindPartition` returns the default partition's
ResultRelInfo when no explicit partition matches.

## Common review-time concerns

- **Adding partition-key columns post-hoc requires recreation.**
  ALTER TABLE doesn't change partition key.
- **Cross-partition UPDATE is expensive.** Audit UPDATEs that
  change partition-key columns.
- **Tuple-conversion maps** are detected at routing setup;
  schema changes invalidate them.
- **The lazy-allocation strategy depends on `proute`**
  remaining live for the query duration — don't release
  prematurely.
- **`ExecFindPartition` returns NULL** for rejected tuples
  (e.g., violating CHECK constraint at partition). Handle
  the NULL.

## Invariants

- **[INV-1]** Routing tree walk is O(partition depth);
  typically 1-3.
- **[INV-2]** Per-partition `ResultRelInfo` allocated lazily
  on first hit.
- **[INV-3]** Cross-partition UPDATE = DELETE + INSERT;
  atomic at xact-commit but two operations.
- **[INV-4]** UNIQUE constraints are per-partition unless
  partition key includes the columns.
- **[INV-5]** Default partition is the catch-all for
  unmatched tuples.

## Useful greps

- The setup entry point:
  `grep -n 'ExecSetupPartitionTupleRouting\|ExecFindPartition' source/src/backend/executor/execPartition.c | head -10`
- Cross-partition update path:
  `grep -RIn 'PartitionUpdateAcrossPartitionMove\|MoveAcrossPartitions' source/src/backend | head -10`
- TupleDesc-conversion map:
  `grep -n 'convert_tuples_by_name' source/src/backend/access/common/tupconvert.c`

## Cross-references

- `knowledge/subsystems/partitioning.md` — partitioning
  subsystem at large.
- `knowledge/subsystems/executor.md` — ResultRelInfo
  lifecycle in the executor.
- `.claude/skills/executor-and-planner/SKILL.md` —
  executor + planner skill.
- `knowledge/data-structures/tupletableslot.md` — slot used
  for routing; tuple-conversion maps operate on slots.
- `source/src/include/executor/execPartition.h` — public API.
- `source/src/backend/executor/execPartition.c` —
  implementation.
