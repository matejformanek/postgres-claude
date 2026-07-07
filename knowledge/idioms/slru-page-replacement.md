# SLRU page replacement — bank-locked LRU with latest-page pin

The Simple-LRU (`slru.c`) caches small "transaction status" pages — CLOG,
commit-ts, multixact offsets+members, subtrans, pg_notify, predicate-locks —
without the full overhead of the shared buffer manager. It is bank-partitioned
(16 slots per bank, hashed by page number), uses a counter-style LRU, and
**refuses to evict the latest-page-number** because that page is the active
write target and would be touched again immediately.

This doc covers the **replacement algorithm and locking dance**: how a
miss-then-victim search finds a slot, how the bank lock and per-buffer I/O
lock interact, how a `group_lsn` WAL flush fires before a dirty write, and
why the latest-page check uses an atomic instead of a lock.

Companion docs:
- [[clog-slru]] — CLOG's bit-packing, group-commit, and async-commit LSNs on top of this layer.
- [[multixact-slru]] — MultiXact's dual SLRU (offsets + members) and its two-stage lookup.
- `knowledge/subsystems/access-transam.md` — the subsystem-level overview that points here.

## Anchors

- `source/src/include/access/slru.h:48-106` — `SlruSharedData` struct (status array, lru-count arrays, group_lsn, latest_page_number atomic).
- `source/src/backend/access/transam/slru.c:11-49` — header banner explaining bank locks + per-buffer locks + deadlock-free I/O dance.
- `source/src/backend/access/transam/slru.c:138-151` — `SLRU_BANK_SIZE = 16` (1<<4); `SlotGetBankNumber(slotno) = slotno >> 4`.
- `source/src/include/pg_config_manual.h:30` — `SLRU_PAGES_PER_SEGMENT = 32` (so one segment file = 32 × 8 KiB = 256 KiB).
- `source/src/backend/access/transam/slru.c:1218-1363` — `SlruSelectLRUPage` (victim search; the heart of the policy).
- `source/src/backend/access/transam/slru.c:549-636` — `SimpleLruReadPage` (miss path; cooperates with `SlruSelectLRUPage`).
- `source/src/backend/access/transam/slru.c:653-687` — `SimpleLruReadPage_ReadOnly` (shared-lock fast path).
- `source/src/backend/access/transam/slru.c:1170-1203` — `SlruRecentlyUsed` (lru-count bump, deliberately race-tolerant).
- `source/src/backend/access/transam/slru.c:925-1090` — `SlruPhysicalWritePage` (WAL-flush via group_lsn before disk write).

## The shared layout

```c
/* slru.h:48 — SlruSharedData (one per SLRU instance) */
struct SlruSharedData {
    int            num_slots;            /* total page slots */
    char         **page_buffer;          /* [slotno] -> 8 KiB page */
    SlruPageStatus *page_status;         /* EMPTY|READ_IN_PROGRESS|VALID|WRITE_IN_PROGRESS */
    bool          *page_dirty;
    int64         *page_number;          /* logical page # within SLRU */
    int           *page_lru_count;       /* bank-relative recency */
    LWLockPadded  *buffer_locks;         /* per-slot I/O lock */
    LWLockPadded  *bank_locks;           /* per-bank control lock */
    int           *bank_cur_lru_count;   /* bank-local LRU counter */
    XLogRecPtr    *group_lsn;            /* optional WAL barrier per N entries */
    int            lsn_groups_per_page;
    pg_atomic_uint64 latest_page_number; /* never-evict pin */
    int            slru_stats_idx;       /* for pg_stat_slru */
};
```

`num_slots % SLRU_BANK_SIZE == 0` always (asserted at init, `slru.c:208`). The
slot array is conceptually a 2-D table: bank `b` owns slots `[b*16,
b*16+16)`. The victim search only scans **one bank**, so it is O(16) under a
single per-bank lock — that is the whole point of banking. [verified-by-code]
(`slru.c:138-151`, `slru.c:1233-1245`).

`bank_locks[]` (16 slots wide) protect the shared state of that bank's slots.
`buffer_locks[]` (one per slot) only protect the in-flight I/O on that slot.
`latest_page_number` is touched outside any lock — it is an atomic
`pg_atomic_uint64`. The reason it doesn't need a lock: both the only writer
(`SimpleLruZeroPage`) and the only consulter (`SlruSelectLRUPage`) run with
the bank lock held; a stale atomic read at worst causes a suboptimal eviction,
never a correctness violation. [from-comment] (`slru.c:1297-1305`,
`slru.c:423-430`).

