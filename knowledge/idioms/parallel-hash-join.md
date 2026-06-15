# Parallel hash join — shared hashtable + build barrier

A parallel hash join lets N workers cooperatively build ONE
shared hash table on the inner side, then probe it concurrently
from the outer side. The shared state lives in DSM; the
coordination uses `Barrier`s that step through well-defined phases
(`PHJ_BUILD_*`) so every worker knows what to do regardless of
when it joined. The hot phase is `PHJ_BUILD_HASH_INNER`: every
worker reads its share of the inner subplan, hashes each tuple,
and inserts into the shared bucket array. If the table outgrows
`work_mem`, the workers cooperatively grow batches / buckets via
auxiliary barriers. Once built, probing is partitioned across
batches.

Anchors:
- `source/src/backend/executor/nodeHash.c:234` —
  MultiExecParallelHash [verified-by-code]
- `source/src/backend/executor/nodeHash.c:266-360` —
  build-barrier phase switch [verified-by-code]
- `source/src/backend/executor/nodeHash.c:471` —
  ExecHashTableCreate [verified-by-code]
- `source/src/backend/executor/nodeHash.c:3182` —
  ExecParallelHashJoinSetUpBatches [verified-by-code]
- `source/src/backend/executor/nodeHashjoin.c:237-245` —
  parallel state hookup [verified-by-code]
- `source/src/backend/executor/nodeHashjoin.c:818` —
  ExecParallelHashJoin [verified-by-code]
- `knowledge/idioms/parallel-gather-merge.md` — companion
- `knowledge/idioms/parallel-bitmap-heap.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The build-barrier phases

[verified-by-code `nodeHash.c:266-360` switch]

```
       ┌──────────────┐
       │ ELECT        │  pick one backend to allocate the hash table
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │ ALLOCATE     │  table is being created
       └──────┬───────┘
              ▼  (barrier: BarrierArriveAndWait)
       ┌──────────────┐
       │ HASH_INNER   │  every worker reads inner, hashes, inserts
       └──────┬───────┘
              ▼  (barrier)
       ┌──────────────┐
       │ HASH_OUTER   │  proceed with probe
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │ RUN          │  probing
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │ FREE         │  cleanup
       └──────────────┘
