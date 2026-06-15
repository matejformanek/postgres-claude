# CLOG (pg_xact) — 2-bit per-XID commit status with group-commit and async-LSN tracking

CLOG (`pg_xact/`, also known as the commit log) stores **2 bits per
TransactionId** to record whether the XID is `IN_PROGRESS`, `COMMITTED`,
`ABORTED`, or `SUB_COMMITTED`. At 32 768 XIDs per 8 KiB page, an entire
`SLRU_PAGES_PER_SEGMENT = 32`-page segment file (256 KiB) covers
~1 048 576 XIDs. The commit log for a 4-billion-XID epoch fits in ~1 GiB.

This doc covers what CLOG does on top of `[[slru-page-replacement]]`:
the 2-bit packing, the **group-commit** that funnels concurrent setters
through one bank-lock acquisition, the **`group_lsn[]` async-commit barrier**,
and how `TransactionIdSetTreeStatus` handles a parent + subxacts that
straddle multiple pages.

Companion docs:
- [[slru-page-replacement]] — the underlying buffer cache; CLOG is one of its tenants.
- [[multixact-slru]] — a sibling SLRU client with a very different access pattern (dual SLRU).
- [[subtransaction-stack]] — the per-PGPROC cached-subxids array that gates the group optimization.

## Anchors

- `source/src/include/access/clog.h:25-30` — XidStatus enum (`IN_PROGRESS=0`, `COMMITTED=1`, `ABORTED=2`, `SUB_COMMITTED=3`).
- `source/src/backend/access/transam/clog.c:1-25` — module banner explaining async-commit LSN handling.
- `source/src/backend/access/transam/clog.c:63-67` — `CLOG_BITS_PER_XACT=2`, `CLOG_XACTS_PER_BYTE=4`, `CLOG_XACTS_PER_PAGE = BLCKSZ × 4` (32 768).
- `source/src/backend/access/transam/clog.c:93-98` — `CLOG_XACTS_PER_LSN_GROUP=32`, `GetLSNIndex` mapping.
- `source/src/backend/access/transam/clog.c:191-257` — `TransactionIdSetTreeStatus` (top-level entry).
- `source/src/backend/access/transam/clog.c:302-365` — `TransactionIdSetPageStatus` (group-update dispatcher).
- `source/src/backend/access/transam/clog.c:449-662` — `TransactionGroupUpdateXidStatus` (CAS-queued follower/leader dance).
- `source/src/backend/access/transam/clog.c:670-726` — `TransactionIdSetStatusBit` (the bit-write + group_lsn update).
- `source/src/backend/access/transam/clog.c:743-767` — `TransactionIdGetStatus` (status + LSN read).
- `source/src/backend/access/transam/clog.c:985-1019` — `TruncateCLOG` (drops segments after vacuum advances `oldestXact`).
- `source/src/backend/access/transam/clog.c:812-826` — `SimpleLruRequest` call: name=`transaction`, dir=`pg_xact`, `nlsns=CLOG_LSNS_PER_PAGE`.

## The 2-bit encoding

```
XidStatus values fit in 2 bits:
  00  IN_PROGRESS        (initial zero — required, since SimpleLruZeroPage
                           memsets new pages to zero)
  01  COMMITTED
  10  ABORTED
  11  SUB_COMMITTED      (intermediate: subxact done, top-level still open)
```

Indexing a transaction inside a page is three arithmetic steps:

```c
/* clog.c:89-91 */
#define TransactionIdToPgIndex(xid) ((xid) % (TransactionId) CLOG_XACTS_PER_PAGE)
#define TransactionIdToByte(xid)    (TransactionIdToPgIndex(xid) / 4)
#define TransactionIdToBIndex(xid)  ((xid) % 4)            /* 0..3 */

byteno = TransactionIdToByte(xid);                          /* byte offset */
bshift = TransactionIdToBIndex(xid) * CLOG_BITS_PER_XACT;   /* 0, 2, 4, or 6 */
byteptr = page_buffer[slotno] + byteno;
status  = (*byteptr >> bshift) & 0x03;
```

A status write is a read-modify-write on that byte:

```c
/* clog.c:706-709 */
byteval = *byteptr;
byteval &= ~(0x03 << bshift);   /* clear those 2 bits */
byteval |= (status << bshift);  /* set them */
*byteptr = byteval;
```

The byte-level race is solved by holding the SLRU bank lock exclusive across
the read-modify-write — see assertion at `clog.c:679`. [verified-by-code]
(`clog.c:670-709`).

## SUB_COMMITTED — the intermediate state

