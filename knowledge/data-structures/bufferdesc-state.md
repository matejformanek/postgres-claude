# BufferDesc — state-encoding bits

- **Source path:** `source/src/include/storage/buf_internals.h`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-11; §1–3 re-verified against `buf_internals.h`: content-lock-in-`state` refactor, `BUF_*_BITS` widths, `StaticAssertDecl`s, full 12-bit flag block incl. bit-6-unused, `BM_MAX_USAGE_COUNT=5`. No claim drift.)
- **Companion docs:** `knowledge/files/src/include/storage/buf_internals.h.md`,
  `knowledge/subsystems/storage-buffer.md`, `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`

## 1. The struct

```c
typedef struct BufferDesc {
    BufferTag         tag;                   // page identity (header spinlock to mutate)
    int               buf_id;                // 0-based array index, write-once
    pg_atomic_uint64  state;                 // packed: refcount + usagecount + flags + content-lock state
    int               wait_backend_pgprocno; // cleanup-lock waiter procnumber (header spinlock)
    PgAioWaitRef      io_wref;               // valid iff AIO is in progress
    proclist_head     lock_waiters;          // content-lock waiter queue (header spinlock)
} BufferDesc;
```

[verified-by-code `source/src/include/storage/buf_internals.h:326-359`]

There is **no separate `content_lock` LWLock anymore** — since PG 18 the
content lock is encoded into the high bits of `state`. The big comment block
at `buf_internals.h:303-310` records the rationale: "We used to use an LWLock
to implement the content lock, but having a dedicated implementation of
content locks allows us to implement some otherwise hard things (e.g.
race-freely checking if AIO is in progress before locking a buffer
exclusively) and enables otherwise impossible optimizations (e.g. unlocking
and unpinning a buffer in one atomic operation)" [from-comment
`source/src/include/storage/buf_internals.h:303-310`].

`BufferDesc[]` is shared-memory; `NBuffers` of them, padded to 64-byte cache
lines via `BufferDescPadded` (on 64-bit hosts) [verified-by-code
`source/src/include/storage/buf_internals.h:381-387`]. The pointed-at
buffer pages live in a separate `BufferBlocks` array indexed by `buf_id`.

## 2. The packed state word — 64 bits

`state` is a single `pg_atomic_uint64` that combines four logical fields.
The widths are fixed by the `BUF_*_BITS` macros and a `StaticAssertDecl`
that their sum is ≤ 64 [verified-by-code
`source/src/include/storage/buf_internals.h:49-55`]:

| bits | width | meaning | macro |
|------|-------|---------|-------|
| 0..17  | 18 | shared refcount       | `BUF_REFCOUNT_BITS`, mask `BUF_REFCOUNT_MASK`        |
| 18..21 | 4  | usage count (clock)   | `BUF_USAGECOUNT_BITS`, shift `BUF_USAGECOUNT_SHIFT`  |
| 22..33 | 12 | flag bits             | `BUF_FLAG_BITS`, shift `BUF_FLAG_SHIFT`              |
| 34..63 | 20 | content-lock state    | `BUF_LOCK_BITS` (= 18 shared-count + 1 SE + 1 X)     |

[verified-by-code `source/src/include/storage/buf_internals.h:33-86`]

Helper macros:

- `BUF_REFCOUNT_ONE = 1` and `BUF_STATE_GET_REFCOUNT(state) = state & BUF_REFCOUNT_MASK`
  [verified-by-code `source/src/include/storage/buf_internals.h:58-91`].
- `BUF_USAGECOUNT_ONE = 1 << BUF_REFCOUNT_BITS` and
  `BUF_STATE_GET_USAGECOUNT(state) = (state & BUF_USAGECOUNT_MASK) >> BUF_USAGECOUNT_SHIFT`
  [verified-by-code `source/src/include/storage/buf_internals.h:62-93`].
