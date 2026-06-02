---
name: psql
description: How to drive `psql` against the local dev cluster for backend-hacking work — connection string (Unix socket /tmp, trust auth, database postgres), useful meta-commands (\d+, \df+, \sf, \timing, \watch, \gexec, \errverbose), session-only debug knobs (client_min_messages, log_min_messages, EXPLAIN ANALYZE BUFFERS), introspection of running backends (pg_stat_activity, pg_backend_memory_contexts, pg_locks), gdb/lldb-friendly idioms (capturing backend PID, pausing in single-user mode), and safe vs unsafe DDL on the dev cluster. Use whenever the task involves running SQL against the local Postgres built from source, exploring the catalog interactively, reproducing a backend bug, or inspecting runtime state of a debug build. Skip when the user wants a read-only one-shot query (use the postgres-dev MCP) or when the task is editing C source / running the test harness (use build-and-run / testing skills).
---

# Working with the local dev cluster via psql

Default connection: `psql -h /tmp -d postgres` — Unix socket at `/tmp`, trust
auth (no password), database `postgres`, superuser = your macOS username.
Server log is `dev/data-debug/server.log` (tail it with `/pg-tail-log`).

## When to reach for what

- **psql** — anything interactive, anything writing, anything that needs meta
  commands (`\d`, `\timing`, `\watch`, `\errverbose`), anything debug-flavored
  (changing `client_min_messages`, capturing a backend PID, running EXPLAIN
  ANALYZE in a loop). Default tool.
- **postgres-dev MCP** — read-only one-shots from a planning/exploration loop
  (sampling rows, schema introspection inside agent reasoning). Strictly
  SELECT, no meta-commands, no session knobs. Treat as a convenience for
  agents, not a substitute for psql.

## Daily-loop one-liners (assumes `/pg-start` already ran)

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"

psql -h /tmp -d postgres                                     # interactive
psql -h /tmp -d postgres -c 'SELECT version();'              # one-shot
psql -h /tmp -d postgres -f /tmp/repro.sql                   # script
psql -h /tmp -d postgres -X -P pager=off -At -c '<sql>'      # script-friendly
```

`-X` skips `~/.psqlrc`, `-A` unaligned, `-t` tuples-only, `-P pager=off` keeps
pipes clean.

## High-yield meta-commands for backend work

| Command | What it does |
| --- | --- |
| `\conninfo` | Confirm socket, port, db, user, PID. |
| `\d <name>` / `\d+ <name>` | Schema for table / index / view. `+` adds storage params and tablespace. |
| `\df+ <fn>` / `\sf <fn>` | Function signature / full source — works for SQL & PL/pgSQL bodies. |
| `\sv <view>` | Source of a view. |
| `\dn+`, `\dt+`, `\di+`, `\dm+` | Schemas / tables / indexes / matviews with sizes. |
| `\d+ pg_catalog.<rel>` | Walk a catalog when debugging planner / cache code. |
| `\dconfig <pattern>` | All GUCs matching pattern, current values + source. |
| `\timing on` | Per-query wall time. |
| `\watch <sec>` | Re-run last query every N seconds — great for `pg_stat_activity` / `pg_locks` while reproducing. |
| `\errverbose` | After an error: print code, detail, hint, file:line of the ereport(). The file:line is the elog location in the backend source — pair with the corpus. |
| `\gexec` | Run a query whose result is itself SQL; e.g., generate `DROP TABLE …` from `pg_tables`. |
| `\set ON_ERROR_STOP on` | Make scripted runs abort on first error (default off is footgunny). |
| `\copy table FROM '/path' WITH (FORMAT csv)` | Client-side copy — bypasses server-side permissions. |

## Session knobs that surface backend behavior

```sql
-- Show every DEBUG2-and-louder log line in psql (no need to tail the log).
SET client_min_messages = DEBUG2;

-- Have the server log them too (so they land in dev/data-debug/server.log).
SET log_min_messages = DEBUG2;

-- Log every statement + duration + parse/plan/exec break-down.
SET log_statement = 'all';
SET log_duration = on;
SET log_min_duration_statement = 0;

-- Make EXPLAIN ANALYZE useful for buffer / WAL / IO debugging.
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE) <query>;
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <query>;  -- machine-parseable

-- Force a specific plan shape to confirm a planner hypothesis.
SET enable_seqscan = off;        -- and friends: enable_hashjoin / _nestloop / _indexonlyscan
SET work_mem = '4MB';            -- sort/hash spill threshold
SET jit = off;                   -- rule JIT in/out when timing things
```

All `SET` is session-scoped — exiting psql resets. Use `SET LOCAL` inside a
transaction to scope to that txn.

## Runtime introspection — what is the backend doing?

```sql
-- All sessions + their state, query, wait event, backend PID.
SELECT pid, state, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE backend_type = 'client backend';

-- Memory contexts of THIS backend — top consumers first.
SELECT name, level, parent, total_bytes/1024 AS kb, used_bytes/1024 AS used_kb
FROM pg_backend_memory_contexts
ORDER BY total_bytes DESC LIMIT 20;

