---
path: src/bin/pg_dump/parallel.c
anchor_sha: 4b0bf0788b0
loc: 1817
depth: deep
---

# parallel.c

- **Source path:** `source/src/bin/pg_dump/parallel.c`
- **Lines:** 1817
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `parallel.h` (the `ParallelState`, `ParallelCompletionPtr`, `WFW_*` enum, `PG_MAX_JOBS` cap), `pg_backup_archiver.c` (caller of `ParallelBackupStart`/`DispatchJobForTocEntry`/`ParallelBackupEnd`/`WaitForWorkers`), `pg_backup_db.c` (`CloneArchive`, `DisconnectDatabase`).

## Purpose

The `-j N` worker pool implementation, with two divergent runtime models:

- **Unix:** `fork()` per worker; each worker is a separate process with its own libpq connection. Communication is via `pipe(2)`. Signal handling via `SIGTERM`/`SIGINT`/`SIGQUIT` handlers that forward to children.
- **Windows:** threads (`_beginthreadex`); communication via socketpair-style pipes built on top of TCP loopback (the `pgpipe` shim at line 1734). Cancellation via `SetConsoleCtrlHandler` running in its own thread plus a critical section guarding `signal_info`.

[from-comment, parallel.c:16-51]

## Public surface

- `init_parallel_dump_utils()` (238) — `WSAStartup` + `TlsAlloc` on Windows; no-op on Unix. [verified-by-code, parallel.c:237-258]
- `on_exit_close_archive(AHX)` / `replace_on_exit_close_archive(AHX)` (330, 345) — wire the cleanup callback. [verified-by-code, parallel.c:329-348]
- `set_archive_cancel_info(AH, conn)` (746) — set/clear the `connCancel` used by signal handlers. On Windows, guarded by critical section against the signal thread. [verified-by-code, parallel.c:745-796]
- `ParallelBackupStart(AH)` (913) — fork/thread the workers; sets up pipes; on Windows reassigns `getLocalPQExpBuffer` to the thread-local version (line 937). [verified-by-code, parallel.c:912-1069]
- `DispatchJobForTocEntry(AH, pstate, te, act, callback, callback_data)` (1221) — block until a worker is idle, send `"DUMP <id>"` or `"RESTORE <id>"` command. [verified-by-code, parallel.c:1220-1245]
- `WaitForWorkers(AH, pstate, mode)` (1467) — collect status messages, dispatch callbacks; modes `NO_WAIT`/`GOT_STATUS`/`ONE_IDLE`/`ALL_IDLE`. [verified-by-code, parallel.c:1466-1522]
- `ParallelBackupEnd(AH, pstate)` (1075) — close pipes (signals EOF → workers exit), wait, free state. [verified-by-code, parallel.c:1074-1107]
- `IsEveryWorkerIdle(pstate)` (1284). [verified-by-code, parallel.c:1283-1294]

## Static spine

