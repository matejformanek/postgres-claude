# pg_subtrans — the subxid→parent SLRU

When the in-PGPROC XID cache overflows ([[subxact-xidcache-and-pgproc]])
or when a backend needs to look up the **topmost** parent of an
arbitrary subxact XID, the answer comes from **pg_subtrans**: a simple
SLRU (Simple LRU) that stores 4 bytes per XID — the parent XID. Walking
the resulting chain from any subxact XID upward eventually reaches
either the top-level XID (whose parent slot is `InvalidTransactionId`)
or `TransactionXmin` (the global oldest-xid horizon).

Unlike pg_xact / clog, pg_subtrans **doesn't need to survive crashes**.
A backend that's mid-subtransaction at crash time will have its top
transaction rolled back anyway, so the parent-pointer information has
no value across a crash. This relaxation lets pg_subtrans skip all
WAL integration — the on-disk pages are zeroed during startup and
re-populated as backends do their work.

This doc covers the SLRU layout, the read/write API,
`SubTransGetTopmostTransaction` (the workhorse called from snapshot
visibility), the bootstrap/startup/truncate machinery, and the
sizing knob (`subtransaction_buffers`).

For the in-memory cache that this SLRU backs, see
[[subxact-xidcache-and-pgproc]]. For how snapshot visibility decides
when to fall back to this SLRU, see [[subxact-visibility-and-overflow]].

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/backend/access/transam/subtrans.c:1-50` — banner with
  the "no XLOG interactions" + "no crash survival" design statement.
- `source/src/backend/access/transam/subtrans.c:54-67` — page math
  (`SUBTRANS_XACTS_PER_PAGE`, `TransactionIdToPage`,
  `TransactionIdToEntry`).
- `source/src/backend/access/transam/subtrans.c:88-123` —
  `SubTransSetParent`.
- `source/src/backend/access/transam/subtrans.c:125-156` —
  `SubTransGetParent`.
- `source/src/backend/access/transam/subtrans.c:157-198` —
  `SubTransGetTopmostTransaction`.
- `source/src/backend/access/transam/subtrans.c:204-263` — shared
  memory request + init.
- `source/src/backend/access/transam/subtrans.c:288-348` —
  `BootStrapSUBTRANS`, `StartupSUBTRANS`, `CheckPointSUBTRANS`.
- `source/src/backend/access/transam/subtrans.c:372-431` —
  `ExtendSUBTRANS`, `TruncateSUBTRANS`, `SubTransPagePrecedes`.
- `source/src/include/access/subtrans.h:1-24` — public API.

## What's stored

Each `pg_subtrans` page holds `BLCKSZ / sizeof(TransactionId) =
8192 / 4 = 2048` entries on a default-built server
[subtrans.c:55]. Entry `i` on page `p` stores the parent XID of the
transaction whose ID equals `p * 2048 + i`. A value of
`InvalidTransactionId = 0` means "this xid is either a top-level
transaction (no parent) or hasn't been recorded yet".

```c
#define SUBTRANS_XACTS_PER_PAGE (BLCKSZ / sizeof(TransactionId))

static inline int64
TransactionIdToPage(TransactionId xid)
{
    return xid / (int64) SUBTRANS_XACTS_PER_PAGE;
}

#define TransactionIdToEntry(xid) \
    ((xid) % (TransactionId) SUBTRANS_XACTS_PER_PAGE)
