# Gather / GatherMerge — the parallel-execution funnels

Below a `Gather` (unordered) or `GatherMerge` (sorted) node lives
a **subplan tree** that runs in N parallel workers; above is the
**leader** doing a normal pull. The Gather node is the funnel:
it launches workers via `ExecInitParallelPlan` + `LaunchParallelWorkers`,
sets up one TupleQueueReader per worker, and on each pull either
reads from a worker queue or — if `parallel_leader_participation`
is on — runs the subplan locally as a fallback. The worker count
is best-effort: requesting 4 might launch 0 (under bgworker
pressure), in which case the leader serially executes the whole
subplan and the parallel plan degrades to a serial one.

Anchors:
- `source/src/backend/executor/nodeGather.c:54` —
  ExecInitGather [verified-by-code]
- `source/src/backend/executor/nodeGather.c:138` —
  ExecGather [verified-by-code]
- `source/src/backend/executor/nodeGather.c:152-217` —
  workers-on-first-pull initialization [verified-by-code]
- `source/src/backend/executor/nodeGather.c:401` —
  ExecShutdownGatherWorkers [verified-by-code]
- `source/src/backend/executor/nodeGatherMerge.c:69` —
  ExecInitGatherMerge [verified-by-code]
- `source/src/backend/executor/nodeGatherMerge.c:184` —
  ExecGatherMerge [verified-by-code]
