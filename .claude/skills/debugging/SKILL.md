---
name: debugging
description: Debug a running PostgreSQL backend — lldb/gdb attach to the right forked backend via pg_backend_pid, single-user mode for postmaster/InitPostgres startup paths, breakpoints in ExecInitNode/heap_update/LWLockAcquire, elog(LOG,...) instrumentation, macOS core dumps, and SQL-level inspection via pg_buffercache / pageinspect / pg_visibility. Use proactively whenever the user wants to step through backend C code, attach to a backend, chase a SIGSEGV/hang in PG, or inspect shared state at runtime. Do NOT trigger for app-level debugging in Node/Python/Go or for tuning a production PG instance.
---

# debugging

PostgreSQL is a **multi-process** server, not threaded: the postmaster
forks a fresh backend per connection. That single fact dictates the whole
debugging workflow. [verified-by-code; see `source/src/backend/postmaster/postmaster.c`,
and `.claude/skills/build-and-run/SKILL.md` line 59–63]

## 1. Build first

Debugging only makes sense against a debug build. See
`.claude/skills/build-and-run/SKILL.md` — `--buildtype=debug -Dcassert=true`.
`debug` (not `debugoptimized`) keeps locals and inline frames readable.
[verified-by-code; build-and-run/SKILL.md line 33]

The upstream FAQ recommends `CFLAGS="-ggdb -Og -g3 -fno-omit-frame-pointer"`
for autoconf builds — `-Og` keeps reasonable perf while preserving frames.
[from-wiki: Developer_FAQ]

## 2. The attach pattern (most common workflow)

The postmaster itself never executes your query. Attach to the **backend**
that handles your session:

```sql
-- in psql, on the connection you want to debug:
SELECT pg_backend_pid();
 pg_backend_pid
----------------
          54321
```

Then in another terminal:

```bash
# Linux / where gdb works
gdb -p 54321

# macOS — lldb is the path of least resistance
lldb -p 54321
```

Why lldb on macOS: gdb on Darwin needs a code-signed binary with the
`com.apple.security.cs.debugger` entitlement; lldb ships with Xcode
Command Line Tools and works out of the box. [from-wiki: Developer_FAQ
implies gdb-or-lldb; macOS codesigning requirement is well-known toolchain
quirk — `[inferred]` for the entitlement specifics]

### Translating common gdb commands to lldb

| gdb                          | lldb                          |
| ---------------------------- | ----------------------------- |
| `b ExecutorRun`              | `b ExecutorRun`               |
| `p MyProcPid`                | `p MyProcPid`                 |
| `bt`                         | `bt`                          |
| `call pprint(node)`          | `expr pprint(node)`           |
| `handle SIGUSR1 noprint pass`| `pro hand -p true -s false SIGUSR1` |

PostgreSQL uses `SIGUSR1` heavily for latch wakeups. Silence it before
you do anything else, or every continue lands back in the signal handler.
[from-wiki: Developer_FAQ]

## 3. Stepping the startup path — single-user mode

Attaching to a forked backend can't help with code that runs *before* the
backend is ready to accept queries (auth, shmem init, startup hooks).
Use `postgres --single` for that. No postmaster, no fork — the debugger
sees the whole lifetime in one process.

```bash
gdb --args postgres --single -D "$PGDATA" postgres
# or
lldb -- postgres --single -D "$PGDATA" postgres
```