- `archive_close_connection(code, arg)` (355) — on-exit handler. Distinguishes leader (forcibly shut down workers via `ShutdownWorkersHard`) from worker (just disconnect own DB; close Windows sockets manually since thread-exit doesn't auto-close them). [verified-by-code, parallel.c:354-400]
- `ShutdownWorkersHard(pstate)` (411) — close write-end of pipes (signals EOF), then on Unix `SIGTERM` each child; on Windows `PQcancel` each worker's connection under critical section. Then `WaitForTerminatingWorkers`. [verified-by-code, parallel.c:410-456]
- `WaitForTerminatingWorkers(pstate)` (462) — Unix `wait()` loop; Windows `WaitForMultipleObjects` (bound by `MAXIMUM_WAIT_OBJECTS=64` — see `parallel.h:46`). [verified-by-code, parallel.c:461-523]
- `RunWorker(AH, slot)` (845) — the worker entry. Clones the archive (`CloneArchive`) even on Unix where `fork` already gave a copy; "CloneArchive resets the state information and also clones the database connection which both seem kinda helpful." Calls `SetupWorkerPtr` (format-specific) then enters `WaitForCommands`. [from-comment, parallel.c:856-861; verified-by-code, parallel.c:844-883]
- `WaitForCommands(AH, pipefd)` (1352) — worker main loop. `parseWorkerCommand` → for DUMP, `lockTableForWorker` then `WorkerJobDumpPtr`; for RESTORE, `WorkerJobRestorePtr`. `buildWorkerResponse` → `sendMessageToLeader`. [verified-by-code, parallel.c:1351-1395]
- `lockTableForWorker(AH, te)` (1317) — `LOCK TABLE … IN ACCESS SHARE MODE NOWAIT`. Comment (1297-1315) documents the deadlock prevention: leader holds AS lock, another session waits for AE behind it, worker would be enqueued behind the AE → deadlock the server can't detect → NOWAIT to fail fast. **Uses `fmtQualifiedId(te->namespace, te->tag)` — relies on the per-thread buffer.** [verified-by-code, parallel.c:1316-1344]
- `buildWorkerCommand` (1124) / `parseWorkerCommand` (1139) / `buildWorkerResponse` (1172) / `parseWorkerResponse` (1187) — command/response codec. Commands are `"DUMP %d"` / `"RESTORE %d"` (line 1128-1130); response is `"OK %d %d %d"` (line 1175). `sscanf("%d%n", ...)` + `Assert(nBytes == strlen(msg))` for parsing. [verified-by-code, parallel.c:1123-1209]
- `readMessageFromPipe(fd)` (1678) — byte-at-a-time read until `\0`. Comment says: "neither leader nor workers send more than one message without waiting for a reply, but we don't wish to assume that here." [from-comment, parallel.c:1685-1693]
- `pgpipe` Windows shim (1734) — TCP loopback socketpair with `bind`/`listen`/`accept`. [verified-by-code, parallel.c:1733-1815]
- `select_loop(maxFd, *workerset)` (1556) — EINTR-restartable `select()`. [verified-by-code, parallel.c:1555-1577]

## Worker → leader trust model

> "Remember that we have forked off the workers only after we have read in the catalog. That's why our worker processes can also access the catalog information." [from-comment, parallel.c:36-40]

This is load-bearing: workers do NOT re-read the catalog. They inherit (Unix) or clone (Windows) the already-populated `ArchiveHandle->toc`. The only per-worker query is `lockTableForWorker` + the actual `COPY` issued by the format module. The worker's libpq connection is fresh (cloned in `RunWorker`), so it has its own snapshot — pg_dump relies on `synchronized_snapshots` (set by the leader, imported by each worker via `pg_export_snapshot`/`SET TRANSACTION SNAPSHOT`). That happens inside `SetupWorkerPtr` (format-specific, not in this file). [from-comment, parallel.c:856-861] [inferred, parallel.c:870]

## Phase D — surfaces of concern

- **Worker command parser uses `sscanf("%d%n", …)`** then asserts `nBytes == strlen(msg)` (parallel.c:1149, 1158). `Assert` is a no-op in NDEBUG builds. The actual error path is `pg_fatal("unrecognized command…")` (1162) which fires only if the leading `"DUMP "` / `"RESTORE "` prefix didn't match. A malicious string `"DUMP 5junk"` would parse `5` and reach assert-only check. **In production builds, junk after the dumpId is silently accepted.** Trust boundary: only the leader writes to this pipe (Unix) or thread (Windows), so this is a defense-in-depth concern not an attack surface. [verified-by-code, parallel.c:1145-1163] [maybe]
- **`buildWorkerCommand` uses a fixed 256-byte stack buffer.** `snprintf` truncates safely; the buffer is plenty for `"DUMP <int>"`. [verified-by-code, parallel.c:1229-1232] [no concern]
- **Connection sharing between leader and workers: there is none.** Each worker has its own libpq connection (`CloneArchive` at parallel.c:862 → calls `ConnectDatabase` internally). The leader's `connCancel` is temporarily cleared (`set_archive_cancel_info(AH, NULL)`, line 955) before forking, so children don't inherit a stale `PGcancel` pointing at the leader connection. [verified-by-code, parallel.c:948-958, 1056-1058] [no concern]
- **Signal-safety in `sigTermHandler` (Unix, 561):** uses `pqsignal`, `kill`, `PQcancel`, `write(2)`, `_exit(1)`. All async-signal-safe. The comment at 532-537 explicitly says `PQcancel` is written to be safe in a signal handler. [verified-by-code, parallel.c:560-618; from-comment, parallel.c:532-537] [no concern]
- **`set_cancel_handler` propagates across `fork`** (parallel.c:626-629 comment): the children inherit `signal_info.handler_set = true` so each fork-self installs handlers in the child. [from-comment, parallel.c:626-629]
- **`TerminateThread` on Windows** is used in `consoleHandler` (line 685); the comment acknowledges resource leaks ("but it doesn't matter since we're about to end the whole process"). [from-comment, parallel.c:679-683] [no concern]
- **`getThreadLocalPQExpBuffer` (Windows-only)** ensures `fmtId`'s static buffer doesn't collide across worker threads. **Reassigned in `ParallelBackupStart` line 937: `getLocalPQExpBuffer = getThreadLocalPQExpBuffer;`** — this is a global function-pointer swap. If any pre-fork code called `fmtId` and held a pointer across the swap, it'd be invalidated; but the lifecycle (`fmtId` results are always consumed in-statement) makes this safe in practice. [verified-by-code, parallel.c:284-323, 935-938] [no concern — but load-bearing for fmtId discipline]
- **`pgpipe` on Windows uses TCP loopback** (parallel.c:1748-1814) bound to a kernel-chosen port. The `listen(s, 1)` queue is 1; the `accept` is racy against a hostile localhost process that connects to the freshly bound port before the legitimate `connect` does. Mitigation: between `bind` (1759) and `connect` (1793), there's no scheduler-friendly window — but the racy port number IS observable via `netstat` in principle. [verified-by-code, parallel.c:1745-1811] [maybe — known limitation of the Windows pgpipe pattern]
- **`readMessageFromPipe` byte-at-a-time read** with `bufsize += 16` realloc (line 1712). Bounded by message length; for malicious peers, OOM is the upper bound. [verified-by-code, parallel.c:1677-1720] [no concern]
- **Worker `lockTableForWorker` builds SQL via `fmtQualifiedId(te->namespace, te->tag)`** — both come from the leader's TOC; trust boundary is leader-internal. [verified-by-code, parallel.c:1316-1344] [no concern]
- **`PG_MAX_JOBS = MAXIMUM_WAIT_OBJECTS` (= 64) on Windows** vs `INT_MAX` on Unix. [verified-by-code, parallel.h:45-49] — pg_dump.c's CLI parser must clamp.

## Cross-references

- Caller: `pg_backup_archiver.c::RestoreArchive` and `WriteDataChunks` paths.
- `CloneArchive`/`DeCloneArchive` in `pg_backup_archiver.c`.
- See also: `knowledge/files/src/bin/pg_dump/parallel.h.md`.

## Open questions

- Where exactly is the snapshot synchronisation done? `SetupWorkerPtr` is format-specific; the comment at parallel.c:38-40 says "we have read in the catalog" but doesn't say "we have exported a snapshot". Worth following into `pg_backup_db.c`'s `setup_connection` / `ExecuteSqlQuery` chain. [unverified — flagged for pg_backup_db.c per-file doc]
- The "junk after dumpId" sscanf issue (1149) — does any path actually invoke `parseWorkerCommand` on attacker-controllable input? If not, this is purely defense-in-depth. [unverified]

## Confidence tag tally
`[verified-by-code]=33 [from-comment]=9 [maybe]=2 [no concern]=8 [inferred]=2 [unverified]=2`