Subtransactions complicate single-page atomicity: a transaction tree's parent
XID and its subxids may straddle several CLOG pages, and we cannot acquire
multiple bank locks safely. The recovery rule is **"if you see a parent as
COMMITTED, every subxact must already be at least SUB_COMMITTED"** — so a
crash mid-update can be detected and corrected on redo.

`TransactionIdSetTreeStatus` (`clog.c:191`) implements the rule:

1. Count subxids that share the parent's CLOG page (`nsubxids_on_first_page`).
2. If all subxids share the parent's page → one `TransactionIdSetPageStatus`
   call, status set atomically under one bank lock.
3. Otherwise, when **committing**:
   - First mark all subxids **not** on the parent's page as `SUB_COMMITTED`.
   - Then set the parent + the same-page subxids to `COMMITTED` (atomic for
     the parent's page).
   - Then walk the remaining subxids page-by-page and upgrade them to
     `COMMITTED`.
4. For aborts the intermediate is skipped — there is no recovery
   inconsistency to worry about because the post-crash assumption is that
   the transaction failed. [from-comment] (`clog.c:14-25`, `clog.c:226-256`).

The single-page assertion in `TransactionIdSetStatusBit` is generous about
the SUB_COMMITTED→COMMITTED transition — it allows the previous bit-state to
be `0` (untouched), `SUB_COMMITTED`, or already `status` (replay-idempotent):

```c
/* clog.c:700-703 */
Assert(curval == 0 ||
       (curval == TRANSACTION_STATUS_SUB_COMMITTED &&
        status != TRANSACTION_STATUS_IN_PROGRESS) ||
       curval == status);
```

## Group-commit optimization

Concurrent commits naturally serialize on the SLRU bank lock — but most
commits touch the **same** latest page. The group-commit path lets one
process (the "leader") drain a queue of waiting commits in a single lock
acquisition.

Eligibility gate (`clog.c:330-335`):

```c
all_xact_same_page                            /* parent+subxids fit */
  && xid == MyProc->xid                       /* it's really us */
  && nsubxids <= THRESHOLD_SUBTRANS_CLOG_OPT  /* ≤ 5 subxids */
  && nsubxids == MyProc->subxidStatus.count   /* matches PGPROC cache */
  && memcmp(subxids, MyProc->subxids.xids, ...) == 0
```

The `THRESHOLD_SUBTRANS_CLOG_OPT = 5` cap (`clog.c:105`) is tuned
empirically — testing showed larger group updates start to hurt. The
static-assert ensures it stays below `PGPROC_MAX_CACHED_SUBXIDS` so the
follower's payload always fits in `MyProc->subxids.xids[]`. [from-comment]
(`clog.c:101-105`, `clog.c:310-311`).

Then the dispatch path (`clog.c:343-358`):

1. `LWLockConditionalAcquire(bank, EXCLUSIVE)` — if we got it instantly, just
   do the update inline and return. This is the common uncontended case.
2. Otherwise → `TransactionGroupUpdateXidStatus` (the CAS-queued path).
3. If the group mechanism couldn't accept us → fall through to
   `LWLockAcquire` + direct update (the slow contention path).

### The queue (`TransactionGroupUpdateXidStatus`)

The queue head is a single atomic `procglobal->clogGroupFirst`. Followers
publish their commit metadata into their own `PGPROC` cells
(`clogGroupMemberXid`, `clogGroupMemberPage`, `clogGroupMemberLsn`,
`clogGroupMemberXidStatus`) then CAS themselves onto the queue:

```c
/* clog.c:496-531 */
nextidx = pg_atomic_read_u32(&procglobal->clogGroupFirst);
while (true) {
    /* page-mismatch escape: don't join if the head is on a different page */
    if (nextidx != INVALID_PROC_NUMBER &&
        GetPGProcByNumber(nextidx)->clogGroupMemberPage != proc->clogGroupMemberPage) {
        proc->clogGroupMember = false;
        return false;            /* caller falls through to direct update */
    }
    pg_atomic_write_u32(&proc->clogGroupNext, nextidx);
    if (CAS(&procglobal->clogGroupFirst, &nextidx, MyProcNumber))
        break;
}
```

The page-mismatch escape exists because the leader takes **one** bank
lock — if the queue's head is on a different page (and thus a different
bank), joining would force the leader to bank-hop. The CAS may still race
with a leader who has just drained and is now seeding a new group on a
different page; the comment acknowledges this and notes the code is
"slightly less efficient" but still correct: the leader does in fact
bank-hop if a follower's page lands in a different bank
(`clog.c:602-613`). [from-comment] (`clog.c:500-511`).

