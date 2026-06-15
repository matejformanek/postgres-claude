# Parallel bitmap heap scan — shared TBM iteration

A parallel BitmapHeapScan starts the same way as the serial one:
build a TIDBitmap from the inner BitmapIndexScan output. The
parallelism kicks in at iteration time — the bitmap is shared,
and `tbm_prepare_shared_iterate` partitions block ranges across
workers so each pulls a different chunk. The bottleneck moves
from "one backend reading sequentially" to "N backends touching
the heap concurrently, deduped at the page level by the bitmap".
A small `ParallelBitmapHeapState` in DSM coordinates: one elected
leader builds the TBM while others wait on a ConditionVariable,
then everyone iterates the shared TBM.

Anchors:
- `source/src/backend/executor/nodeBitmapHeapscan.c:87-93` —
  ParallelBitmapHeapState [verified-by-code]
- `source/src/backend/executor/nodeBitmapHeapscan.c:102` —
  BitmapTableScanSetup [verified-by-code]
- `source/src/backend/executor/nodeBitmapHeapscan.c:115-134` —
  leader-builds, others-wait [verified-by-code]
- `source/src/backend/executor/nodeBitmapHeapscan.c:136-140` —
  tbm_begin_iterate with shared dsa_pointer
  [verified-by-code]
- `source/src/backend/executor/nodeBitmapHeapscan.c:174` —
  BitmapHeapNext [verified-by-code]
- `source/src/backend/executor/nodeBitmapHeapscan.c:229-235` —
  BitmapDoneInitializingSharedState [verified-by-code]
- `knowledge/idioms/parallel-gather-merge.md` — companion
- `knowledge/idioms/parallel-hash-join.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The control struct

[verified-by-code `nodeBitmapHeapscan.c:87-93`]

```c
typedef struct ParallelBitmapHeapState
{
    dsa_pointer        tbmiterator;   /* shared iterator state */
    slock_t            mutex;
    SharedBitmapState  state;          /* BM_INITIAL/INPROGRESS/FINISHED */
    ConditionVariable  cv;             /* sleep for build completion */
} ParallelBitmapHeapState;
```

Three fields do the coordination:
- **`state`** — tristate: `BM_INITIAL` (no leader yet),
  `BM_INPROGRESS` (a leader is building the TBM), `BM_FINISHED`
  (TBM ready, iterate).
- **`tbmiterator`** — the shared iterator state in DSA, set
  when the leader finishes.
- **`cv` + `mutex`** — sleep/wake on state transitions.

## BitmapTableScanSetup — the once-per-scan initialization

[verified-by-code `nodeBitmapHeapscan.c:101-165`]

Three paths depending on parallelism:

```c
if (!pstate)
{
    /* Non-parallel: just build the TBM. */
    node->tbm = MultiExecProcNode(outerPlanState(node));
}
else if (BitmapShouldInitializeSharedState(pstate))
{
    /* Elected leader: build the TBM and prepare shared iterator. */
    node->tbm = MultiExecProcNode(outerPlanState(node));
    pstate->tbmiterator = tbm_prepare_shared_iterate(node->tbm);
    BitmapDoneInitializingSharedState(pstate);
}
/* Everyone (including the leader) reaches here: begin iterating */
tbmiterator = tbm_begin_iterate(node->tbm, dsa,
                                pstate ? pstate->tbmiterator
                                       : InvalidDsaPointer);

if (!node->ss.ss_currentScanDesc)
    node->ss.ss_currentScanDesc =
        table_beginscan_bm(node->ss.ss_currentRelation, snapshot, 0, NULL, flags);

node->ss.ss_currentScanDesc->st.rs_tbmiterator = tbmiterator;
```

## Election + wait — BitmapShouldInitializeSharedState

[verified-by-code via the function name + state transitions]

The first worker to enter atomically CAS-transitions
`state: BM_INITIAL → BM_INPROGRESS` and becomes the leader.
Others see `BM_INPROGRESS` and call
`ConditionVariableSleep(&pstate->cv, ...)`.

When the leader finishes (calls
`BitmapDoneInitializingSharedState`):

[verified-by-code `nodeBitmapHeapscan.c:229-235`]

```c
static inline void
BitmapDoneInitializingSharedState(ParallelBitmapHeapState *pstate)
{
    SpinLockAcquire(&pstate->mutex);
    pstate->state = BM_FINISHED;
    SpinLockRelease(&pstate->mutex);
    ConditionVariableBroadcast(&pstate->cv);
}
```

The broadcast wakes every sleeping worker. They re-check state,
proceed to `tbm_begin_iterate`.

## tbm_prepare_shared_iterate vs tbm_begin_iterate

| Function | Who calls | What it does |
|---|---|---|
| `tbm_prepare_shared_iterate(tbm)` | leader only | builds a shared iterator state in DSA, returns dsa_pointer |
| `tbm_begin_iterate(tbm, dsa, ptr)` | every worker | attaches a per-worker iterator handle to the shared state |

The TBM itself (a hash table of (block, chunk-of-tids))
also lives in DSA when the scan is parallel. Workers consume
block ranges atomically from the shared iterator.

## Iteration — atomic block-range claim

[verified-by-code via `tbm_shared_iterate` semantics]

Each call to `tbm_iterate` (or the AM-specific
`table_scan_bitmap_next_block`) atomically:
1. Reads the current iterator position.
2. CAS-advances it by one block (or one chunk).
3. Returns the claimed block.

If two workers race, only one wins the CAS; the other retries.
Empty TBM → all workers exit at once.

## table_beginscan_bm + bitmap-aware heap scan

[verified-by-code `nodeBitmapHeapscan.c:152-160`]

```c
if (node->ss.ps.state->es_instrument & INSTRUMENT_IO)
    flags |= SO_SCAN_INSTRUMENT;
