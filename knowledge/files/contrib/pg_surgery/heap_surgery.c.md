# `pg_surgery/heap_surgery.c` — destructive WAL-logged tuple surgery

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_surgery/heap_surgery.c`)

## Role

Two SQL functions, `heap_force_kill` and `heap_force_freeze`, that take a
relation OID and a TID array and **directly modify heap tuples on disk**
to either mark them dead (`ItemIdSetDead`) or force-freeze them
(`HEAP_XMIN_FROZEN | HEAP_XMAX_INVALID`, ctid reset, infomask cleared).
This is the documented escape hatch for hand-fixing corruption after
amcheck/pageinspect identifies an unrecoverable tuple.

The module is WAL-logged via `log_newpage_buffer` so the surgery
replicates and survives crash recovery, but it bypasses every other
heap invariant (MVCC, vacuum coordination, xid generation).

## Public API

- `heap_force_kill(regclass, tid[]) -> void` — `source/contrib/pg_surgery/heap_surgery.c:58`
- `heap_force_freeze(regclass, tid[]) -> void` — `source/contrib/pg_surgery/heap_surgery.c:73`

SQL gating: `REVOKE EXECUTE ... FROM PUBLIC` in
`pg_surgery--1.0.sql:14-15` [verified-by-code grep].

## Invariants

- Refuses to run during recovery [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:97-101`).
- Relation must have a table AM, and must be heap AM specifically
  [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:111-121`).
- Caller must be owner of the table or superuser
  (`object_ownercheck(RelationRelationId, …, GetUserId())`)
  [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:123-127`). **This is the
  only C-side check, but it is present.**
- TID array must be one-dimensional and non-null [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:373-386`).
- TIDs are sorted then processed page-at-a-time
  (`source/contrib/pg_surgery/heap_surgery.c:131-146`).
- Each modified page is touched inside `START_CRIT_SECTION`; the buffer
  is acquired via `LockBufferForCleanup` (exclusive pin-and-content
  lock, the strongest buffer guarantee) [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:178-179, 243`).
- All actions are WAL-logged via `log_newpage_buffer(buf, true)` so the
  modified page is replicated as a full-page image; if the VM was
  cleared, the VM page is also logged via `log_newpage_buffer(vmbuf,
  false)` [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:316-328`).
- For `HEAP_FORCE_KILL`, if the page was `PD_ALL_VISIBLE`, the
  visibility map is pinned (before crit section), then cleared in the
  per-tuple loop [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:239-273`).
