# Eval 3 — with_skill

This is the **per-connection fork model gotcha** — `.claude/skills/build-and-run/SKILL.md`
covers it directly. The postmaster forks a fresh backend for every `psql`
connection; query-execution and most startup paths run in that *child*, not
in the postmaster you attached to. lldb on the postmaster will never break.

You have two options.

## Option A: single-user mode (best for startup/recovery code paths)

For code that runs *before* any client connection — `InitPostgres`, recovery,
GUC bootstrap, shared-memory init early in backend startup — use single-user
mode. No postmaster, no fork; the backend runs in the foreground attached
to your terminal:

```bash
postgres --single -D "$PGDATA" postgres
```

You can launch this directly under lldb:

```bash
lldb -- $PWD/dev/install-debug/bin/postgres --single -D "$PGDATA" postgres
(lldb) breakpoint set --name InitPostgres
(lldb) run
```

This is exactly the pattern the skill recommends for "stepping through
startup-time code paths".

## Option B: the `pg_usleep` waitpoint trick

If the code runs in a forked backend during normal startup (post-fork but
before you can possibly type fast enough to attach), inject a sleep in the
source, rebuild, and attach inside the window. This pattern is documented
in `.claude/commands/pg-attach.md`:

```c
/* in the code path you want to catch */
elog(LOG, "WAITPOINT pid=%d sleeping 30s", MyProcPid);
pg_usleep(30 * 1000000L);  /* 30 seconds */
```

Then:

```bash
ninja -C dev/build-debug install
pg_ctl -D "$PGDATA" restart
tail -F "$PGDATA/server.log"   # watch for "WAITPOINT pid=..."
lldb -p <that PID>
```

## Why lldb (not gdb) on macOS

The skill notes: gdb on macOS needs codesigning gymnastics; lldb is the
default Apple debugger and "just works". On Linux you'd use `gdb -p <pid>`.

## Build prerequisites already in place

Your dev clone is built with `--buildtype=debug -Dcassert=true -Ddebug=true`
(see `setup-pg.md`), so symbols are present and inlining is minimal —
backtraces are readable.

## For ordinary (non-startup) query debugging

Use the documented pattern: connect with `psql`, run `SELECT
pg_backend_pid();`, attach lldb to that PID in another terminal. Helper:
`/pg-attach` (`.claude/commands/pg-attach.md`) prints the exact command.
Useful breakpoints from that file: `exec_simple_query`, `ExecutorRun`,
`errfinish`.