```

[subtrans.c:54-67]. Plain integer division. No hashing, no
indirection — the XID is the address.

The total addressable space wraps at `0xFFFFFFFF /
SUBTRANS_XACTS_PER_PAGE` pages
[subtrans.c:45-52 comment]. With ~2k entries per page, that's
~2 million pages of 8 KiB = 16 GiB of disk space if it were ever
fully populated. In practice pg_subtrans is truncated regularly to
match `TransactionXmin`, so it stays a few MB.

## `SubTransSetParent` — record a child→parent mapping

[subtrans.c:88-123]:

```c
void
SubTransSetParent(TransactionId xid, TransactionId parent)
{
    int64 pageno = TransactionIdToPage(xid);
    int   entryno = TransactionIdToEntry(xid);
    int   slotno;
    LWLock *lock;
    TransactionId *ptr;

    Assert(TransactionIdIsValid(parent));
    Assert(TransactionIdFollows(xid, parent));  /* child > parent */

    lock = SimpleLruGetBankLock(SubTransCtl, pageno);
    LWLockAcquire(lock, LW_EXCLUSIVE);

    slotno = SimpleLruReadPage(SubTransCtl, pageno, true, &xid);
    ptr = (TransactionId *) SubTransCtl->shared->page_buffer[slotno];
    ptr += entryno;

    if (*ptr != parent) {
        /* "It's possible we'll try to set the parent xid multiple times
         * but we shouldn't ever be changing the xid from one valid xid
         * to another valid xid, which would corrupt the data structure." */
        Assert(*ptr == InvalidTransactionId);
        *ptr = parent;
        SubTransCtl->shared->page_dirty[slotno] = true;
    }

    LWLockRelease(lock);
}
```

Three points:

1. **`Assert(TransactionIdFollows(xid, parent))`** — the child XID
   must be numerically greater than the parent. This invariant is
   guaranteed by how XIDs are assigned (monotonically increasing
   from `XidGenLock`-protected counter), and `SubTransGetTopmostTransaction`
   relies on it to detect corruption.

2. **Lock granularity: per-bank.** `SimpleLruGetBankLock(SubTransCtl,
   pageno)` returns one of N LWLocks, where N = number of banks in
   the SLRU's slot array. Buffer contention is partitioned across
   these locks, so multiple writers to different pages don't
   serialize on a single lock. This matters because subxid creation
   happens at every `BeginInternalSubTransaction` on every backend.

3. **Idempotent.** If the slot is already set to the same parent,
   we don't dirty the page. If it's set to a *different* parent,
   we Assert — this would mean two transactions claimed the same
   child XID, which is a corruption indicator.

The "first time we record a subxact" path comes via
`AssignTransactionId` (in xact.c) when a write inside a subxact
requires it to obtain an XID. The flow is:

1. `AssignTransactionId` allocates a fresh XID from the XID
   generator.
2. If we're inside a subtransaction (nesting level > 0), call
   `SubTransSetParent(new_xid, parent_xid)`.
3. Push the new XID onto the parent's `childXids[]` array (the
   per-backend transaction-state stack, see [[subtransaction-stack]]).

## `SubTransGetParent` — single-step lookup

[subtrans.c:125-156]:

```c
TransactionId
SubTransGetParent(TransactionId xid)
{
    int64 pageno = TransactionIdToPage(xid);
    int   entryno = TransactionIdToEntry(xid);
    int   slotno;
    TransactionId *ptr;
    TransactionId parent;

    Assert(TransactionIdFollowsOrEquals(xid, TransactionXmin));

    if (!TransactionIdIsNormal(xid))
        return InvalidTransactionId;

    /* SimpleLruReadPage_ReadOnly acquires the bank lock for us. */
    slotno = SimpleLruReadPage_ReadOnly(SubTransCtl, pageno, &xid);
    ptr = (TransactionId *) SubTransCtl->shared->page_buffer[slotno];
    ptr += entryno;
    parent = *ptr;
    LWLockRelease(SimpleLruGetBankLock(SubTransCtl, pageno));

    return parent;
}
```

Three checks before the read:

- **`TransactionIdFollowsOrEquals(xid, TransactionXmin)`** —
  asserts the caller isn't asking about a transaction older than
  the global xmin horizon. Such XIDs may have already had their
  pg_subtrans page truncated. The caller is responsible for not
  reaching past `TransactionXmin`; the assert catches mistakes.
- **`!TransactionIdIsNormal(xid)` returns `InvalidTransactionId`** —
  bootstrap and frozen XIDs have no parent.
- **`SimpleLruReadPage_ReadOnly` does the actual I/O.** If the
  requested page isn't in the shared SLRU buffer, this reads it
  from disk. The bank lock is acquired before the read and held
  until the caller releases it after consuming `parent`.

The function is the lowest-level read. `SubTransGetTopmostTransaction`
wraps it in a loop.

## `SubTransGetTopmostTransaction` — walk the chain

[subtrans.c:157-198]:

```c
TransactionId
SubTransGetTopmostTransaction(TransactionId xid)
{
    TransactionId parentXid = xid;
    TransactionId previousXid = xid;

    Assert(TransactionIdFollowsOrEquals(xid, TransactionXmin));

    while (TransactionIdIsValid(parentXid)) {
        previousXid = parentXid;

        if (TransactionIdPrecedes(parentXid, TransactionXmin))
            break;  /* can't see past the horizon */

        parentXid = SubTransGetParent(parentXid);

        if (!TransactionIdPrecedes(parentXid, previousXid))
            elog(ERROR, "pg_subtrans contains invalid entry: "
                        "xid %u points to parent xid %u",
                 previousXid, parentXid);
    }

    Assert(TransactionIdIsValid(previousXid));
    return previousXid;
}
```

Four interesting design points:

1. **The walk stops at `TransactionXmin`**, not at "the root".
   The comment at subtrans.c:162-167 acknowledges this:

   > Because we cannot look back further than TransactionXmin, it is
   > possible that this function will lie and return an intermediate
   > subtransaction ID instead of the true topmost parent ID. This is
   > OK, because in practice we only care about detecting whether the
   > topmost parent is still running or is part of a current
   > snapshot's list of still-running transactions. Therefore, any XID
   > before TransactionXmin is as good as any other.

   The intuition: anything before `TransactionXmin` is either
   committed or aborted (definitively settled), and the "is it
   running?" question is answered by clog (pg_xact), not by walking
   higher up the subxact tree.

2. **Returns `previousXid`, not `parentXid`.** After the loop,
   `parentXid` is either `InvalidTransactionId` (the chain reached
   a top-level XID with no parent) or precedes `TransactionXmin`.
   In both cases, `previousXid` is the closest-to-top XID we can
   safely talk about. So it's the answer.

3. **Corruption detection: `!TransactionIdPrecedes(parentXid,
   previousXid)`** — if the parent isn't numerically less than the
   child, the chain has cycled or been corrupted. `elog(ERROR)`
   rather than infinite-loop. This relies on the
   `Assert(TransactionIdFollows(xid, parent))` in
   `SubTransSetParent` to be true at write time.

4. **No locking across iterations.** Each `SubTransGetParent` call
   acquires and releases its bank lock independently. Between
   iterations, the pages we just read could be evicted from SLRU
   buffers and re-read. That's fine — the parent value is
   immutable once written.

## How the SLRU is sized and initialized

`SUBTRANSShmemBuffers` [subtrans.c:204-215]:

```c
static int
SUBTRANSShmemBuffers(void)
{
    if (subtransaction_buffers == 0)
        return SimpleLruAutotuneBuffers(512, 1024);
    return Min(Max(16, subtransaction_buffers), SLRU_MAX_ALLOWED_BUFFERS);
}
```

`subtransaction_buffers` is a GUC. When zero (the default,
"auto-tune"), the size scales with `shared_buffers`:
2 MB of pg_subtrans buffers per 1 GB of `shared_buffers`, capped
at 8 MB.

Why auto-tune: workloads with many subxacts and frequent overflow
benefit from more buffers (less SLRU I/O); workloads with rare
subxacts don't need much. Manual tuning is for the rare cases where
the auto-tune is wrong.

`SUBTRANSShmemInit` [subtrans.c:263-285] allocates the buffer pool,
initializes the `SlruDesc`, and registers shared-memory hooks.
`SUBTRANSShmemRequest` [subtrans.c:223-260] computes how much shmem
to reserve at startup.

## `BootStrapSUBTRANS` and `StartupSUBTRANS`

`BootStrapSUBTRANS` [subtrans.c:288-300] is called from `initdb` and
zeros the first page so the cluster has a clean slate.

`StartupSUBTRANS(oldestActiveXID)` [subtrans.c:302-346] is the
critical "no crash survival" enforcer:

```c
void
StartupSUBTRANS(TransactionId oldestActiveXID)
{
    /* Open the first page (at oldestActiveXID) on disk;
     * if it doesn't exist, zero it. */
    /* Loop through all subsequent pages up to the latest XID;
     * zero each one. */
}
```

After startup, pg_subtrans **for any XID ≥ oldestActiveXID** is
guaranteed to be zero. As transactions resume after recovery, they
populate fresh entries via `SubTransSetParent` as needed. Older
entries (pages < oldestActiveXID's page) are left alone but will
get truncated by `TruncateSUBTRANS` at the next checkpoint.

The "zero out unused pages" trick is what enables the no-WAL
design: we don't need to recover the prior state because we'll
recompute it.

## `CheckPointSUBTRANS` and `TruncateSUBTRANS`

`CheckPointSUBTRANS` [subtrans.c:348-370] flushes dirty SLRU pages
to disk during checkpoint. There's no WAL, but the on-disk pages
still need to be consistent at recovery start (specifically, they
need to be readable — though their contents may be wiped by
`StartupSUBTRANS`).

`TruncateSUBTRANS(oldestXact)` [subtrans.c:404-426] removes
pg_subtrans pages older than `oldestXact`. Called from
`vac_truncate_clog` after VACUUM advances the global xmin horizon.
The truncation reclaims disk space proportional to how far the xmin
horizon has advanced.

`SubTransPagePrecedes` [subtrans.c:428-446] is the
modular-comparison helper that handles XID wrap. Two pages compare
"this is older than that" with the same wrap semantics as XID
comparison itself.

## `ExtendSUBTRANS` — lazy page allocation

[subtrans.c:372-402]. Called from `GetNewTransactionId` whenever
the new XID crosses a page boundary:

```c
void
ExtendSUBTRANS(TransactionId newestXact)
{
    if (newestXact % SUBTRANS_XACTS_PER_PAGE != 0 &&
        !TransactionIdEquals(newestXact, FirstNormalTransactionId))
        return;  /* nothing to do */

    pageno = TransactionIdToPage(newestXact);
    lock = SimpleLruGetBankLock(SubTransCtl, pageno);
    LWLockAcquire(lock, LW_EXCLUSIVE);
    SimpleLruZeroPage(SubTransCtl, pageno);
    LWLockRelease(lock);
}
```

So pg_subtrans grows one page at a time as XIDs are allocated, not
in big chunks. The zeroing happens on the page-crossing boundary,
which means the page is ready to receive its first
`SubTransSetParent` for the new XID range.

## Performance characteristics

- **Cache hits** (page in the SLRU buffer pool) — single bank-lock
  acquire + memory access. Nanoseconds.
- **Cache misses** (page on disk) — bank-lock + disk read. With
  default `subtransaction_buffers` (auto-tuned), miss rates are low
  for typical workloads but can climb in workloads with many
  long-running transactions and deep subxact nesting.
- **`SubTransGetTopmostTransaction`** is O(depth-of-subxact-chain)
  in pg_subtrans reads. For a 5-level savepoint stack, that's 5
  bank-lock acquires + 5 page reads (or hits). Bounded but not
  trivial.

`pg_stat_slru` shows hit/miss/flush counts per SLRU; the row named
`'SubTrans'` is this one. Workloads under contention show up there
as elevated flush counts and elevated misses.

## Invariants

- **No WAL, no crash survival.** All pg_subtrans data is volatile.
  `StartupSUBTRANS` zeros every page that could be referenced by
  the post-crash state.
- **Child XID > parent XID.** Enforced at write
  (`SubTransSetParent`'s assert) and relied on at read
  (`SubTransGetTopmostTransaction`'s corruption check).
- **The chain root** is either `InvalidTransactionId` (true top
  of a never-aborted transaction tree) or an XID precedes
  `TransactionXmin` (older than the global horizon).
- **One `SubTransSetParent` per (xid, parent) pair.** Repeated
  calls with the same arguments are idempotent. Calls with a
  different parent for an already-set xid are corruption.
- **Bank-level locking** for write and read. Multiple banks scale
  out across multiple subxact-using backends.
- **Pages truncated at `oldestActiveXID` on startup,
  `oldestXact` on checkpoint truncate.** Disk usage is bounded by
  how far the global xmin horizon lags behind the latest XID.

## Useful greps

```bash
# Find every caller of SubTransGetTopmostTransaction (the hot path):
grep -RnE 'SubTransGetTopmostTransaction' source/src/backend