- Flag macros emitted by `BUF_DEFINE_FLAG(n) = (1 << (BUF_FLAG_SHIFT + n))`
  [verified-by-code `source/src/include/storage/buf_internals.h:102-103`].
- Content-lock sub-bits: `BM_LOCK_VAL_SHARED` (one per shared holder, low
  18 bits of the lock field), `BM_LOCK_VAL_SHARE_EXCLUSIVE` (bit 18 of the
  lock field), `BM_LOCK_VAL_EXCLUSIVE` (bit 19), combined by `BM_LOCK_MASK`
  [verified-by-code `source/src/include/storage/buf_internals.h:77-86`].

`MAX_BACKENDS_BITS` is `StaticAssertDecl`-constrained to ≤ `BUF_REFCOUNT_BITS`
and ≤ `BUF_LOCK_BITS - 2` so the shared refcount and the shared-lock counter
can both index every backend [verified-by-code
`source/src/include/storage/buf_internals.h:130-133`].

Everything goes through `pg_atomic_fetch_*` / `pg_atomic_compare_exchange_*`
or the spinlock-via-state pattern (§4); the whole 64-bit word changes in one
atomic step.

## 3. Flag bits (12 bits, 11 defined, bit 6 unused)

[verified-by-code `source/src/include/storage/buf_internals.h:106-127`].
Values shown are the in-word values (already shifted by `BUF_FLAG_SHIFT = 22`).

| flag | flag-bit | in-word value | role |
|------|----------|---------------|------|
| `BM_LOCKED`               | 0  | `1 << 22` | header spinlock held |
| `BM_DIRTY`                | 1  | `1 << 23` | page contents differ from disk |
| `BM_VALID`                | 2  | `1 << 24` | page contents are valid (I/O succeeded) |
| `BM_TAG_VALID`            | 3  | `1 << 25` | hashtable entry exists for `tag` |
| `BM_IO_IN_PROGRESS`       | 4  | `1 << 26` | read or write in progress |
| `BM_IO_ERROR`             | 5  | `1 << 27` | previous I/O failed |
| *(unused)*                | 6  | —          | `/* flag bit 6 is not used anymore */` |
| `BM_PIN_COUNT_WAITER`     | 7  | `1 << 29` | one backend waiting for sole pin |
| `BM_CHECKPOINT_NEEDED`    | 8  | `1 << 30` | checkpointer should write this buffer |
| `BM_PERMANENT`            | 9  | `1 << 31` | permanent (logged) relation; gates `XLogFlush` |
| `BM_LOCK_HAS_WAITERS`     | 10 | `1 << 32` | content-lock has queued waiters |
| `BM_LOCK_WAKE_IN_PROGRESS`| 11 | `1 << 33` | waiter signalled but not yet run |

[verified-by-code `source/src/include/storage/buf_internals.h:105-127`].

Notes:

- `BM_TAG_VALID` "essentially means that there is a buffer hashtable entry
  associated with the buffer's tag" [from-comment
  `source/src/include/storage/buf_internals.h:98-100`].
- `BM_PERMANENT` distinguishes logged rels from unlogged / init-fork rels;
  `FlushBuffer` only `XLogFlush`es when it is set, because unlogged rels
  have "fake LSNs" from `XLogGetFakeLSN` that could outrun the WAL insert
  pointer [from-comment `source/src/backend/storage/buffer/bufmgr.c:4553-4569`].
- `BM_IO_INVALID` no longer exists. The previous distinction between
  "I/O failed" and "buffer dropped during I/O" has been collapsed; only
  `BM_IO_ERROR` remains.
- `BM_LOCK_HAS_WAITERS` / `BM_LOCK_WAKE_IN_PROGRESS` are new — they
  belong to the in-`state` content-lock machinery and exist because there
  is no LWLock layer to manage the waiter queue anymore.

## 4. Spinlock-via-state, and the "two locks" formerly two locks