## The bank-local LRU counter

Standard LRU schemes hand out a global tick that everyone bumps on every
access. That serializes badly under read-mostly workloads. SLRU instead keeps
a **per-bank** counter (`bank_cur_lru_count[bankno]`) and bumps it only when
the slot's count is already behind:

```c
/* slru.c:1198 — SlruRecentlyUsed */
if (new_lru_count != shared->page_lru_count[slotno]) {
    shared->bank_cur_lru_count[bankno] = ++new_lru_count;
    shared->page_lru_count[slotno] = new_lru_count;
}
```

The if-test "suppresses useless increments" when many consecutive accesses
hit the same page (extremely common — the *latest* CLOG page is touched on
every transaction commit). Without the suppression, the counter would
wrap quickly and break the relative-age computation. [from-comment]
(`slru.c:1180-1185`).

The "delta" used by the victim search is the **lag** of a slot behind the
bank's current counter:

```c
this_delta = cur_count - shared->page_lru_count[slotno];
```

Largest delta wins (i.e. that slot is the least-recently-used). Ties are
broken by `PagePrecedes()` — the per-SLRU callback that knows the page-number
modular comparison; this prefers evicting the older logical page when two
slots are equally cold. [verified-by-code] (`slru.c:1283-1331`).

A subtle correctness point: `SimpleLruReadPage_ReadOnly` runs
`SlruRecentlyUsed` under a **shared** bank lock, so concurrent processes can
read-modify-write the same counter cells. The comment is explicit that this
is OK: the worst case is a slot that "appears recently used" when it is not,
which causes a non-optimal but not incorrect eviction. [from-comment]
(`slru.c:1187-1197`).

## Hit path — `SimpleLruReadPage_ReadOnly`

Read-only callers (most CLOG status lookups, MultiXact membership lookups)
take this fast path. It tries the bank under **shared** lock first:

```
1. LWLockAcquire(banklock, LW_SHARED)
2. linear scan slots [bankstart, bankend):
     if page_status != EMPTY && page_number == pageno && status != READ_IN_PROGRESS:
        SlruRecentlyUsed(); hit-counter++; return slotno (lock still held shared)
3. LWLockRelease(banklock); LWLockAcquire(banklock, LW_EXCLUSIVE)
4. fall through to SimpleLruReadPage(write_ok=true)
```

The function returns with the bank lock still held — but the caller doesn't
know whether it is shared or exclusive. That asymmetry is documented and is
why the API contract says "Bank control lock must NOT be held at entry, but
will be held at exit. It is unspecified whether the lock will be shared or
exclusive." Callers that need to modify the page must redo the lock dance.
[from-comment] (`slru.c:650-651`, `slru.c:653-687`).

## Miss path — `SimpleLruReadPage`

Called with the bank lock held **exclusive**. The outer `for (;;)` retries on
I/O wait:

1. `SlruSelectLRUPage` returns either the slot already holding the page (any
   status), or a freeable victim slot (EMPTY or VALID+clean).
2. If the slot holds the page but is `READ_IN_PROGRESS`, or `WRITE_IN_PROGRESS`
   and the caller said `write_ok=false`, we **release the bank lock,
   shared-lock the buffer lock to wait, drop it, re-acquire the bank lock,
   restart**. The shared/exclusive handoff is the deadlock-free wait pattern
   from the file banner. [from-comment] (`slru.c:37-45`).
3. Otherwise it is a brand-new read:
   - Mark slot READ_IN_PROGRESS, clear dirty, set page_number = pageno.
   - Take per-buffer lock exclusive.
   - Release bank lock.
   - `SlruPhysicalReadPage` reads `pageno % SLRU_PAGES_PER_SEGMENT * BLCKSZ` from
     the segment file.
   - Zero the group_lsn array for this slot.
   - Re-acquire bank lock; flip status to VALID (or back to EMPTY on read
     failure), release per-buffer lock, ereport if failed.

The split — bank lock for state mutation, per-buffer lock for I/O — is what
lets multiple processes do disk reads on **different** slots in the same bank
simultaneously without serializing on the bank lock. The per-buffer lock is
shared/exclusive in mode-swapped form: an I/O initiator takes it exclusive,
waiters take it shared just to block until the initiator releases. The
"never try to initiate I/O when someone else is already doing I/O on the same
buffer" invariant rules out deadlock. [from-comment]
(`slru.c:37-45`, `slru.c:602-623`).

