---
path: src/bin/pg_dump/parallel.c
anchor_sha: f25a07b2d94c
loc: 1803
depth: deep
---

# parallel.c

- **Source path:** `source/src/bin/pg_dump/parallel.c`
- **Lines:** 1803
- **Last verified commit:** `f25a07b2d94c`
- **Companion files:** `parallel.h` (the `ParallelState`, `ParallelCompletionPtr`, `WFW_*` enum, `PG_MAX_JOBS` cap), `pg_backup_archiver.c` (caller of `ParallelBackupStart`/`DispatchJobForTocEntry`/`ParallelBackupEnd`/`WaitForWorkers`), `pg_backup_db.c` (`CloneArchive`, `DisconnectDatabase`).

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** re-pinned
> from `4b0bf0788b0` to `f25a07b2d94c`. Upstream commit `7ca548f23a60`
> ("Revert non-text output formats for pg_dumpall") removed the
> `replace_on_exit_close_archive` helper that the reverted dumpall-archive
> multi-DB restore used to swap the on-exit cleanup hook between
> per-database restores. That deleted ~14 lines around old line 345, so
> every cite below line 345 is unchanged and every cite above it shifted
> down by 14. All line numbers re-verified.

## Purpose

The `-j N` worker pool implementation, with two divergent runtime models:

- **Unix:** `fork()` per worker; each worker is a separate process with its own libpq connection. Communication is via `pipe(2)`. Signal handling via `SIGTERM`/`SIGINT`/`SIGQUIT` handlers that forward to children.
- **Windows:** threads (`_beginthreadex`); communication via socketpair-style pipes built on top of TCP loopback (the `pgpipe` shim at line 1721). Cancellation via `SetConsoleCtrlHandler` running in its own thread plus a critical section guarding `signal_info`.

[from-comment, parallel.c:16-51]

## Public surface

- `init_parallel_dump_utils()` (238) — `WSAStartup` + `TlsAlloc` on Windows; no-op on Unix. [verified-by-code, parallel.c:237-258]
- `on_exit_close_archive(AHX)` (330) — wire the cleanup callback. (The `replace_on_exit_close_archive` helper that briefly existed for pg_dumpall-archive multi-DB restore was removed with the `7ca548f23a60` revert.) [verified-by-code, parallel.c:330-339]
- `set_archive_cancel_info(AH, conn)` (732) — set/clear the `connCancel` used by signal handlers. On Windows, guarded by critical section against the signal thread. [verified-by-code, parallel.c:731-782]
- `ParallelBackupStart(AH)` (899) — fork/thread the workers; sets up pipes; on Windows reassigns `getLocalPQExpBuffer` to the thread-local version (line 923). [verified-by-code, parallel.c:898-1055]
- `DispatchJobForTocEntry(AH, pstate, te, act, callback, callback_data)` (1207) — block until a worker is idle, send `"DUMP <id>"` or `"RESTORE <id>"` command. [verified-by-code, parallel.c:1206-1231]
- `WaitForWorkers(AH, pstate, mode)` (1453) — collect status messages, dispatch callbacks; modes `NO_WAIT`/`GOT_STATUS`/`ONE_IDLE`/`ALL_IDLE`. [verified-by-code, parallel.c:1452-1508]
- `ParallelBackupEnd(AH, pstate)` (1061) — close pipes (signals EOF → workers exit), wait, free state. [verified-by-code, parallel.c:1060-1093]
- `IsEveryWorkerIdle(pstate)` (1270). [verified-by-code, parallel.c:1269-1280]

## Static spine