# Where does subxact write happen?
grep -RnE 'SubTransSetParent' source/src/backend

# Inspect pg_subtrans state at runtime:
#   psql:  SELECT * FROM pg_stat_slru WHERE name = 'SubTrans';
#   ls -la $PGDATA/pg_subtrans/

# Find the autotune behavior:
grep -nE 'SimpleLruAutotuneBuffers' source/src/backend/access/transam/subtrans.c

# Subtransaction-overflow isolation test:
ls source/src/test/isolation/specs/subxid-overflow.spec
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 1 | banner with the "no XLOG interactions" + "no crash survival" design statement |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 54 | page math (SUBTRANS_XACTS_PER_PAGE, TransactionIdToPage, TransactionIdToEntry) |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 88 | SubTransSetParent |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 125 | SubTransGetParent |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 157 | SubTransGetTopmostTransaction |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 204 | shared memory request + init |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 288 | BootStrapSUBTRANS, StartupSUBTRANS, CheckPointSUBTRANS |
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | 372 | ExtendSUBTRANS, TruncateSUBTRANS, SubTransPagePrecedes |
| [`src/include/access/subtrans.h`](../files/src/include/access/subtrans.h.md) | 1 | public API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- [[subxact-xidcache-and-pgproc]] — the in-PGPROC cache; pg_subtrans
  is the fallback when it overflows.
- [[subxact-visibility-and-overflow]] — how
  `SubTransGetTopmostTransaction` plugs into
  `TransactionIdIsInProgress` and `XidInMVCCSnapshot`.
- [[slru-page-replacement]] — the SLRU framework; bank locks,
  page eviction, autotune.
- [[clog-slru]] — the sibling SLRU that *does* survive crashes
  (with WAL). Useful for contrast — pg_subtrans's no-WAL design is
  unique.
- [[multixact-slru]] — another SLRU, this one with two segments
  (offsets + members) and WAL.
- [[xmin-horizon-management]] — `TransactionXmin` advancement
  drives `TruncateSUBTRANS`.
- [[snapshot-static-and-current]] — `GetSnapshotData()` reads
  enough state from PGPROC + ProcGlobal that the SubTrans fallback
  is rare in non-overflow workloads.
- [[subtransaction-stack]] — per-backend xact.c stack that drives
  subxact lifecycle and calls `SubTransSetParent`.
