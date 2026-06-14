---
name: debugging
description: Debug a running PostgreSQL backend — lldb/gdb attach to the right forked backend via pg_backend_pid, single-user mode for postmaster/InitPostgres startup paths, breakpoints in ExecInitNode/heap_update/LWLockAcquire, elog(LOG,...) instrumentation, macOS core dumps, and SQL-level inspection via pg_buffercache / pageinspect / pg_visibility. Use proactively whenever the user wants to step through backend C code, attach to a backend, chase a SIGSEGV/hang in PG, or inspect shared state at runtime. Do NOT trigger for app-level debugging in Node/Python/Go or for tuning a production PG instance.
when_to_load: Step through, attach to, or instrument a live PG backend; chase a SIGSEGV / hang / leak; inspect shared state without a debugger.
companion_skills:
  - build-and-run
  - psql
  - locking
  - error-handling
  - memory-contexts
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

**Project shortcuts.** In this repo, `/pg-attach` automates the held-PID
grab and prints the exact `lldb -p <pid>` line ready to paste; `/pg-tail-log`
follows `dev/data-debug/server.log` (where `pprint` and `elog` output land).
Use them.

The postmaster itself never executes your query. Attach to the **backend**
that handles your session. The key footgun: a one-shot
`psql -tAc "SELECT pg_backend_pid()"` closes the connection immediately,
so the backend you "got the PID of" is already gone by the time you read
the output. You need a **held** backend — one whose connection stays open
long enough for you to attach.

### The held-PID pattern (works from a script)

Open a backend that holds its connection for N seconds via `pg_sleep`, tag
it with a recognizable `application_name`, then look the PID up via
`pg_stat_activity`:

```bash
# Hold a backend open for 60s, tagged so we can find it.
PGAPPNAME=hold psql -h /tmp -d postgres -X -c 'SELECT pg_sleep(60);' &

# Look up its backend PID (give it a moment to register).
sleep 0.5
PID=$(psql -h /tmp -d postgres -tAc \
  "SELECT pid FROM pg_stat_activity WHERE application_name='hold'")
echo "$PID"

# Attach in a separate terminal:
lldb -p "$PID"
```

`PGAPPNAME` is a libpq env var (NOT a psql `\set` variable — that won't
propagate to the server). Inside the lldb session, the backend will be
parked inside `pg_sleep`'s `WaitLatch` loop, ready for breakpoints.

### The interactive variant

When you actually want to drive queries through the attached session, hold
psql open interactively instead:

```sql
-- in psql, on the connection you want to debug:
SELECT pg_backend_pid();
 pg_backend_pid
----------------
          54321
```

Keep that psql session alive while you attach in another terminal:

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

### First command after every attach

PostgreSQL uses `SIGUSR1` heavily for latch wakeups. **Silence it before
you do anything else**, or every `continue` lands back in the signal
handler:

```
(lldb) pro hand -p true -s false SIGUSR1
(gdb)  handle SIGUSR1 noprint pass
```

[from-wiki: Developer_FAQ]

## 3. Stepping the startup path — single-user mode

**Decision rule — which tool for which startup phase:**

| Symptom                                                                | Tool                                  |
| ---------------------------------------------------------------------- | ------------------------------------- |
| Code runs *before* shared memory is attached / inside `InitPostgres`   | `postgres --single` (this section)    |
| Code runs in the forked-backend startup path (post-shmem, pre-query)   | `PGOPTIONS="-W N" psql ...` (§4)      |
| Code runs in a worker (autovacuum / parallel / bgworker)               | spin-loop waitpoint (§4)              |
| Code runs during a query you can drive from psql                       | normal `lldb -p` attach (§2)          |

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

### 5.1 Trapping every error (the universal ereport breakpoint)

For SIGSEGV chases or "I don't know which `ereport()` is firing", break on
`errfinish` — it's the single funnel every `ereport`/`elog` call goes
through. Filter on `elevel >= ERROR` (= 21) so you don't stop on every
LOG/NOTICE:

```
(lldb) b errfinish
(lldb) br mod -c 'edata->elevel >= 21'   # ERROR = 21
(gdb)  b errfinish
(gdb)  cond <n> edata->elevel >= 21
```

[`ERROR = 21` verified-by-code: `source/src/include/utils/elog.h:53`.]

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

### Prerequisites

```bash
# 1. The shell that launches postgres must allow cores.
ulimit -c unlimited
# expected (after setting): "unlimited"

# 2. /cores must exist and be writable.
ls -ld /cores
# expected: drwxrwxrwt  root  wheel   (sticky, world-writable)
sudo chmod 1777 /cores    # only if the perms above don't match

# 3. Verify kernel allows cores.
sysctl kern.coredump
# expected: kern.coredump: 1
```

Then crash the backend and open the core:

```bash
lldb /path/to/postgres /cores/core.<pid>
```

### Caveats (macOS-specific)

- **Apple-signed / hardened binaries suppress cores** regardless of
  `ulimit`. Our locally-built `postgres` is unsigned, so this isn't a
  concern here — but if you ever try to core-dump `/usr/bin/postgres` or a
  Homebrew bottle, this is why nothing lands in `/cores`.