- `archive_close_connection(code, arg)` (341) — on-exit handler. Distinguishes leader (forcibly shut down workers via `ShutdownWorkersHard`) from worker (just disconnect own DB; close Windows sockets manually since thread-exit doesn't auto-close them). [verified-by-code, parallel.c:340-386]
- `ShutdownWorkersHard(pstate)` (397) — close write-end of pipes (signals EOF), then on Unix `SIGTERM` each child; on Windows `PQcancel` each worker's connection under critical section. Then `WaitForTerminatingWorkers`. [verified-by-code, parallel.c:396-442]
- `WaitForTerminatingWorkers(pstate)` (448) — Unix `wait()` loop; Windows `WaitForMultipleObjects` (bound by `MAXIMUM_WAIT_OBJECTS=64` — see `parallel.h:46`). [verified-by-code, parallel.c:447-509]
- `RunWorker(AH, slot)` (831) — the worker entry. Clones the archive (`CloneArchive`) even on Unix where `fork` already gave a copy; "CloneArchive resets the state information and also clones the database connection which both seem kinda helpful." Calls `SetupWorkerPtr` (format-specific) then enters `WaitForCommands`. [from-comment, parallel.c:842-847; verified-by-code, parallel.c:830-869]
- `WaitForCommands(AH, pipefd)` (1338) — worker main loop. `parseWorkerCommand` → for DUMP, `lockTableForWorker` then `WorkerJobDumpPtr`; for RESTORE, `WorkerJobRestorePtr`. `buildWorkerResponse` → `sendMessageToLeader`. [verified-by-code, parallel.c:1337-1381]
- `lockTableForWorker(AH, te)` (1303) — `LOCK TABLE … IN ACCESS SHARE MODE NOWAIT`. Comment (1283-1301) documents the deadlock prevention: leader holds AS lock, another session waits for AE behind it, worker would be enqueued behind the AE → deadlock the server can't detect → NOWAIT to fail fast. **Uses `fmtQualifiedId(te->namespace, te->tag)` — relies on the per-thread buffer.** [verified-by-code, parallel.c:1302-1330]
- `buildWorkerCommand` (1110) / `parseWorkerCommand` (1125) / `buildWorkerResponse` (1158) / `parseWorkerResponse` (1173) — command/response codec. Commands are `"DUMP %d"` / `"RESTORE %d"` (line 1114-1116); response is `"OK %d %d %d"` (line 1161). `sscanf("%d%n", ...)` + `Assert(nBytes == strlen(msg))` for parsing. [verified-by-code, parallel.c:1109-1195]
- `readMessageFromPipe(fd)` (1664) — byte-at-a-time read until `\0`. Comment says: "neither leader nor workers send more than one message without waiting for a reply, but we don't wish to assume that here." [from-comment, parallel.c:1671-1679]
- `pgpipe` Windows shim (1721) — TCP loopback socketpair with `bind`/`listen`/`accept`. [verified-by-code, parallel.c:1719-1801]
- `select_loop(maxFd, *workerset)` (1542) — EINTR-restartable `select()`. [verified-by-code, parallel.c:1541-1563]

## Worker → leader trust model

> "Remember that we have forked off the workers only after we have read in the catalog. That's why our worker processes can also access the catalog information." [from-comment, parallel.c:36-40]

This is load-bearing: workers do NOT re-read the catalog. They inherit (Unix) or clone (Windows) the already-populated `ArchiveHandle->toc`. The only per-worker query is `lockTableForWorker` + the actual `COPY` issued by the format module. The worker's libpq connection is fresh (cloned in `RunWorker`), so it has its own snapshot — pg_dump relies on `synchronized_snapshots` (set by the leader, imported by each worker via `pg_export_snapshot`/`SET TRANSACTION SNAPSHOT`). That happens inside `SetupWorkerPtr` (format-specific, not in this file). [from-comment, parallel.c:842-847] [inferred, parallel.c:856]

## Phase D — surfaces of concern

- **Worker command parser uses `sscanf("%d%n", …)`** then asserts `nBytes == strlen(msg)` (parallel.c:1135, 1144). `Assert` is a no-op in NDEBUG builds. The actual error path is `pg_fatal("unrecognized command…")` (1148) which fires only if the leading `"DUMP "` / `"RESTORE "` prefix didn't match. A malicious string `"DUMP 5junk"` would parse `5` and reach assert-only check. **In production builds, junk after the dumpId is silently accepted.** Trust boundary: only the leader writes to this pipe (Unix) or thread (Windows), so this is a defense-in-depth concern not an attack surface. [verified-by-code, parallel.c:1131-1149] [maybe]
- **`buildWorkerCommand` uses a fixed 256-byte stack buffer.** `snprintf` truncates safely; the buffer is plenty for `"DUMP <int>"`. [verified-by-code, parallel.c:1215-1218] [no concern]
- **Connection sharing between leader and workers: there is none.** Each worker has its own libpq connection (`CloneArchive` at parallel.c:848 → calls `ConnectDatabase` internally). The leader's `connCancel` is temporarily cleared (`set_archive_cancel_info(AH, NULL)`, line 941) before forking, so children don't inherit a stale `PGcancel` pointing at the leader connection. [verified-by-code, parallel.c:934-944, 1042-1044] [no concern]
- **Signal-safety in `sigTermHandler` (Unix, 547):** uses `pqsignal`, `kill`, `PQcancel`, `write(2)`, `_exit(1)`. All async-signal-safe. The comment at 518-523 explicitly says `PQcancel` is written to be safe in a signal handler. [verified-by-code, parallel.c:546-604; from-comment, parallel.c:518-523] [no concern]
- **`set_cancel_handler` propagates across `fork`** (parallel.c:612-615 comment): the children inherit `signal_info.handler_set = true` so each fork-self installs handlers in the child. [from-comment, parallel.c:612-615]
- **`TerminateThread` on Windows** is used in `consoleHandler` (line 671); the comment acknowledges resource leaks ("but it doesn't matter since we're about to end the whole process"). [from-comment, parallel.c:665-669] [no concern]
- **`getThreadLocalPQExpBuffer` (Windows-only)** ensures `fmtId`'s static buffer doesn't collide across worker threads. **Reassigned in `ParallelBackupStart` line 923: `getLocalPQExpBuffer = getThreadLocalPQExpBuffer;`** — this is a global function-pointer swap. If any pre-fork code called `fmtId` and held a pointer across the swap, it'd be invalidated; but the lifecycle (`fmtId` results are always consumed in-statement) makes this safe in practice. [verified-by-code, parallel.c:284-323, 921-924] [no concern — but load-bearing for fmtId discipline]
- **`pgpipe` on Windows uses TCP loopback** (parallel.c:1734-1800) bound to a kernel-chosen port. The `listen(s, 1)` queue is 1; the `accept` is racy against a hostile localhost process that connects to the freshly bound port before the legitimate `connect` does. Mitigation: between `bind` (1745) and `connect` (1779), there's no scheduler-friendly window — but the racy port number IS observable via `netstat` in principle. [verified-by-code, parallel.c:1731-1797] [maybe — known limitation of the Windows pgpipe pattern]
- **`readMessageFromPipe` byte-at-a-time read** with `bufsize += 16` realloc (line 1698). Bounded by message length; for malicious peers, OOM is the upper bound. [verified-by-code, parallel.c:1663-1706] [no concern]
- **Worker `lockTableForWorker` builds SQL via `fmtQualifiedId(te->namespace, te->tag)`** — both come from the leader's TOC; trust boundary is leader-internal. [verified-by-code, parallel.c:1302-1330] [no concern]
- **`PG_MAX_JOBS = MAXIMUM_WAIT_OBJECTS` (= 64) on Windows** vs `INT_MAX` on Unix. [verified-by-code, parallel.h:45-49] — pg_dump.c's CLI parser must clamp.

## Cross-references

- Caller: `pg_backup_archiver.c::RestoreArchive` and `WriteDataChunks` paths.
- `CloneArchive`/`DeCloneArchive` in `pg_backup_archiver.c`.
- See also: `knowledge/files/src/bin/pg_dump/parallel.h.md`.

## Open questions

- Where exactly is the snapshot synchronisation done? `SetupWorkerPtr` is format-specific; the comment at parallel.c:38-40 says "we have read in the catalog" but doesn't say "we have exported a snapshot". Worth following into `pg_backup_db.c`'s `setup_connection` / `ExecuteSqlQuery` chain. [unverified — flagged for pg_backup_db.c per-file doc]
- The "junk after dumpId" sscanf issue (1135) — does any path actually invoke `parseWorkerCommand` on attacker-controllable input? If not, this is purely defense-in-depth. [unverified]

## Confidence tag tally
`[verified-by-code]=33 [from-comment]=9 [maybe]=2 [no concern]=8 [inferred]=2 [unverified]=2`
