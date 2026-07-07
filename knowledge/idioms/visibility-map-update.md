# Visibility map update — VM bits + WAL + heap interplay

The visibility map (`pg_VM` per relation) is one bit per page (two
bits since PG 9.6: `ALL_VISIBLE` + `ALL_FROZEN`) telling whether
every tuple on the heap page is visible to all transactions / is
frozen. Vacuum uses it to skip pages cheaply; index-only scans use
it to skip heap fetches.

The update path looks small but has **strict ordering rules with WAL
+ buffer locking** — getting them wrong corrupts hot standby
visibility decisions. This idiom doc covers the canonical sequence.

Anchors:
- `source/src/backend/access/heap/visibilitymap.c` — implementation
- `source/src/include/access/visibilitymap.h` — public API
- `source/src/backend/access/heap/README.HOT` — VM design discussion
- `.claude/skills/locking/SKILL.md` — buffer-pin + WAL-before-data rules

## What the VM stores

Per page in the heap, two bits in `pg_VM`:

- `VISIBILITYMAP_ALL_VISIBLE` (0x01) — every tuple is visible to
  every transaction (older than `OldestXmin`).
- `VISIBILITYMAP_ALL_FROZEN` (0x02) — every tuple is frozen
  (`xmin/xmax` replaced with `FrozenTransactionId`). Implies
  `ALL_VISIBLE`.

A VM page covers `HEAPBLOCKS_PER_PAGE = 4096` heap blocks (8K page
holding 8192 bits at 2 bits per block). VM pages are read into shared
buffers like any other relation page.

## The four operations

- `visibilitymap_get_status(rel, heapBlk, &vmbuf)` — read, returns
  the 2-bit value (0..3). Pins `vmbuf`. Cheap.
- `visibilitymap_clear(rel, heapBlk, vmbuf, flags)` — clear bits.
  Called from any heap insert / update / delete that makes a
  previously-all-visible page non-all-visible.
- `visibilitymap_pin(rel, heapBlk, &vmbuf)` — pin the VM buffer
  *without* taking its lock. Used by the caller before the set
  operation, so that the set itself doesn't need to do I/O while
  holding the heap-page lock.
- `visibilitymap_set(rel, heapBlk, heapBuf, recptr, vmbuf, cutoff_xid,
   flags)` — set bits. The recptr / cutoff_xid are for WAL.

## The set ordering rule (this is the load-bearing one)

When setting an `ALL_VISIBLE` bit, the **WAL must be flushed past
the heap-page LSN before the VM page is written to disk**. Otherwise
on crash recovery, the standby could see an `ALL_VISIBLE` bit for a
page whose visibility-marking transaction hasn't been replayed yet —
giving wrong answers to index-only scans.

The canonical sequence (heap vacuum / heap insert path):

```c
/* 1. Pin the VM buffer in advance (no lock yet). */
visibilitymap_pin(rel, heapBlk, &vmbuf);

/* 2. Lock the heap buffer exclusive. */
LockBuffer(heapBuf, BUFFER_LOCK_EXCLUSIVE);

/* 3. Inspect the heap page; decide whether to mark all-visible. */
if (all_tuples_visible(heapBuf))
{
    /* 4. Start a critical section. WAL the change. */
    XLogBeginInsert();
    XLogRegisterBuffer(0, heapBuf, REGBUF_STANDARD);
    XLogRegisterBuffer(1, vmbuf, 0);
    recptr = XLogInsert(RM_HEAP2_ID, XLOG_HEAP2_VISIBLE);

    /* 5. Set the VM bit and the page-LSN on both buffers. */
    visibilitymap_set(rel, heapBlk, heapBuf, recptr, vmbuf,
                      cutoff_xid, VISIBILITYMAP_ALL_VISIBLE);

    /* 6. End critical section, release locks. */
}
LockBuffer(heapBuf, BUFFER_LOCK_UNLOCK);
```

Key points enforced by `visibilitymap_set`:

- The heap page MUST be marked with the `PD_ALL_VISIBLE` page flag.
  The VM bit and the heap page flag are kept in sync; either flag
  set without the other is a corruption marker that `amcheck` looks
  for.
- The VM buffer's LSN is bumped to `recptr` (via
  `PageSetLSN(vmpage, recptr)`), so the buffer-manager won't flush
  the VM page to disk before the WAL record reaches durable storage.