## Victim selection — the latest-page exception

`SlruSelectLRUPage` (`slru.c:1218`) scans the 16 slots of the relevant bank.
For each non-EMPTY slot it computes `this_delta = cur_count -
page_lru_count[slotno]`. Two passes happen concurrently — best valid
(non-busy) candidate and best invalid (busy) candidate — because if every
slot is mid-I/O we have to wait on the LRU-est busy one. The crucial filter:

```c
/* slru.c:1297 */
this_page_number = shared->page_number[slotno];
if (this_page_number == pg_atomic_read_u64(&shared->latest_page_number))
    continue;
```

This pins the **active write target** in cache. Every commit appends to the
latest CLOG page; if it could be evicted, the commit path would oscillate
between read-from-disk and write-back. The atomic read is sufficient because
both producer (`SimpleLruZeroPage`) and this consumer hold the bank lock
during the comparison's relevant scope. [from-comment] (`slru.c:1297-1305`).

If the chosen victim is clean → return it. If dirty → call
`SlruInternalWritePage` (releases bank lock, takes per-buffer lock, does the
I/O, re-takes bank lock), then **loop back** to re-scan. The loop-back is
necessary because while the bank lock was dropped, anything could have
happened — the target page could now be in another slot, the victim could
have been re-dirtied, etc. [verified-by-code] (`slru.c:1346-1362`).

## The "all busy" wait

If `best_valid_delta < 0` after the scan, every slot in the bank is in
I/O — there is no clean victim. The code waits on the LRU-est busy slot:

```c
if (best_valid_delta < 0) {
    SimpleLruWaitIO(ctl, bestinvalidslot);
    continue;
}
```

"On the assumption that it was likely initiated first of all the I/Os in
progress and may therefore finish first" — a heuristic, but cheaper than
randomly polling. The 16-slot bank size is small enough that this case is
rare in practice. [from-comment] (`slru.c:1333-1344`).

## Group-LSN WAL barrier on write

SLRUs that record async-commit LSNs (CLOG specifically — `group_lsn != NULL`)
must respect the write-WAL-before-data rule. `SlruPhysicalWritePage` does this
before the disk write:

```c
/* slru.c:942 — SlruPhysicalWritePage */
if (shared->group_lsn != NULL) {
    /* find max LSN among this page's lsn_groups_per_page entries */
    XLogRecPtr max_lsn = ...;
    if (XLogRecPtrIsValid(max_lsn)) {
        START_CRIT_SECTION();
        XLogFlush(max_lsn);
        END_CRIT_SECTION();
    }
}
```

The crit section is required because `elog(ERROR)` from XLogFlush would be
unsafe at this point — we have already torn off into the I/O dance with the
buffer lock held. PANIC on XLogFlush failure is the chosen poison.
[from-comment] (`slru.c:937-975`).

Other SLRUs (commit_ts, multixact offsets/members, subtrans, pg_notify,
predicate) set `nlsns = 0` and so `group_lsn == NULL`; their writes need no
WAL barrier because their changes are either already WAL-logged before the
page is dirtied, or they are not durable (pg_notify). [inferred from header
description] (`slru.c:11-15`).

## Fsync deferral via the checkpointer

After the `pg_pwrite`, an `INIT_SLRUFILETAG(tag, sync_handler, segno)` is
enqueued with `RegisterSyncRequest(&tag, SYNC_REQUEST, false)`. If the
checkpointer's queue is full, the write does a synchronous `pg_fsync`
inline. Otherwise the dirty file is flushed by the next `ProcessSyncRequests`
the checkpointer runs. [verified-by-code] (`slru.c:1056-1076`).

SLRUs with `sync_handler == SYNC_HANDLER_NONE` (pg_notify) skip the request
entirely — their data is purely in-memory-buffered and segments are truncated
when listeners drain. [verified-by-code] (`slru.c:1057`).

## File layout — segments and short vs long names

A "segment" file holds `SLRU_PAGES_PER_SEGMENT = 32` consecutive pages —
256 KiB at the default 8 KiB block size. The filename is the segment number
in hex:

- **Short names** (default; CLOG, commit_ts, subtrans, multixact, pg_notify):
  4 to 6 hex chars, supports `segno ∈ [0, 2^24-1]`.
