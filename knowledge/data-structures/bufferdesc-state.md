# BufferDesc — state-encoding bits

- **Source path:** `source/src/include/storage/buf_internals.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion docs:** `knowledge/files/src/include/storage/buf_internals.h.md`,
  `knowledge/subsystems/storage-buffer.md`, `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`

## 1. The struct

```c
typedef struct BufferDesc {
    BufferTag       tag;            // rel + fork + block#
    pg_atomic_uint32 state;         // packed: refcount + usagecount + flags
    int             buf_id;         // index into shared buffer pool
    int             wait_backend_pgprocno;
    int             freeNext;
    LWLock          content_lock;
} BufferDesc;
```

[verified-by-code source/src/include/storage/buf_internals.h]

`BufferDesc[]` is shared-memory; `NBuffers` of them; pointed at the
`shared_buffers`-byte buffer pool via `buf_id`.

## 2. The packed state word — 32 bits

`state` is a single `pg_atomic_uint32` that packs three fields plus 8 flag
bits. Layout (low-to-high):

```
bits  0..17 (18 bits): BufferDesc-private refcount        max  262143
bits 18..21 ( 4 bits): usage count (clock-sweep)          max      31 (actually capped at BM_MAX_USAGE_COUNT=5)
bits 22..23 ( 2 bits): unused
bits 24..31 ( 8 bits): flags (one bit each)
```

The 8 flag bits are:

```
BM_LOCKED               // someone holds the buffer header spinlock (via state)
BM_DIRTY                // buffer page is dirty
BM_VALID                // page contents are valid
BM_TAG_VALID            // the BufferTag is populated (not free)
BM_IO_IN_PROGRESS       // I/O is happening; do not touch the page
BM_IO_ERROR             // last I/O failed
BM_JUST_DIRTIED         // dirty bit set during I/O; must re-dirty
BM_PIN_COUNT_WAITER     // someone is waiting on the wait_backend_pgprocno field
BM_CHECKPOINT_NEEDED    // checkpointer should write this buffer
BM_IO_INVALID           // similar to IO_ERROR but caused by buffer drop, not failure
BM_PERMANENT            // (unlogged-table marker: relation is permanent)
```

[verified-by-code `buf_internals.h:38-66`]

Everything goes through `pg_atomic_fetch_*` or the LockBufHdr spinlock-via-state
pattern; the whole word changes in one atomic step.

## 3. The spinlock-via-state pattern

PG doesn't use a separate spinlock per buffer descriptor — it would double
the size of `BufferDesc`. Instead `BM_LOCKED` is treated as a spinlock bit:

```
LockBufHdr(buf):
    do {
        state = pg_atomic_read_u32(&buf->state)
        if (state & BM_LOCKED) { spin_delay(); continue; }
    } while (!pg_atomic_compare_exchange_u32(&buf->state, &state, state | BM_LOCKED));

UnlockBufHdr(buf, new_state):
    pg_atomic_write_u32(&buf->state, new_state & ~BM_LOCKED);
```

Holding `BM_LOCKED` is a true spinlock — never sleep, never `ERROR` while
holding it. Hold for at most a few instructions. [verified-by-code
`buf_internals.h` `LockBufHdr` macro family]

## 4. Two different "locks" on a buffer

Critical confusion-source for new readers — a buffer has TWO independent locks:

- **Buffer header spinlock** (`BM_LOCKED` bit, above) — protects only the
  `BufferDesc` metadata. Very short critical sections. Held during
  buffer-allocation hashtable lookups and during state transitions.
- **Buffer content LWLock** (`content_lock`) — protects the actual page
  contents. Acquired SHARED for reads, EXCLUSIVE for writes. Can be held
  for an arbitrarily long time (e.g. across a tuple-level update).

A backend can hold the content LWLock without holding the header spinlock,
and vice versa. They synchronize different things.

## 5. Pin vs lock

A **pin** is a refcount increment. It prevents the buffer from being
evicted but says nothing about who can read or write the page. Multiple
backends can have pinned and content-shared the same buffer simultaneously.

A **content lock** is a read/write coordination over the page bytes.

A **cleanup lock** is a content lock acquired exclusive AND with refcount=1
(only this backend has it pinned). Required when you're about to compact or
reorganize tuples on a page (e.g. VACUUM removing dead line pointers).

[verified-by-code `bufmgr.c` `LockBufferForCleanup`, `ConditionalLockBufferForCleanup`]

## 6. The usage count (clock-sweep)

`usage_count` is bumped on pin, capped at `BM_MAX_USAGE_COUNT` (5). The
clock-sweep walks the BufferDesc array in circular order, decrementing usage
counts and choosing the first one that reaches 0 (and is unpinned and
non-dirty) as the eviction victim.

[verified-by-code `freelist.c.md`]

Increments happen in `PinBuffer` only on the slow path (when the buffer was
not already pinned by this backend); they don't happen on every tuple read.

## 7. The wait_backend_pgprocno field

When a backend wants to acquire a cleanup lock but other backends have the
buffer pinned, it stores its PGPROC number in `wait_backend_pgprocno` and
sets `BM_PIN_COUNT_WAITER`. Other backends, on `UnpinBuffer`, check this
flag and wake the waiter via `SetLatch`. Only one waiter at a time —
`LockBufferForCleanup` must spin on `ConditionalLockBufferForCleanup` if
`BM_PIN_COUNT_WAITER` is already set.

[verified-by-code `bufmgr.c` `LockBufferForCleanup`]

## 8. I/O coordination

`BM_IO_IN_PROGRESS` is set under header spinlock by whoever starts a read
or write. Other backends seeing this flag wait via `WaitIO`, which uses a
LWLock owned by `BufferIOLWLockArray[buf_id % NUM_BUFFER_PARTITIONS]`.
After I/O completes, the I/O-starter clears `BM_IO_IN_PROGRESS` and
LWLockRelease wakes any waiters.

If the I/O failed, `BM_IO_ERROR` is set; readers must retry.

[verified-by-code `bufmgr.c` `WaitIO`, `StartBufferIO`, `TerminateBufferIO`]

## 9. The BM_JUST_DIRTIED interlock

If a backend dirties a buffer while I/O is in progress (someone is writing
the previous version to disk), `BM_JUST_DIRTIED` is set. After the I/O
completes, the I/O-starter checks this flag: if set, it re-dirties the
buffer so it gets written again. Without this, a write that races a dirty
could leave a dirty-in-memory but clean-on-disk state, and the dirty edit
would be lost on the next eviction.

## 10. Glossary

- **Buffer**: an integer index into the shared buffer pool (1-based;
  0 = `InvalidBuffer`). External API uses this everywhere.
- **buf_id**: the 0-based array index; `buf_id = Buffer - 1`.
- **BufferDesc**: the metadata for a buffer (the struct above).
- **Pin**: refcount increment; prevents eviction.
- **Content lock**: LWLock protecting page bytes.
- **Cleanup lock**: content-exclusive lock with refcount=1 (no other pinners).
- **Usage count**: 0-5 counter for clock-sweep eviction.
- **Header spinlock**: short-critical-section lock via `BM_LOCKED` bit.
- **BM_JUST_DIRTIED**: re-dirty interlock for writes racing edits.
