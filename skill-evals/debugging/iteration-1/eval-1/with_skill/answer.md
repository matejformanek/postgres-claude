# Attaching lldb to the backend serving a slow query (macOS)

Per `.claude/skills/debugging/SKILL.md`, PostgreSQL is a multi-process server — the postmaster forks a fresh backend per connection. The postmaster itself never executes your query, so **do not attach to the postmaster PID**. You must attach to the specific backend handling your psql session (SKILL.md §2, lines 26–28).

## Step 1 — identify the right PID

In the psql session running the slow query (keep it open):

```sql
SELECT pg_backend_pid();
 pg_backend_pid
----------------
          54321
```

That PID belongs to *this* connection's backend and persists for the life of the connection (SKILL.md §2, lines 29–35; also `.claude/commands/pg-attach.md` Troubleshooting note: "the PID you got was from a transient psql ... Open an interactive psql in a separate terminal, get its `pg_backend_pid()`, and attach while that session stays open").

## Step 2 — use lldb (not gdb) on macOS

Use `lldb -p 54321`. On Darwin, `gdb` requires a code-signed binary with the `com.apple.security.cs.debugger` entitlement; `lldb` ships with Xcode Command Line Tools and works out of the box (SKILL.md §2, lines 39–51; `.claude/commands/pg-attach.md` macOS note lines 74–76).

The project ships a slash command that automates PID grabbing + prints the attach line: `/pg-attach` (see `.claude/commands/pg-attach.md`).

## Step 3 — silence SIGUSR1 in lldb

PostgreSQL uses `SIGUSR1` heavily for latch wakeups; without silencing it, every `continue` lands back in the signal handler (SKILL.md §2, lines 62–65):

```
(lldb) pro hand -p true -s false SIGUSR1
```

(The gdb equivalent is `handle SIGUSR1 noprint pass`.)

## Step 4 — breakpoint at the executor entry

From SKILL.md §5 (lines 113–129) and `.claude/commands/pg-attach.md` lines 47–52:

```
(lldb) b ExecutorRun
(lldb) continue
```

Other useful executor breakpoints: `ExecutorStart`, `ExecutorEnd`, or `exec_simple_query` (entry point for any text-protocol query, `src/backend/tcop/postgres.c`).

## Step 5 — pretty-print the PlannedStmt Node*

PostgreSQL ships `pprint()` for `Node *` trees. From lldb (SKILL.md §6, lines 132–142):

```
(lldb) expr pprint(queryDesc->plannedstmt)
```

(In gdb it would be `call pprint(...)`.) Output goes to the backend's stderr — i.e. `dev/data-debug/server.log` in this project. Tail it with `/pg-tail-log` in another terminal.

## Then in the psql session

Re-run the slow query. The breakpoint fires, the backtrace is yours, and `pprint` dumps the plan tree into the server log.
