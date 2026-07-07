# Commit transaction sequence — the ordered shutdown

`CommitTransaction` in `xact.c` is a **strictly ordered**
shutdown sequence: pre-commit user code first, then catalog
locks, WAL flush, smgr sync, on-commit actions, ProcArray
removal, and resource cleanup. Reordering any phase risks
either subtle correctness bugs (smgr files lost after
crash, ProcArray entry seen by readers after WAL gone) or
deadlocks (LW locks held across user code). Knowing the
phase boundaries is essential for any work touching xact
callbacks, smgr, or commit semantics.

Anchors:
- `source/src/backend/access/transam/xact.c:2270` —
  CommitTransaction entry [verified-by-code]
- `source/src/backend/access/transam/xact.c:2298-2312` —
  pre-commit trigger loop [verified-by-code]
- `source/src/backend/access/transam/xact.c:2322` —
  CallXactCallbacks(XACT_EVENT_PRE_COMMIT) [verified-by-code]
- `source/src/backend/access/transam/xact.c:2354-2357` —
  smgrDoPendingSyncs [verified-by-code]
- `knowledge/data-structures/pgproc-fields.md` — companion;
  ProcArray entry removed at commit
- `knowledge/idioms/abort-transaction-cleanup.md` —
  companion (the opposite path)
- `knowledge/idioms/prepare-transaction-2pc.md` — companion
  (the prepared variant)
- `.claude/skills/wal-and-xlog/SKILL.md` — companion

## The phase order

[verified-by-code `xact.c:2270-2510`]

The sequence (compressed):

```
1. Sanity check state == TRANS_INPROGRESS
2. Pre-commit user code (LOOP):
   - AfterTriggerFireDeferred
   - PreCommit_Portals(false)
3. CallXactCallbacks(XACT_EVENT_PRE_COMMIT)
4. AtEOXact_Parallel + parallel-mode reset
5. AfterTriggerEndXact(true)
6. PreCommit_on_commit_actions  (ON COMMIT DROP/DELETE)
7. smgrDoPendingSyncs           (unlogged-relation sync)
8. AtEOXact_LargeObject(true)
9. State transition: TRANS_INPROGRESS → TRANS_COMMIT
10. RecordTransactionCommit     (WAL flush + ProcArray update)
11. AtEOXact_RelationCache + Relation* + Inval
12. ResourceOwnerRelease (locks, planning state, etc.)
13. ProcArrayEndTransaction
14. State transition: TRANS_COMMIT → TRANS_DEFAULT
```

The "user-code-allowed → user-code-forbidden" boundary is
at step 3. Once `XACT_EVENT_PRE_COMMIT` is dispatched,
new triggers or cursor opens would re-enter the loop —
illegal at this phase.

## The pre-commit looping pattern

[verified-by-code `xact.c:2298-2312`]

> Do pre-commit processing that involves calling user-defined
> code, such as triggers. SECURITY_RESTRICTED_OPERATION
> contexts must not queue an action that would run here,
> because that would bypass the sandbox. Since closing
> cursors could queue trigger actions, triggers could open
> cursors, etc, we have to keep looping until there's
> nothing left to do.

```c
for (;;) {
    AfterTriggerFireDeferred();
    if (!PreCommit_Portals(false))
        break;
}
```

Two interleaving callers: deferred triggers can open
cursors, cursors can fire on-close triggers. Loop until
both quiesce.

## smgrDoPendingSyncs — durability before commit record

[verified-by-code `xact.c:2354-2357`]

> Synchronize files that are created and not WAL-logged
> during this transaction. This must happen before
> AtEOXact_RelationMap(), so that we don't see
> committed-but-broken files after a crash.

For unlogged-relation creation, COPY into newly-created
table, etc., file contents weren't WAL-logged — they must
be physically synced before the commit record is durable.
Otherwise a crash could leave the catalog promising data
that's on disk only in OS cache.

## RecordTransactionCommit — the atomic point

The commit becomes durable here. Sub-steps:
1. Compute `latestXid` (max of self + child xids).
2. Assemble `xl_xact_commit` WAL record.
3. `XLogInsert(RM_XACT_ID, XLOG_XACT_COMMIT_*)`.
4. If `synchronous_commit > off`: `XLogFlush` to commit LSN.
5. `TransactionIdCommitTree` (CLOG).
6. ProcArray update (xid → marked done, xmin re-min).

Step 4's flush is the durability boundary. Before flush,
the commit is in WAL buffers only — a crash here would
roll back. After flush, the commit is permanent.