If we were not the first to publish (`nextidx != INVALID_PROC_NUMBER`),
we are a follower → `PGSemaphoreLock(proc->sem)` until the leader clears
`proc->clogGroupMember`. Otherwise we are the leader. [verified-by-code]
(`clog.c:539-561`).

The leader's job (`clog.c:563-661`):

1. Take the bank lock that matches our seed page.
2. `pg_atomic_exchange_u32(&clogGroupFirst, INVALID_PROC_NUMBER)` — closes
   the queue and returns the linked-list head. ABA-safe because we exchange
   the head pointer, not pop one element at a time. [from-comment]
   (`clog.c:571-580`).
3. Walk the list. If a follower's page is in a different bank, swap the
   bank lock; otherwise keep going.
4. For each follower, call `TransactionIdSetPageStatusInternal` with their
   stored xid + cached subxids.
5. Release the bank lock.
6. **Then** wake followers: walk the saved list head, for each follower
   write `pg_atomic_write_u32(&clogGroupNext, INVALID_PROC_NUMBER)`,
   `pg_write_barrier()`, set `clogGroupMember = false`, `PGSemaphoreUnlock`.
   Wakes happen outside the bank lock to minimize hold time.
   [from-comment] (`clog.c:636-643`).

## Async-commit LSN tracking — the `group_lsn[]` array

Synchronous commits flush their WAL record before calling into CLOG, so the
write-WAL-before-data rule is automatic. **Async** commits do not — they
return success to the client before the commit record is flushed. If CLOG
were to write that page to disk before the commit record made it to WAL, a
crash would reveal a "committed" XID with no commit record, corrupting MVCC.

The fix: track, per group of 32 XIDs per page, the highest LSN of any
async-committed XID in that group. CLOG's page-write path (in
`[[slru-page-replacement]]`, `slru.c:937-975`) computes the max across the
page's `lsn_groups_per_page` entries and `XLogFlush(max_lsn)` before the
disk write.

CLOG configures `nlsns = CLOG_LSNS_PER_PAGE` (`clog.c:817-818`):

```c
/* clog.c:93-98 */
#define CLOG_XACTS_PER_LSN_GROUP    32          /* power of 2 */
#define CLOG_LSNS_PER_PAGE          (CLOG_XACTS_PER_PAGE / CLOG_XACTS_PER_LSN_GROUP)
                                                /* = 32768 / 32 = 1024 */

#define GetLSNIndex(slotno, xid)    ((slotno) * CLOG_LSNS_PER_PAGE + \
    ((xid) % (TransactionId) CLOG_XACTS_PER_PAGE) / CLOG_XACTS_PER_LSN_GROUP)
```

Write side, every status update bumps the relevant group's LSN if higher
(`clog.c:719-725`):

```c
if (XLogRecPtrIsValid(lsn)) {
    int lsnindex = GetLSNIndex(slotno, xid);
    if (XactCtl->shared->group_lsn[lsnindex] < lsn)
        XactCtl->shared->group_lsn[lsnindex] = lsn;
}
```

