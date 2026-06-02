# Eval 3 — with_skill (iter-2)

This is the **per-connection fork model gotcha** — covered directly in
`.claude/skills/build-and-run/SKILL.md`. The postmaster forks a fresh
backend for every `psql` connection; query execution and most startup
paths run in that *child*, not in the postmaster. lldb attached to the
postmaster will never break.

You have two main options.

## Option A: single-user mode under lldb (best for startup paths)

For code that runs *before* any client connection — `InitPostgres`,
recovery, GUC bootstrap, shared-memory init — use single-user mode. No
postmaster, no fork; the backend runs in the foreground attached to your
terminal. Launch it directly under lldb so you're at instruction 0 with
no race (this is the new "Launching single-user mode under lldb"
subsection):

```bash
lldb -- $PWD/dev/install-debug/bin/postgres --single -D "$PGDATA" postgres
(lldb) breakpoint set --name InitPostgres
(lldb) run
```

This sidesteps the per-connection fork problem entirely.

## Option B: attach to a live backend (query debugging)

For *post-startup* query debugging, attach to a live forked backend by PID:

1. Connect with `psql` and capture the backend PID:

   ```sql
   SELECT pg_backend_pid();
   ```

2. In another terminal, attach lldb to that PID:

   ```bash
   lldb -p <pid>
   ```

3. Set breakpoints (`exec_simple_query`, `ExecutorRun`, `errfinish`),
   continue, then issue your query in the `psql` session.

The slash command `/pg-attach` (`.claude/commands/pg-attach.md`,
indexed at the top of the skill) automates the `SELECT pg_backend_pid()`
+ `lldb -p <pid>` flow.

## Option C: the `pg_usleep` waitpoint

For code paths in a forked backend that fire before you can type fast
enough to attach (post-fork early init, autovacuum workers, parallel
workers), inject a sleep, rebuild, and attach inside the window:

```c
/* in the code path you want to catch */
elog(LOG, "WAITPOINT pid=%d sleeping 30s", MyProcPid);
pg_usleep(30 * 1000000L);  /* 30 seconds */
```

Then:

```bash
ninja -C dev/build-debug install
pg_ctl -D "$PGDATA" restart    # mandatory — see edit/rebuild/retest section
tail -F "$PGDATA/server.log"   # watch for "WAITPOINT pid=..."
lldb -p <that PID>
```

## Why lldb (not gdb) on macOS

gdb on macOS needs codesigning gymnastics; lldb is Apple's default
debugger and "just works". On Linux you'd use `gdb -p <pid>` instead.

## Build prerequisites already in place

Your dev clone is built with `--buildtype=debug -Dcassert=true
-Ddebug=true` (see the skill's one-time setup), so symbols are present,
asserts are live, and inlining is minimal — backtraces are readable.
