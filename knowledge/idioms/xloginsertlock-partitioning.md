# XLogInsertLock partitioning — the 8-lock pool

WAL insert is the hottest write path in PostgreSQL; every modifying
backend touches it. The pre-PG-9.4 design used a single big lock
serializing inserts. The current design partitions WAL insertion
across `NUM_XLOGINSERT_LOCKS = 8` parallel LWLocks, each carrying
its own `insertingAt` progress marker so a flusher can wait for
only the relevant ones rather than for all in-flight inserters.
Combined with a small spinlock-protected `(CurrBytePos,
PrevBytePos)` reservation step, this lets N backends compute their
WAL slots concurrently and copy bytes into shared buffers without
serializing on each other.

Anchors:
- `source/src/backend/access/transam/xlog.c:157` —
  NUM_XLOGINSERT_LOCKS = 8 [verified-by-code]
- `source/src/backend/access/transam/xlog.c:374-379` —
  WALInsertLock struct [verified-by-code]
- `source/src/backend/access/transam/xlog.c:388-392` —
  WALInsertLockPadded (cache-line padding) [verified-by-code]
- `source/src/backend/access/transam/xlog.c:1149` —
  ReserveXLogInsertLocation (the spinlock window) [verified-by-code]
- `source/src/backend/access/transam/xlog.c:1412` —
  WALInsertLockAcquire [verified-by-code]
- `source/src/backend/access/transam/xlog.c:1456` —
  WALInsertLockAcquireExclusive (all 8) [verified-by-code]
- `knowledge/idioms/wal-buffer-state.md` — companion
- `knowledge/idioms/wal-page-write-flush.md` — companion
- `.claude/skills/wal-and-xlog/SKILL.md` — companion

## The two-tier discipline

```
   backend wants to insert WAL
        │
        ▼
  ─────────────────────────────
  TIER 1: pick one of 8 insert locks (shared LWLock pool)
        │
        ├── WALInsertLockAcquire — first attempt: lockToTry
        ├── if contended, lockToTry++ for next call
        └── lockToTry % NUM_XLOGINSERT_LOCKS
        ▼
  ─────────────────────────────
  TIER 2: reserve the byte range (spinlock on insertpos_lck)
        │
        ├── SpinLockAcquire(insertpos_lck)
        ├── startbytepos = CurrBytePos; CurrBytePos += size
        ├── PrevBytePos = startbytepos
        └── SpinLockRelease(insertpos_lck)
        ▼
  ─────────────────────────────
  COPY into WAL buffers (no centralized lock held)
        │
        ▼
  Update insertingAt via LWLockUpdateVar (only if crossed page)
        ▼
  WALInsertLockRelease
```

Tier 1 is the LWLock; tier 2 is the spinlock-protected
`CurrBytePos` reservation. Most of the per-record work (computing
data, copying bytes into buffers) happens with the LWLock held
but the spinlock released.

## The lock struct

[verified-by-code `xlog.c:374-379`]

```c
typedef struct
{
    LWLock              lock;
    pg_atomic_uint64    insertingAt;
    XLogRecPtr          lastImportantAt;
} WALInsertLock;
```

- `lock` — the LWLock used for exclusion. Held EXCLUSIVE for
  insertion (multiple inserters across different locks proceed
  in parallel).
- `insertingAt` — atomic; the LSN this lock's holder is currently
  copying to. Used by flushers (`WaitXLogInsertionsToFinish`) to
  know "this inserter has finished copying up to here, you can
  safely write that region to disk".
- `lastImportantAt` — LSN of the last non-XLOG_MARK_UNIMPORTANT
  record inserted through this lock; consulted by checkpointer
  to decide if a new checkpoint is needed.

## Cache-line padding

[verified-by-code `xlog.c:388-392`]

```c
typedef union WALInsertLockPadded
{
    WALInsertLock l;
    char          pad[PG_CACHE_LINE_SIZE];
} WALInsertLockPadded;
```

