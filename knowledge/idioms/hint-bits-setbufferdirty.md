# Hint bits — lazy commit-status caches with WAL-flush + lock-mode discipline

Hint bits (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_COMMITTED`, `HEAP_XMIN_INVALID`,
`HEAP_XMAX_INVALID`) are **cached visibility verdicts** written into the
heap tuple header (`t_infomask`) by visibility code after consulting CLOG
or the snapshot's in-progress set. They are not WAL logged in the normal
sense — losing one just makes the next visitor redo the check.

But "not WAL logged" hides three subtleties that the implementation has
to keep straight:

1. **Setting a "committed" bit before that xact's commit-WAL is flushed**
   would let crash recovery resurrect a tuple whose committer is gone —
   data loss. `SetHintBitsExt` guards this with `XLogNeedsFlush`.
2. **Writing into a page mid-IO** would corrupt the page checksum (or the
   filesystem's, with btrfs). Hint-bit setting requires at least a
   share-exclusive content lock; `BufferBeginSetHintBits` acquires it (or
   upgrades from a shared lock) and serializes hint-setters per page.
3. **Marking a page dirty without WAL** is normally forbidden — but
   `MarkBufferDirtyHint` is the explicit exception. With page checksums
   enabled (`wal_log_hints`/`XLogHintBitIsNeeded`), the first hint-write
   per checkpoint cycle WAL-logs an `XLOG_FPI_FOR_HINT` full-page image so
   torn-write recovery sees a consistent page.

This doc walks the three layers — `SetHintBits*` in `heapam_visibility.c`,
the `BufferBeginSetHintBits` / `BufferFinishSetHintBits` /
`BufferSetHintBits16` / `MarkBufferDirtyHint` set in `bufmgr.c`, and the
WAL-flush precondition that ties them to commit durability.

Companion docs:
- [[heap-tuple-visibility-mvcc]] — the caller side; explains *which* bits get set when.
- [[wal-page-write-flush]] — why a committer's WAL flush matters for hint-bit safety.
- `knowledge/subsystems/storage-buffer.md` — the share-vs-share-exclusive content-lock model.

## Anchors

- `source/src/backend/access/heap/heapam_visibility.c:6-36` — module banner on hint-bit safety + the race rule.
- `source/src/backend/access/heap/heapam_visibility.c:82-99` — `SetHintBitsState` enum (`SHB_INITIAL` / `SHB_DISABLED` / `SHB_ENABLED`).
- `source/src/backend/access/heap/heapam_visibility.c:101-192` — `SetHintBitsExt` (the WAL-flush check + batched/non-batched dispatch).
- `source/src/backend/access/heap/heapam_visibility.c:198-203` — `SetHintBits` (single-tuple wrapper).
- `source/src/include/access/htup_details.h:204-210` — hint-bit definitions.
- `source/src/backend/storage/buffer/bufmgr.c:5697-5812` — `MarkSharedBufferDirtyHint` (the WAL-log-FPI-for-hint logic).
- `source/src/backend/storage/buffer/bufmgr.c:5829-5848` — `MarkBufferDirtyHint` (top-level entry).
- `source/src/backend/storage/buffer/bufmgr.c:6952-7019` — `SharedBufferBeginSetHintBits` (lock-mode upgrade dance).
- `source/src/backend/storage/buffer/bufmgr.c:7050-7068` — `BufferBeginSetHintBits` (acquire right to set hints).
- `source/src/backend/storage/buffer/bufmgr.c:7078-7087` — `BufferFinishSetHintBits`.
- `source/src/backend/storage/buffer/bufmgr.c:7101-7140` — `BufferSetHintBits16` (single-write fast path).

## The four hint bits

```c
/* htup_details.h:204-210 */
#define HEAP_XMIN_COMMITTED  0x0100  /* t_xmin committed */
#define HEAP_XMIN_INVALID    0x0200  /* t_xmin aborted/crashed */
#define HEAP_XMIN_FROZEN     0x0300  /* both = frozen (see [[heap-tuple-freeze]]) */
#define HEAP_XMAX_COMMITTED  0x0400  /* t_xmax committed */
#define HEAP_XMAX_INVALID    0x0800  /* t_xmax aborted/crashed/locker-only */
```

When set, a hint bit means "the visibility code has already consulted
CLOG/PGPROC for this XID and resolved its fate." A future visitor reads
the bit and skips the lookup.

Hint bits are **set in the buffer page memory directly** — there is no
WAL record carrying "now-committed status for xid 12345". The page may
or may not be marked dirty (see `MarkBufferDirtyHint` below). If the
backend crashes after setting a hint without ever flushing the page,
the bit is lost; the next visitor redoes the work. This is fine — the
underlying truth (CLOG entry) is durable.

The danger is the *opposite* mistake: setting a "committed" hint and
flushing the page **before** the committer's WAL record is on disk. A
crash between heap-page flush and WAL flush could leave the heap with
`HEAP_XMIN_COMMITTED` set on a tuple whose committer is gone — visibility
would say "yes, visible to anyone" but the row should have aborted.

## The WAL-flush precondition — `SetHintBitsExt`

```c
/* heapam_visibility.c:142-192 */
static inline void
SetHintBitsExt(HeapTupleHeader tuple, Buffer buffer,
               uint16 infomask, TransactionId xid, SetHintBitsState *state)
{
    if (state && *state == SHB_DISABLED) return;

    if (TransactionIdIsValid(xid)) {
        if (BufferIsPermanent(buffer)) {
            XLogRecPtr commitLSN = TransactionIdGetCommitLSN(xid);
            if (XLogNeedsFlush(commitLSN) &&
                BufferGetLSNAtomic(buffer) < commitLSN)
            {
                /* not flushed and no LSN interlock, so don't set hint */
                return;
            }
        }
    }
    ...
}
```

Three gates control whether the hint actually gets written:

1. **State already disabled?** (batched mode only) — skip.
2. **Is `xid` valid and the buffer permanent?**
   - Temp tables (`!BufferIsPermanent`) and unlogged tables that will be
     obliterated on crash anyway: skip the check, set the hint freely.
   - Aborted hints (`xid == InvalidTransactionId` is the sentinel from
     callers setting `HEAP_X*_INVALID`): also safe to set unconditionally
     — there is no commit-record durability story for an abort.
   - Real "committed" hint: must consult `TransactionIdGetCommitLSN`.
3. **Is the commit-WAL flushed (or the page already has a newer LSN)?**
   - `XLogNeedsFlush(commitLSN)` returns true if `commitLSN >
     XLogCtl->LogwrtResult.Flush`, i.e. the commit-record is still in
     WAL buffers or unflushed segments.
   - `BufferGetLSNAtomic(buffer) >= commitLSN`: even if WAL isn't
     directly flushed, the page's own LSN may *transitively* guarantee
     it — a normal page-write rule ensures any WAL with LSN ≤ page-LSN
     is flushed first, so a page-write following this hint set is safe.
   - If both conditions fail to provide a guarantee → skip the hint.
     The next visitor will retry, hopefully after the WAL flush
     happens naturally.

This is the corner that prevents data loss. Get this wrong and a crash
between hint-flush and WAL-flush leaves a "committed" tuple whose
commit record is gone. [from-comment] (`heapam_visibility.c:115-122`).

`TransactionIdGetCommitLSN` consults the per-xid LSN cache that
`[[clog-slru]]`'s `group_lsn[]` exposes — see that doc for how CLOG
tracks the highest commit LSN per group of 32 XIDs per page.

## Aborted hints are unconditional

```c
SetHintBitsExt(tuple, buffer, HEAP_XMIN_INVALID, InvalidTransactionId, state);
```

When visibility code determines that an xact aborted (via process of
elimination — not in-progress and not committed), it sets the hint with
`xid == InvalidTransactionId`. The `if (TransactionIdIsValid(xid))` gate
above means the WAL-flush check is **skipped**: an aborted-hint can
always be set safely because there is no commit record whose loss
would matter. [from-comment] (`heapam_visibility.c:124-125`).

`HEAP_MOVED_OFF` / `HEAP_MOVED_IN` (pre-9.0 VACUUM FULL artifacts) are
also always-safe — the banner explains: "pre-9.0 VACUUM FULL always
used synchronous commits and didn't move tuples that weren't previously
hinted." Modern VACUUM FULL doesn't move tuples; the bits are kept for
binary-upgrade compatibility. [from-comment]
(`heapam_visibility.c:127-133`).

## Batched mode — `SetHintBitsState`

Setting hint bits requires a buffer lock-mode upgrade (shared →
share-exclusive). That upgrade is cheap per call but adds up across
hundreds of tuples on the same page. Callers that scan a buffer
top-to-bottom (`HeapTupleSatisfiesMVCCBatch`) amortize this:

```c
typedef enum SetHintBitsState {
    SHB_INITIAL,   /* not yet checked */
    SHB_DISABLED,  /* upgrade failed; don't try again */
    SHB_ENABLED,   /* upgrade succeeded; hint-setting allowed */
} SetHintBitsState;
```

Flow:

1. First call: `BufferBeginSetHintBits(buffer)`. If returns true →
   `state = SHB_ENABLED`. If false (someone else holds an exclusive or
   the upgrade race lost) → `state = SHB_DISABLED`, never try again
   this batch.
2. Subsequent calls: write directly to `tuple->t_infomask |= infomask`
   (no per-call lock upgrade) when `SHB_ENABLED`; skip when
   `SHB_DISABLED`.
3. At end: caller does **one** `BufferFinishSetHintBits(buffer, true,
   true)` to dirty the buffer.

[verified-by-code] (`heapam_visibility.c:82-99`, `heapam_visibility.c:146-192`).

In single-tuple mode (`state == NULL`), `SetHintBitsExt` falls through to
`BufferSetHintBits16` which combines acquire+write+release in one call —
cheaper than begin/finish when only one bit is being set per buffer-lock
acquisition. The comment in `bufmgr.c:7097-7099` notes this is "a bit
faster" for the single-shot case but "slower than the former when setting
hint bits multiple times in the same buffer." [verified-by-code]
(`heapam_visibility.c:174-179`).

## The lock-mode upgrade — `SharedBufferBeginSetHintBits`

Hint-setting requires at least `BUFFER_LOCK_SHARE_EXCLUSIVE`. The dance:

```c
/* bufmgr.c:6960-7019 */
mode = ref->data.lockmode;            /* what we currently hold */

if (mode == BUFFER_LOCK_EXCLUSIVE || mode == BUFFER_LOCK_SHARE_EXCLUSIVE)
    return true;                      /* already sufficient */

Assert(mode == BUFFER_LOCK_SHARE);

old_state = pg_atomic_read_u64(&buf_hdr->state);
while (true) {
    if (old_state & (BM_LOCK_VAL_EXCLUSIVE | BM_LOCK_VAL_SHARE_EXCLUSIVE))
        return false;                 /* somebody else has E or SE */

    desired = old_state - BM_LOCK_VAL_SHARED + BM_LOCK_VAL_SHARE_EXCLUSIVE;
    if (CAS(&buf_hdr->state, &old_state, desired)) {
        ref->data.lockmode = BUFFER_LOCK_SHARE_EXCLUSIVE;
        return true;
    }
}
```

The CAS-loop converts our existing shared lock into a share-exclusive
lock atomically. If another backend holds (or is acquiring) exclusive or
share-exclusive, the upgrade fails and we return false — hint-setting is
deferred. [verified-by-code] (`bufmgr.c:6986-7018`).

Why share-exclusive specifically:

> Requiring a share-exclusive lock to set hint bits prevents setting
> hint bits on buffers that are currently being written out, which could
> corrupt the checksum on the page. Flushing buffers also requires a
> share-exclusive lock.

[from-comment] (`bufmgr.c:7035-7038`).

So the lock mode is the synchronization with the buffer-flush path —
flushers also take share-exclusive, so as long as a hint-setter holds
that mode, no I/O is in flight. Once we hold it, we may set arbitrarily
many hint bits without re-checking, until the lock is released.
[from-comment] (`bufmgr.c:7030-7032`).

The choice to allow only **one backend at a time** to set hints is
explicit: "given that the share-exclusive lock for setting hint bits is
only held for a short time, that backends often would just set the same
hint bits and that the cost of occasionally not setting hint bits in
hotly accessed pages is fairly low, this seems like an acceptable
tradeoff." [from-comment] (`bufmgr.c:7039-7048`).

## Marking dirty without WAL — `MarkBufferDirtyHint`

`MarkBufferDirtyHint` (`bufmgr.c:5829`) is the "dirty for non-WAL
changes" entry, contrasted with the normal `MarkBufferDirty`:

> This is essentially the same as MarkBufferDirty, except:
> 1. The caller does not write WAL; so if checksums are enabled, we may
>    need to write an XLOG_FPI_FOR_HINT WAL record to protect against
>    torn pages.
> 2. The caller might have only a share-exclusive-lock instead of an
>    exclusive-lock.
> 3. This function does not guarantee that the buffer is always marked
>    dirty (it e.g. can't always on a hot standby), so it cannot be used
>    for important changes.

[from-comment] (`bufmgr.c:5815-5827`).

The interior calls `MarkSharedBufferDirtyHint` (`bufmgr.c:5704-5812`).
The key conditional:

```c
if (XLogHintBitIsNeeded() && (lockstate & BM_PERMANENT)) {
    if (RecoveryInProgress() ||
        RelFileLocatorSkippingWAL(BufTagGetRelFileLocator(&bufHdr->tag)))
        return;                       /* can't WAL → don't dirty */
    wal_log = true;
}
```

- `XLogHintBitIsNeeded()` returns true if (page checksums are enabled
  OR `wal_log_hints = on`) AND we are past startup. With checksums
  enabled, a torn write to a hint-dirtied page would invalidate the
  checksum on crash recovery.
- `BM_PERMANENT` means the buffer belongs to a logged relation — temp
  and unlogged tables don't need the FPI.
- `RecoveryInProgress() || RelFileLocatorSkippingWAL(...)` are the
  cases where we can't write WAL right now: standby, or a relation
  being built via bulk-load that's skipping WAL. In those cases the
  hint is set but the page is **not** marked dirty — the bit lives in
  memory only and is lost on eviction. [from-comment]
  (`bufmgr.c:5740-5752`).

If we are going to WAL-log:

```c
buf_state = LockBufHdr(bufHdr);
UnlockBufHdrExt(bufHdr, buf_state, BM_DIRTY, 0, 0);   /* mark dirty */

if (wal_log)
    lsn = XLogSaveBufferForHint(buffer, buffer_std);  /* XLOG_FPI_FOR_HINT */

if (XLogRecPtrIsValid(lsn)) {
    LockBufHdr(bufHdr);
    PageSetLSN(page, lsn);              /* under header lock for tear-free read */
    UnlockBufHdr(bufHdr);
}
```

**Mark dirty before WAL-log, not after**, even though the normal rule is
the reverse:

> We must mark the page dirty before we emit the WAL record, as per
> the usual rules, to ensure that BufferSync()/SyncOneBuffer() try to
> flush the buffer, even if we haven't inserted the WAL record yet.
> As we hold at least a share-exclusive lock, checkpoints will wait
> for this backend to be done with the buffer before continuing. If we
> did it the other way round, a checkpoint could start between writing
> the WAL record and marking the buffer dirty.

[from-comment] (`bufmgr.c:5757-5765`).

The argument: a checkpoint that sees the buffer clean but the WAL
record present would skip the page on the next checkpoint cycle, then
fail to replay-from-WAL the hint set if the page is later evicted
without write — losing the FPI's protection.

The `PageSetLSN(page, lsn)` under the buffer-header lock is the
**tear-free LSN write** discussion in
`[[buffer-content-lock-modes]]` (if it exists) — readers with only a
share lock may still read the page LSN atomically because the lock-byte
serves as a tear-free synchronization point.

## `XLOG_FPI_FOR_HINT` — the full-page image for torn-write protection

When `wal_log_hints` is on (the default with checksums enabled), the
**first hint write per checkpoint cycle** to each page WAL-logs a full
image:

```c
lsn = XLogSaveBufferForHint(buffer, buffer_std);
```

This records the entire 8 KiB page contents in WAL with the
`XLOG_FPI_FOR_HINT` record. The point: if a hint-set causes a partial
write to disk (torn write) before the next checkpoint, replay will
detect the checksum mismatch on the partially-written page and restore
the FPI from WAL.

The "first per checkpoint" deduplication is implicit — the conditional is
`if (unlikely(!(lockstate & BM_DIRTY)))` — once a page is dirty, no
further FPI-for-hint is needed in this checkpoint cycle.
[from-comment] (`bufmgr.c:5778-5784`).

## Invariants and races

1. **Hint bits are not WAL-logged as content**, only the FPI (if needed)
   is. A lost hint is fine; an incorrect hint is data loss.
2. **Setting a committed-hint requires either**: the committer's WAL
   record is already flushed (`XLogNeedsFlush(commitLSN) == false`), OR
   the page's own LSN is ≥ commitLSN (transitive flush guarantee), OR
   the buffer is non-permanent (temp/unlogged). [from-comment]
   (`heapam_visibility.c:115-122`).
3. **Aborted-hints are always safe** (`xid == InvalidTransactionId`)
   because there is no commit record to lose. [from-comment]
   (`heapam_visibility.c:124-125`).
4. **Hint-setting requires share-exclusive content lock** (shared is not
   enough). `BufferBeginSetHintBits` upgrades from shared if possible;
   if the upgrade race fails, hint-setting is deferred to a future
   visitor. [from-comment] (`bufmgr.c:7035-7038`).
5. **Only one backend at a time** can set hints on a given page (the
   share-exclusive lock is mutually exclusive with itself).
   [from-comment] (`bufmgr.c:7039-7048`).
6. **`MarkBufferDirtyHint` does not guarantee the dirty mark**. On
   recovery / WAL-skipping / hot-standby, it returns silently without
   dirtying. The bit is still set in memory but won't survive eviction.
   [from-comment] (`bufmgr.c:5825-5827`, `bufmgr.c:5743-5752`).
7. **Mark dirty BEFORE WAL log** (inverse of the normal rule) — see the
   checkpoint-race argument above. [from-comment] (`bufmgr.c:5757-5765`).

## Useful greps

```bash
# Every hint-bit setter site:
grep -n "SetHintBitsExt\|SetHintBits\b" \
     source/src/backend/access/heap/heapam_visibility.c

# The buffer-mgr hint-bit API:
grep -nE "BufferBeginSetHintBits|BufferFinishSetHintBits|BufferSetHintBits16|MarkBufferDirtyHint" \
     source/src/backend/storage/buffer/bufmgr.c

# Per-xid LSN consultation:
grep -rn "TransactionIdGetCommitLSN\|XLogNeedsFlush\b" \
     source/src/backend/

# Torn-write FPI for hints:
grep -n "XLOG_FPI_FOR_HINT\|XLogSaveBufferForHint" \
     source/src/backend/access/transam/xloginsert.c

# Where wal_log_hints is consulted:
grep -rn "XLogHintBitIsNeeded\|wal_log_hints" source/src/
```

## Cross-references

- [[heap-tuple-visibility-mvcc]] — the caller; when each hint gets set.
- [[heap-tuple-freeze]] — `HEAP_XMIN_FROZEN` is set by freeze, not by visibility.
- [[clog-slru]] — `TransactionIdGetCommitLSN` consults CLOG's `group_lsn[]`.
- [[wal-page-write-flush]] — `XLogNeedsFlush` and the LSN-flush model.
- `knowledge/subsystems/storage-buffer.md` — buffer content-lock modes (SHARE / SHARE_EXCLUSIVE / EXCLUSIVE).
- `knowledge/subsystems/access-heap.md` §"Hint bits" — subsystem-level overview.
