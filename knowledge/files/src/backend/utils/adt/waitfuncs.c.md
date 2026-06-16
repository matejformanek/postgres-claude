# src/backend/utils/adt/waitfuncs.c

## Purpose

Wait-event SQL helpers. Despite the file name, this currently houses exactly
one function: `pg_isolation_test_session_is_blocked(blocked_pid,
interesting_pids[])` — a privately-used helper for the isolation tester to
detect blockage. [from-comment] (`waitfuncs.c:1-12`)

## Role in PG

- Called from `src/test/isolation/isolationtester.c` to ask "is session
  PID `blocked_pid` waiting on anything caused by one of these other
  PIDs?". Used to time advancing of the isolation script.
- Comment is explicit: "undocumented function intended for use by the
  isolation tester, and may change in future releases" (`waitfuncs.c:36-37`).
  Therefore NOT considered a stable user API.

## Key functions

- `pg_isolation_test_session_is_blocked(PG_FUNCTION_ARGS)` —
  (`waitfuncs.c:38-113`). Three blockage probes:
  1. **Injection point wait** — `BackendPidGetProc(blocked_pid)` then
     check `proc->wait_event_info`'s wait-event type against the
     `"InjectionPoint"` string (`waitfuncs.c:54-61`). Atomically read
     via the local `UINT32_ACCESS_ONCE` macro
     (`waitfuncs.c:23`).
  2. **Heavyweight-lock blockage** — calls
     `DirectFunctionCall1(pg_blocking_pids, blocked_pid)` and
     intersects with `interesting_pids` by O(n*m) nested loops
     (deliberately, to avoid cache lookups when
     `debug_discard_caches > 0`, `waitfuncs.c:84-92`).
  3. **Safe-snapshot wait (SSI)** —
     `GetSafeSnapshotBlockingPids(blocked_pid, &dummy, 1) > 0`
     (`waitfuncs.c:108-110`). Doesn't bother checking which PIDs are
     blockers because autovacuum never blocks `GetSafeSnapshot`, so
     any blocker is interesting.

## State / globals

None.

## Phase D notes

- Trust: caller can pass any PID and probe its wait state via
  `BackendPidGetProc`. `BackendPidGetProc` itself is open to any backend
  in shared memory (returns NULL if no such backend), so this exposes
  no more than reading `pg_stat_activity`. [inferred]
- The function returns `false` when the target PID has exited
  (`waitfuncs.c:56-57`); isolationtester relies on that.

## Potential issues

- [ISSUE-undocumented-invariant: the comment warns the function may
  change. Anyone discovering and using it for non-isolationtester
  purposes will break on minor upgrades (low)]
- [ISSUE-info-disclosure: callable by PUBLIC unless explicitly
  revoked; lets a low-privilege role enumerate which PIDs of high-privilege
  sessions are blocked — but only on heavyweight locks they themselves
  participate in, since interesting_pids is caller-supplied (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
