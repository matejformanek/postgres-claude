# pqmq.h

- **Source path:** `source/src/include/libpq/pqmq.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Use the frontend/backend protocol for communication over a shm_mq" —
lets a parallel worker pretend to be a client and ship NotifyResponse /
ErrorResponse / progress messages to the leader through a shared-memory
message queue [from-comment].

## Public API surface

- `void pq_redirect_to_shm_mq(dsm_segment *seg, shm_mq_handle *mqh)` —
  swap `PqCommMethods` so subsequent `pq_putmessage` calls write to the
  given shm_mq instead of the client socket.
- `void pq_set_parallel_leader(pid_t pid, ProcNumber procNumber)` —
  identify the leader for routing.
- `void pq_parse_errornotice(StringInfo msg, ErrorData *edata)` — leader
  side: turn a received ErrorResponse/NoticeResponse back into an
  `ErrorData` for re-`ereport`.

## Cross-refs

- Related backend: `src/backend/libpq/pqmq.c`.
- Related: `knowledge/files/src/include/libpq/libpq.h.md` (`PQcommMethods`
  dispatch table this header swaps).
- Related: `storage/shm_mq.h`, `access/parallel.c`.

## Tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
