# Eval 3 — with_skill answer

Stopping in `InitPostgres` before any client can connect.

## The decision rule

| Symptom                                                              | Tool                                  |
| -------------------------------------------------------------------- | ------------------------------------- |
| Code runs *before* shared memory is attached / inside `InitPostgres` | `postgres --single`                   |
| Code runs in the forked-backend startup path (post-shmem, pre-query) | `PGOPTIONS="-W N" psql ...`           |
| Code runs in a worker (autovacuum / parallel / bgworker)             | spin-loop waitpoint                   |
| Code runs during a query you can drive from psql                     | normal `lldb -p` attach               |

`InitPostgres` runs during backend startup, partially before the backend
is ready to accept queries. Attaching after psql is connected is too
late (and even `PGOPTIONS="-W N"` happens after the early part of
`InitPostgres`). The clean answer is **single-user mode**.

## Single-user mode

`postgres --single` runs the entire server in a single process — no
postmaster, no fork. The debugger sees the whole lifetime, including
startup, in one PID:

```bash
lldb -- /Users/matej/Work/postgres/postgres-claude/dev/install-debug/bin/postgres \
        --single -D "$PGDATA" postgres
(lldb) b InitPostgres
(lldb) run

# or gdb:
gdb --args postgres --single -D "$PGDATA" postgres
(gdb) b InitPostgres
(gdb) run
```

`$PGDATA` here is `dev/data-debug` and `postgres` (the trailing arg) is
the database name.

### Quirks of single-user mode

- **Newline terminates a command**, not semicolon. Press Enter at the
  end of a statement — semicolons are passed through. Use `-j` to switch
  to "use `;\n\n` as terminator" mode if you're pasting multi-line
  scripts.
- Single-user mode means no concurrent connections — fine because the
  whole point is to debug startup, not concurrency.

## Alternative: `-W N` to pause an early backend

If what you actually want is to stop just *after* the postmaster forks
but before the backend gets to your query (post-shmem, pre-`exec_simple_query`):

```bash
PGOPTIONS="-W 10" psql -d postgres
```

The backend sleeps 10 seconds at startup. In another terminal, get the
PID and attach with `lldb -p <pid>`. This is too late for `InitPostgres`
proper, but ideal for "after auth, before query".

## Alternative: spin-loop waitpoint

For worker processes (autovac, parallel, bgworker) where you can't grab
the PID at all, drop a temporary spin-loop in the C code:

```c
bool wait = true;
elog(LOG, "waiting for debugger, pid=%d", MyProcPid);
while (wait) pg_usleep(1000000L);
```

The `elog(LOG, ...)` writes the PID to the server log
(`dev/data-debug/server.log`) so you can find the right process. Tail it
with `/pg-tail-log`, then `lldb -p <pid>`, then `expr wait = 0` to
release.

## Summary for your case

`InitPostgres` → use `postgres --single`. That's the one that lets the
debugger watch startup end-to-end without a fork in between.