Each lock takes a full cache line so two CPUs holding different
locks don't ping-pong cache lines. The 8-element array's base
must also be cache-line-aligned (shmem allocator does this).

`PG_CACHE_LINE_SIZE` is typically 64 (x86) or 128 (Apple Silicon).

## WALInsertLockAcquire — pick one of 8

[verified-by-code `xlog.c:1412-1450`]

```c
static int lockToTry = -1;

if (lockToTry == -1)
    lockToTry = MyProcNumber % NUM_XLOGINSERT_LOCKS;
MyLockNo = lockToTry;

immed = LWLockAcquire(&WALInsertLocks[MyLockNo].l.lock, LW_EXCLUSIVE);
if (!immed)
{
    /* not free, try a different lock next time */
    lockToTry = (lockToTry + 1) % NUM_XLOGINSERT_LOCKS;
}
```

Three design tricks:
1. **First-time hash** — `MyProcNumber % 8` spreads connections.
2. **Backoff on contention** — if you blocked, rotate so you don't
   bang the same lock again.
3. **Affinity on success** — if the lock was immediately free,
   keep `lockToTry` pointing at it. This minimizes cache-line
   migration when the system is uncontended.

## WALInsertLockAcquireExclusive — all 8 at once

[verified-by-code `xlog.c:1456-1477`]

```c
for (i = 0; i < NUM_XLOGINSERT_LOCKS - 1; i++) {
    LWLockAcquire(&WALInsertLocks[i].l.lock, LW_EXCLUSIVE);
    LWLockUpdateVar(&WALInsertLocks[i].l.lock,
                    &WALInsertLocks[i].l.insertingAt,
                    PG_UINT64_MAX);
}
LWLockAcquire(&WALInsertLocks[i].l.lock, LW_EXCLUSIVE);
holdingAllLocks = true;
```

Used by checkpoint, by `pg_switch_wal()`, and by anything that
needs a stable view of WAL state. Acquires all 8, then sets
`insertingAt` to MAX_UINT on the first 7 so any waiters skip past
them. The last lock keeps its real `insertingAt` value (updated
via `WALInsertLockUpdateInsertingAt`) so this acquirer can
itself advance its position while holding everything.

This is a **rare** path; the common case is single-lock acquire.

## ReserveXLogInsertLocation — the spinlock window

[verified-by-code `xlog.c:1149-1193`]

```c
SpinLockAcquire(&Insert->insertpos_lck);

startbytepos = Insert->CurrBytePos;
endbytepos = startbytepos + size;
prevbytepos = Insert->PrevBytePos;
Insert->CurrBytePos = endbytepos;
Insert->PrevBytePos = startbytepos;

SpinLockRelease(&Insert->insertpos_lck);

*StartPos = XLogBytePosToRecPtr(startbytepos);
*EndPos = XLogBytePosToEndRecPtr(endbytepos);
*PrevPtr = XLogBytePosToRecPtr(prevbytepos);
```

Two crucial design choices:
- **Byte positions, not LSNs** — `CurrBytePos` counts only
  "usable" WAL bytes, excluding page headers. Reserving X bytes
  is then literally "CurrBytePos += X". The LSN conversion
  (`XLogBytePosToRecPtr`) happens OUTSIDE the spinlock.
- **Spinlock not LWLock** — the critical section is just two
  field reads and two writes. A spinlock is faster than LWLock
  here, and we trust everyone to release quickly.

`PrevBytePos` tracks the prior record's start position; it's
copied into the new record's `xl_prev` field for the WAL
back-link chain.

## insertingAt and the flusher

[verified-by-code `xlog.c:1511-1528, 1544-1620`]

Inserters typically:
1. Reserve `[StartPos, EndPos]` (Tier 2).
2. `GetXLogBuffer(StartPos)` — maybe wait for buffer.
3. Copy data; `WALInsertLockUpdateInsertingAt(currPos)` ONLY if
   they crossed a page boundary (else the lock release covers it).
4. Release.

