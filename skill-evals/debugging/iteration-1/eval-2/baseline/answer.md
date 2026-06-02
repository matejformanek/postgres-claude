# Narrowing down a SIGSEGV in a new C function (general approach)

## Build with debug symbols

First, make sure you've built Postgres with debug symbols and ideally with assertions enabled. Optimization makes stack frames and locals harder to read, so use `-O0` or `-Og`.

For meson builds: `meson setup --buildtype=debug ...`. For autoconf: `./configure --enable-debug --enable-cassert CFLAGS="-O0 -g3"`.

Assertions (`--enable-cassert`) often catch the problem before the segfault — Postgres sprinkles `Assert()` macros liberally throughout heapam.

## Enable core dumps on macOS

In the shell where you launch the postmaster:

```bash
ulimit -c unlimited
```

macOS writes cores to `/cores/core.<pid>`. The `/cores` directory must exist and be writable:

```bash
sudo mkdir -p /cores
sudo chmod 1777 /cores
```

You may also need `sysctl kern.coredump=1` though this is typically the default.

Then trigger the crash and open the core:

```bash
lldb /path/to/postgres /cores/core.<pid>
(lldb) bt
(lldb) frame variable
```

## Attach to the live backend before the crash

You can also attach lldb before the crash happens, so you can step through the code. Get the PID from psql:

```sql
SELECT pg_backend_pid();
```

Then `lldb -p <pid>`. Set a breakpoint somewhere in your function:

```
(lldb) b your_function_name
(lldb) continue
```

When the breakpoint hits, you can step (`n`, `s`) and inspect variables.

## Use elog/printf instrumentation

A quick way to bisect "where does it die" without a debugger is to sprinkle `elog(LOG, "got here, x=%d", x)` calls and watch the server log. Cheap, fast, and the output ends up in `dev/data-debug/server.log` (or wherever you configured logging).

Once the last LOG message that appears tells you the function returned from line N but not N+1, you've localized it.

## Misc

- If lldb says "attach failed: Operation not permitted", try with sudo.
- Make sure the backend you're attaching to is the one running your query (not a transient psql or the postmaster).
- A SIGSEGV usually means a null/wild pointer dereference. Common culprits in new C code touching heap: forgetting to `LockBuffer`, dereferencing a HeapTuple before calling `ItemIdIsNormal`, using freed memory across a memory context reset.
