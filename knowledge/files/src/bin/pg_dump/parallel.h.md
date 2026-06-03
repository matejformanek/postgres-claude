---
path: src/bin/pg_dump/parallel.h
anchor_sha: 4b0bf0788b0
loc: 85
depth: read
---

# parallel.h

- **Source path:** `source/src/bin/pg_dump/parallel.h`
- **Lines:** 85
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `parallel.c` (implementation), `pg_backup_archiver.h` (`ArchiveHandle`, `TocEntry`, `T_Action`), `<limits.h>` (for `INT_MAX`).

## Purpose

Public surface for the `-j N` worker pool. Declares the `ParallelCompletionPtr` callback type, the `WFW_WaitOption` enum, `PG_MAX_JOBS` cap, the opaque `ParallelSlot` forward decl, the visible `ParallelState` struct, and the six extern entry points. [verified-by-code, parallel.h:14-85]

## Public types

- `ParallelCompletionPtr` (24) — `void(*)(ArchiveHandle *AH, TocEntry *te, int status, void *callback_data)`. Called by the leader when a worker reports completion. [verified-by-code, parallel.h:23-27]
- `WFW_WaitOption` (30-36) — `NO_WAIT | GOT_STATUS | ONE_IDLE | ALL_IDLE`. [verified-by-code, parallel.h:30-36]
- `PG_MAX_JOBS` (45-49) — `MAXIMUM_WAIT_OBJECTS` (= 64 typically) on Windows; `INT_MAX` elsewhere. [from-comment, parallel.h:39-44]
- `ParallelSlot` (52) — forward-declared opaque; full definition in `parallel.c:95`. [verified-by-code, parallel.h:51-52]
- `ParallelState` (55-61) — `{int numWorkers; TocEntry **te; ParallelSlot *parallelSlot;}`. The `te[]` and `parallelSlot[]` arrays have `numWorkers` entries each. [verified-by-code, parallel.h:54-61]

## Public surface

- `init_parallel_dump_utils()` (68).
- `IsEveryWorkerIdle(pstate)` (70).
- `WaitForWorkers(AH, pstate, mode)` (71).
- `ParallelBackupStart(AH)` (74).
- `DispatchJobForTocEntry(AH, pstate, te, act, callback, callback_data)` (75).
- `ParallelBackupEnd(AH, pstate)` (81).
- `set_archive_cancel_info(AH, conn)` (83) — exposed because pg_backup_db.c (re-)wires `connCancel` whenever a connection is opened or reset, even outside parallel mode.

[verified-by-code, parallel.h:68-83]

## Windows-only externs

- `parallel_init_done` (64) — guards re-entry into `init_parallel_dump_utils`. Also referenced inside `getThreadLocalPQExpBuffer` (parallel.c:301) — before this flag is set, the static `s_id_return` is used; after, TLS. [verified-by-code, parallel.h:63-66, parallel.c:301-318]
- `mainThreadId` (65) — captured in `init_parallel_dump_utils`; used by `set_archive_cancel_info` to decide whether to overwrite `signal_info.myAH`. [verified-by-code, parallel.c:248, 789]

## Phase D — surfaces of concern

- **`numWorkers` is the per-pool cap, not a global cap.** A future invocation that creates multiple ParallelStates would multiply worker count; nothing in this header guards against that. Today there is exactly one pstate per pg_dump run. [verified-by-code, parallel.h:55-61] [no concern]
- **No prototype for an "abort one worker" path.** The only termination paths are `ShutdownWorkersHard` (internal) and natural EOF on pipe close. A long-running CREATE INDEX in a worker can be cancelled only via process-wide signal → forwarded to all workers. [verified-by-code, parallel.c:411-456, 1083-1094] [no concern]
- **`PG_MAX_JOBS = INT_MAX` on Unix** with no soft cap. pg_dump.c parses `-j` and clamps to >= 1 but does NOT clamp to a reasonable upper bound. A 100000-worker request would `fork` 100000 times. [verified-by-code, parallel.h:48] [maybe — DoS surface only against the local machine]

## Cross-references

- Implementation: `knowledge/files/src/bin/pg_dump/parallel.c.md`.

## Confidence tag tally
`[verified-by-code]=11 [from-comment]=1 [maybe]=1 [no concern]=2`