-- Memory contexts of ANOTHER backend (PG 14+).
SELECT pg_log_backend_memory_contexts(<pid>);
-- → lands in dev/data-debug/server.log; tail it.

-- Live locks + blockers.
SELECT locktype, relation::regclass, mode, granted, pid
FROM pg_locks ORDER BY relation, pid;

-- Buffer cache hit ratio per relation (run after a workload).
SELECT relname,
       heap_blks_read AS read, heap_blks_hit AS hit,
       round(heap_blks_hit::numeric / nullif(heap_blks_hit + heap_blks_read,0), 3) AS ratio
FROM pg_statio_user_tables ORDER BY hit + read DESC LIMIT 10;
```

## Capturing a backend PID for gdb/lldb

```sql
SELECT pg_backend_pid();
```

Then in another shell: `/pg-attach <pid>` (the slash command wraps lldb with
breakpoints on `errstart` and `MemoryContextStats` pre-set).

If the backend you want to debug doesn't exist yet (e.g., you're studying
startup), use single-user mode instead — see `.claude/skills/debugging/SKILL.md`.

## Memory-leak workflow on the debug build

The build defaults (`-Ddebug=true -Dcassert=true`) wire in the asserts and
the clobber-freed-memory machinery. To hunt a suspected leak:

1. Note baseline:
   ```sql
   SELECT name, total_bytes FROM pg_backend_memory_contexts WHERE name='MessageContext';
   ```
2. Run the suspect workload N times (`\watch` is your friend).
3. Re-check the context — growth across iterations is the leak signature.
4. To pin the leak to a callsite, attach lldb (`/pg-attach <pid>`) and set
   a breakpoint on `MemoryContextAlloc` filtered to the suspect context.
5. macOS-specific: `MallocStackLogging=1` env on the postmaster before
   `pg_ctl start` makes `leaks <pid>` produce real backtraces.

## Safe vs not-safe on the dev cluster

The dev cluster is **disposable** — `dev/data-debug/` can be wiped at any
time via `/pg-fresh`. So:

- ✅ `DROP DATABASE`, `DROP SCHEMA CASCADE`, `TRUNCATE`, anything destructive
  on the dev cluster.
- ✅ `ALTER SYSTEM SET …` for testing GUCs (writes `postgresql.auto.conf`;
  reset with `ALTER SYSTEM RESET <guc>` then `SELECT pg_reload_conf()`).
- ✅ `CREATE EXTENSION` whatever's compiled into `dev/install-debug/share/extension/`.
- ⚠️ Avoid editing `pg_catalog.*` directly — even on the dev cluster it
  often crashes the backend in interesting-but-not-useful ways. If you need
  to perturb catalogs, write a regression test instead.
- ⚠️ `DELETE FROM pg_class …` is exactly the wrong way to do anything.

## Connection-string variants for psql / libpq tools

Built from the trust + socket defaults:

```
postgresql:///postgres?host=/tmp                              # the canonical one
postgresql://$USER@/postgres?host=/tmp                        # explicit user
postgresql:///postgres?host=/tmp&application_name=repro       # tag the session for pg_stat_activity
postgresql:///postgres?host=/tmp&options=-c%20client_min_messages%3DDEBUG2   # set GUC in URL
```

The MCP at `.mcp.json` uses the canonical form. If you need a different
database, edit `.mcp.json` rather than passing flags ad-hoc.

## Common gotchas

- **`psql: connection to server on socket "/tmp/.s.PGSQL.5432" failed: No
  such file or directory`** — the server isn't running, or `unix_socket_directories`
  isn't `/tmp`. Check `dev/data-debug/postgresql.conf`; `/pg-start` sets this.
- **`role "postgres" does not exist`** — `initdb` makes the superuser
  match `$USER`, not literally `postgres`. Connect as your shell user; the
  *database* called `postgres` does exist.
- **Hung session blocks something** — `\watch` `pg_stat_activity` to find
  the blocker PID, then `SELECT pg_terminate_backend(<pid>)`.
- **`SET client_min_messages = DEBUG2` floods psql** — fine for one query,
  painful for an interactive session. Use `SET LOCAL` inside `BEGIN`/`COMMIT`
  for scoped noise.

## Cross-references into corpus

- `knowledge/architecture/process-model.md` — how psql's connection becomes
  a postmaster `fork()` + per-connection backend.
- `knowledge/idioms/error-handling.md` — what `\errverbose` is actually
  showing (the `ereport()` machinery).
- `knowledge/idioms/memory-contexts.md` — interpreting
  `pg_backend_memory_contexts`.
- `knowledge/data-structures/snapshot-lifecycle.md` — what `\d+ <table>`
  is computing under the hood when it touches catalog snapshots.
- `knowledge/subsystems/storage-buffer.md` — what `BUFFERS` in
  `EXPLAIN (ANALYZE, BUFFERS)` is counting.