Two distinct locks exist on a buffer, but **both now live in `state`**:

### 4.1 Buffer header spinlock — `BM_LOCKED`

PG doesn't use a separate spinlock per buffer descriptor — that would inflate
the struct. Instead `BM_LOCKED` is treated as a spinlock bit:

```
LockBufHdr(buf):
    fast path: pg_atomic_fetch_or_u64(&buf->state, BM_LOCKED)
    if old state already had BM_LOCKED, enter spin_delay loop and retry

UnlockBufHdr(buf):
    Assert(state & BM_LOCKED);
    pg_atomic_fetch_sub_u64(&buf->state, BM_LOCKED);

UnlockBufHdrExt(buf, old_state, set_bits, unset_bits, refcount_change):
    CAS loop: apply flag changes + refcount delta + clear BM_LOCKED in one step
```

[verified-by-code `source/src/include/storage/buf_internals.h:457-497`,
`source/src/backend/storage/buffer/bufmgr.c:7527-7593`]

Holding `BM_LOCKED` is a true spinlock — never sleep, never `ERROR` while
holding it. Hold for at most a few instructions. `LockBufHdr` asserts
`!BufferIsLocal(...)` [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:7531`]; local buffers manipulate
`state` with the unlocked atomic ops only.

Per-field rules (the giant comment block at `buf_internals.h:267-325`):

- `tag` may only be changed under header spinlock, but **may be read without
  it if the buffer is pinned** (a pinned buffer's tag is stable)
  [from-comment `source/src/include/storage/buf_internals.h:281-294`].
- Pin **release** is permitted while another backend holds the header
  spinlock — done via atomic subtraction [from-comment
  `source/src/include/storage/buf_internals.h:283-289`].
- `wait_backend_pgprocno` and `lock_waiters` require the header spinlock
  [from-comment `source/src/include/storage/buf_internals.h:346-358`].

### 4.2 Buffer content lock — top 20 bits of `state`

Protects the actual page bytes. Three modes, encoded as separate counter +
flag bits in `state`:

- `BUFFER_LOCK_SHARE` — adds `BM_LOCK_VAL_SHARED` to the shared count
- `BUFFER_LOCK_SHARE_EXCLUSIVE` — sets `BM_LOCK_VAL_SHARE_EXCLUSIVE`; new
  share readers can still join, but new exclusive is blocked (used by
  `FlushBuffer` so checkpoints don't block readers)
- `BUFFER_LOCK_EXCLUSIVE` — sets `BM_LOCK_VAL_EXCLUSIVE`

Acquire / release primitives (replacing the old `LWLockAcquire` paths):

- `BufferLockAcquire(buffer, buf_hdr, mode)` — CAS-attempts via
  `BufferLockAttempt`; on contention queues self on `lock_waiters` under
  the header spinlock, sets `BM_LOCK_HAS_WAITERS`, then
  `PGSemaphoreLock(MyProc->sem)` [verified-by-code
  `source/src/backend/storage/buffer/bufmgr.c:5907-6017`].
- `BufferLockRelease` / `BufferLockReleaseSub` — atomically subtract the
  mode-specific value; on contention edge, `BufferLockProcessRelease`
  dequeues and signals a waiter, using `BM_LOCK_WAKE_IN_PROGRESS` to
  suppress redundant wakeups [verified-by-code
  `source/src/backend/storage/buffer/bufmgr.c:6022-6045`].
- `BufferLockConditional(buffer, buf_hdr, mode)` — single-shot CAS;
  refuses if this backend already holds the lock because "we currently do
  not have space to track multiple lock ownerships of the same buffer
  within one backend" [from-comment
  `source/src/backend/storage/buffer/bufmgr.c:6051-6057`].
- `BufferLockHeldByMe(buf_hdr)` / `BufferLockHeldByMeInMode(buf_hdr, mode)`
  — interrogate the backend-local `PrivateRefCountEntry` state
  [verified-by-code `source/src/backend/storage/buffer/bufmgr.c:680-682`].

Public wrappers in `bufmgr.h`: `LockBuffer` (macro → `LockBufferInternal`),
`UnlockBuffer`, `ConditionalLockBuffer`, `LockBufferForCleanup`,
`ConditionalLockBufferForCleanup`, `BufferIsLockedByMe[InMode]`.

A backend can hold the content lock without holding the header spinlock,
and vice versa — they're separate fields within the same word, manipulated
by separate CAS / fetch operations. The big payoff of co-locating them is
that `UnpinBuffer` / unlock-and-unpin can happen in a single atomic op
[from-comment `source/src/include/storage/buf_internals.h:303-310`].

## 5. Pin vs lock vs cleanup-lock

A **pin** is a refcount increment in the low 18 bits. It prevents eviction
but grants no read/write rights. Multiple backends can simultaneously pin
and content-share the same buffer.

A **content lock** is the in-`state` 20-bit reader/writer coordination above.

A **cleanup lock** is `BUFFER_LOCK_EXCLUSIVE` plus refcount == 1 (only this
backend pins it). Required when compacting/reorganising tuples on a page
(e.g. VACUUM removing dead line pointers). Acquired via
`LockBufferForCleanup` / `ConditionalLockBufferForCleanup`
[verified-by-code `source/src/backend/storage/buffer/bufmgr.c:6678-6818,
6852-6899`].

## 6. The usage count (clock-sweep)

`usage_count` lives in bits 18..21, capped at `BM_MAX_USAGE_COUNT = 5`
[verified-by-code `source/src/include/storage/buf_internals.h:144-147`].
The clock-sweep walks the `BufferDesc` array in circular order, decrementing
usage counts and choosing the first one that reaches 0 (and is unpinned and
non-dirty) as the eviction victim.

Increments happen in `PinBuffer` only on the slow path — when the buffer was
not already pinned by this backend; repeat pins from the same backend only
bump the backend-local `PrivateRefCount` and never touch shared `state`
[verified-by-code `source/src/backend/storage/buffer/bufmgr.c:3280-3372`].

`UnlockBufHdrExt` cannot adjust usage count because the field needs capping
at `BM_MAX_USAGE_COUNT`, which a single CAS delta cannot express
[from-comment `source/src/include/storage/buf_internals.h:469-471`].

## 7. The `wait_backend_pgprocno` field

When a backend wants a cleanup lock but other backends still pin the buffer,
it writes its `MyProcNumber` into `wait_backend_pgprocno` and sets
`BM_PIN_COUNT_WAITER`, both under the header spinlock (via
`UnlockBufHdrExt`). It then releases the content lock and
`ProcWaitForSignal(WAIT_EVENT_BUFFER_CLEANUP)`s [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:6678-6818`].