- **Long names** (set via `SlruOpts.long_segment_names = true`; multixact
  members specifically, after the 32-bit MultiXactOffset became 64-bit
  internally): 15 hex chars, supports `segno ∈ [0, 2^60-1]`.

The 15-char (not 16) length is deliberate — keeps SLRU filenames visually
distinguishable from 24-char WAL segment names. [from-comment]
(`slru.c:96-117`).

## Invariants and races

1. **Bank lock + per-buffer lock are deadlock-free** because nobody waits on a
   per-buffer lock while another I/O is in flight on the same buffer — that
   case is explicitly checked-and-restart-from-top in `SimpleLruReadPage`.
   [from-comment] (`slru.c:37-41`).
2. **`latest_page_number` is atomic, not lock-protected**, because the only
   write (`SimpleLruZeroPage`) and the only read (`SlruSelectLRUPage`) both
   run with the bank lock held during the relevant scope; the atomic is just
   a publish-without-tearing primitive. [from-comment] (`slru.c:423-430`).
3. **Read-only fast path may race on LRU counters** under shared lock. The
   worst case is suboptimal eviction, never an incorrect read.
   [from-comment] (`slru.c:1187-1197`).
4. **Re-dirty during write is handled by re-setting page_dirty.** A page can
   become dirty again while WRITE_IN_PROGRESS; the next checkpoint sweep
   will rewrite it. [from-comment] (`slru.c:47-49`).
5. **EMPTY slot status implies undefined `page_number` and `page_lru_count`** —
   never read those fields without first checking status. The struct comment
   makes this explicit. [from-comment] (`slru.h:56-60`).
6. **PagePrecedes is modular**, not signed. For SLRUs that wrap (everything
   indexed by TransactionId / MultiXactId), the callback uses
   `TransactionIdPrecedes`-style 32-bit modular comparison. Lookup tests in
   `SlruPagePrecedesUnitTests` enforce this for SLRUs that call
   `SimpleLruTruncate`. [verified-by-code] (`slru.h:156-167`,
   `slru.c:1655-1761`).

## Useful greps

```bash
# Every SLRU instance and how it sets up:
grep -rn "SimpleLruRequest(" source/src/backend/

# Bank-related arithmetic:
grep -n "SLRU_BANK_SIZE\|SlotGetBankNumber\|nbanks" \
     source/src/backend/access/transam/slru.c

# Callers that use group_lsn (CLOG only at time of writing):
grep -n "lsn_groups_per_page\|group_lsn\[" \
     source/src/backend/access/transam/

# Truncation entry points (vacuum drives these):
grep -n "SimpleLruTruncate\|SlruScanDirCbDeleteCutoff" \
     source/src/backend/access/transam/
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 11 | header banner explaining bank locks + per-buffer locks + deadlock-free I/O dance |
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 138 | SLRU_BANK_SIZE = 16 (1<<4); SlotGetBankNumber(slotno) = slotno >> 4 |
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 549 | SimpleLruReadPage (miss path; cooperates with SlruSelectLRUPage) |
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 653 | SimpleLruReadPage_ReadOnly (shared-lock fast path) |
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 925 | SlruPhysicalWritePage (WAL-flush via group_lsn before disk write) |
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 1170 | SlruRecentlyUsed (lru-count bump, deliberately race-tolerant) |
| [`src/backend/access/transam/slru.c`](../files/src/backend/access/transam/slru.c.md) | 1218 | SlruSelectLRUPage (victim search; the heart of the policy) |
| [`src/include/access/slru.h`](../files/src/include/access/slru.h.md) | 48 | SlruSharedData struct (status array, lru-count arrays, group_lsn, latest_page_number atomic) |
| [`src/include/pg_config_manual.h`](../files/src/include/pg_config_manual.h.md) | 30 | SLRU_PAGES_PER_SEGMENT = 32 (so one segment file = 32 × 8 KiB = 256 KiB) |

<!-- /callsites:auto -->

## Cross-references

- [[clog-slru]] — how CLOG sits on top of this layer.
- [[multixact-slru]] — MultiXact's two SLRUs and their interaction.
- [[subtransaction-stack]] — subtrans uses one SLRU for parent-XID lookups.
- [[xmin-horizon-management]] — vacuum advancing oldestXmin drives
  `SimpleLruTruncate` on the relevant SLRUs.
- `knowledge/subsystems/access-transam.md` §"SLRU caches" — subsystem-level overview.
