# vacuumlazy.c — the three-phase heap+indexes+heap orchestration

`vacuumlazy.c` is the orchestrator of lazy (non-blocking) VACUUM. It
drives three logically distinct phases over a single heap relation plus
its indexes:

- **Phase I** — scan the heap. For each page, take a cleanup lock (or
  fall back to a share lock under reduced-work mode), run
  `heap_page_prune_and_freeze` to prune HOT chains, freeze old tuples,
  set VM bits, and accumulate `LP_DEAD` offsets into the `TidStore`
  (`dead_items`).
- **Phase II** — vacuum each index using the accumulated dead-TID set.
  Index AMs walk their structures and delete entries pointing at
  `LP_DEAD` heap slots.
- **Phase III** — sweep the heap again, this time converting
  `LP_DEAD` line pointers to `LP_UNUSED` (now safe because no index
  entry points at them). This step requires only an exclusive lock,
  not a cleanup lock, because no tuple data moves.

The two-pass-heap shape is forced by the constraint that **an index
entry cannot be deleted before the heap line pointer it points to has
been collected, AND the heap line pointer cannot be reused before the
index entry is deleted**. The intermediate `LP_DEAD` state is the
bridge.

But Phase I can fill the `TidStore` past `maintenance_work_mem` before
the relation is done. When that happens, vacuum **drains** by running
phases II + III for the items currently buffered, then resumes Phase I
where it left off. So the actual execution is a state machine that may
cycle through (I, II, III) repeatedly. The banner is explicit: "In a
way, the phases are more like states in a state machine."

This doc covers `heap_vacuum_rel`'s top-level setup, the `lazy_scan_heap`
loop with its inline TidStore-spill check, the cleanup-lock fallback
to `lazy_scan_noprune`, the `lazy_vacuum` decision tree (bypass /
failsafe / normal), and the post-vacuum truncation step.

Companion docs:
- [[vacuum-hot-prune]] — heap_page_prune_and_freeze (the work each Phase I page does).
- [[vacuum-tid-store]] — the dead-TID accumulator that bridges Phase I and Phase II.
- [[heap-tuple-freeze]] — the freeze plan-then-execute that Phase I integrates.
- [[xmin-horizon-management]] — OldestXmin / FreezeLimit / relfrozenxid management.

## Anchors

- `source/src/backend/access/heap/vacuumlazy.c:1-160` — banner with the three-phase + state-machine + eager-scan policy.
- `source/src/backend/access/heap/vacuumlazy.c:623-1100` — `heap_vacuum_rel` (top-level entry).
- `source/src/backend/access/heap/vacuumlazy.c:1279-1500` — `lazy_scan_heap` main loop.
- `source/src/backend/access/heap/vacuumlazy.c:1648-1875` — `heap_vac_scan_next_block` (ReadStream callback; eager-scan + skip-with-VM policy).
- `source/src/backend/access/heap/vacuumlazy.c:2021-2135` — `lazy_scan_prune` (per-page cleanup-lock path).
- `source/src/backend/access/heap/vacuumlazy.c:2157-2350` — `lazy_scan_noprune` (share-lock fallback).
- `source/src/backend/access/heap/vacuumlazy.c:2369-2483` — `lazy_vacuum` (drain decision tree).
- `source/src/backend/access/heap/vacuumlazy.c:2494-2640` — `lazy_vacuum_all_indexes`.
- `source/src/backend/access/heap/vacuumlazy.c:2640-2760` — `lazy_vacuum_heap_rel` (Phase III).
- `source/src/backend/access/heap/vacuumlazy.c:3549+` — `lazy_truncate_heap` (post-vacuum truncation).

## The data structure — LVRelState

The pervasive `LVRelState *vacrel` carries everything the three phases
share:

