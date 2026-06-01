# `storage/ipc/shm_mq.c`

- **Source:** `source/src/backend/storage/ipc/shm_mq.c` (1330 lines)
- **Header:** `source/src/include/storage/shm_mq.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

**Single-reader, single-writer shared-memory message queue.** A pipe-like
construct sitting inside a region of (usually) DSM. Primary user:
parallel query (leader ↔ worker tuple stream).

> "Both the sender and the receiver must have a PGPROC; their respective
> process latches are used for synchronization." [from-comment] `:5-9`.

## Concurrency model

The big idea (`:31-71`):
- `mq_bytes_read` (cursor) is written only by the receiver, read by
  both.
- `mq_bytes_written` (cursor) is written only by the sender, read by
  both.
- Both are read/written **without any lock** as atomic uint64s; only
  `pg_memory_barrier` discipline.
- `mq_receiver` / `mq_sender` (PGPROC pointers) are set under `mq_mutex`
  spinlock but **immutable once set**, so further reads need no lock.
- `mq_detached` — also lock-free; only ever flips false→true.

### Producing and consuming bytes

The ring buffer `mq_ring[mq_ring_size]` at offset `mq_ring_offset`:
- Unread bytes occupy `[mq_bytes_read, mq_bytes_written)`.
- The sender can write to slots ≥ `mq_bytes_written` (the unused part)
  without locking — only the sender writes there. The receiver bumps
  `mq_bytes_read` to give the sender more room.
- The receiver reads `[mq_bytes_read, mq_bytes_written)` without
  locking — those bytes are stable because only the sender can extend
  the range, and after the sender extends it, a barrier-published
  `mq_bytes_written` precedes the data.

The discipline: writer does `memcpy → pg_write_barrier →
atomic_add(mq_bytes_written, n)`; reader does `atomic_read(mq_bytes_written)
→ pg_read_barrier → memcpy → atomic_add(mq_bytes_read, n)`.

## Latch wakeups

When sender writes and the receiver might be sleeping, sender calls
`SetLatch(receiver->procLatch)`. Same in reverse. The detach flag
+ counterparty latch is how a process learns its peer is gone.
`[from-comment] :47-52`: setting `mq_detached` then setting the
counterparty's latch is safe because `SetLatch` begins with a memory
barrier.

## API

- `shm_mq_create(addr, size)` — initialize the queue at given address
  (caller must arrange the memory; typically via `shm_toc`).
- `shm_mq_set_sender(mq, proc)` / `shm_mq_set_receiver(mq, proc)` —
  must be called before send/receive.
- `shm_mq_attach(mq, seg, handle)` — returns a `shm_mq_handle` tied
  to a `dsm_segment` and the optional `BackgroundWorkerHandle` (so
  detach gets noticed if the worker dies before attaching).
- `shm_mq_send(handle, nbytes, data, nowait, force_flush)` —
  result: `SHM_MQ_SUCCESS`, `SHM_MQ_WOULD_BLOCK`, `SHM_MQ_DETACHED`.
- `shm_mq_receive(handle, nbytesp, datap, nowait)` — gives a pointer
  *into* the ring buffer (zero-copy if message doesn't wrap; otherwise
  a per-handle bounce buffer is used).
- `shm_mq_wait_for_attach(handle)` — block until peer is set.
- `shm_mq_detach(handle)` — set `mq_detached`, wake peer.

## Message framing

Messages are length-prefixed: `uint64 nbytes` followed by `nbytes`
bytes of payload. The send/receive code handles the case where the
message wraps around the ring end by copying into a `mqh_buffer`
private to the handle.

## Detach semantics

- Receiver detaches: sender's next `send` returns `SHM_MQ_DETACHED`.
- Sender detaches: receiver consumes any pending bytes, then next
  `receive` returns `SHM_MQ_DETACHED`.
- Background worker dies without explicit detach: the
  `BackgroundWorkerHandle` machinery in `bgworker.c` detects the death
  and the queue's `dsm_segment` callback marks it detached.

## Cross-references

- `dsm.c` — segments hosting the queue.
- `shm_toc.c` — typically used to find queue offsets inside a parallel
  DSM.
- `access/parallel.c` — wraps a queue per worker for error message
  propagation; the executor also uses these to ship tuples.
- `libpq/pqmq.c` — bridges shm_mq into the libpq protocol machinery
  (so a worker can `pq_putmessage` and have it land in a queue
  consumed by the leader).

## Open questions

1. The zero-copy receive returns a pointer *into the ring*; the caller
   must not advance `mq_bytes_read` until done with the pointer. The
   API requires another `shm_mq_receive` call (or detach) to indicate
   the previous message is consumed; that's the standard pattern but I
   didn't verify whether the wrap-bounce-buffer makes that pointer
   stable across re-entry. `[unverified]`.
2. **Atomic 64-bit ops on 32-bit platforms** — the comment at
   `:42-46` says "they are written atomically using 8 byte loads and
   stores". On platforms where `pg_atomic_uint64` falls back to a
   spinlock-emulation, this is still "atomic" but performance-different.
   `[from-comment]`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
