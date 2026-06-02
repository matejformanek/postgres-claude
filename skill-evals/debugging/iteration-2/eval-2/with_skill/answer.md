# Eval 2 — with_skill answer

SIGSEGV in a new C function — how to narrow it down on macOS.

## 1. Build the right binary

Make sure you're running the `--buildtype=debug -Dcassert=true` build out
of `dev/build-debug`. Asserts catch a lot of misuse (palloc context
mismatches, null pointer derefs, lock-order violations) *before* they
turn into a segfault. If your crashing function violates an invariant, an
`Assert(...)` somewhere upstream will likely fire first and give you a
much better stack trace than the bare SIGSEGV does.

## 2. Enable core dumps on macOS (so you can post-mortem the crash)

Three things must all be true:

```bash
ulimit -c unlimited                # in the shell that starts postgres
ls -ld /cores                      # must exist & be writable
sudo chmod 1777 /cores             # if not
sysctl kern.coredump               # should be 1; or "unknown oid" → ulimit alone suffices
```

Caveat: Apple-signed / hardened binaries suppress cores regardless of
ulimit. Our `dev/install-debug/bin/postgres` is locally built and
unsigned, so this is fine — just don't try to core-dump a Homebrew
bottle.

Then trigger the crash and:

```bash
lldb /Users/matej/Work/postgres/postgres-claude/dev/install-debug/bin/postgres /cores/core.<pid>
(lldb) bt all
```

## 3. Attach BEFORE it crashes (often more productive)

Post-mortem cores show the final frame, but if your new function corrupts
state long before the segfault you want to step it live. From the
crashing psql session:

```sql
SELECT pg_backend_pid();
```

In another terminal (use `/pg-attach` for the shortcut):

```
lldb -p <pid>
(lldb) pro hand -p true -s false SIGUSR1     # silence latch wakeups
(lldb) b my_new_function
(lldb) c
```

## 4. Trap any error before the SEGV — `errfinish`

If your function calls into PG code that raises an `ereport(ERROR, ...)`
before the segfault, you want to stop on that first. `errfinish` is the
single funnel every `ereport`/`elog` goes through:

```
(lldb) b errfinish
(lldb) br mod -c 'edata->elevel >= 21'   # ERROR = 21 in elog.h
```

Now any ERROR/FATAL/PANIC stops you with a usable stack — frequently
the *cause* of the subsequent segfault is an unhandled error path.

## 5. If it crashes too fast to attach

For paths that fire before you can grab the PID:

- `PGOPTIONS="-W 10" psql ...` — the backend sleeps 10 seconds at startup
  so you can `pg_backend_pid()` + `lldb -p` in another terminal.
- Drop a temporary spin-loop directly in your suspect C code:
  ```c
  bool wait = true;
  elog(LOG, "waiting for debugger, pid=%d", MyProcPid);
  while (wait) pg_usleep(1000000L);
  ```
  Tail `dev/data-debug/server.log` to see the PID, attach, then
  `expr wait = 0` to release.

## 6. Lightweight instrumentation if the debugger feels heavy

Sprinkle `elog(DEBUG1, "my_new_func: step=%d, ptr=%p", step, p)` and run
with `log_min_messages = debug1`. Often "which branch did I take and
what's the pointer value" is enough to localize the crash without a full
debugger session.

## Order to try

1. Run with cassert build → see if an Assert fires first.
2. `errfinish` breakpoint → catch any ERROR before the SEGV.
3. Breakpoint on the new function → step in live.
4. If too fast: `-W 10` or spin-loop waitpoint.
5. If unattended: core dump from `/cores/core.<pid>`, open with lldb.