Read side, `TransactionIdGetStatus` returns the **group's** LSN, not the
exact commit LSN — the comment is explicit ("we group transactions on the
same clog page to conserve storage, we might return the LSN of a later
transaction that falls into the same group"). Callers waiting on commit
durability (e.g. `pg_xact_status`, `SyncRepWaitForLSN` chains) flush to
that LSN, which is at-or-after the real commit. [from-comment]
(`clog.c:730-738`).

CLOG is the **only** SLRU that sets `nlsns > 0`. All others
(commit_ts, multixact-offset, multixact-members, subtrans, pg_notify,
predicate) pass `nlsns = 0` and so have `group_lsn == NULL`. [verified-by-code]
(grep `SimpleLruRequest.*nlsns` across `transam/`).

## Truncation — vacuum-driven, segment-aligned

CLOG only grows; it shrinks when vacuum advances the global `oldestXact`
horizon. `TruncateCLOG` (`clog.c:985`) is called from vacuum:

1. Compute `cutoffPage = TransactionIdToPage(oldestXact)`.
2. `SlruScanDirectory(..., SlruScanDirCbReportPresence, &cutoffPage)` —
   check whether any segment file precedes the cutoff. If not, return
   without writing WAL.
3. `AdvanceOldestClogXid(oldestXact)` — publish the new horizon so concurrent
   lookups don't try to read truncated pages.
4. Write a `CLOG_TRUNCATE` xlog record (`xl_clog_truncate { pageno,
   oldestXact, oldestXactDb }`) and **flush it synchronously** —
   `WriteTruncateXlogRec` does `XLogInsert` + `XLogFlush(recptr)`
   (`clog.c:1080-1083`). This ensures any standby learns the new horizon
   before its own truncation, and that crash recovery preserves the
   ordering.
5. `SimpleLruTruncate(XactCtl, cutoffPage)` — drop segments where every
   page precedes the cutoff.

The "Advance before truncate, write WAL before truncate" ordering is the
crash-safety invariant: a backend's `TransactionIdGetStatus` must never
look up a truncated XID. [from-comment] (`clog.c:998-1013`).

`CLOGPagePrecedes` (`clog.c:1040-1053`) is the comparator that knows
TransactionId wraparound — both pages are offset by
`FirstNormalTransactionId + 1` so `TransactionIdPrecedes` does
modular-correct arithmetic, then we double-check that the entire candidate
page precedes the cutoff (i.e. `xid1 + CLOG_XACTS_PER_PAGE - 1` also
precedes). [from-comment] (`clog.c:1023-1038`).

## Lookup path

`TransactionIdGetStatus(xid, *lsn)` is the lowest-level read API. It is
called by `TransactionLogFetch` (in `transam.c`), which in turn underlies
`TransactionIdDidCommit` / `TransactionIdDidAbort` and the visibility
routines.

```c
/* clog.c:743-767 */
slotno  = SimpleLruReadPage_ReadOnly(XactCtl, pageno, &xid);
byteptr = XactCtl->shared->page_buffer[slotno] + byteno;
status  = (*byteptr >> bshift) & 0x03;
*lsn    = XactCtl->shared->group_lsn[GetLSNIndex(slotno, xid)];
LWLockRelease(SimpleLruGetBankLock(XactCtl, pageno));
```

`SimpleLruReadPage_ReadOnly` returns with the bank lock held (shared or
exclusive — caller doesn't know). The caller releases it directly.
[verified-by-code] (`clog.c:754-764`).

The `&xid` opaque passed through is for `clog_errdetail_for_io_error` —
if the underlying I/O fails, ereport adds "Could not access commit status
of transaction %u." [verified-by-code] (`clog.c:1055-1061`).

## Invariants and races

1. **All-zeroes is `IN_PROGRESS`.** A freshly-zeroed CLOG page implicitly
   marks every XID it covers as in-progress, which is the correct initial
   state. `SimpleLruZeroPage` memsets to zero (`slru.c:418`). [from-comment]
   (`clog.h:19-20`).
2. **CLOG bank lock held exclusive for the bit write**, asserted by
   `TransactionIdSetStatusBit`. The byte read-modify-write would race
   otherwise — adjacent XIDs share a byte. [verified-by-code] (`clog.c:679`).
3. **`group_lsn` is monotonic per slot/group.** A status-set never lowers
   it; CLOG-write flushes the max. [verified-by-code] (`clog.c:723-724`).
4. **Group-update queue is CAS-only**; ABA is dodged by exchanging the
   head pointer (not popping per-element). [from-comment]
   (`clog.c:573-577`).
5. **Followers are woken outside the bank lock** to keep hold times minimal.
   The leader publishes wake signals after dropping the lock.
   [from-comment] (`clog.c:636-643`).
6. **CLOG truncation is WAL-logged-then-flushed before disk truncation**, so
   crash recovery can replay it and standbys learn the horizon.
   [verified-by-code] (`clog.c:1080-1083`).
7. **The bit-write Assert is recovery-tolerant**: SUB_COMMITTED→COMMITTED
   may already have happened on a replay, so `curval == status` is allowed.
   [from-comment] (`clog.c:686-703`).

## Useful greps

```bash
# Every status-write entry point:
grep -n "TransactionIdSet" source/src/backend/access/transam/clog.c

# Where async-commit LSN tracking matters (group_lsn writers):
grep -n "GetLSNIndex\|group_lsn\[" source/src/backend/access/transam/clog.c

# Group-update queue plumbing in PGPROC:
grep -n "clogGroup" source/src/backend/storage/lmgr/proc.c \
                    source/src/include/storage/proc.h

# Callers of TransactionIdGetStatus:
grep -rn "TransactionIdGetStatus\|TransactionLogFetch" \
       source/src/backend/access/transam/
```

## Cross-references

- [[slru-page-replacement]] — buffer cache + group-LSN WAL barrier on write.
- [[multixact-slru]] — sibling SLRU client with very different access pattern.
- [[subtransaction-stack]] — PGPROC cached-subxids array (the group-update gate).
- [[xmin-horizon-management]] — vacuum advances `oldestXact`, which drives `TruncateCLOG`.
- `knowledge/subsystems/access-transam.md` §"CLOG" — subsystem-level view.
