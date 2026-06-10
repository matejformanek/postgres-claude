# src/include/commands/repack_internal.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 124 [verified-by-code]

## Role

Internal protocol between the REPACK-driving backend and its dedicated
logical-decoding bgworker. Defines the on-disk change format and the
shared-memory handshake.

## Public API

- `ConcurrentChangeKind` = `char` — `CHANGE_INSERT 'i'`,
  `CHANGE_UPDATE_OLD 'u'`, `CHANGE_UPDATE_NEW 'U'`, `CHANGE_DELETE 'd'`
  (`:27-32`).
- `RepackDecodingState` — output plugin state holding `change_cxt`
  memory context, a `TupleTableSlot`, the worker's `worker_cxt` and
  `worker_resowner`, and the current `BufFile *` output file (`:40-61`).
- `DecodingWorkerShared` — shared-memory control block:
  - `initialized` flag, `lsn_upto` (XLogRecPtr the worker must stop
    at), `done` flag, `SharedFileSet sfs`, `last_exported` file seq,
    `slock_t mutex`, `dbid`, `roleid`, `relid`,
    `ConditionVariable cv`, backend `PGPROC*` + pid +
    ProcNumber, fixed-size `error_queue[FLEXIBLE_ARRAY_MEMBER]` of
    `REPACK_ERROR_QUEUE_SIZE = 16384` (`:67-119`).
- `DecodingWorkerFileName(char *fname, Oid relid, uint32 seq)`
  (`:121`).

## Invariants

- INV-REPACK-MUTEX-SCOPE: the `slock_t mutex` (`:92`) protects
  `initialized`, `lsn_upto`, `done`, `last_exported`. Access without
  holding it is a race; the spinlock-vs-CV split is the same pattern
  as `parallel.c`.
- INV-REPACK-CV-BACKEND: the `ConditionVariable cv` (`:104`) is owned
  by the backend, signalled by the worker when it has flushed a new
  output file. Standard CV protocol — wait under prepare/sleep.
- INV-REPACK-LSN-SENTINEL: `lsn_upto == InvalidXLogRecPtr` means
  "keep decoding indefinitely" (`:75-79` [from-comment]); any valid
  LSN tells the worker to close-and-stop (or close-and-continue per
  `done`).
- INV-ERROR-QUEUE-SIZE: 16384 bytes — comment cross-references
  `PARALLEL_ERROR_QUEUE_SIZE` in `parallel.c` (`:112-117`); change
  one and the other should match.

## Notable internals

- `BufFile *file` (`:60`) — the output is sequential per file; the
  worker rotates to new files when `lsn_upto` is reached. The backend
  reads them in order during the catch-up phase.
- The `roleid` field (`:98`) lets the worker `SetUserId` to the
  REPACK invoker — necessary so RLS / row-level security applies
  consistently between the driver and the decoder.
- `relid` redundant with backend's parameter but kept for assertion
  in the worker.

## Trust boundary / Phase D surface

- **A8 / A14 logical-decoding echo.** The decoding worker has full
  WAL access for the duration; it reads the WAL stream for a single
  relation but the API surface doesn't enforce that — a bug in
  `decode.c`'s filter could leak inserts to OTHER relations into the
  output files. The on-disk output (`BufFile`) is in
  `pg_replslot/<slot>` style storage with the executor's role mode —
  files are world-readable inside the data directory.
- **Shared-memory protocol.** `DecodingWorkerShared` lives in a DSM
  segment attached by both backend and worker. A backend crashed
  mid-REPACK leaves the worker waiting on `cv` — `done=true` cleanup
  required from postmaster's death handling.
- **Error queue.** 16 KB shm_mq for the worker to propagate ereport
  back to the backend (parallel-worker pattern). An attacker process
  attached to the DSM (not possible without backend privilege, but
  worth flagging) could DoS by filling the queue.
- **Privilege bracket.** `roleid` is trusted — sourced from
  `GetUserId()` at REPACK start. If somehow set by an untrusted
  party, the worker would SetUserId to the wrong role.

## Cross-references

- `commands/repack.h` — driver-side API.
- `replication/decode.h`, `replication/logical.h` — output plugin
  framework.
- `storage/shm_mq.h`, `storage/sharedfileset.h` — DSM + temp-file
  set.
- `storage/condition_variable.h` — `cv` semantics.
- Sibling: `access/parallel.h` for the parallel-error-queue pattern.

## Issues / drift

- `[ISSUE-TRUST: A14 — decoding worker output files in pg_replslot are not encrypted; A8 logical-replication path inherits this (medium)] — source/src/include/commands/repack_internal.h:67-119`
- `[ISSUE-CODE: REPACK_ERROR_QUEUE_SIZE hard-coded; should reuse PARALLEL_ERROR_QUEUE_SIZE macro (low)] — source/src/include/commands/repack_internal.h:112-117`
- `[ISSUE-TRUST: roleid field is trusted but not validated against current process credentials at worker startup; relies on shm being inaccessible to non-PG processes (low)] — source/src/include/commands/repack_internal.h:97-98`
