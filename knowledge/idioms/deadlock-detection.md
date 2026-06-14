# Deadlock detection — DeadLockCheck cycle-finding

Unlike LWLocks (no detector — discipline enforced),
**heavyweight locks have a deadlock detector**. When a
backend has been blocked on a heavyweight lock for
`deadlock_timeout` (default 1 second), it triggers
`DeadLockCheck()` which walks the wait-graph looking for
cycles. If a cycle is found, ONE backend (the "victim") is
aborted; the deadlock is broken.

Anchors:
- `source/src/backend/storage/lmgr/deadlock.c` —
  implementation [verified-by-code]
- `source/src/backend/storage/lmgr/deadlock.c:80-86` —
  recursive cycle-find functions
- `knowledge/idioms/lwlock-rank-discipline.md` — companion;
  no-detector LWLock world
- `knowledge/data-structures/locallock.md` — per-backend
  lock cache

## The triggering mechanism

`deadlock_timeout` GUC (default 1000 ms):

1. A backend waits on a heavyweight lock.
2. After `deadlock_timeout`, a SIGALRM fires.
3. The signal handler runs `DeadLockCheck` (NOT in the
   signal handler proper — defers to a safe point).
4. The check walks the wait-graph.
5. If a cycle is found, the LAST-acquired lock is aborted
   (the victim is the backend whose acquire would close the
   cycle).

If `DeadLockCheck` finds no cycle, the backend continues
waiting. The check runs on every subsequent waiter timeout
until either lock acquisition succeeds or a cycle is found.

## The graph model

The wait-graph is:
- **Nodes**: backends (PGPROC pointers).
- **Edges**: "this backend is waiting on a lock held by
  that backend."

A deadlock = a cycle in this graph.

Example:
```
proc A waits on Lock X (held by B)
proc B waits on Lock Y (held by A)
```

Cycle: A → B → A.

## FindLockCycle — the worker function

[verified-by-code `deadlock.c:82-86`]

```c
static bool FindLockCycle(PGPROC *checkProc, ...);
static bool FindLockCycleRecurse(PGPROC *checkProc,
                                  int depth, ...);
```

The recursion:

1. Start at the waiter `checkProc`.
2. For each lock the waiter wants, find who HOLDS it.
3. For each holder, recurse — what are THEY waiting on?
4. If recursion returns to `checkProc`, cycle found.

Max recursion depth is bounded by `MaxBackends` (the number
of process slots).

## The workspace — per-backend allocation

[verified-by-code `deadlock.c:102-151`]

Per-backend storage for the cycle-walk:

```c
static PGPROC **visitedProcs;     /* MaxBackends entries */
static DeadLockEdge *deadlockDetails;
```

Allocated at `InitDeadLockChecking` during backend startup,
NOT at deadlock check time. Allocating during the check
would risk OOM in already-busy state.

## The "soft" vs "hard" edge

Some lock-wait relationships can be resolved by reordering:

- **Hard edge**: P1 holds X mode A; P2 wants X mode B that
  conflicts with A; P2 must wait.
- **Soft edge**: P1 has X mode A in a SOFT queue position
  (e.g., behind another waiter). Reordering could avoid the
  cycle.

`DeadLockCheck` tries reordering FIRST. Only if reordering
can't resolve the cycle does it pick a victim.

## Victim selection

The victim is the backend whose lock-wait CLOSES the cycle —
i.e., the one whose acquire is the "last edge" added. This
is heuristic but gives consistent victim selection across
runs.

## The victim error

The aborted backend sees:

```
ERROR:  deadlock detected
DETAIL:  Process N waits for ExclusiveLock on row ...
         Process M waits for ExclusiveLock on row ...
         Process N: ...
         Process M: ...
HINT:    See server log for query details.
```

Server log includes the full lock graph that triggered
detection. Application code is expected to retry the
transaction on this error (it's the protocol's promise that
deadlock-victim transactions can always be retried).

## The detector's runtime cost

Cycle detection runs when SOME backend's wait exceeds the
timeout — not continuously. Even on a busy system, the
detector fires only a few times per second.

The walk itself is fast — O(backends × avg lock count).
A 100-backend cluster with 10 locks each is ~1000
edge-traversals.

## Why heavyweight has a detector but LWLock doesn't

- **Heavyweight locks are user-controllable** (via SQL).
  Users can construct cyclic wait patterns; detector saves
  them.
- **LWLocks are PG internals**. Code discipline ensures no
  cycles. Cheaper than a detector.
- **LWLock acquire is microseconds**; deadlock-check
  overhead would dominate.
- **Heavyweight acquire is potentially milliseconds**;
  detector overhead is amortized.

## Configurable behavior

- **`deadlock_timeout`** — how long to wait before
  triggering detection. Default 1s.
- **`log_lock_waits`** — log every lock wait exceeding
  `deadlock_timeout`. Useful for spotting near-deadlock
  patterns.
- **`max_locks_per_transaction`** — affects detector's
  walk size; larger = more work per check.

## Detection in two-phase commit

Prepared transactions (XID held in `pg_twophase/`) can
hold locks indefinitely. The detector handles this:

- A prepared transaction's PGPROC slot remains in
  `ProcArray`.
- Wait edges to that PGPROC are valid.
- Cycle detection works as if the prepared TX were just a
  long-running backend.

The downside: a prepared transaction can be the "ghost
holder" of a lock cycle forever; only manual
`COMMIT/ROLLBACK PREPARED` resolves.

## Common review-time concerns

- **New lock-acquisition paths must respect the standard
  ordering.** Don't construct cycles that detector then
  has to break — annoying for users.
- **Lock acquire from inside a trigger** can deadlock with
  the wrapping statement; common bug.
- **`deadlock_timeout` < `lock_timeout`** in
  application configuration — otherwise deadlocks are
  reported as lock-timeout instead of deadlock.
- **Retry logic should distinguish** deadlock errors
  (retryable) from other errors.

## Invariants

- **[INV-1]** Heavyweight locks have a deadlock detector;
  LWLocks don't.
- **[INV-2]** Detector fires after `deadlock_timeout`
  (default 1s).
- **[INV-3]** Reordering is tried before victim selection.
- **[INV-4]** Victim is the closure-of-cycle backend;
  aborted transactionally.
- **[INV-5]** Prepared transactions participate in
  detection but can't be auto-aborted.

## Useful greps

- The main check:
  `grep -n 'DeadLockCheck\|FindLockCycle' source/src/backend/storage/lmgr/deadlock.c | head -10`
- The trigger point:
  `grep -RIn 'DeadLockTimeoutId\|enable_timeout' source/src/backend/storage/lmgr | head -10`
- Victim error path:
  `grep -RIn 'deadlock detected' source/src/backend/storage/lmgr/deadlock.c`

## Cross-references

- `knowledge/idioms/lwlock-rank-discipline.md` — the
  no-detector LWLock world by contrast.
- `knowledge/data-structures/locallock.md` — backend-local
  lock cache the detector walks.
- `knowledge/idioms/predicate-locks.md` — SSI's separate
  serializable-conflict detection.
- `knowledge/idioms/tuple-locking-modes.md` — row-level
  locks; deadlocks possible on rows too.
- `.claude/skills/locking/SKILL.md` — heavyweight + LWLock
  + spinlock + predicate-lock decision tree.
- `source/src/backend/storage/lmgr/deadlock.c` —
  implementation.
