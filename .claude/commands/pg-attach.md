---
description: Get a backend PID and print the lldb attach command + useful breakpoints.
---

# pg-attach

PostgreSQL uses a per-connection fork model: every `psql` session spawns a
fresh backend process. To debug backend code you have to attach to the *right*
PID — the one serving your psql connection.

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"

# Verify the postmaster is up
if ! pg_ctl -D "$PWD/dev/data-debug" status >/dev/null 2>&1; then
  echo "Postmaster not running. Start it with /pg-start first."
  exit 1
fi

# Grab the PID of a backend (this opens a connection, asks, closes)
PID=$(psql -h /tmp -d postgres -tAc "SELECT pg_backend_pid()" | head -1)

if [ -z "$PID" ]; then
  echo "Could not get backend PID — is the cluster reachable on /tmp?"
  exit 1
fi

echo "Backend PID: $PID"
echo ""
echo "Attach with:"
echo "  lldb -p $PID"
echo ""
echo "Note: that PID belongs to the psql session that just exited."
echo "For an interactive session, open psql in another terminal, run"
echo "  SELECT pg_backend_pid();"
echo "and attach to *that* PID — it persists for the life of that connection."
```

## Useful breakpoints (lldb)

Once attached, inside `(lldb)`:

```
breakpoint set --name exec_simple_query
breakpoint set --name ExecutorRun
breakpoint set --name errfinish        # catches every ereport()
continue
```

- `exec_simple_query` — entry point for any text-protocol query (`tcop/postgres.c`).
- `ExecutorRun` — the executor's per-statement entry (`executor/execMain.c`).
- `errfinish` — every error report goes through here; great for catching the
  exact moment an `ERROR` is raised.

## The `pg_usleep` waitpoint pattern

Some interesting code runs *before* you can possibly attach (startup, recovery,
early backend init). To catch it, add a sleep in the source and rebuild:

```c
/* in the code path you want to catch */
elog(LOG, "WAITPOINT pid=%d sleeping 30s", MyProcPid);
pg_usleep(30 * 1000000L);  /* 30 seconds */
```

Then `/setup-pg` to rebuild, `/pg-start`, watch `dev/data-debug/server.log` for
the WAITPOINT line with PID, and `lldb -p <pid>` within the 30s window.

## macOS note

`lldb` is the right tool on macOS — `gdb` works but needs codesigning gymnastics
the system tooling doesn't ship with. On Linux, `gdb -p <pid>` is the equivalent.

## Troubleshooting

- **`error: attach failed: Operation not permitted`**: macOS SIP / hardened
  runtime. Either run lldb under sudo (`sudo lldb -p $PID`) or ensure the
  postgres binary you built isn't hardened (debug builds normally aren't).
- **Backend exits before you attach**: the PID you got was from a transient
  psql. Open an interactive psql in a separate terminal, get its
  `pg_backend_pid()`, and attach while that session stays open.
- **Breakpoint never hits**: you may have attached to the postmaster instead
  of a backend. The postmaster forks for each connection; breakpoints on
  query-execution functions only fire in backends.
