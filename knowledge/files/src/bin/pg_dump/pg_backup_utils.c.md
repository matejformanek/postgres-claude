---
path: src/bin/pg_dump/pg_backup_utils.c
anchor_sha: 4b0bf0788b0
loc: 107
depth: read
---

# pg_backup_utils.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_utils.c`
- **Lines:** 107
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_utils.h` (companion header redefining `pg_fatal` to call `exit_nicely`), `parallel.h` (Windows parallel thread support), `common/logging.h`.

## Purpose

Tiny utility module that hosts three things used by every other file in `pg_dump`/`pg_restore`:

1. The `progname` global (set by `set_pglocale_pgservice` in `main`).
2. `set_dump_section(arg, *dumpSections)` — parses `--section=<pre-data|data|post-data>`.
3. The `on_exit_nicely` callback list and `exit_nicely(code)` runner.

The associated `pg_backup_utils.h` re-`#define`s `pg_fatal` so that it routes through `exit_nicely` (and thus runs cleanup callbacks) instead of the default `exit`. [verified-by-code, pg_backup_utils.c:22-32, 41-72, 91-106; pg_backup_utils.h:34-39]

## Public surface

- `const char *progname` (22) — defined here; declared `extern` in the header. Set once at process start. [verified-by-code, pg_backup_utils.c:22]
- `set_dump_section(arg, *dumpSections)` (41) — bitwise-OR `DUMP_PRE_DATA` / `DUMP_DATA` / `DUMP_POST_DATA` into `*dumpSections`. Initializes `*dumpSections = 0` on first call (was `DUMP_UNSECTIONED = 0xff` per header). Unrecognized arg → `pg_log_error` + hint + `exit_nicely(1)`. [verified-by-code, pg_backup_utils.c:41-60]
- `on_exit_nicely(function, arg)` (64) — register a cleanup callback. Hard cap `MAX_ON_EXIT_NICELY = 20`. Overflow → `pg_fatal("out of on_exit_nicely slots")`. [verified-by-code, pg_backup_utils.c:24, 63-72]
- `exit_nicely(code)` (91) — run all registered callbacks in **LIFO order**, then on Windows worker thread `_endthreadex(code)`, else `exit(code)`. Tagged `pg_noreturn` in the header. [verified-by-code, pg_backup_utils.c:91-106; pg_backup_utils.h:32]

## Internal landmarks

- `on_exit_nicely_list[MAX_ON_EXIT_NICELY]` (26-30) — static array of `{function, arg}` slots. No heap. [verified-by-code, pg_backup_utils.c:24-30]
- `on_exit_nicely_index` (32) — count of registered slots; not reset across exec. [verified-by-code, pg_backup_utils.c:32]
- `#ifdef WIN32` includes `parallel.h` (16-18) — for `parallel_init_done` and `mainThreadId` referenced in `exit_nicely`. On non-WIN32, that block compiles to nothing. [verified-by-code, pg_backup_utils.c:16-18, 100-103]

## Invariants & gotchas

- **`MAX_ON_EXIT_NICELY = 20`.** Adding callbacks per child archive entry would blow this. Currently called at most a handful of times per process (DB connection cleanup, archive cleanup, log file close, etc.). [verified-by-code, pg_backup_utils.c:24]
- **Callbacks fire in LIFO order** — last registered, first run. Matters when one cleanup depends on another (e.g. close archive before disconnect). [verified-by-code, pg_backup_utils.c:96-98]
- **Forking caveat.** "On Unix, callbacks are also run by each process, but only for callbacks established before we fork off the child processes." Parallel pg_dump's per-worker callbacks must be set up before fork to avoid divergence; alternatively the long comment notes the design tradeoff (would-be-cleaner to reset post-fork, but inconsistent with Windows-thread model). [from-comment, pg_backup_utils.c:74-90]
- **Windows worker threads call `_endthreadex` instead of `exit`.** Otherwise one worker's fatal would tear down the whole process. The check `parallel_init_done && GetCurrentThreadId() != mainThreadId` distinguishes worker from main. [verified-by-code, pg_backup_utils.c:100-103]
- **`set_dump_section`'s "first call" detection is via `DUMP_UNSECTIONED = 0xff` sentinel.** First call clears it to 0 before OR-ing in the bit. So a script that sets `*dumpSections = 0` itself before calling would inadvertently force `set_dump_section` to NOT skip the clear — but since 0 stays 0 through the clear, the result is the same. Subtle but safe. [verified-by-code, pg_backup_utils.c:44-46]
- **No `errno` save/restore around `exit_nicely`.** Callbacks see whatever `errno` was on entry; they may themselves mutate it. [verified-by-code, pg_backup_utils.c:91-106]
- **`pg_fatal` macro redefinition in the header** (pg_backup_utils.h:34-39) replaces the default `pg_fatal` (which calls `exit`) with one that calls `exit_nicely`. Any `.c` that `#includes "pg_backup_utils.h"` gets the override. Order of includes matters — including `common/logging.h` *after* this header would un-define and revert. [verified-by-code, pg_backup_utils.h:34-39]

## Phase D — error-message hygiene

- **`set_dump_section` error includes the user-supplied `arg` verbatim:** `pg_log_error("unrecognized section name: \"%s\"", arg)`. `arg` comes from argv. Reflecting argv to stderr is not a leak (the user already controls it). [verified-by-code, pg_backup_utils.c:56]
- **Hint includes `progname`:** `pg_log_error_hint("Try \"%s --help\" for more information.", progname)`. `progname` is `argv[0]`. Same reasoning — not a leak. [verified-by-code, pg_backup_utils.c:57]
- **No environment variables, file paths, or query text in any error string.** `pg_fatal("out of on_exit_nicely slots")` is the only other ereport here. No `getenv` calls. **No issues surfaced.** [verified-by-code, full file]
- The wider concern (env/argv leakage in errors) lives in the per-backend `pg_log_*` / `pg_fatal` call sites scattered across `pg_dump.c`, `pg_backup_archiver.c`, etc. — outside this file's scope.

## Cross-references

- `pg_backup_utils.h` — declares the surface and the `pg_fatal` override.
- `pg_dump.c`, `pg_restore.c` — set `progname`, call `set_dump_section`, register cleanup callbacks.
- `parallel.c` (Windows) — provides `parallel_init_done` and `mainThreadId`.

## Confidence tag tally
`[verified-by-code]=13 [from-comment]=1`
