---
path: src/test/modules/test_shm_mq/worker.c
anchor_sha: e18b0cb7344
loc: 193
depth: read
---

# src/test/modules/test_shm_mq/worker.c

## Purpose

Worker side of the `test_shm_mq` module: the background-worker main
function that attaches to the test DSM segment, claims a worker slot,
attaches to its assigned input and output `shm_mq` queues, signals the
registrant backend that startup is complete, then loops echoing messages
in→out until the connection is broken. Demonstrates the recommended
shape for a parallel-computation worker. `[verified-by-code]`
`worker.c:38-47`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_shm_mq_main(Datum)` | `:49` | bgworker entry point — `main_arg` is the `dsm_handle` |

## Internal landmarks

- `BackgroundWorkerUnblockSignals()` (`:60`) — standard worker signal
  setup; uses default handlers.
- `dsm_attach` + `shm_toc_attach` (`:76-85`) — both bail with
  `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` on failure.
- Worker-number claim (`:95-102`) — spinlock-protected increment of
  `hdr->workers_attached`; fails if it overshoots `workers_total`.
- "Ready" signaling (`:118-127`) — increments `workers_ready` under
  spinlock, then `SetLatch(&registrant->procLatch)` to wake the parent;
  the registrant is looked up via `MyBgworkerEntry->bgw_notify_pid` +
  `BackendPidGetProc` (early exit `DEBUG1` if the registrant already
  died).
- `attach_to_queues` (`:149`) — convention: worker `n` reads queue `n`
  and writes queue `n+1`; user backend writes to queue 1 and reads from
  queue `nworkers+1` (`[from-comment]` `:143-148`).
- `copy_messages` (`:171`) — blocking `shm_mq_receive` / `shm_mq_send`
  loop with `CHECK_FOR_INTERRUPTS` between operations; exits on any
  non-success result (typically `SHM_MQ_DETACHED`).

## Invariants & gotchas

- TEST MODULE — never use in production. Worker entry point only.
- No `ResourceOwner` is created in this process — DSM mapping survives
  to process exit, which is fine here `[from-comment]` `:71-74`.
- `proc_exit(1)` always exits with status 1, even on success path
  (`:137`) — the framework treats this as normal worker termination.
- The "ready" handshake guarantees that once the worker signals ready,
  its `on_dsm_detach` callbacks will fire before disconnect — caller can
  assume orderly teardown `[from-comment]` `:109-117`.

## Cross-refs

- `knowledge/files/src/test/modules/test_shm_mq/setup.c.md` — registrant
  side that allocates the segment and launches workers.
- `knowledge/files/src/test/modules/test_shm_mq/test_shm_mq.h.md` — the
  shared header struct.
- `source/src/include/storage/shm_mq.h` — message queue API.
- `source/src/include/storage/shm_toc.h` — table-of-contents API.
- `knowledge/subsystems/bgworker-and-extensions.md` — worker lifecycle.
