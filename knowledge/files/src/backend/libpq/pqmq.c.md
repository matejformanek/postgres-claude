---
path: src/backend/libpq/pqmq.c
anchor_sha: 9a60f295bcb1
loc: 342
depth: medium
---

# pqmq.c

- **Source path:** `source/src/backend/libpq/pqmq.c`
- **Last verified commit:** `9a60f295bcb1`
- **LOC:** 342

## Purpose

Bridges the libpq frontend/backend wire protocol over a `shm_mq` shared-memory
queue, so that a parallel worker / logical-apply worker / repack worker can
"send" protocol messages (errors, notices, tuples) to its leader exactly as
if it were talking to a real client socket. Implements the `PQcommMethods`
vtable just like `pqcomm.c` does for sockets. [from-comment, pqmq.c:1-12]

## Public API surface

| Line | Symbol | Semantics |
|---|---|---|
| 56 | `pq_redirect_to_shm_mq(seg, mqh)` | Replace `PqCommMethods` with the shm_mq vtable; register a `dsm_detach` callback. |
| 85 | `pq_set_parallel_leader(pid, procNumber)` | After redirect, name the leader to SIGUSR1 on each putmessage. |
| 228 | `pq_parse_errornotice(msg, edata)` | Reverse of `send_message_to_frontend` — turn an ErrorResponse/NoticeResponse payload back into an `ErrorData` on the leader side. |

## Internal landmarks

- File-static state:
  - `pq_mq_handle` (29) — the active `shm_mq_handle *`, NULL when none.
  - `pq_mq_busy` (30) — reentrancy guard; if a putmessage interrupts
    itself we detach instead of recursing. [verified-by-code, pqmq.c:138-147]
  - `pq_mq_parallel_leader_pid`, `pq_mq_parallel_leader_proc_number` (31-32) —
    where to SendProcSignal after each send.
- `PqCommMqMethods` vtable (42): only `putmessage` and `putmessage_noblock`
  are non-trivial; `comm_reset` / `flush` / `flush_if_writable` /
  `is_send_pending` are all no-ops because shm_mq has no buffer to flush.
  [verified-by-code, pqmq.c:42-117]
- `pq_cleanup_redirect_to_shm_mq` (69) — registered with `on_dsm_detach`;
  zeroes `pq_mq_handle` and sets `whereToSendOutput = DestNone` so later
  `elog`s during shutdown become no-ops. [verified-by-code, pqmq.c:69-78]
- `mq_putmessage` (125): wraps the 1-byte msg-type and the payload in a
  2-elt `shm_mq_iovec`, deliberately *omits* the 4-byte length prefix —
  receiver reads the whole record length from `shm_mq_receive()`.
  [from-comment, pqmq.c:120-123]
- After every `shm_mq_sendv`, signal the leader via `SendProcSignal` with
  the right `PROCSIG_*` for the worker flavour:
  `PROCSIG_PARALLEL_APPLY_MESSAGE` (logical apply),
  `PROCSIG_REPACK_MESSAGE` (repack worker),
  `PROCSIG_PARALLEL_MESSAGE` (everything else; asserted to be parallel
  worker). [verified-by-code, pqmq.c:175-192]

## Invariants & gotchas

- **No length prefix on the wire.** The wire bytes here are NOT the
  standard libpq framing; `mq_putmessage` ships just `<msgtype><payload>`,
  trusting `shm_mq_receive` boundary. Anyone reading these queues raw is
  in for a surprise. [from-comment, pqmq.c:120-123]
- **Reentrancy → detach, not retry.** If a putmessage blocks (queue
  full), then an interrupt fires, and that interrupt tries to send another
  message (typical: a CHECK_FOR_INTERRUPTS during sendv handles an error
  that wants to ereport), we *detach the queue* and return EOF. There is
  no "queue + replay" option. [from-comment, pqmq.c:130-137]
- **`pq_mq_handle == NULL` is benign.** "DEBUG messages can be generated
  late in the shutdown sequence, after all DSMs have already been
  detached" — so the put is just silently dropped, returning 0. [from-comment, pqmq.c:149-156]
- `mq_putmessage_noblock` is **not supported** — calls `elog(ERROR)`.
  shm_mq's "begin non-blocking send" API doesn't permit partial commits.
  [from-comment, pqmq.c:213-221]
- `pq_parse_errornotice` (228) is the *receiver* side. Severity is parsed
  from `PG_DIAG_SEVERITY_NONLOCALIZED`; the localised severity is ignored
  (trusting the worker speaks the leader's protocol version). The
  function ereports `ERROR` on unrecognised severity / bad SQLSTATE / bad
  field code — meaning a malformed worker message kills the leader's
  current statement. [verified-by-code, pqmq.c:251-340]
- The DEBUG-level remap "we can't reconstruct the exact DEBUG level…
  presumably it was >= client_min_messages, so select DEBUG1 to ensure
  we'll pass it on" is a quiet correctness compromise: a DEBUG5 from a
  parallel worker reaches the client as DEBUG1. [from-comment, pqmq.c:255-263]

## Cross-refs

- Header: `source/src/include/libpq/pqmq.h`
- Vtable peer: `source/src/backend/libpq/pqcomm.c` (`PqCommSocketMethods`)
- shm_mq impl: `source/src/backend/storage/ipc/shm_mq.c`
- Leader-side consumer: `source/src/backend/access/transam/parallel.c`
  (`HandleParallelMessages`)

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: silent DEBUG-level downgrade across parallel boundary]**
  `pqmq.c:255-263` — a parallel worker DEBUG5 reaching the leader becomes
  DEBUG1, so it WILL be sent to the client even if the client requested
  only LOG. Effectively `client_min_messages` is partially bypassed for
  parallel-worker debug output. Probably intentional ("at most one round
  trip"), but undocumented. severity: maybe
- **[ISSUE-correctness: SHM_MQ_DETACHED treated as success]** `pqmq.c:205-207`
  — `Assert(result == SHM_MQ_SUCCESS || result == SHM_MQ_DETACHED)` then
  returns EOF only on non-success. SHM_MQ_DETACHED is logged as EOF and
  silently dropped; callers do not get a distinct error. Likely fine, but
  obscures genuine queue-detach during transmit. severity: nit
- **[ISSUE-undocumented-invariant: SendProcSignal happens BEFORE checking
  the send result for retry]** `pqmq.c:172-194` — we always signal the
  leader, even if `shm_mq_sendv` returned WOULD_BLOCK (no new data
  visible). A spurious signal is cheap, but it does invert the
  produce-then-notify ordering most readers assume. severity: nit

## Tally

`[verified-by-code]=11 [from-comment]=6 [inferred]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
