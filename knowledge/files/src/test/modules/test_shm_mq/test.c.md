---
path: src/test/modules/test_shm_mq/test.c
anchor_sha: e18b0cb7344
loc: 275
depth: read
---

# src/test/modules/test_shm_mq/test.c

## Purpose

SQL-callable harness for the `test_shm_mq` module. Two functions:
`test_shm_mq` exercises the **blocking** `shm_mq_send` / `shm_mq_receive`
APIs by passing a message around a ring of workers a configurable number
of times; `test_shm_mq_pipelined` exercises the **non-blocking**
variants by sending N copies in flight and receiving them as they come
back. `[verified-by-code]` `test.c:36-43,123-131`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_shm_mq(queue_size, message, loop_count, nworkers)` | `:45` | Blocking round-trip test |
| `test_shm_mq_pipelined(queue_size, message, loop_count, nworkers, verify)` | `:134` | Non-blocking pipelined test (workers may be 0) |

## Internal landmarks

- `test_shm_mq` (`:45`) — calls `test_shm_mq_setup` to spawn workers,
  sends one message, then enters a `loop_count` iteration loop of
  receive→send; final iteration just receives and `verify_message`s the
  bytes (`:111-115`).
- `test_shm_mq_pipelined` (`:134`) — tracks `send_count` /
  `receive_count` independently, alternates non-blocking send and
  non-blocking receive in a `wait`-flag-driven loop; sleeps on a custom
  wait event `we_message_queue` registered as
  `WaitEventExtensionNew("TestShmMqMessageQueue")` (`:233-235`).
- `verify_message` (`:259`) — compares length and bytes; reports the
  mismatching byte index in `errdetail` when corruption is detected.

## Invariants & gotchas

- TEST MODULE — never load in production.
- `test_shm_mq` requires `nworkers >= 1` because the blocking API
  cannot send to itself (`[from-comment]` `:66-69`); `test_shm_mq_pipelined`
  allows `nworkers == 0` (the message just loops the single queue with
  the caller writing and reading the ring's only segment).
- The pipelined variant requires that the *same* message size and
  contents be presented on every retry after `SHM_MQ_WOULD_BLOCK`
  (`[from-comment]` `:177-180`).
- `verify` is optional in pipelined mode because per-message verification
  serializes throughput (`[from-comment]` `:206-208`).
- A consistency check at end of pipelined run asserts
  `send_count == receive_count` and panics if they disagree (`:223-227`).

## Cross-refs

- `knowledge/files/src/test/modules/test_shm_mq/setup.c.md` — DSM and
  worker registration.
- `knowledge/files/src/test/modules/test_shm_mq/worker.c.md` — worker
  side echoing the messages.
- `source/src/include/storage/shm_mq.h` — `shm_mq_send`,
  `shm_mq_receive`, `SHM_MQ_*` result codes.