## ProcArrayEndTransaction — the visibility cutover

After CLOG + WAL but before resource cleanup, the
ProcArray entry is updated:
- `MyProc->xid` cleared.
- `MyProc->xmin` reset.
- Subxact stack cleared.

Snapshot acquisitions starting **after** this point will
NOT include this xid in their in-progress set — i.e., they
will see this transaction's effects.

## ResourceOwner release — locks last

```c
ResourceOwnerRelease(...);
```

Locks, planning state, file handles, buffer pins are
released in resource-owner order. Heavyweight locks last
to allow waiting queries to proceed.

Releasing locks BEFORE the commit becomes durable would
let other backends see the modifications as committed
before they actually are. The order is: durability first
(WAL flush + CLOG + ProcArray), then visibility (locks).

## Parallel-mode commit twist

[verified-by-code `xact.c:2276-2342`]

Parallel workers participate in commit specially:
- `is_parallel_worker = (blockState == TBLOCK_PARALLEL_INPROGRESS)`.
- They run `AtEOXact_Parallel(true)` early.
- `XACT_EVENT_PARALLEL_PRE_COMMIT` callback variant.
- `parallelModeLevel` reset later than leader's.

The leader waits for all workers to finish their commit
sequence (via `WaitForParallelWorkersToFinish`) before
emitting the commit WAL record.

## XACT_EVENT callbacks — extension hook points

```c
typedef enum {
    XACT_EVENT_COMMIT,
    XACT_EVENT_PARALLEL_COMMIT,
    XACT_EVENT_ABORT,
    XACT_EVENT_PARALLEL_ABORT,
    XACT_EVENT_PREPARE,
    XACT_EVENT_PRE_COMMIT,
    XACT_EVENT_PARALLEL_PRE_COMMIT,
    XACT_EVENT_PRE_PREPARE,
} XactEvent;
```

Extensions register via `RegisterXactCallback`. Common
uses: foreign-data-wrapper commit / 2PC, custom commit
logging, audit hooks. Run at PRE_COMMIT (user code OK) and
COMMIT (post-WAL-flush, no errors allowed).

## Common review-time concerns

- **PRE_COMMIT callbacks may run user code** — COMMIT
  callbacks may NOT.
- **smgr syncs MUST precede commit record** — durability
  invariant.
- **WAL flush ↔ synchronous_commit** — async commits return
  before flush.
- **ProcArray cutover is visibility boundary** — not WAL.
- **Locks released AFTER commit durable** — never before.
- **Parallel workers commit slightly differently** —
  XACT_EVENT_PARALLEL_* variants.

## Invariants

- **[INV-1]** Pre-commit loop runs until triggers + portals
  quiesce.
- **[INV-2]** smgr pending syncs precede commit WAL record.
- **[INV-3]** Commit WAL flush precedes ProcArray update.
- **[INV-4]** Locks release after commit durable.
- **[INV-5]** Parallel workers use PARALLEL_PRE_COMMIT /
  PARALLEL_COMMIT callback variants.

## Useful greps

- The main function:
  `grep -n 'CommitTransaction\|RecordTransactionCommit' source/src/backend/access/transam/xact.c | head -10`
- WAL record assembly:
  `grep -n 'XactLogCommitRecord\|XLOG_XACT_COMMIT' source/src/backend/access/transam/xact.c | head -10`
- ProcArray:
  `grep -n 'ProcArrayEndTransaction' source/src/backend/storage/ipc/procarray.c | head -5`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2270 | CommitTransaction entry |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2298 | pre-commit trigger loop |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2322 | CallXactCallbacks(XACT_EVENT_PRE_COMMIT) |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2354 | smgrDoPendingSyncs |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/abort-transaction-cleanup.md` —
  AbortTransaction (the failure path).
- `knowledge/idioms/prepare-transaction-2pc.md` —
  PrepareTransaction (the 2PC variant).
- `knowledge/data-structures/pgproc-fields.md` — PROC
  fields updated by ProcArrayEndTransaction.
- `knowledge/idioms/snapshot-acquisition.md` — ProcArray
  cutover is the snapshot boundary.
- `knowledge/idioms/wal-record-construction.md` — commit
  record assembly via XLogInsert.
- `knowledge/idioms/checkpoint-coordination.md` — commit
  ordering vs checkpoint.
- `knowledge/subsystems/access-transam.md` — xact.c
  subsystem.
- `.claude/skills/wal-and-xlog/SKILL.md` — companion.
- `source/src/backend/access/transam/xact.c:2270` —
  CommitTransaction entry.