`UnpinBuffer` calls `WakePinCountWaiter` when the post-unpin refcount is 1
and `BM_PIN_COUNT_WAITER` is set; that helper re-reads
`wait_backend_pgprocno` under header spinlock, clears the flag in one CAS,
and `ProcSendSignal(pgprocno)` [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:3429-3456, 5661`].

Only one waiter is allowed per buffer — `LockBufferForCleanup` `ERROR`s with
`"multiple backends attempting to wait for pincount 1"` if it sees
`BM_PIN_COUNT_WAITER` already set [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:6738-6743`].

## 8. I/O coordination

`BM_IO_IN_PROGRESS` is set by `StartSharedBufferIO` on a pinned buffer.
Three result values: `BUFFER_IO_READY_FOR_IO` (we own the I/O),
`BUFFER_IO_ALREADY_DONE` (someone finished it while we waited),
`BUFFER_IO_IN_PROGRESS` (someone else is doing it) [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:7250-7322`].

`WaitIO` uses the per-buffer `ConditionVariable` from `BufferIOCVArray`
(kept outside `BufferDesc` to control struct size, but moveable in
principle [from-comment `source/src/include/storage/buf_internals.h:322-324`])
and, for AIO, the buffer's `io_wref`. It re-reads `state` under
`LockBufHdr` each iteration because the spinlock is essential for
correctness here [from-comment
`source/src/backend/storage/buffer/bufmgr.c:7165-7170`].

`TerminateBufferIO` clears `BM_IO_IN_PROGRESS | BM_IO_ERROR` (and optionally
`BM_DIRTY | BM_CHECKPOINT_NEEDED`), applies caller's `set_flag_bits` (e.g.
`BM_VALID` after a successful read), broadcasts the CV, and — if
`release_aio` is true and the cleared state shows `BM_PIN_COUNT_WAITER` —
calls `WakePinCountWaiter` [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:7366-7413`].