- `knowledge/idioms/parallel-hash-join.md` — companion
- `knowledge/idioms/parallel-bitmap-heap.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## Two flavors

| Node | Output order | Used when |
|---|---|---|
| `Gather` | Unordered (whoever sends first) | Aggregate / hash join / scan with no order requirement |
| `GatherMerge` | Sorted (k-way merge over already-sorted worker outputs) | When a parent requires sorted input (e.g., MergeJoin, ORDER BY) |

GatherMerge requires that each worker's subplan produces output
in the same sort order — usually via a Sort node or an
IndexScan with matching ordering.

## ExecGather — workers-on-first-pull

[verified-by-code `nodeGather.c:152-217`]

```c
if (!node->initialized)
{
    if (gather->num_workers > 0 && estate->es_use_parallel_mode)
    {
        if (!node->pei)
            node->pei = ExecInitParallelPlan(outerPlanState(node), estate, ...);
        else
            ExecParallelReinitialize(outerPlanState(node), node->pei, ...);

        pcxt = node->pei->pcxt;
        LaunchParallelWorkers(pcxt);
        node->nworkers_launched = pcxt->nworkers_launched;
        estate->es_parallel_workers_launched += pcxt->nworkers_launched;

        if (pcxt->nworkers_launched > 0) {
            ExecParallelCreateReaders(node->pei);
            node->nreaders = pcxt->nworkers_launched;
            node->reader = palloc(node->nreaders * sizeof(TupleQueueReader *));
            memcpy(node->reader, node->pei->reader, ...);
        }
        else {
            /* Got zero workers despite asking — leader handles it */
            node->nreaders = 0;
        }
    }

    /* Decide if leader also runs the plan */
    node->need_to_scan_locally = (node->nreaders == 0)
        || (!gather->single_copy && parallel_leader_participation);
    node->initialized = true;
}
```

Key design points:
- **Lazy launch** — workers only start on first ExecGather call,
  not at ExecInitNode. Saves cost if Gather is below a LIMIT 0
  or a never-executed plan branch.
- **Workers are advisory** — `LaunchParallelWorkers` may launch
  fewer than requested if the pool is saturated; the
  `max_parallel_workers` GUC caps the cluster-wide total.
- **Leader-participation gating** — `parallel_leader_participation
  = on` (default) lets the leader pull from the subplan too;
  `single_copy = true` (used for parallel-INSERT) keeps the leader
  out so workers don't double-process.

## gather_getnext — read from worker OR local

[verified-by-code `nodeGather.c:263+`]

```c
while (gatherstate->nreaders > 0 || gatherstate->need_to_scan_locally)
{
    CHECK_FOR_INTERRUPTS();
    if (gatherstate->nreaders > 0) {
        tup = gather_readnext(gatherstate);
        if (HeapTupleIsValid(tup)) return slot_with_tup;
    }
    if (gatherstate->need_to_scan_locally) {
        outerTupleSlot = ExecProcNode(outerPlan);
        if (!TupIsNull(outerTupleSlot)) return outerTupleSlot;
        gatherstate->need_to_scan_locally = false;
    }
}
```

Reads from worker queues first (round-robin via `nextreader`);
falls back to local plan execution when all workers are quiet OR
the leader has more work. Both can run concurrently: workers
push to their queues asynchronously, the leader spins on
gather_readnext + ExecProcNode.

## gather_readnext — round-robin queue read

[verified-by-code `nodeGather.c:gather_readnext`]

Walks `node->reader[nextreader]`; if that queue is empty,
advances `nextreader`. When a reader returns EOF (worker
finished), it's removed from the array. Loop ends when all
readers are EOF AND `need_to_scan_locally` is false.

Uses `tuple_queue_reader_next` with `nowait = true` to avoid
blocking on any one worker. If all queues are empty,
`tuple_queue_reader_next` with `nowait = false` is used to
sleep on the queue's latch.

## TupleQueue — the shared-memory tuple channel

Each worker has its own `shm_mq` (single-producer, single-
consumer queue) sized by `PARALLEL_TUPLE_QUEUE_SIZE`. Workers
write `MinimalTuple`s; the leader reads them. The queue is
implemented as a ring buffer in DSM with a latch for blocking.

Per-worker queue:
- One producer (the worker).
- One consumer (the leader's `gather_readnext`).
- Latch-signaled wakeup on insert + on read.

The queue's tear-down on worker exit is what produces EOF for
the reader.

## ExecShutdownGather — clean up workers

[verified-by-code `nodeGather.c:419-450`]

Called from ExecEndNode (and from `ExecShutdownNode` when a
LIMIT is satisfied and the upper plan signals "no more"). The
sequence:
1. **ExecParallelFinish** on the parallel context — waits for
   workers to detach from their queues.
2. **ExecParallelCleanup** — destroys the DSM segment, frees
   the parallel context.
3. NULLs out the reader array.

Early shutdown (LIMIT path) signals workers via the DSM control
area to stop ASAP without finishing their scans.

## GatherMerge — sorted variant

[verified-by-code `nodeGatherMerge.c:184+`]

GatherMerge maintains a **binary heap** of (worker_index, current
tuple) pairs ordered by the plan's sort key. Each `ExecGatherMerge`
call:
1. Pop the smallest from the heap.
2. Pull the next tuple from that worker's queue; re-insert with
   the new tuple key.
3. Return the popped tuple.

Cost vs Gather:
- **Memory**: O(num_workers) heap.
- **Latency**: heap operations on every pull.
- **Benefit**: parent plan can rely on sorted output (e.g.,
  Merge Append above partitioned table scans).

The leader can participate (`parallel_leader_participation`); its
local output is plugged into the heap as a virtual extra worker.

## es_use_parallel_mode discipline

Set during executor startup based on the plan's parallel-safety
classification. Once `es_use_parallel_mode = true`, the executor
enforces:
- No catalog modifications.
- No prepared-stmt modifications.
- Parallel-restricted functions reject calls.

The check is `IsInParallelMode()` in the function's entry. CFs
that loosen this set explicit GUCs.

## Common review-time concerns

- **`num_workers` is best-effort** — code must handle 0 workers.
- **Per-worker subplan state is `ExecInitParallelPlan`-allocated**
  in DSM; field by field via `ParallelExecutorInfo`.
- **`single_copy = true` excludes leader** — INSERT, COPY use
  this.
- **EXPLAIN ANALYZE shows actual workers** — "Workers Planned: 4
  Workers Launched: 2" indicates pool saturation.
- **GatherMerge requires sort-key-matching child output** —
  planner enforces; runtime asserts.
- **Early-shutdown signal** is via DSM control; workers poll
  `ParallelWorkerShouldStop` between tuples.
- **Worker errors propagate** via the error queue + reraise in
  the leader (see HandleParallelMessages).

## Invariants

- **[INV-1]** Workers launch on first ExecGather call, NOT at
  ExecInitNode.
- **[INV-2]** `nworkers_launched` ≤ `num_workers`; either count
  may be 0.
- **[INV-3]** With `parallel_leader_participation = on` and
  `single_copy = false`, leader and workers both pull tuples.
- **[INV-4]** GatherMerge requires sorted child output.
- **[INV-5]** ExecShutdownGather destroys the DSM segment and
  waits for worker detach.

## Useful greps

- The funnels:
  `grep -n '^ExecInitGather\|^ExecGather\|^ExecShutdownGather' source/src/backend/executor/nodeGather.c source/src/backend/executor/nodeGatherMerge.c | head -10`
- Worker launch + queues:
  `grep -RIn 'LaunchParallelWorkers\|ExecInitParallelPlan\|ExecParallelCreateReaders' source/src/backend/executor | head -10`
- Reader loop:
  `grep -n 'gather_readnext\|tuple_queue_reader_next' source/src/backend/executor/nodeGather.c source/src/backend/executor/tqueue.c | head -10`
- Parallel-mode enforcement:
  `grep -RIn 'IsInParallelMode\|es_use_parallel_mode' source/src/backend | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execParallel.c`](../files/src/backend/executor/execParallel.c.md) | — | DSM setup |
| [`src/backend/executor/nodeGather.c`](../files/src/backend/executor/nodeGather.c.md) | 54 | ExecInitGather |
| [`src/backend/executor/nodeGather.c`](../files/src/backend/executor/nodeGather.c.md) | 138 | ExecGather |
| [`src/backend/executor/nodeGather.c`](../files/src/backend/executor/nodeGather.c.md) | 152 | workers-on-first-pull initialization |
| [`src/backend/executor/nodeGather.c`](../files/src/backend/executor/nodeGather.c.md) | 401 | ExecShutdownGatherWorkers |
| [`src/backend/executor/nodeGather.c`](../files/src/backend/executor/nodeGather.c.md) | — | full module |
| [`src/backend/executor/nodeGatherMerge.c`](../files/src/backend/executor/nodeGatherMerge.c.md) | 69 | ExecInitGatherMerge |
| [`src/backend/executor/nodeGatherMerge.c`](../files/src/backend/executor/nodeGatherMerge.c.md) | 184 | ExecGatherMerge |
| [`src/backend/executor/nodeGatherMerge.c`](../files/src/backend/executor/nodeGatherMerge.c.md) | — | sorted variant |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/parallel-hash-join.md` —
  inner-side build coordination under Gather.
- `knowledge/idioms/parallel-bitmap-heap.md` —
  shared TBM iteration.
- `knowledge/idioms/parallel-worker-coordination.md` —
  Barrier / ConditionVariable primitives.
- `knowledge/data-structures/plannerinfo.md` — partial paths +
  parallel-safe flag.
- `knowledge/subsystems/parallel-query.md` — module overview.
- `knowledge/data-structures/estate.md` — es_use_parallel_mode.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `.claude/skills/parallel-query/SKILL.md` — planning side.
- `source/src/backend/executor/nodeGather.c` — full module.
- `source/src/backend/executor/nodeGatherMerge.c` — sorted
  variant.
- `source/src/backend/executor/execParallel.c` — DSM setup.
