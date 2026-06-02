# Eval 1 — baseline answer (no skill)

End-to-end on macOS.

## 1. Find the right PID

PostgreSQL forks a separate backend per connection (multi-process server,
not threaded). The postmaster never runs your query — you need to attach
to the specific backend that's serving the slow psql session. From
*inside* that psql session (not a fresh one — a new connection would give
you a different PID):

```sql
SELECT pg_backend_pid();
```

That returns the PID, e.g. 54321.

## 2. Use lldb on macOS

On macOS, lldb is the path of least resistance. gdb on Darwin requires a
code-signed binary with debugging entitlements (a hassle); lldb ships
with the Xcode Command Line Tools and Just Works.

```bash
lldb -p 54321
```

(Run as your user if you launched postgres as your user; otherwise `sudo
lldb -p 54321`.)

## 3. Breakpoint at the executor entry

The executor entry points are in `src/backend/executor/execMain.c`:
`ExecutorStart`, `ExecutorRun`, `ExecutorEnd`. `ExecutorRun` is usually
what you want — it's the driver that pulls tuples.

```
(lldb) b ExecutorRun
(lldb) c
```

If you also want to catch parse/plan/execute as a whole, break on
`exec_simple_query` in `src/backend/tcop/postgres.c`.

## 4. The query resumes when you continue

Once attached, lldb pauses the backend. The slow query was stalled there;
on `continue` it runs and you hit `ExecutorRun`.

## 5. Tip

The path to your debug-built postgres is in
`postgres-claude/dev/install-debug/bin/postgres`. lldb will pick up the
symbols automatically since you attached by PID.
