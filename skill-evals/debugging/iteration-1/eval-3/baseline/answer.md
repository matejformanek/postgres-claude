# Debugging early backend startup (general knowledge)

The challenge: by the time psql is connected and you can run `pg_backend_pid()`, the startup code has already executed. You need to either pause the backend during startup, or change how it's invoked so the debugger is attached from the start.

## Option 1 — single-user mode

Postgres can run as a standalone backend without the postmaster:

```bash
postgres --single -D /path/to/PGDATA dbname
```

In this mode there's no fork — it's one process from start to finish. So you can launch it under a debugger:

```bash
# Linux
gdb --args postgres --single -D $PGDATA postgres

# macOS
lldb -- postgres --single -D $PGDATA postgres
```

Then set a breakpoint on `InitPostgres` (or wherever) and `run`.

A couple of quirks of single-user mode that catch people: I believe it reads commands from stdin line by line, and the terminator behavior is different from psql. I'd want to double-check the docs on the exact terminator.

## Option 2 — `PGOPTIONS="-W N"`

There's a startup delay option you can pass through PGOPTIONS that makes the backend sleep for N seconds at startup. Something like:

```bash
PGOPTIONS="-W 10" psql -d postgres
```

That gives you a 10-second window to find the PID and attach. You'd need to `ps` for it or grep the log since you can't run a SQL query yet.

## Option 3 — sleep loop in the code

The dirtiest but most reliable: add a temporary loop in the source where you want to stop, rebuild, run it, attach, then set the loop variable to false.

```c
volatile bool wait = true;
while (wait) sleep(1);
```

This works for anything — including background workers and parallel workers where there's no psql to query.

## When to use which

- For InitPostgres specifically: single-user mode is the cleanest. You get the whole startup sequence in one debuggable process.
- For verifying behavior of the actual forked-backend path: PGOPTIONS -W.
- For weird workers (autovac, parallel): the sleep loop is sometimes the only option.

I'd lean on single-user mode for InitPostgres unless there's a reason the forked path matters.