When XLogWrite needs to flush WAL up to `upto`,
`WaitXLogInsertionsToFinish(upto)`:
- Loops through all 8 locks.
- For each, calls `LWLockWaitForVar(&lock, &insertingAt, upto, ...)`
  which returns when either the lock is released OR `insertingAt
  >= upto`.

The dual condition means a slow inserter holding a lock past
`upto` doesn't block flushers — once it updates `insertingAt`
past `upto`, the flusher proceeds.

## The deadlock scenario the design avoids

[verified-by-code `xlog.c:353-358` comment]

> If all the WAL buffers are dirty, an inserter that's holding a
> WAL insert lock might need to evict an old WAL buffer, which
> requires flushing the WAL. If it's possible for an inserter to
> block on another inserter unnecessarily, deadlock can arise
> when two inserters holding a WAL insert lock wait for each
> other to finish their insertion.

The `insertingAt` discipline + "always update before sleeping"
rule (`xlog.c:362-363`) breaks this cycle: an inserter who's
about to sleep first publishes its position, so the other
inserter can flush past it without waiting.

## Common review-time concerns

- **NUM_XLOGINSERT_LOCKS is compile-time** — changing it requires
  rebuild + shmem layout change.
- **MyLockNo is per-backend** — set on acquire, used on release.
- **Spinlock window is tiny** — never add heavy work inside the
  insertpos_lck region.
- **Crossing-page updates insertingAt** — small records don't
  need this; only records spanning multiple WAL pages.
- **All-8-locks acquire is rare** — checkpoint, pg_switch_wal,
  fullPageWrites change. If you write code holding all 8, you're
  serializing all WAL.
- **lastImportantAt is read by checkpoint** — driver for the
  "skip checkpoint if no important activity" optimization.

## Invariants

- **[INV-1]** Holding ANY one of the 8 locks is enough to insert.
- **[INV-2]** Holding ALL 8 locks blocks every inserter.
- **[INV-3]** `insertingAt` MUST be updated before sleeping while
  holding a lock (deadlock avoidance).
- **[INV-4]** `insertpos_lck` is a spinlock; critical section is
  read/write of two uint64 fields only.
- **[INV-5]** `CurrBytePos` is monotonically increasing; the
  byte-position-to-XLogRecPtr conversion accounts for page headers.

## Useful greps

- Lock count + struct:
  `grep -n 'NUM_XLOGINSERT_LOCKS\|WALInsertLockPadded\|^WALInsertLock' source/src/backend/access/transam/xlog.c | head -10`
- Acquire / release / update-var:
  `grep -n '^WALInsertLockAcquire\|^WALInsertLockRelease\|WALInsertLockUpdateInsertingAt' source/src/backend/access/transam/xlog.c | head -10`
- Reservation:
  `grep -n 'ReserveXLogInsertLocation\|CurrBytePos\|insertpos_lck' source/src/backend/access/transam/xlog.c | head -15`
- Flusher wait:
  `grep -n 'WaitXLogInsertionsToFinish\|LWLockWaitForVar' source/src/backend/access/transam/xlog.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 157 | NUM_XLOGINSERT_LOCKS = 8 |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 374 | WALInsertLock struct |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 388 | WALInsertLockPadded (cache-line padding) |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 1149 | ReserveXLogInsertLocation (the spinlock window) |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 1412 | WALInsertLockAcquire |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 1456 | WALInsertLockAcquireExclusive (all 8) |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | — | full module |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)
- [`bump-catversion`](../scenarios/bump-catversion.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/wal-buffer-state.md` — the buffer pool that
  inserters copy into.
- `knowledge/idioms/wal-page-write-flush.md` — XLogWrite consumes
  the byte ranges produced here.
- `knowledge/idioms/lwlock-acquire-release.md` —
  LWLockUpdateVar / LWLockWaitForVar mechanics.
- `knowledge/data-structures/xlogrecord.md` —
  per-record structure being inserted.
- `knowledge/subsystems/transam-xlog.md` — module overview.
- `.claude/skills/wal-and-xlog/SKILL.md` — companion.
- `source/src/backend/access/transam/xlog.c` — full module.
