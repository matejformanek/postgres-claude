# Prepare transaction (2PC) — the staged commit

`PrepareTransaction` in `xact.c` is the **first phase of
two-phase commit**: instead of committing immediately, the
backend writes a `GlobalTransaction` (gxact) record to
durable storage with all the locks and resources still
owned by the prepared xid. A later `COMMIT PREPARED` (from
any backend) finalizes; `ROLLBACK PREPARED` discards. Used
by external transaction managers coordinating multi-database
or XA-style transactions.

Anchors:
- `source/src/backend/access/transam/xact.c:2558` —
  PrepareTransaction entry [verified-by-code]
- `source/src/backend/access/transam/xact.c:2574-2596` —
  pre-prepare loop (mirrors pre-commit) [verified-by-code]
- `source/src/backend/access/transam/xact.c:2598` —
  CallXactCallbacks(XACT_EVENT_PRE_PREPARE) [verified-by-code]
- `source/src/backend/access/transam/twophase.c` — 2PC
  state file format
- `knowledge/idioms/commit-transaction-sequence.md` —
  companion (the single-phase variant)
- `knowledge/idioms/abort-transaction-cleanup.md` —
  companion
- `.claude/skills/wal-and-xlog/SKILL.md` — companion

## The two-phase model

```sql
PREPARE TRANSACTION 'my-xact-id';
-- xid is now "prepared"; locks held; backend exits xact
-- but the xid is NOT committed
...
COMMIT PREPARED 'my-xact-id';   -- finalize (or ROLLBACK PREPARED)
```

Between PREPARE and COMMIT PREPARED, the transaction is in
a unique state: durable to disk, but visible only as
"in-progress" to other backends. Locks remain held. A
crash + restart finds the prepared state and re-establishes
it; another backend can then COMMIT or ROLLBACK PREPARED.

Used for distributed-transaction coordinators
(XA, JTA-style 2PC managers).

## The PrepareTransaction sequence

[verified-by-code `xact.c:2558-2700`]

```
1.  Assert(!IsInParallelMode)
2.  ShowTransactionState
3.  Sanity check state == TRANS_INPROGRESS
4.  Pre-prepare user-code loop:
    - AfterTriggerFireDeferred
    - PreCommit_Portals(true)        <-- note: true for prepare
5.  CallXactCallbacks(XACT_EVENT_PRE_PREPARE)
6.  AfterTriggerEndXact(true)
7.  PreCommit_on_commit_actions
8.  smgrDoPendingSyncs(true)
9.  AtEOXact_LargeObject
10. AtPrepare_* (Notify, Inval, Locks, PgStat, MultiXact...)
11. MarkAsPreparing(gxact)
12. RegisterTwoPhaseRecord (per-rmgr 2PC records)
13. EndPrepare(gxact)                 <-- WAL flush + state file
14. ProcArray update (don't remove yet)
15. State: TRANS_INPROGRESS → TRANS_PREPARED → TRANS_DEFAULT
16. PostPrepare_* (Locks transferred to gxact, Inval, MultiXact...)
17. ResourceOwnerRelease (most resources; LOCKS STAY)
```

The critical difference from commit: the **xid remains
in-progress** (other backends still see it as running) and
**locks are transferred** from this backend's PROC to the
gxact.

## PreCommit_Portals(true) — close holdable cursors

[verified-by-code `xact.c:2589`]

The `true` argument means "for prepare": holdable cursors
are converted to non-holdable (would be reset by 2PC
serialization), and ON COMMIT actions are applied
differently.

## AtPrepare_* family — per-subsystem records

[from-comment / pattern]

Each subsystem participating in 2PC contributes records:
- `AtPrepare_Notify` — pending LISTEN/NOTIFY messages.
- `AtPrepare_Inval` — pending cache invalidations.
- `AtPrepare_Locks` — held heavyweight locks list.
- `AtPrepare_PgStat` — pgstat counter snapshot.
- `AtPrepare_MultiXact` — multixact state.
- `AtPrepare_PredicateLocks` — SSI lock state.

Each writes records via `RegisterTwoPhaseRecord` for later
replay at COMMIT/ROLLBACK PREPARED time.

## MarkAsPreparing + EndPrepare — the durability point

```c
MarkAsPreparing(fxid, gid, prepared_at, owner, database);
RegisterTwoPhaseRecord(...);  // one per subsystem
EndPrepare(gxact);            // WAL + state file flush
```

`MarkAsPreparing` reserves a `GlobalTransaction` shmem
slot. `RegisterTwoPhaseRecord` accumulates per-rmgr data
into a buffer. `EndPrepare` writes:
1. WAL record `XLOG_XACT_PREPARE` (containing the accumulated
   data).