[verified-by-code; `source/doc/src/sgml/ref/postgres-ref.sgml` line 714+:
"To start a single-user mode server, use a command like
`postgres --single -D /usr/local/pgsql/data other-options my_database`"]

In single-user mode newline terminates a command (not semicolon).
Use `-j` to switch to `;\n\n` mode if you're pasting psql-style scripts.
[verified-by-code; postgres-ref.sgml around line 730]

## 4. Catching things that happen too fast

For code that runs before you can grab the PID (e.g. early backend
startup, parallel workers, autovacuum workers):

- `PGOPTIONS="-W 10" psql ...` — the backend sleeps 10 seconds at startup
  so you have time to `pg_backend_pid()` and attach. [from-wiki: Developer_FAQ]
- For short-lived background workers, insert a temporary spin-loop:
  ```c
  bool wait = true;
  elog(LOG, "waiting for debugger, pid=%d", MyProcPid);
  while (wait) pg_usleep(1000000L);
  ```
  Attach, then `set var wait = 0` to release. [from-wiki: Developer_FAQ
  — pattern shown there with `sleep()`; using `pg_usleep` is the
  PG-idiomatic equivalent, `[inferred]`]
- Some test paths already sleep deliberately. Example: WAL recovery has
  `pg_usleep(10000L); /* wait for 10 msec */` retry loops.
  [verified-by-code; `source/src/backend/access/transam/xlog.c:7707, 7724`]
- True waitpoint infrastructure exists for tests — see
  `source/src/test/authentication/t/007_pre_auth.pl` line 38: "Connect
  to the server and inject a waitpoint." Waitpoints let TAP tests pause
  the backend at a labeled location. [verified-by-code]

## 5. Useful breakpoints

Where to break depends on what you're chasing:

| Goal                           | Breakpoint                                          |
| ------------------------------ | --------------------------------------------------- |
| Any incoming SQL               | `exec_simple_query` (`src/backend/tcop/postgres.c`) |
| Plan execution                 | `ExecutorStart`, `ExecutorRun`, `ExecutorEnd`       |
| All errors (`ereport`/`elog`)  | `errfinish` (filter on `edata->elevel >= ERROR`)    |
| Buffer pin/lookup              | `BufferAlloc`, `ReadBuffer_common`                  |
| Lock acquisition               | `LockAcquire`, `LockAcquireExtended`                |
| Transaction boundaries         | `StartTransaction`, `CommitTransaction`             |
| Heap insert/update             | `heap_insert`, `heap_update`                        |
| WAL insert                     | `XLogInsert`                                        |

[`errfinish` for trapping errors: from-wiki Developer_FAQ.
The rest: verified-by-code, names exist as symbols in
`source/src/backend/{tcop,executor,storage/buffer,storage/lmgr,access/transam,access/heap}/`.]

## 6. Pretty-printing PG internals

Postgres ships `pprint()` for `Node *` trees (parse trees, plans).
Call it from the debugger:

```
(gdb) call pprint(parsetree)
(lldb) expr pprint(parsetree)
```

Output goes to the backend's stderr (the server log, typically).
[from-wiki: Developer_FAQ]

Memory inspection without stopping execution:

```
(gdb) p MemoryContextStats(TopMemoryContext)
```

Or, from SQL on PG 14+: `SELECT * FROM pg_backend_memory_contexts;`.
[from-wiki: Developer_FAQ; pg_backend_memory_contexts: verified-by-code,
view exists.]

There is **no `gdbpg.py`** in the current source tree (searched
`source/src/tools/` — not present). Community pretty-printers exist on
GitHub but are not bundled. [verified-by-code: `find` returned zero
matches under `source/`.]

## 7. `elog` / `ereport` instrumentation pattern

For "I want to know which path got taken" rather than stepping:

```c
elog(DEBUG1, "BufferAlloc: blkno=%u, hit=%d", blkno, found);
```

Then start the server with `log_min_messages = debug1` (or higher number
through `debug5`). See `.claude/skills/build-and-run/SKILL.md` line 78
for the GUC name. [verified-by-code; `ereport`/`elog` are the canonical
logging macros throughout the backend — see
`.claude/skills/error-handling/` for full conventions.]

For ad-hoc tracing, `fprintf(stderr, ...)` works in `--single` mode and
goes straight to the controlling terminal. Don't ship that.

## 8. Core dumps on macOS

Three things must all be true before you get a usable core:

```bash
# 1. The shell that launches postgres must allow cores.
ulimit -c unlimited

# 2. macOS writes cores to /cores by default. Make sure it exists
#    and is writable by your user.
ls -ld /cores
sudo chmod 1777 /cores    # if needed

# 3. The kern.coredump sysctl must be 1 (default on most macOS, but check).
sysctl kern.coredump
# expected: kern.coredump: 1
```

Then crash the backend and:

```bash
lldb /path/to/postgres /cores/core.<pid>
```

[`ulimit -c unlimited` and `/cores` location: `[verified-by-code]`
behavior of macOS — these are standard Darwin defaults documented in
`man 5 core` on macOS. `kern.coredump` sysctl: `[inferred]` from
historical macOS behavior; if `sysctl` reports it missing, cores are
controlled solely by `ulimit` on recent macOS. Verify on your box.]

Cores from Apple-signed binaries are suppressed regardless of ulimit;
this is not a concern for a locally-built `postgres`, which is unsigned.
[inferred]

## 9. SQL-level inspection extensions

When you want to look at shared state without a debugger attach, the
contrib extensions are the right tool:

- **`pg_buffercache`** — one row per shared buffer with relfilenode,
  block number, usage count, dirty flag, pin count. Now also exposes
  `pg_buffercache_evict()` and `pg_buffercache_numa` (NUMA-page mapping).
  [verified-by-code; `source/contrib/pg_buffercache/pg_buffercache--1.5--1.6.sql`,
  `pg_buffercache_pages.c`]
- **`pageinspect`** — raw page contents (heap tuples, btree pages, GIN,
  BRIN). For "why is this page corrupt" or "what's the actual lp_off of
  this line pointer."
- **`pg_visibility`** — visibility map state per page; functions like
  `pg_check_frozen(regclass)` and `pg_check_visible(regclass)` flag VM
  bits that disagree with the heap. [verified-by-code;
  `source/contrib/pg_visibility/pg_visibility--1.1--1.2.sql`]
- **`amcheck`** — structural integrity checks for btree and heap.
  Reproduce-suspected-corruption tool.

All four are in-tree under `source/contrib/`. [verified-by-code]

## 10. Reproducing locking bugs

The hard ones. Standard recipe:

```sql
-- Session A: get the PID, take the lock you want to study.
SELECT pg_backend_pid();
BEGIN;
LOCK TABLE t IN ACCESS EXCLUSIVE MODE;

-- Session B: from a third session (so you can still query),
-- watch who holds what and who is waiting on whom:
SELECT pid, locktype, mode, granted, relation::regclass, transactionid
FROM   pg_locks
WHERE  NOT granted
   OR  pid IN (<A pid>, <B pid>);

SELECT pid, wait_event_type, wait_event, state, query
FROM   pg_stat_activity
WHERE  pid IN (<A pid>, <B pid>);
```

The `wait_event_type` / `wait_event` columns name the exact wait point
inside the backend — usually enough to know which LWLock or heavyweight
lock is blocking.

For deadlocks, set `deadlock_timeout = '100ms'` (default 1s) to make the
detector fire quickly, then check the server log for the standard
`DETAIL: Process N waits for X on Y; blocked by process M.` block.
[verified-by-code: `deadlock_timeout` GUC; deadlock log format from
`source/src/backend/storage/lmgr/deadlock.c` and `proc.c`. The
`100ms` value: `[inferred]` reasonable shorter-than-default — adjust to
taste.]

To dive deeper into the locking model itself, see
`.claude/skills/locking/`.

## 11. Quick checklist

When something is wrong, in order:

1. Reproduce against a **debug+cassert** build. Asserts catch a lot.
2. Check the server log — `log_min_messages = debug2` is usually enough
   to surface the path taken.
3. `SELECT pg_backend_pid()` → attach lldb/gdb → set the breakpoint
   you suspect.
4. If it's startup or auth, switch to `postgres --single`.
5. If it's shared state, ask `pg_buffercache` / `pg_locks` /
   `pg_stat_activity` before reaching for the debugger.
6. If it crashed, check `/cores/core.<pid>` and open it with lldb.