```c
/* Selected fields (paraphrased from LVRelState; see vacuumlazy.h) */
struct LVRelState {
    Relation        rel;                    /* the heap */
    Relation       *indrels;                /* all indexes (cached open) */
    int             nindexes;
    BufferAccessStrategy bstrategy;         /* ring buffer = 256 KiB */

    /* Cutoffs computed by vacuum_get_cutoffs (see [[xmin-horizon-management]]) */
    VacuumCutoffs   cutoffs;
    GlobalVisState *vistest;
    bool            aggressive;             /* must scan every unfrozen page */
    bool            skipwithvm;             /* allowed to skip via VM bits */

    /* The dead-TID accumulator (see [[vacuum-tid-store]]) */
    TidStore       *dead_items;
    VacDeadItemsInfo *dead_items_info;      /* max_bytes + num_items */

    /* Per-vacuum tracking */
    BlockNumber     rel_pages, scanned_pages, removed_pages;
    BlockNumber     lpdead_item_pages, missed_dead_pages, nonempty_pages;
    int64           tuples_deleted, tuples_frozen, lpdead_items;
    int             num_index_scans;        /* increments per drain cycle */

    /* Output candidates for pg_class.relfrozenxid/relminmxid */
    TransactionId   NewRelfrozenXid;
    MultiXactId     NewRelminMxid;

    /* Bypass / failsafe state */
    bool            do_index_vacuuming, do_index_cleanup, do_rel_truncate;
    bool            consider_bypass_optimization;
};
```

The struct is allocated once at the top of `heap_vacuum_rel`
(`vacuumlazy.c:686`) and lives until the function returns. Index
relations are opened once (`vac_open_indexes`, line 700) and reused
across all drain cycles.

## Top-level setup — heap_vacuum_rel

```c
/* vacuumlazy.c:623-1100 (abridged) */
void heap_vacuum_rel(Relation rel, VacuumParams *params, ...) {
    /* 1. Allocate vacrel, set up error-context callback */
    vacrel = palloc0_object(LVRelState);
    error_context_stack = &errcallback;     /* phase-aware error messages */

    /* 2. Open indexes */
    vac_open_indexes(vacrel->rel, RowExclusiveLock, &vacrel->nindexes, ...);

    /* 3. Apply index_cleanup / truncate params */
    if (params->index_cleanup == VACOPTVALUE_DISABLED)
        vacrel->do_index_vacuuming = vacrel->do_index_cleanup = false;

    /* 4. Compute cutoffs and decide aggressive mode */
    vacrel->aggressive = vacuum_get_cutoffs(rel, params, &vacrel->cutoffs);
    vacrel->vistest    = GlobalVisTestFor(rel);

    /* 5. Initialize NewRelfrozenXid candidate to OldestXmin */
    vacrel->NewRelfrozenXid = vacrel->cutoffs.OldestXmin;
    vacrel->NewRelminMxid   = vacrel->cutoffs.OldestMxact;

    /* 6. Set up eager-scan tracking (only for non-aggressive vacuums) */
    heap_vacuum_eager_scan_setup(vacrel, params);

    /* 7. Allocate the TidStore */
    dead_items_alloc(vacrel, params->nworkers);   /* shared if parallel */

    /* 8. THE WORK */
    lazy_scan_heap(vacrel);

    /* 9. Final cleanup pass (calls amvacuumcleanup on each index) */
    lazy_cleanup_all_indexes(vacrel);

    /* 10. Maybe truncate the relation */
    if (should_attempt_truncation(vacrel))
        lazy_truncate_heap(vacrel);

    /* 11. Update pg_class.relfrozenxid/relminmxid/reltuples/relpages */
    vac_update_relstats(rel, new_rel_pages, ..., vacrel->NewRelfrozenXid, ...);

    /* 12. Free the TidStore */
    dead_items_cleanup(vacrel);
}
```

[verified-by-code] (`vacuumlazy.c:686-1100`).

The error-context callback (`vacuum_error_callback`) reads the current
phase (`vacrel->phase`) and emits messages like "while scanning block
X in relation Y" — invaluable for diagnosing corruption mid-VACUUM.

## Phase I — lazy_scan_heap