2. WAL flush.
3. State file `pg_twophase/<xid>` on disk (so the prepared
   state survives even before a checkpoint).

After `EndPrepare`, the prepared state is durable; the
backend can exit but the xid stays alive.

## Lock transfer — PostPrepare_Locks

[from-comment]

> Transfer locks to the prepared transaction's
> GlobalTransaction structure.

The heavyweight locks held by the backend's PROC are
detached and re-attached to the gxact. They remain
"held" — other backends see them as blocking — but no
longer tied to this specific backend's lifetime.

This is what makes 2PC work: backend exits, locks remain,
COMMIT PREPARED runs from a different backend later.

## COMMIT PREPARED — the finalize

A later session runs `COMMIT PREPARED 'gid'`:

```c
FinishPreparedTransaction(gid, true)  // true = commit
```

This:
1. Loads state file or in-memory gxact.
2. Calls each rmgr's `twophase_*_callback(true)`:
   - locks released for real.
   - inval messages dispatched.
   - notify messages queued.
3. WAL writes `XLOG_XACT_COMMIT_PREPARED`.
4. CLOG marked committed.
5. Removes state file.
6. ProcArrayRemove gxact entry.

`ROLLBACK PREPARED` mirrors with `(false)`.

## Crash recovery

[from twophase.c]

At startup, `RecoverPreparedTransactions` reads
`pg_twophase/*` and reconstructs gxacts. Their locks are
re-established in shared memory; their xids are entered
into ProcArray. The system can then accept COMMIT PREPARED
/ ROLLBACK PREPARED commands for them.

This is why 2PC requires `max_prepared_transactions > 0`:
shmem slots must be pre-allocated to permit recovery.

## Why no parallel mode

[verified-by-code `xact.c:2563`]

```c
Assert(!IsInParallelMode());
```

Parallel workers share state with leader. Prepare requires
transferring that state to gxact — incompatible with
workers still running.

## Common review-time concerns

- **`max_prepared_transactions = 0` disables 2PC** —
  PREPARE will error.
- **Locks survive backend exit** — held by gxact.
- **State file durability** — flushed before EndPrepare
  returns.
- **`AtPrepare_*` family is per-subsystem** — adding a new
  shared-state subsystem usually needs a 2PC entry.
- **No parallel mode** during prepare.
- **GID uniqueness** — gxact id is user-supplied; collision
  fails.

## Invariants

- **[INV-1]** PrepareTransaction never runs in parallel
  mode.
- **[INV-2]** Pre-prepare loop quiesces triggers + portals.
- **[INV-3]** Locks transferred from PROC to gxact;
  survive backend exit.
- **[INV-4]** State file + WAL both durable before
  EndPrepare returns.
- **[INV-5]** COMMIT/ROLLBACK PREPARED can run from any
  backend (with permission).

## Useful greps

- The main flow:
  `grep -n 'PrepareTransaction\|EndPrepare\|MarkAsPreparing' source/src/backend/access/transam/xact.c source/src/backend/access/transam/twophase.c | head -15`
- The AtPrepare family:
  `grep -RIn 'AtPrepare_\|PostPrepare_' source/src/backend | head -15`
- Recovery:
  `grep -n 'RecoverPreparedTransactions' source/src/backend/access/transam/twophase.c | head -5`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/twophase.c`](../files/src/backend/access/transam/twophase.c.md) | — | 2PC state-file machinery |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2558 | PrepareTransaction entry |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2574 | pre-prepare loop (mirrors pre-commit) |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2598 | CallXactCallbacks(XACT_EVENT_PRE_PREPARE) |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/commit-transaction-sequence.md` —
  single-phase commit (no gxact).
- `knowledge/idioms/abort-transaction-cleanup.md` —
  abort variants.
- `knowledge/idioms/crash-recovery-startup.md` —
  RecoverPreparedTransactions at startup.
- `knowledge/idioms/notify-listen-coordination.md` —
  AtPrepare_Notify participant.
- `knowledge/idioms/cache-invalidation-registration.md` —
  AtPrepare_Inval participant.
- `knowledge/idioms/predicate-locks.md` —
  AtPrepare_PredicateLocks participant.
- `knowledge/subsystems/access-transam.md` — xact.c
  subsystem.
- `.claude/skills/wal-and-xlog/SKILL.md` — companion.
- `source/src/backend/access/transam/xact.c:2558` —
  PrepareTransaction entry.
- `source/src/backend/access/transam/twophase.c` — 2PC
  state-file machinery.
