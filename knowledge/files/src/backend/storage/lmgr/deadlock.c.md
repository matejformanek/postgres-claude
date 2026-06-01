# `storage/lmgr/deadlock.c`

- **Source:** `source/src/backend/storage/lmgr/deadlock.c` (1 162 lines)
- **Last verified commit:** `ef6a95c` (2026-06-01)
- **Algorithm narrative:** `source/src/backend/storage/lmgr/README:338-588` `[from-README]`

## 1. Purpose

POSTGRES deadlock detection. Top-of-file refers the reader to the README:

> "See src/backend/storage/lmgr/README for a description of the deadlock detection and resolution algorithms." `[from-comment]` (`deadlock.c:1-24`).

Implements the optimistic-waiting deadlock detector: a waiter triggers detection only when its `deadlock_timeout` elapses (default 1 s). The detector walks the waits-for graph (WFG) using "soft" and "hard" edge classification and, when only soft edges close the cycle, tries every legal wait-queue rearrangement to dissolve it before falling back to aborting the transaction.

## 2. Public surface

`DeadLockCheck(proc) → DeadLockState` (`deadlock.c:220`) — called from `CheckDeadLock` in `proc.c` with all 16 lock-partition LWLocks held.

`DeadLockReport(void)` (`deadlock.c:1075`) — emits the ereport with the recorded `deadlockDetails[]`, after the partition locks have been released.

`RememberSimpleDeadLock(proc1, lockmode, lock, proc2)` (`deadlock.c:1147`) — called from `JoinWaitQueue` (`proc.c:1276`) when the trivial "two-proc same-object" deadlock is detected at enqueue time, so we can still produce a useful ereport.

`InitDeadLockChecking(void)` (`deadlock.c:143`) — backend-startup allocation of the detector's worst-case workspace (sized from `MaxBackends`).

`GetBlockingAutoVacuumPgproc(void)` (`deadlock.c:290`) — returns and clears `blocking_autovacuum_proc`, used by `ProcSleep` to send the cancel signal (the `README:581-588` "abuse" hook).

## 3. Key types

- `EDGE` (`deadlock.c:47-54`): `{PGPROC *waiter; PGPROC *blocker; LOCK *lock; int pred, link}`. **`waiter` and `blocker` are always group leaders** (`deadlock.c:40-46`): "if either is [a lock group member], it will be the leader rather than any other member" — comment is the key invariant for understanding the rest. `[from-comment]`.
- `WAIT_ORDER` (`deadlock.c:57-62`): a proposed wait-queue reordering — `{LOCK *lock; PGPROC **procs; int nProcs}`.
- `DEADLOCK_INFO` (`deadlock.c:72-77`): `{LOCKTAG, LOCKMODE, int pid}` — *value*-copied so we can ereport after releasing partition locks (`[from-comment]` lines 64-71).

### Workspace globals (`deadlock.c:99-130`)

All pre-allocated in `InitDeadLockChecking` based on `MaxBackends`:

- `visitedProcs[], nVisitedProcs` — FindLockCycle BFS-visited set.
- `topoProcs[], beforeConstraints[], afterConstraints[]` — TopoSort scratch.
- `waitOrders[], nWaitOrders, waitOrderProcs[]` — proposed rearrangements output area.
- `curConstraints[], nCurConstraints, maxCurConstraints` — active soft-edge reversal set.
- `possibleConstraints[], nPossibleConstraints, maxPossibleConstraints` — recently-found soft edges.
- `deadlockDetails[], nDeadlockDetails` — value-copied cycle info for the ereport.
- `blocking_autovacuum_proc` — pointer set during cycle walk if any cycle node is autovacuum.

## 4. Key invariants and locking

### Entry contract

`DeadLockCheck` is called by `CheckDeadLock` (`proc.c:1856`) **while holding all 16 lock-partition LWLocks in exclusive mode**, in partition-number order. The function therefore reads any PGPROC's lock-related fields and any LOCK's procLocks/waitProcs lists without taking additional locks. `[from-README]` (`README:660-667`) and `[verified-by-code]` (`proc.c:1871-1872`).

### Group-leader collapsing

Every PGPROC encountered is replaced by its `lockGroupLeader` before recording or comparison (`FindLockCycleRecurse` lines 469-470). This means cycles are reported in group-leader space, which is also how `RememberSimpleDeadLock` records them and how `JoinWaitQueue`'s adjacency check (`proc.c:1214-1227`) computes group-held locks.

### Relation-extension short-circuit

`FindLockCycleRecurseMember` returns false immediately if the awaited lock is `LOCKTAG_RELATION_EXTEND` (`deadlock.c:556-557`):

> "The relation extension lock can never participate in actual deadlock cycle. See Assert in LockAcquireExtended." `[from-comment]`.

This pairs with the `Assert(!IsRelationExtensionLockHeld)` at `lock.c:951` `[verified-by-code]`.

### Hard vs soft edges

- **Hard edge** A→B: B holds a granted lock that conflicts with A's wait request. Cannot be resolved by reordering.
- **Soft edge** A→B: A is queued behind B in the same wait queue, and their requests conflict. Can be resolved by moving A in front of B.

A cycle of all soft edges → try every reversal subset; if any survives `TestConfiguration`, apply it. A cycle that contains *any* hard edge → hard deadlock → abort the start-point's transaction.

### Output rule

Both outcomes write `deadlockDetails[]` so `DeadLockReport` (called *after* partition lock release) can print the cycle. Pointer fields in EDGE are dereferenced *before* release; `DEADLOCK_INFO` is value-copied for exactly this reason.

## 5. Functions of note

### 5.1 `DeadLockCheck` (`deadlock.c:220-282`)