## The clear path

The inverse — clearing the VM bit when inserting / updating into a
previously `ALL_VISIBLE` page — happens **without** WAL of its own.
The heap page's update / insert WAL record carries enough info that
recovery clears the VM bit in `heap_xlog_*_redo`. Live code path:

1. The mutating xact pins `vmbuf` (via `visibilitymap_pin`) before
   it locks the heap buffer.
2. The heap-buffer-content lock is acquired exclusive.
3. The heap mutation is logged via its normal WAL record (with
   `XLOG_HEAP_*_VM` info-bit set if the page was previously all-
   visible).
4. `visibilitymap_clear` is called inside the critical section.
5. On replay, the heap-record redo function calls
   `visibilitymap_clear` to mirror the in-memory effect.

The clear has **no** crash-recovery hazard because the WAL record
carrying the heap mutation also carries the VM-clear effect. No
separate VM WAL record needed.

## What is NOT WAL-logged separately

The VM has **no `xl_visible` WAL record family of its own** for
clears. Only the SET path emits its own WAL
(`XLOG_HEAP2_VISIBLE`). Clears piggyback on the heap mutation's
WAL.

## What's safe vs unsafe to call

Safe to call without VM-buffer-lock:

- `visibilitymap_get_status` (it reads; locks the buffer briefly
  itself).
- `visibilitymap_pin`.

Requires the VM buffer to be content-locked exclusive:

- `visibilitymap_set` (it does the locking internally; caller passes
  a pinned buffer).
- `visibilitymap_clear` (same).

Caller pre-pinning + the function internally locking is the
discipline. Don't try to hold the VM buffer lock yourself across
heap operations; you'll create lock-order conflicts with cursor /
backward-scan paths.

## Invariants

- **[INV-1]** PD_ALL_VISIBLE page flag and the VM `ALL_VISIBLE`
  bit are kept in sync. `amcheck` flags either alone.
- **[INV-2]** ALL_FROZEN implies ALL_VISIBLE. Setting ALL_FROZEN
  without ALL_VISIBLE is a bug.
- **[INV-3]** A SET emits WAL of its own
  (`XLOG_HEAP2_VISIBLE`). A CLEAR does NOT — it piggybacks on the
  heap mutation's WAL.
- **[INV-4]** Pin the VM buffer BEFORE locking the heap buffer.
  Pinning under heap lock creates an LWLock-vs-buffer-pin
  inversion that can stall.
- **[INV-5]** `visibilitymap_set` bumps the VM page LSN to the WAL
  record's LSN — the WAL-before-data invariant is honored by
  the bufmgr automatically.
- **[INV-6]** Hot standby reads VM bits to answer index-only scans
  but trusts the standby's *own* OldestXmin (which lags the
  primary's). Setting bits on the primary that the standby's
  OldestXmin hasn't caught up to is safe because the standby waits
  for WAL replay before consulting the page.

## When to update this doc

- Any new VM bit added (was 1 bit pre-9.6, became 2 bits at 9.6).
  Bit assignment + on-disk format affects pg_upgrade.
- Any change to the SET / CLEAR sequence — extremely rare.
- Any new WAL record family in `RM_HEAP2_ID` related to VM.

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/README.HOT`](../files/src/backend/access/heap/README.md) | — | VM + HOT update design discussion |
| [`src/backend/access/heap/visibilitymap.c`](../files/src/backend/access/heap/visibilitymap.c.md) | — | implementation |
| [`src/include/access/visibilitymap.h`](../files/src/include/access/visibilitymap.h.md) | — | public API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `.claude/skills/locking/SKILL.md` — buffer-pin + content-lock ordering; WAL-before-data invariant.
- `.claude/skills/wal-and-xlog/SKILL.md` — `XLogRegisterBuffer`, `RM_HEAP2_ID`, redo function rules.
- `.claude/skills/access-method-apis/SKILL.md` — index-only scan consumers of the VM.
- `knowledge/subsystems/access-heap.md` — the heap-page side of the same operation.
- `knowledge/subsystems/storage-buffer.md` — VM pages live in shared buffers like any other.
- `source/src/backend/access/heap/README.HOT` — VM + HOT update design discussion.
- `source/contrib/pg_visibility/` — SQL-level tools for inspecting VM state.
