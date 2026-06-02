# Attaching a debugger to a Postgres backend (general knowledge)

PostgreSQL is a multi-process server: each connection is served by a separate backend process. You need to attach to the backend serving your psql, not to the postmaster.

## Find the backend PID

From the psql session you want to debug:

```sql
SELECT pg_backend_pid();
```

This returns the OS PID of the backend handling that connection. Keep the session open so the process stays alive.

## Pick the debugger

On macOS, prefer lldb. gdb on macOS is painful — it requires code-signing the gdb binary with debugging entitlements, and Apple's toolchain doesn't ship it. lldb comes with the Xcode Command Line Tools.

```bash
lldb -p <pid>
```

On Linux you'd use `gdb -p <pid>`.

Make sure Postgres was built with debug symbols (typically `CFLAGS="-O0 -g"` or similar) — otherwise stepping and symbol resolution will be useless.

## Set a breakpoint at the executor entry point

The main executor entry points in Postgres are:

- `ExecutorStart` — sets up state for plan execution
- `ExecutorRun` — actually drives tuple production
- `ExecutorEnd` — cleanup

For text-protocol queries, `exec_simple_query` is the entry from the protocol layer.

In lldb:

```
(lldb) breakpoint set --name ExecutorRun
(lldb) continue
```

Or short form: `b ExecutorRun`.

Then run the query in psql and the breakpoint should fire.

## Notes

- Don't attach to the postmaster — it spawns backends but doesn't execute queries itself.
- If the breakpoint never hits, double-check you attached to the right PID and that you didn't accidentally pick up a transient psql connection's PID.
- You might need `sudo lldb -p <pid>` depending on macOS security settings.