Top-level entry. Initialises constraint set to empty, then calls `DeadLockCheckRecurse(proc)`. Three outcomes:

- Returns `true` (no rearrangement works): `DS_HARD_DEADLOCK`. Re-runs `FindLockCycle` once to repopulate `deadlockDetails[]` for the *unmodified* configuration (because the recursion left some constraints applied that we won't apply for real). `[from-comment]` (`deadlock.c:233-244`).
- Returns `false` with `nWaitOrders > 0`: `DS_SOFT_DEADLOCK`; applies each rearrangement by zeroing the wait queue and re-pushing procs in the new order, then `ProcLockWakeup` on each rearranged queue.
- Returns `false` with `nWaitOrders == 0` but `blocking_autovacuum_proc != NULL`: `DS_BLOCKED_BY_AUTOVACUUM`. Caller (`ProcSleep`) handles the cancel signal.

### 5.2 `DeadLockCheckRecurse` (`deadlock.c:311-360`)

Try each soft edge in the current cycle as a reversal constraint; recurse. Returns true if no solution; false if a valid configuration exists (in which case `waitOrders[]` holds the implementation).

### 5.3 `TestConfiguration` (`deadlock.c:378-444`)

Given the active constraint set, runs `ExpandConstraints` (which produces a `WAIT_ORDER` per affected queue via `TopoSort`); then `FindLockCycle` from the start proc to see if any cycle remains. Returns `0` = good, `-1` = inconsistent/hard-deadlock, `>0` = soft-cycle-found-and-edges-recorded.

### 5.4 `FindLockCycleRecurse` (`deadlock.c:457-533`)

DFS over `MyProc`'s waits-for edges:

- For the proc's own `waitLink`, follow the lock's `procLocks` to find blockers (hard edges if their holdMask conflicts; soft if they're queue-ahead-with-conflict).
- Then iterate `lockGroupMembers` and follow each member's `waitLink` separately — needed because a leader can be waiting via a worker (`README:600-650`).
- The `visitedProcs[]` check at line 475 returns "cycle includes start-point" (true) only if we loop back to `visitedProcs[0]`; otherwise we have *a* cycle but not *our* cycle, and we return false (matches `README:393-417`).

### 5.5 `FindLockCycleRecurseMember` (`deadlock.c:536-789`)

The grungy part. For one waiting proc:
1. Skip if waiting on RELATION_EXTEND.
2. Scan `lock->procLocks` for hard-edge holders (granted conflict).
3. Scan the wait queue (or, if this lock has an active `WAIT_ORDER` in the lookaside table, the proposed order) for soft-edge blockers ahead of us in queue.
4. For each candidate edge, follow it recursively. On cycle, append the edge to `softEdges[]` and return true; the caller may discard soft edges from this list if the cycle is found to be hard.

### 5.6 `ExpandConstraints` + `TopoSort` (`deadlock.c:790-1052`)

`ExpandConstraints` collects, per affected lock, all soft-edge reversal constraints in `curConstraints[]`; `TopoSort` performs an order-preserving Kahn's topological sort (deepest-comment block at `deadlock.c:862-1052`). A failing `TopoSort` (`return false` at the contradiction case) means the proposed reversal set is internally inconsistent and we must back out — matches README:476-484 "Topological sort failure tells us the un-reversal is not a legitimate move."

### 5.7 `DeadLockReport` (`deadlock.c:1075-1146`)

Emits `ereport(ERROR, errcode(ERRCODE_T_R_DEADLOCK_DETECTED), ...)` with a per-edge `errdetail`. Reads from `deadlockDetails[]` only — no shared-memory access — because this runs after partition locks are released.

### 5.8 `RememberSimpleDeadLock` (`deadlock.c:1147-1161`)

Fast-path "two procs, same object, mutually conflicting" deadlock detected inside `JoinWaitQueue` without invoking the full detector. Records the two-edge cycle into `deadlockDetails[]` directly.

## 6. Cross-references

- `proc.c` — `CheckDeadLock` is the sole caller of `DeadLockCheck`; `LockErrorCleanup` and `ProcSleep` route the result.
- `lock.c` — `RemoveFromWaitQueue` is called by `CheckDeadLock` on hard deadlock.
- `README:338-588` — algorithm spec; this file is its implementation.

## 7. Open questions

1. **Cycle reporting under simultaneous detection.** If two waiters simultaneously hit deadlock timeout, both will queue for the partition locks; only one runs the check at a time (since they're exclusive). The later one will find the cycle has been broken and return `DS_NO_DEADLOCK`. README:553-555 acknowledges this. `[from-README]`.
2. **`maxPossibleConstraints` sizing.** It's `MaxBackends * MaxBackends`-ish; I didn't trace exact bound in `InitDeadLockChecking`. If undersized in pathological cases, `DeadLockCheckRecurse` falls back to regenerating the edge list (line 336). `[unverified]`.
3. **Whether `WAIT_ORDER` lookaside fully covers nested rearrangement.** README:461-484 describes it; code in `ExpandConstraints` builds it. Verified at a high level but I did not trace edge cases. `[from-README]`.
4. **Autovacuum-cancel race.** The detector sets `blocking_autovacuum_proc` while holding all partition LWLocks; `ProcSleep` reads it after release. If a second deadlock detection on a different waiter clears it (via `GetBlockingAutoVacuumPgproc`) in between, the first waiter doesn't cancel. Not obviously a bug since the autovac will be cancelled by *someone*, but the race is subtle. `[unverified]`.

## 8. Tag tally

- `[verified-by-code]`: 8
- `[from-comment]`: 6
- `[from-README]`: 4
- `[unverified]`: 3

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/deadlock.c | deep (full algorithm trace) | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/deadlock.c.md |

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
