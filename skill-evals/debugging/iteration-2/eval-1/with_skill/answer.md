# Eval 1 — with_skill answer

End-to-end recipe on macOS against the local `dev/` build.

## 1. Get the PID of the *right* backend

PostgreSQL is multi-process: the postmaster forks a fresh backend per
connection. Attaching to the postmaster won't help — it never runs your
query. You need the PID of the specific backend serving your psql
session. Get it from inside that session:

```sql
-- in the slow psql session itself, NOT a transient one
SELECT pg_backend_pid();
 pg_backend_pid
----------------
          54321
```

A second `psql` invocation would fork a different backend and give you a
useless PID.

## 2. Project shortcut

In this repo, `/pg-attach` automates the `pg_backend_pid()` grab and
prints the exact `lldb -p <pid>` line ready to paste. `/pg-tail-log`
follows `dev/data-debug/server.log` (where `elog` output and `pprint`
results land). Use them.

## 3. Attach with lldb (macOS)

```bash
lldb -p 54321
```

Use lldb rather than gdb on macOS. gdb on Darwin needs a code-signed
binary with the `com.apple.security.cs.debugger` entitlement, which is a
pain; lldb ships with Xcode Command Line Tools and works against your
`dev/install-debug/bin/postgres` immediately.

## 4. First thing after attach — silence SIGUSR1

PostgreSQL uses SIGUSR1 heavily for latch wakeups. If you don't tell the
debugger to ignore it, every `continue` lands back in the signal handler:

```
(lldb) pro hand -p true -s false SIGUSR1
```

## 5. Set the breakpoint at the executor entry point

The real executor entry points (pick one):

- `ExecutorStart` — plan tree just received, before run.
- `ExecutorRun` — the actual per-tuple execution driver. This is the
  "executor entry point" most people mean.
- `ExecutorEnd` — teardown.
- `exec_simple_query` (`src/backend/tcop/postgres.c`) is one level higher
  if you want to also see parse + plan.

```
(lldb) b ExecutorRun
(lldb) c
```

The query, which has been stuck because you froze the backend, will
resume and hit your breakpoint.

## 6. Useful next steps once stopped

- `bt` — backtrace.
- `expr pprint(queryDesc->plannedstmt->planTree)` — pretty-print the plan
  tree. Output goes to the server log (`dev/data-debug/server.log` — tail
  it with `/pg-tail-log`).

That's it: get the PID from the right session, `lldb -p`, silence
SIGUSR1, break on `ExecutorRun`, continue.
