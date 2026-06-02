# Eval 3 — baseline answer (no skill)

Stopping in `InitPostgres` before any client can connect.

## Use single-user mode

The right answer is `postgres --single`. It runs the entire server as a
single process — no postmaster, no fork — so the debugger follows
startup, including everything in `InitPostgres`, end to end.

```bash
gdb --args postgres --single -D "$PGDATA" postgres
# or, on macOS:
lldb -- postgres --single -D "$PGDATA" postgres

(gdb) b InitPostgres
(gdb) run
```

`postgres` at the end is the database name. `$PGDATA` is your data
directory (`dev/data-debug`).

## Why this works

Because there's no fork, the PID you launched under the debugger *is* the
PID running `InitPostgres`. Contrast with the normal multi-process mode:
the postmaster accepts a connection, forks a child, and the child runs
`InitPostgres` in a PID the debugger has never seen.

## Alternative: pause the forked backend with PGOPTIONS=-W

If you actually only need to break after auth and shmem (not in the
earliest parts of `InitPostgres`), you can use:

```bash
PGOPTIONS="-W 10" psql -d postgres
```

The backend sleeps 10 seconds at startup, giving you time to grab its
PID (from psql via `pg_backend_pid()` or from `ps`) and `lldb -p` /
`gdb -p` it before it proceeds. That said, this is *after* the
postmaster has already forked — so for code that runs *before* the
backend is ready, it's not early enough. Use `--single` instead.

## Decision

- Need to step the very beginning of startup, or pre-shmem code →
  `postgres --single`.
- Need to step post-shmem, post-auth, pre-first-query →
  `PGOPTIONS="-W N"` and attach by PID.