```c
/* vacuumlazy.c:1279-1500 (skeleton) */
static void lazy_scan_heap(LVRelState *vacrel) {
    /* Set up ReadStream for prefetched async I/O */
    stream = read_stream_begin_relation(READ_STREAM_MAINTENANCE, ..., MAIN_FORKNUM,
                                        heap_vac_scan_next_block, ...);

    while (true) {
        /* Spill check: if TidStore is over max_bytes, drain via lazy_vacuum */
        if (TidStoreMemoryUsage(vacrel->dead_items) > max_bytes) {
            ReleaseBuffer(vmbuffer);                    /* don't hold across drain */
            vacrel->consider_bypass_optimization = false;
            lazy_vacuum(vacrel);                        /* runs phases II + III */
            FreeSpaceMapVacuumRange(rel, prev_blkno, blkno + 1);
        }

        buf = read_stream_next_buffer(stream, &per_buffer_data);
        if (!BufferIsValid(buf)) break;                 /* relation exhausted */

        /* Pin VM page (may be needed to set bits) */
        visibilitymap_pin(rel, blkno, &vmbuffer);

        /* Try for cleanup lock; fall back to share lock */
        got_cleanup_lock = ConditionalLockBufferForCleanup(buf);
        if (!got_cleanup_lock) LockBuffer(buf, BUFFER_LOCK_SHARE);

        /* New or all-zero page: simple handling */
        if (lazy_scan_new_or_empty(vacrel, buf, blkno, page, !got_cleanup_lock, vmbuffer))
            continue;

        /* Share-lock path: may return false if aggressive vacuum needs cleanup lock */
        if (!got_cleanup_lock && !lazy_scan_noprune(vacrel, buf, ...)) {
            LockBuffer(buf, BUFFER_LOCK_UNLOCK);
            LockBufferForCleanup(buf);                  /* wait! */
            got_cleanup_lock = true;
        }

        /* Cleanup-lock path: full prune + freeze + dead-TID collection */
        if (got_cleanup_lock)
            lazy_scan_prune(vacrel, buf, blkno, page, vmbuffer, &has_lpdead_items,
                            &vm_page_frozen);

        /* Eager-freeze accounting (non-aggressive vacuums only) */
        if (was_eager_scanned) {
            if (vm_page_frozen) vacrel->eager_scan_remaining_successes--;
            else                vacrel->eager_scan_remaining_fails--;
            if (... hit caps) disable_eager_scanning_this_region();
        }

        UnlockReleaseBuffer(buf);
    }
    /* End of relation: do one last drain if anything pending */
    if (vacrel->dead_items_info->num_items > 0)
        lazy_vacuum(vacrel);
}
```

The inline `TidStoreMemoryUsage > max_bytes` check at the top is the
**spill loop**. The drain runs `lazy_vacuum` (Phase II + Phase III),
which empties the store, then the heap scan resumes from the same
block it was paused at. [verified-by-code] (`vacuumlazy.c:1355-1386`).

Each drain bumps `num_index_scans`. A relation that requires many
drains is a clue that `maintenance_work_mem` is undersized for the
table's churn rate. The `dead_items_reset` is called inside
`lazy_vacuum` (line 2482).

## Cleanup lock vs share lock — the two-tier scan

`ConditionalLockBufferForCleanup(buf)` returns true only if **no other
backend holds a pin** on the buffer. Cleanup lock is required for
`lazy_scan_prune` because the underlying `heap_page_prune_execute`
calls `PageRepairFragmentation`, which moves tuple data — concurrent
pin holders would see torn reads.

If cleanup-lock acquisition fails (concurrent pin), vacuum tries
`lazy_scan_noprune` under just a share lock
(`vacuumlazy.c:2157`). This path:

