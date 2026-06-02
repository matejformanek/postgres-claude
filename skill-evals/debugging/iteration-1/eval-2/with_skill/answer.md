# Narrowing down a SIGSEGV in a new heapam C function (macOS)

Per `.claude/skills/debugging/SKILL.md` §11 (Quick checklist, lines 269–281), the right order is: debug+cassert build → server log → attach lldb at a breakpoint → core dump if it crashed.

## 1. Rebuild with debug + cassert

From SKILL.md §1 (lines 13–18): only debug builds are usable. Configure with `--buildtype=debug -Dcassert=true` (cross-ref `.claude/skills/build-and-run/SKILL.md`). `cassert` makes `Assert()` macros fire — many invariants in heapam are guarded that way and they will catch corruption *before* the SIGSEGV.

Also consider `CFLAGS="-ggdb -Og -g3 -fno-omit-frame-pointer"` for autoconf-style builds (SKILL.md §1, lines 20–22; from the upstream Developer_FAQ).

## 2. Enable core dumps on macOS

From SKILL.md §8 (lines 177–204) — three prerequisites:

```bash
# In the shell that launches postgres:
ulimit -c unlimited

# /cores must exist and be writable
ls -ld /cores
sudo chmod 1777 /cores      # if needed

# kern.coredump sysctl
sysctl kern.coredump        # expect: kern.coredump: 1
```

Restart the cluster from that shell (so the postmaster — and the backends it forks — inherit the ulimit). When the backend SIGSEGVs, you get `/cores/core.<pid>`.

**macOS gotcha** (SKILL.md §8, lines 206–208): cores from Apple-signed binaries are suppressed regardless of ulimit. A locally-built `postgres` is unsigned, so this isn't a concern — but if you ever try to debug `/usr/bin/...` you won't get a core.

Open the core:

```bash
lldb /Users/matej/Work/postgres/postgres-claude/dev/install-debug/bin/postgres /cores/core.<pid>
(lldb) bt
```

## 3. Catch the crash live instead of (or in addition to) a core

A core gives you the state at the moment of death; an interactive attach lets you single-step the approach. Get the backend PID with `SELECT pg_backend_pid();` from psql, then `lldb -p <pid>` (SKILL.md §2; project slash command `/pg-attach`).

### Break on every ereport(ERROR)

From SKILL.md §5 (lines 113–129) and `.claude/commands/pg-attach.md` lines 47–52:

```
(lldb) b errfinish
(lldb) continue
```

Every `ereport()`/`elog()` funnels through `errfinish`. Filter on `edata->elevel >= ERROR` to skip routine LOG messages. This is how you catch the exact moment an ERROR is raised — which often precedes (or replaces) the segfault if your code at least manages to call `ereport` before going off the rails.

### Catch fast/early paths

If the crash happens before you can grab the PID (SKILL.md §4, lines 88–110):

- `PGOPTIONS="-W 10" psql ...` — backend sleeps 10s at startup so you can attach.
- Insert a temporary spin-loop waitpoint in your code:
  ```c
  bool wait = true;
  elog(LOG, "waiting for debugger, pid=%d", MyProcPid);
  while (wait) pg_usleep(1000000L);
  ```
  Attach, then `(lldb) expr wait = 0` to release. Project's `/pg-attach` command documents the same pattern (lines 59–71).

## 4. Pure-instrumentation alternative

If a debugger is overkill (SKILL.md §7, lines 159–175):

```c
elog(DEBUG1, "myfunc: ptr=%p, n=%d", ptr, n);
```

Set `log_min_messages = debug1` and tail the log (`/pg-tail-log`). This is often faster than stepping for "which path got taken" questions.

## Core vs live attach — when to use which

- **Live attach**: best when the bug is reproducible on demand. You can set conditional breakpoints, inspect call sites, step into the failing call.
- **Core dump**: best when the crash is rare/non-deterministic or happens deep in a long test. You don't need to re-run. But you only see the post-mortem state — locals on the trapping frame may be optimized away even in a `-Og` build.

In practice for a new function that segfaults during a regression test: enable cores *and* set a breakpoint on `errfinish` while running the test interactively. Whichever fires first tells you something.