node->ss.ss_currentScanDesc =
    table_beginscan_bm(node->ss.ss_currentRelation, snapshot,
                       0, NULL, flags);
```

The bitmap-flavor scan descriptor knows it's reading specific
blocks (not sequential). The per-block work is the same as a
serial bitmap scan: read the page, project rows whose CTIDs match
the TBM's per-page tid array.

## BitmapHeapNext — per-tuple pull

[verified-by-code `nodeBitmapHeapscan.c:174-220`]

```c
while (table_scan_bitmap_next_tuple(scan, slot, &recheck,
                                    &stats.lossy_pages,
                                    &stats.exact_pages))
{
    if (recheck)
    {
        econtext->ecxt_scantuple = slot;
        if (!ExecQualAndReset(bitmapqualorig, econtext))
        {
            InstrCountFiltered2(node, 1);
            ExecClearTuple(slot);
            continue;
        }
    }
    return slot;
}
return ExecClearTuple(slot);
```

`table_scan_bitmap_next_tuple` internally:
- If the current block's TID array is exhausted, calls
  `table_scan_bitmap_next_block` which advances the shared
  iterator.
- Returns one slot per matching row in the page.
- Sets `recheck = true` for lossy TBM pages (where the bitmap
  stored "this page has matches" but not the specific TIDs).

The recheck-after-lossy pattern keeps the TBM small for huge
result sets at the cost of re-qualifying rows on retrieval.

## Lossy vs exact stats

The TBM tracks two kinds of entries:
- **Exact** — per-page list of matching TIDs (precise).
- **Lossy** — per-page bit ("this page has SOMETHING matching")
  used when memory pressure forces compaction.

`stats.exact_pages` / `stats.lossy_pages` populate EXPLAIN
output. High lossy% means `work_mem` was too small for the index
scan output.

## Per-worker vs shared lifecycle

| Per-worker | Shared |
|---|---|
| `TBMIterator` handle | `dsa_pointer` to shared iterator state |
| `TableScanDesc` for heap | TBM contents in DSA |
| Local `recheck`, `stats` | `ParallelBitmapHeapState` mutex+state |

At shutdown, each worker calls `tbm_end_iterate` on its handle;
the last detacher frees the shared iterator.

## Why parallel BitmapHeapScan is a win

- The inner BitmapIndexScan can also be parallel (one TBM build
  across workers).
- Heap I/O parallelizes across workers without page-level
  contention (workers claim disjoint blocks).
- The TBM dedup means double-fetches don't happen.
- Backed by `effective_io_concurrency` for prefetch.

## Common review-time concerns

- **Election must use atomic CAS** —
  `BitmapShouldInitializeSharedState` enforces single-leader.
- **All workers (including the leader) call tbm_begin_iterate**
  — the leader is not exempt.
- **Lossy pages cost recheck** — keep work_mem high enough for
  exact-only TBMs on hot queries.
- **Bitmap qual is rerun on recheck** — must be deterministic.
- **ConditionVariable broadcast wakes ALL waiters** — they
  re-check state.
- **Shared iterator is one writer at a time** — internally
  serialized by tbm_shared_iterate's CAS.

## Invariants

- **[INV-1]** Exactly one worker builds the TBM (election via
  BM_INITIAL → BM_INPROGRESS CAS).
- **[INV-2]** All workers (including leader) call
  tbm_begin_iterate after build.
- **[INV-3]** Block-range claim is atomic; two workers never
  read the same block.
- **[INV-4]** Lossy pages trigger per-row qual recheck.
- **[INV-5]** Last detacher frees the shared iterator + TBM.

## Useful greps

- The control struct:
  `grep -n 'ParallelBitmapHeapState\|SharedBitmapState' source/src/backend/executor/nodeBitmapHeapscan.c | head -10`
- Election + wait:
  `grep -n 'BitmapShouldInitializeSharedState\|BitmapDoneInitializingSharedState\|ConditionVariable' source/src/backend/executor/nodeBitmapHeapscan.c | head -10`
- TBM shared iterator:
  `grep -n 'tbm_prepare_shared_iterate\|tbm_begin_iterate\|tbm_shared_iterate' source/src/backend/nodes/tidbitmap.c | head -10`
- Heap-AM bitmap path:
  `grep -RIn 'table_beginscan_bm\|table_scan_bitmap_next_block\|table_scan_bitmap_next_tuple' source/src/backend/access/heap | head -10`

## Cross-references

- `knowledge/idioms/parallel-gather-merge.md` — Gather above.
- `knowledge/idioms/parallel-worker-coordination.md` —
  Barrier / ConditionVariable.
- `knowledge/idioms/parallel-hash-join.md` — sibling parallel
  node.
- `knowledge/data-structures/tidbitmap.md` — TBM struct.
- `knowledge/idioms/tableam-vtable.md` — bitmap callbacks.
- `knowledge/subsystems/parallel-query.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `.claude/skills/parallel-query/SKILL.md` — planning side.
- `source/src/backend/executor/nodeBitmapHeapscan.c` —
  full module.
- `source/src/backend/nodes/tidbitmap.c` — TBM implementation.