If the I/O failed, `BM_IO_ERROR` is set; readers must retry. The old
`BM_IO_INVALID` flag has been removed — buffer-drop during I/O is now
handled without a distinct flag.

## 9. `BM_DIRTY` while writing — no separate JUST_DIRTIED flag

Older PG had a `BM_JUST_DIRTIED` interlock for "page was re-dirtied while a
write was in flight". In the current source, no such flag exists in the
flag block at `source/src/include/storage/buf_internals.h:106-127`
[verified-by-code]. The race is handled implicitly: `MarkBufferDirty`
requires `BUFFER_LOCK_EXCLUSIVE` and CAS-loops on `state` setting `BM_DIRTY`
[verified-by-code `source/src/backend/storage/buffer/bufmgr.c:3156-3205`];
`FlushBuffer` only requires `BUFFER_LOCK_SHARE_EXCLUSIVE` or stronger and
clears `BM_DIRTY` via `TerminateBufferIO(clear_dirty=true, ...)` after the
write succeeds [verified-by-code
`source/src/backend/storage/buffer/bufmgr.c:4520-4628`]. Because a
re-dirtier must hold `BUFFER_LOCK_EXCLUSIVE` while the writer holds at
least `BUFFER_LOCK_SHARE_EXCLUSIVE`, the two cannot overlap — eliminating
the need for an explicit re-dirty flag.

## 10. Glossary

- **Buffer**: an integer index into the shared buffer pool (1-based;
  0 = `InvalidBuffer`). External API uses this everywhere.
- **buf_id**: the 0-based array index; `buf_id = Buffer - 1`.
- **BufferDesc**: the metadata for a buffer (the struct above).
- **Pin**: refcount increment in `state` bits 0..17; prevents eviction.
- **Content lock**: reader/writer coordination encoded in `state` bits
  34..63. Modes: `BUFFER_LOCK_SHARE`, `BUFFER_LOCK_SHARE_EXCLUSIVE`,
  `BUFFER_LOCK_EXCLUSIVE`.
- **Cleanup lock**: content-exclusive lock with refcount = 1 (no other
  pinners).
- **Usage count**: 0–5 counter (bits 18..21) for clock-sweep eviction.
- **Header spinlock**: short-critical-section lock via the `BM_LOCKED`
  flag bit, acquired by `LockBufHdr`, released by `UnlockBufHdr` or
  `UnlockBufHdrExt`.
- **`lock_waiters`**: per-buffer proclist of backends waiting for the
  content lock; protected by the header spinlock.
- **`BM_LOCK_HAS_WAITERS` / `BM_LOCK_WAKE_IN_PROGRESS`**: tell
  `BufferLockRelease` whether anyone needs waking and whether a wake is
  already in flight.

## Synthesized by
<!-- backlinks:auto -->
- [files/src/include/storage/buf_internals.h.md](../files/src/include/storage/buf_internals.h.md)
- [files/src/backend/storage/buffer/bufmgr.c.md](../files/src/backend/storage/buffer/bufmgr.c.md)
