# Eval 2 — baseline answer (no skill)

SIGSEGV in a new C function.

## 1. Use a debug + assertions build

Configure with `--buildtype=debug -Dcassert=true` (meson) or
`--enable-debug --enable-cassert` (autoconf). cassert turns on the
`Assert()` macros throughout the backend — they often catch the
underlying invariant violation a few frames before the SIGSEGV and give a
much clearer signal than a raw segfault would.

## 2. Get a core dump

On macOS:

```bash
ulimit -c unlimited       # in the shell that started postgres
sudo mkdir -p /cores && sudo chmod 1777 /cores
```

Crash the backend, then:

```bash
lldb /path/to/postgres /cores/core.<pid>
(lldb) bt
```

That gives you the failing frame and the call chain.

## 3. Attach lldb live

If the crash is reproducible from psql, attach to the live backend before
it dies:

```sql
SELECT pg_backend_pid();
```

```bash
lldb -p <pid>
(lldb) b my_new_function
(lldb) c
```

Step in and watch where it dies.

## 4. Instrument with elog/ereport

Sprinkle `elog(LOG, "...")` or `elog(DEBUG1, "...")` calls around the
suspect lines and tail the server log. Often a few well-placed logs
localize the crash without needing the debugger at all.

Alternatively, a `pg_usleep(...)` spin-loop is a classic trick for paths
that run too fast to attach — log the PID, sleep, attach, then exit the
loop manually.

## 5. Common causes for "new C function segfaults"

- Returning a pointer to a palloc'd value from a context that's been
  freed (memory context lifetime).
- Forgetting `PG_FUNCTION_ARGS` boilerplate / using wrong argument macros.
- Not handling NULL inputs with `PG_ARGISNULL`.

Check those first.