- Redirected / dead / unused line pointers are SKIPPED with NOTICE; only
  `ItemIdIsNormal` items are operated on (asserted at line 254)
  [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:206-228`).
- Out-of-range block numbers and offset numbers are SKIPPED with
  NOTICE rather than ERROR — partial application by design
  [verified-by-code]
  (`source/contrib/pg_surgery/heap_surgery.c:165-176, 195-201`).

## Notable internals

- `find_tids_one_page` scans the sorted TID array starting at
  `next_start_ptr` and returns the blkno + the index past the last
  TID for that blkno. Walks of one block at a time
  (`source/contrib/pg_surgery/heap_surgery.c:397-421`).
- `include_this_tid[MaxHeapTuplesPerPage]` is a stack-allocated bool
  bitmap that's `memset` before each page
  (`source/contrib/pg_surgery/heap_surgery.c:95, 189`).
- `RowExclusiveLock` on the relation is the heaviest non-DDL lock; it
  blocks `LOCK TABLE … IN EXCLUSIVE MODE` and lets concurrent reads
  proceed.
- `heap_force_freeze` mimics `heap_execute_freeze_tuple` but **also
  resets `t_ctid` and `xmin`** as documented at lines 283-288: "we
  choose to reset xmin and ctid just to be sure that no
  potentially-garbled data is left behind."

## Trust-boundary / Phase D surface

1. **Ownership-or-superuser is the C-side check, GOOD.** Unlike
   pg_visibility / pg_buffercache / pg_freespacemap / amcheck (A12),
   this module DOES enforce `object_ownercheck` at the C level
   [verified-by-code line 124]. So a malicious GRANT in the install
   script cannot undermine the gate. This is the right pattern.
   ✅ NOT an issue.
2. **`object_ownercheck(RelationRelationId, …)` is checked but the
   target can be a system catalog.** The only relkind/AM checks are
   `RELKIND_HAS_TABLE_AM` and `relam == HEAP_TABLE_AM_OID`. A superuser
   (which owns system catalogs in effect) can `heap_force_kill` on
   `pg_class`, `pg_attribute`, etc. — this is **explicitly the
   intended use** (these are the most corrupt-able catalogs) but
   warrants flagging.
   [ISSUE-correctness: heap_force_kill / _freeze accept system catalog
   OIDs as targets; intended for emergency recovery, but a confused
   superuser session can render the catalog inconsistent in seconds
   — no extra confirmation gate (confirmed)]
   (`source/contrib/pg_surgery/heap_surgery.c:111-127`).
3. **Force-freeze sets `HeapTupleHeaderSetXmin(htup, FrozenTransactionId)`
   on tuples that may have been INSERT'd in an aborted xact.** That
   means a tuple whose xmin had not yet been visible to any snapshot
   becomes immediately visible to all snapshots, including snapshots
   that already saw it as "not committed." Documented hazard, but the
   only mention is "potentially-garbled data" comment line 287.
   [ISSUE-correctness: heap_force_freeze on an aborted xact's tuple
   resurrects the tuple as frozen-visible to ALL snapshots, including
   prior snapshots that saw it as aborted — silent timeline violation,
   not documented (likely)]
   (`source/contrib/pg_surgery/heap_surgery.c:289-308`).
4. **Force-kill clears `PD_ALL_VISIBLE` but does not reset hint bits on
   surrounding tuples.** If page has 100 tuples and only one is killed,
   the page is no longer all-visible but other tuples' hint bits are
   untouched — fine, but vacuum will need to re-set them.
5. **`MaxHeapTuplesPerPage` stack array** is on the order of 1700; using
   `bool include_this_tid[MaxHeapTuplesPerPage]` is fine as a 1.7 KB
   stack allocation per page processed
   (`source/contrib/pg_surgery/heap_surgery.c:95`).
6. **`PG_GETARG_ARRAYTYPE_P_COPY(1)` makes a deep copy** of the TID
   array — important because the function `qsort`s it in place.
   `pfree(ta)` at line 343 is paired correctly [verified-by-code].
7. **`log_newpage_buffer` writes the entire 8 KB page image** for each
   modified page. For surgery on a 1-million-TID array that happens
   to span 100k pages, this is 800 MB of WAL. Documented? No.
   [ISSUE-resource: log_newpage_buffer per modified page can produce
   8 KB FPI * affected-pages of WAL; no docstring warning (nit)]
   (`source/contrib/pg_surgery/heap_surgery.c:319-328`).
8. **CHECK_FOR_INTERRUPTS at top of each-block loop only** (line 157),
   not within the per-TID inner loop or the modify-page loop. Both
   are bounded by `MaxHeapTuplesPerPage`, so OK.
9. **No locking of the relation OID for ACL/visibility purposes before
   the `RowExclusiveLock`.** A concurrent DROP TABLE would block on
   the heavier lock from this function, but a concurrent reindex /
   vacuum can race. Heap surgery is documented as last-resort
   recovery, so the system is expected to be quiesced during use, but
   the C code does not enforce this.
10. **`HEAP_HOT_UPDATED` and `HEAP_KEYS_UPDATED` bits are cleared
    unconditionally on freeze.** This is correct (frozen tuple is
    terminal) but combined with the xmin reset, a HOT chain headed by
    this tuple may become unfollowable — downstream tuples in the
    chain still reference the old ctid.
    [ISSUE-correctness: force-freezing a HOT-update root tuple leaves
    dangling HOT successors with a redirect/ctid pointing at the now-
    rewritten tuple — chain semantics undefined (maybe)]
    (`source/contrib/pg_surgery/heap_surgery.c:289-308`).

## Cross-refs

- `knowledge/subsystems/access-heap.md` — heap tuple infomask layout, freeze semantics
- `knowledge/subsystems/wal.md` — log_newpage_buffer / FPI
- `knowledge/idioms/locking.md` — LockBufferForCleanup discipline
- `knowledge/files/contrib/amcheck/` — A12, partner tool (find corruption first)
- `knowledge/files/contrib/pageinspect/` — A12, partner tool (read raw bytes to identify what's broken)

<!-- issues:auto:begin -->
- [Issue register — `pg_surgery`](../../../issues/pg_surgery.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-correctness: accepts system catalog OIDs; superuser confusion → instant catalog corruption (confirmed)] — `source/contrib/pg_surgery/heap_surgery.c:111-127`
2. [ISSUE-correctness: force-freeze on aborted-xact tuple silently makes it visible to ALL snapshots (likely)] — `source/contrib/pg_surgery/heap_surgery.c:289-308`
3. [ISSUE-resource: log_newpage_buffer FPI per affected page; undocumented WAL amplification (nit)] — `source/contrib/pg_surgery/heap_surgery.c:319-328`
4. [ISSUE-correctness: force-freeze on HOT-chain root leaves successors dangling (maybe)] — `source/contrib/pg_surgery/heap_surgery.c:289-308`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_surgery.md](../../../subsystems/contrib-pg_surgery.md)