```

`BarrierPhase` returns the current phase; `BarrierArriveAndWait`
advances when all attached workers have arrived. The `switch +
fallthrough` pattern in `MultiExecParallelHash` lets a late-joiner
jump into the current phase regardless of when it attached.

## ParallelHashJoinState — the shared header

```c
typedef struct ParallelHashJoinState
{
    Barrier           build_barrier;        /* PHJ_BUILD_* phases */
    Barrier           grow_buckets_barrier; /* sub-coordination */
    Barrier           grow_batches_barrier;
    /* shared atomic counters: nbuckets, nbatch, total_tuples */
    /* shared batch table: dsa_pointer to per-batch state */
    /* lock for size resizing */
} ParallelHashJoinState;
```

(simplified; the real struct is in `parallel.h` adjacent files.)

Lives in DSM. Every worker reads/writes via
`hashtable->parallel_state` pointer set up at
`ExecHashTableCreate`.

## The hash insert loop

[verified-by-code `nodeHash.c:297-329`]

```c
for (;;)
{
    slot = ExecProcNode(outerNode);   /* outer here = INNER side */
    if (TupIsNull(slot)) break;
    econtext->ecxt_outertuple = slot;

    hashvalue = DatumGetUInt32(ExecEvalExprSwitchContext(
                                   node->hash_expr, econtext, &isnull));

    if (!isnull)
        ExecParallelHashTableInsert(hashtable, slot, hashvalue);
    else if (node->keep_null_tuples)
        /* save to per-worker null tuplestore */
}
```

Each worker pulls tuples from its parallel-aware child (typically
a parallel SeqScan or Append). The child distributes work via
the standard parallel-scan mechanism (block-range allocation in
the table-AM). So inner-side parallelism happens at TWO levels:
the scan reads in parallel, and the hash insert is concurrent.

## ExecParallelHashTableInsert — concurrent bucket insert

The shared bucket array is `bucket_count` slots, each a
`dsa_pointer` to a chunk chain. Inserting:
1. Compute bucket = `hashvalue % nbuckets`.
2. Allocate a chunk in DSM if needed.
3. Append the tuple to the chunk.
4. Atomically swap the bucket head pointer.

Atomic head-swap is what allows multiple writers per bucket
without locking each bucket.

## Growing during build

[verified-by-code `nodeHash.c:289-294`]

If a worker detects `nbatch` or `nbuckets` should grow (load
factor too high), it joins the `grow_batches_barrier` or
`grow_buckets_barrier`. Phases:
- `ELECT` — one worker is picked to coordinate.
- `REALLOCATE` — the resize work happens.
- `REPARTITION` — tuples move between batches.
- `FINISH` — done.

Workers not in the elected role spin on the barrier until done.
This is how PG handles "table doesn't fit in work_mem" while
multiple workers are filling it — they cooperatively rebatch.

## Batch handling — when work_mem is exceeded

[verified-by-code `nodeHash.c:3182-3290`]

If the inner side is too large for `work_mem`, the table is
split into `nbatch` batches. Tuples are partitioned by hash
prefix: batch 0 stays in memory; batches 1..N spill to disk via
`SharedTuplestore` (sts_).

Workers cooperatively:
- Write inner tuples to per-batch `inner_tuples` SharedTuplestores.
- Write outer tuples (during probe) to per-batch
  `outer_tuples` SharedTuplestores.
- After batch 0 probe, advance to batch 1: load inner from disk,
  probe outer from disk.

`ExecParallelHashJoinSetUpBatches` creates the per-batch DSM
state on initial allocation.

## ExecParallelHashJoin — the probe loop

[verified-by-code `nodeHashjoin.c:818+`]

After build completes, each worker:
1. Reads outer side (also parallel via its scan).
2. Hashes the outer tuple.
3. Probes the shared bucket.
4. Emits matches.

For inner unmatched rows (right outer / full outer), a
post-probe phase scans the hashtable for unmatched slots — one
worker takes each bucket.

## Cross-batch synchronization

When all workers finish current batch, they wait at a
per-batch barrier, then advance together. This avoids workers
racing ahead to load batch N+1 before others finished batch N.

## ExecHashTableCreate — the entry point

[verified-by-code `nodeHash.c:471+`]

Called from `ExecInitHashJoin`. For parallel:
1. Allocate the shared state in DSM via `ExecParallelHashJoinSetUpBatches`.
2. The elected backend (first to ALLOCATE phase) does the
   initial bucket allocation.
3. Others wait at the build_barrier.

## Why phases not LWLocks

A barrier is cheaper than per-step LWLocking when:
- Number of coordinated steps is small (~5-10).
- Each step is short, then synchronization, repeat.
- Late attach matters (workers may join after some phases passed).

LWLocks would require holding-and-releasing on every step;
barriers let workers proceed past a phase as soon as all are
present at it.

## Common review-time concerns

- **Build barrier order matters** — the switch fallthrough is
  intentional; late-joining workers skip phases they missed.
- **Bucket head swap is atomic** — no per-bucket lock; relies
  on `dsa_pointer` CAS.
- **`keep_null_tuples` keeps null-keyed rows for left/full outer**.
- **SharedTuplestore is the cross-worker spill backing store** —
  not the same as the serial Tuplestore.
- **Grow barriers can stall the build phase** — workers must
  finish grow before resuming insert.
- **Parallel-restricted clauses** in the hash key prevent
  parallelism; planner checks at path generation.
- **Probe is partitioned across batches**, not across workers —
  every worker probes every batch.

## Invariants

- **[INV-1]** Build_barrier phases progress strictly:
  ELECT → ALLOCATE → HASH_INNER → HASH_OUTER → RUN → FREE.
- **[INV-2]** Workers attaching late jump to the current phase
  via switch-fallthrough.
- **[INV-3]** Bucket head is atomic dsa_pointer; insert via CAS.
- **[INV-4]** Per-batch outer/inner SharedTuplestores spill
  cross-batch tuples to disk.
- **[INV-5]** Inner unmatched scan (right/full outer) partitions
  buckets across workers; one worker per bucket.

## Useful greps

- Build phase + barriers:
  `grep -n 'PHJ_BUILD_\|build_barrier' source/src/backend/executor/nodeHash.c source/src/include/executor/parallel.h | head -10`
- Insert + atomic bucket:
  `grep -n 'ExecParallelHashTableInsert\|HashJoinTable' source/src/backend/executor/nodeHash.c | head -10`
- Grow barriers:
  `grep -n 'grow_batches_barrier\|grow_buckets_barrier\|PHJ_GROW' source/src/backend/executor/nodeHash.c | head -10`
- SharedTuplestore for spill:
  `grep -RIn 'sts_init\|sts_begin_write\|sts_puttuple' source/src/backend/utils/sort/sharedtuplestore.c | head -10`

## Cross-references

- `knowledge/idioms/parallel-gather-merge.md` — the Gather above.
- `knowledge/idioms/parallel-worker-coordination.md` —
  Barrier primitive.
- `knowledge/idioms/parallel-bitmap-heap.md` — sibling parallel
  scan node.
- `knowledge/data-structures/hashjointable.md` —
  HashJoinTable struct.
- `knowledge/subsystems/parallel-query.md` — module overview.
- `knowledge/idioms/cost-modeling.md` — parallel_setup_cost,
  parallel_tuple_cost.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `.claude/skills/parallel-query/SKILL.md` — planning side.
- `source/src/backend/executor/nodeHash.c` — full Hash module.
- `source/src/backend/executor/nodeHashjoin.c` — the join.
- `source/src/backend/utils/sort/sharedtuplestore.c` — spill
  store.