- Collects existing `LP_DEAD` line pointers (already dead; setting
  them doesn't move data).
- Counts live and recently-dead tuples for vacuum logging.
- Tracks whether the page can later be truncated.
- Maintains `NoFreezePage*` trackers (the conservative
  `pg_class.relfrozenxid` candidate if we *don't* freeze this page).

`lazy_scan_noprune` returns **false** if the page contains XIDs old
enough to require freezing AND the vacuum is aggressive. In that case,
the calling code releases the share lock and **waits** for the cleanup
lock (`LockBufferForCleanup`, line 1451), then calls `lazy_scan_prune`.

Non-aggressive vacuums never need to wait — they accept "missing" the
work on contested pages, will catch up in a future vacuum.
[from-comment] (`vacuumlazy.c:2146-2150`).

## Phase I per-page work — lazy_scan_prune

```c
/* vacuumlazy.c:2021-2135 (abridged) */
static int lazy_scan_prune(LVRelState *vacrel, Buffer buf, BlockNumber blkno,
                           Page page, Buffer vmbuffer,
                           bool *has_lpdead_items, bool *vm_page_frozen)
{
    PruneFreezeParams params = {
        .relation = rel, .buffer = buf, .vmbuffer = vmbuffer,
        .reason = PRUNE_VACUUM_SCAN,
        .options = HEAP_PAGE_PRUNE_FREEZE | HEAP_PAGE_PRUNE_SET_VM,
        .vistest = vacrel->vistest,
        .cutoffs = &vacrel->cutoffs,
    };

    /* No-index relations: can flip would-be LP_DEAD straight to LP_UNUSED */
    if (vacrel->nindexes == 0)
        params.options |= HEAP_PAGE_PRUNE_MARK_UNUSED_NOW;

    /* Skip-with-VM optimization */
    if (vacrel->skipwithvm)
        params.options |= HEAP_PAGE_PRUNE_ALLOW_FAST_PATH;

    heap_page_prune_and_freeze(&params, &presult, &vacrel->offnum,
                               &vacrel->NewRelfrozenXid, &vacrel->NewRelminMxid);

    /* If page has LP_DEAD items, push them to the dead_items TidStore */
    if (presult.lpdead_items > 0) {
        qsort(presult.deadoffsets, presult.lpdead_items, sizeof(OffsetNumber),
              cmpOffsetNumbers);                                /* TidStore requires sorted */
        dead_items_add(vacrel, blkno, presult.deadoffsets, presult.lpdead_items);
    }

    /* Update per-vacuum counters */
    vacrel->tuples_deleted += presult.ndeleted;
    vacrel->tuples_frozen  += presult.nfrozen;
    vacrel->lpdead_items   += presult.lpdead_items;
    ...
    return presult.ndeleted;
}
```

The pivotal call is `heap_page_prune_and_freeze` (covered in
[[vacuum-hot-prune]]), which packs prune, freeze, and VM-set into a
single critical-section + WAL-record application. `lazy_scan_prune`
collects the outputs (`lpdead_items`, `deadoffsets`, frozen counts)
and integrates them into the `LVRelState`.

The `qsort` on `deadoffsets` is required because
`heap_page_prune_and_freeze` collects offsets in HOT-chain-walk order,
not page order, but `TidStoreSetBlockOffsets` requires sorted-ascending
input. [verified-by-code] (`vacuumlazy.c:2098-2106`). See
[[vacuum-tid-store]].

The `HEAP_PAGE_PRUNE_MARK_UNUSED_NOW` option is the **no-indexes
shortcut**: if there are no indexes, no entry references any heap TID,
so dead tuples can skip the `LP_DEAD` bridge state and go straight to
`LP_UNUSED`. This eliminates the need for Phase II and Phase III
entirely for index-free relations. [verified-by-code]
(`vacuumlazy.c:2058-2059`).

## Phase II — lazy_vacuum_all_indexes

After the TidStore is full (spill) or the heap scan is done,
`lazy_vacuum(vacrel)` (`vacuumlazy.c:2369`) decides what to do:

```c
if (!vacrel->do_index_vacuuming) {
    dead_items_reset(vacrel); return;        /* user disabled; just forget */
}

if (consider_bypass_optimization && vacrel->rel_pages > 0) {
    threshold = vacrel->rel_pages * BYPASS_THRESHOLD_PAGES;   /* 2% by default */
    bypass = (vacrel->lpdead_item_pages < threshold &&
              TidStoreMemoryUsage(vacrel->dead_items) < 32 * 1024 * 1024);
}

if (bypass) {
    vacrel->do_index_vacuuming = false;       /* skip phases II & III */
} else if (lazy_vacuum_all_indexes(vacrel)) {
    lazy_vacuum_heap_rel(vacrel);             /* phase III */
} else {
    Assert(VacuumFailsafeActive);             /* wraparound emergency */
}

dead_items_reset(vacrel);
```

Three exits:

1. **User-disabled** — `index_cleanup = off`: phases II/III skipped.
2. **Bypass optimization** — fewer than ~2% of pages have LP_DEADs
   AND TidStore < 32 MiB. The rationale is **stability**: a workload
   that mostly uses HOT will occasionally leave a few stragglers; we
   don't want vacuum duration to spike from "a few" to "fan-out
   index scan" for those. Better to let the next vacuum collect them.
   [from-comment] (`vacuumlazy.c:2393-2433`).
3. **Failsafe** — `lazy_check_wraparound_failsafe` returned true (XID
   wraparound is imminent). `VacuumFailsafeActive` becomes true; the
   ongoing vacuum stops all index/heap cleanup and just focuses on
   advancing `relfrozenxid`. [verified-by-code] (`vacuumlazy.c:2462-2476`).

The normal path runs `lazy_vacuum_all_indexes`, which serially calls
`lazy_vacuum_one_index(indrel, ...)` for each index, or hands off to
the parallel-worker pool via `parallel_vacuum_bulkdel_all_indexes` if
parallelism is configured. Each index AM's `ambulkdelete` callback
receives the `TidStore` and walks its structure to delete entries.

## Phase III — lazy_vacuum_heap_rel

```c
/* vacuumlazy.c:2640-2760 (skeleton) */
static void lazy_vacuum_heap_rel(LVRelState *vacrel) {
    /* Iterate the TidStore, one block at a time */
    iter = TidStoreBeginIterate(vacrel->dead_items);
    while ((iter_result = TidStoreIterateNext(iter)) != NULL) {
        ReadBufferExtended(rel, MAIN_FORKNUM, iter_result->blkno, ...);
        LockBuffer(buf, BUFFER_LOCK_EXCLUSIVE);              /* not cleanup! */

        offsets_n = TidStoreGetBlockOffsets(iter_result, offsets, ...);
        lazy_vacuum_heap_page(vacrel, blkno, buf, offsets, offsets_n, vmbuffer);

        UnlockReleaseBuffer(buf);
    }
    TidStoreEndIterate(iter);
}
```

`lazy_vacuum_heap_page` (`vacuumlazy.c:2758`) applies
`heap_page_prune_execute(buffer, lp_truncate_only=true, ..., nowunused,
nunused)` — the `lp_truncate_only` mode that flips `LP_DEAD` to
`LP_UNUSED` without touching tuple data. This is why Phase III only
needs an exclusive lock, not a cleanup lock: no tuples move, just
2-bit line-pointer state changes.

After the line pointers are updated, vacuum may set the page
`PD_ALL_VISIBLE` and update the VM bits if the page is now fully
clean. [verified-by-code] (`pruneheap.c:2169-2206` for the applier;
`vacuumlazy.c:2758+` for the orchestration).

## Eager scanning — the page-skipping policy

Non-aggressive vacuums skip pages marked `VM_ALL_VISIBLE` (and
especially `VM_ALL_FROZEN`) in the visibility map. But two cases
override:

1. **`SKIP_PAGES_THRESHOLD`** — even if VM says skippable, scan a
   short run anyway for readahead efficiency. [from-comment]
   (`vacuumlazy.c:49-52`).
2. **Eager freeze** — scan some all-visible pages to freeze them,
   reducing the backlog of "all-visible but not all-frozen" pages
   that the next aggressive vacuum would have to scan.

Eager freeze has two caps to bound wasted work:

- **Global success cap**: at most `MAX_EAGER_FREEZE_SUCCESS_RATE` of
  the all-visible-but-not-all-frozen page count. Once hit, eager
  scanning is disabled for the rest of the relation.
- **Per-region failure cap**: `vacuum_max_eager_freeze_failure_rate`
  of `EAGER_SCAN_REGION_SIZE` blocks. Failure counter resets per
  region. Localized failure suspends eager scanning until the next
  region.

This is the policy that keeps non-aggressive vacuum from doing too
much work freezing pages that may be re-dirtied soon, while still
making forward progress on the long-term wraparound horizon.
[from-comment] (`vacuumlazy.c:64-87`).

## Truncation — lazy_truncate_heap

After the three phases complete, if the **tail** of the relation
consists entirely of empty pages (`vacrel->nonempty_pages <
rel_pages`), vacuum tries to **truncate** the relation file:

```c
if (should_attempt_truncation(vacrel))
    lazy_truncate_heap(vacrel);
```

Truncation requires an `AccessExclusiveLock` on the relation — vacuum
attempts this with `ConditionalLockRelationWithTimeout` so concurrent
queries aren't blocked indefinitely. If the lock can't be acquired in
a short time, truncation is skipped (this VACUUM can't shrink the
file; the next one may). The mechanism is more deeply covered in
[[vacuum-truncate-relation]].

## The wraparound failsafe

`lazy_check_wraparound_failsafe(vacrel)` is called periodically (every
`FAILSAFE_EVERY_PAGES` pages and at index-vacuum start). If
`relfrozenxid` or `relminmxid` is **dangerously old** —
`vacuum_failsafe_age` past the wraparound limit — the failsafe
activates: `VacuumFailsafeActive = true`, all index and heap-pass-2
cleanup is **abandoned**, and vacuum focuses solely on advancing
`relfrozenxid` by freezing what it has scanned so far. This is the
"don't let the database refuse new XIDs" escape hatch.
[verified-by-code] (`vacuumlazy.c:1343-1345`).

After a failsafe activation, the LP_DEAD work is discarded; the next
vacuum will rediscover them.

## Invariants and races

1. **Phases II and III must run together or not at all** in a single
   drain cycle. You can't index-vacuum and skip heap-vacuum (or
   vice versa) without leaving dangling state. The drain loop's
   `dead_items_reset` reflects this.
2. **TidStore drains preserve mid-relation position.** Phase I
   resumes from the next unscanned block. The `next_fsm_block_to_vacuum`
   tracker is also preserved across drains. [verified-by-code]
   (`vacuumlazy.c:1374-1381`).
3. **`vacrel->NewRelfrozenXid` only ratchets *backward*** during
   the scan — it tracks the oldest still-unfrozen XID seen. The
   final `pg_class.relfrozenxid` is the safest (oldest) of all
   per-page candidates. [verified-by-code] (`vacuumlazy.c:807-808`).
4. **Cleanup-lock fallback is not a free pass.** Aggressive vacuums
   `LockBufferForCleanup` (block) rather than skip a page that
   needs freezing. Non-aggressive vacuums skip silently.
   [from-comment] (`vacuumlazy.c:2146-2150`).
5. **Index-cleanup bypass is bounded.** The `< 32 MiB` TidStore
   limit on bypass-eligibility prevents "bypass forever" from
   resulting in a giant non-CPU-cache-resident TID set later.
   [from-comment] (`vacuumlazy.c:2421-2425`).
6. **Truncation is best-effort.** A vacuum that can't acquire
   `AccessExclusiveLock` skips truncation; the next vacuum tries.
7. **Failsafe is sticky for the rest of the vacuum.** Once
   `VacuumFailsafeActive` flips on, the current call won't re-enable
   index/heap cleanup. [from-comment] (`vacuumlazy.c:2470-2474`).
8. **Eager-freeze caps are per-vacuum, not per-relation.** A relation
   visited again later starts with fresh caps.

## Useful greps

```bash
# Top-level entry and the three-phase boundaries:
grep -nE "^heap_vacuum_rel|^lazy_scan_heap|^lazy_vacuum\b|^lazy_vacuum_heap_rel|^lazy_truncate_heap" \
       source/src/backend/access/heap/vacuumlazy.c

# Spill loop:
grep -n "TidStoreMemoryUsage\|FreeSpaceMapVacuumRange\|dead_items_reset" \
       source/src/backend/access/heap/vacuumlazy.c | head -10

# Cleanup lock fallback:
grep -nE "ConditionalLockBufferForCleanup|LockBufferForCleanup|lazy_scan_noprune" \
       source/src/backend/access/heap/vacuumlazy.c

# Bypass + failsafe:
grep -nE "BYPASS_THRESHOLD_PAGES|consider_bypass_optimization|VacuumFailsafeActive|lazy_check_wraparound_failsafe" \
       source/src/backend/access/heap/vacuumlazy.c

# Eager scan policy:
grep -nE "eager_scan|EAGER_SCAN_REGION_SIZE|MAX_EAGER_FREEZE_SUCCESS_RATE|vacuum_max_eager_freeze_failure_rate" \
       source/src/backend/access/heap/vacuumlazy.c | head -15
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 1 | banner with the three-phase + state-machine + eager-scan policy |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 623 | heap_vacuum_rel (top-level entry) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 1279 | lazy_scan_heap main loop |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 1648 | heap_vac_scan_next_block (ReadStream callback; eager-scan + skip-with-VM policy) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 2021 | lazy_scan_prune (per-page cleanup-lock path) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 2157 | lazy_scan_noprune (share-lock fallback) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 2369 | lazy_vacuum (drain decision tree) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 2494 | lazy_vacuum_all_indexes |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 2640 | lazy_vacuum_heap_rel (Phase III) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 3549 | + — lazy_truncate_heap (post-vacuum truncation) |

<!-- /callsites:auto -->

## Cross-references

- [[vacuum-hot-prune]] — heap_page_prune_and_freeze (Phase I per-page work).
- [[vacuum-tid-store]] — dead_items radix tree (bridge between phases).
- [[heap-tuple-freeze]] — freeze plan-then-execute integrated into Phase I.
- [[heap-tuple-visibility-mvcc]] — HeapTupleSatisfiesVacuum verdicts that drive pruning.
- [[xmin-horizon-management]] — OldestXmin / FreezeLimit / relfrozenxid management.
- [[visibility-map-update]] — VM bit-set machinery (lazy_scan_prune triggers this).
- [[vacuum-truncate-relation]] — the final truncation step.
- [[vacuum-skip-pages]] — page-skipping heuristics (the eager-scan policy).
- `knowledge/subsystems/access-heap.md` §"Vacuum" — subsystem-level overview.