- **No `kern.coredump` sysctl on your machine?** If `sysctl kern.coredump`
  returns `unknown oid`, your macOS version controls cores via `ulimit`
  alone — steps 1 and 2 are sufficient.

[`ulimit -c unlimited` and `/cores` location: standard Darwin defaults
documented in `man 5 core` on macOS. `kern.coredump` sysctl and
hardened-binary suppression: `[inferred]` from well-known Darwin behavior.]

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

## 11. Memory bugs and leak hunting

Three tools, in increasing order of "bring out the heavy machinery":

### 11.1 `pg_backend_memory_contexts` — observe before debugging

Cheapest first step for any "the backend's RSS keeps growing" suspicion.
Run on the suspect connection between iterations of a workload:

```sql
SELECT name, level, parent, total_bytes/1024 AS kb, used_bytes/1024 AS used_kb
FROM   pg_backend_memory_contexts
ORDER  BY total_bytes DESC
LIMIT  20;
```

Run the suspect workload N times via `\watch`, then re-check. A context
that grows monotonically across iterations is your leak signature. For
*another* backend's contexts, use `pg_log_backend_memory_contexts(<pid>)`
(PG 14+) — it dumps to `dev/data-debug/server.log`. [verified-by-code;
`pg_backend_memory_contexts` view and `pg_log_backend_memory_contexts`
function exist in `src/backend/utils/adt/mcxtfuncs.c`.]

### 11.2 AddressSanitizer + UndefinedBehaviorSanitizer

For use-after-free, heap-buffer-overflow, double-free, and undefined
behavior (signed overflow, alignment violations, bool-from-non-bool).
Use the sanitizer build profile — see
`.claude/skills/build-and-run/SKILL.md` "Sanitizer builds":

```bash
# One-time build
/setup-pg-asan
# Start the asan cluster (separate data dir from debug cluster)
/pg-start-asan
```

Important runtime knobs (the `/pg-start-asan` wrapper sets them):

```bash
export ASAN_OPTIONS="abort_on_error=1:detect_leaks=0:detect_stack_use_after_return=1:print_stacktrace=1"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"
```

On a hit, ASan writes a full stack to the server log AND the controlling
terminal, then aborts the backend (postmaster restarts a fresh one).
Check `dev/data-asan/server.log` for the report. The stack frames will
have file:line directly into the source you built — no addr2line dance.

**`detect_leaks=0` is required on macOS** — LeakSanitizer is not
supported on Darwin and setting `detect_leaks=1` errors out at startup.
For leaks specifically, use 11.3 instead, or rebuild this profile on
Linux. [verified: macOS ASan does NOT include LSan, per LLVM
sanitizer-platform compat matrix.]

### 11.3 macOS-native leak detection (`leaks` / `malloc_history`)

When LSan isn't an option (i.e., on this Mac), the Darwin tooling does
the job — no rebuild required, works against the existing `build-debug`:

```bash
# Before pg_ctl start, enable malloc backtraces.
export MallocStackLogging=1
/pg-restart

# Reproduce the leak workload, then:
PID=<the suspect backend pid>
leaks "$PID"           # one-shot report
leaks --atExit -- /path/to/cmd       # for short-lived subprocesses

# Get allocation backtrace for a specific address found by `leaks`:
malloc_history "$PID" <addr>
```

`MallocStackLogging` adds ~10-30% RSS overhead — fine for dev, don't
ship.

**When `pg_backend_memory_contexts` is the right tool vs `leaks`:**
PG-context allocations (`palloc`/`MemoryContextAlloc`) show up in the
context view, NOT in `leaks` — because palloc'd memory is freed via
`MemoryContextDelete()` and is not "leaked" from libc's perspective.
For raw `malloc()` leaks (which do exist — extension code, libpq,
third-party libs called from the backend), `leaks` is the answer.

### 11.4 Choosing the right tool

| Symptom                                           | Reach for     |
| ------------------------------------------------- | ------------- |
| RSS grows, suspect a palloc-context not freed     | 11.1 contexts |
| Use-after-free, heap-buffer-overflow, double-free | 11.2 ASan     |
| Signed overflow / alignment / undefined behavior  | 11.2 UBSan    |
| raw `malloc()` leak (often in extension code)     | 11.3 `leaks`  |
| Need real LSan-quality leak reports               | Linux + ASan  |

## 12. Quick checklist

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
7. If it's a memory bug (UAF, OOB, leak), pick the right tool from §11.4.

## Cross-references

- `.claude/skills/build-and-run/SKILL.md` — get a debug+cassert build before debugging anything; ASan profile lives here.
- `.claude/skills/psql/SKILL.md` — held-PID handoff (`PGAPPNAME=hold` + `pg_sleep`), `pg_backend_memory_contexts`, `\errverbose` from the SQL side.
- `.claude/skills/locking/SKILL.md` — interpret `pg_locks` / `wait_event` output once §10 surfaces the contention.
- `.claude/skills/error-handling/SKILL.md` — `errfinish` + `elevel` numbering + `ereport` macro structure (§5.1, §7).
- `.claude/skills/memory-contexts/SKILL.md` — what `pg_backend_memory_contexts` shows and how to read it (§11.1).
- `.claude/commands/pg-attach.md`, `.claude/commands/pg-tail-log.md` — slash-command wrappers built on top of this skill.
