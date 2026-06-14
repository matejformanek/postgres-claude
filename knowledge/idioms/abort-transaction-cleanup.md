# Abort transaction cleanup — the unwound shutdown

`AbortTransaction` in `xact.c` is the **fail-safe inverse**
of `CommitTransaction`. Where commit is gated on every
phase succeeding, abort assumes every phase may have left
state in an unknown condition — and unwinds it
defensively. The phase order differs from commit's:
**interrupts disabled first**, **LW locks released
early**, **WAL insertion state reset**, and only then is
the abort WAL record written. Knowing what abort *can't*
trust (anything possibly partially-modified) is essential
for any work in error-handling paths.

Anchors:
- `source/src/backend/access/transam/xact.c:2853` —
  AbortTransaction entry [verified-by-code]
- `source/src/backend/access/transam/xact.c:2858` —
  HOLD_INTERRUPTS [verified-by-code]
- `source/src/backend/access/transam/xact.c:2877` —
  LWLockReleaseAll [verified-by-code]
- `source/src/backend/access/transam/xact.c:2892` —
  XLogResetInsertion [verified-by-code]
- `knowledge/idioms/commit-transaction-sequence.md` —
  companion (the success path)
- `knowledge/idioms/error-context-callbacks.md` —
  companion (abort follows ereport(ERROR))
- `.claude/skills/error-handling/SKILL.md` — companion

## The defensive ordering

[verified-by-code `xact.c:2853-3000`]

Compressed sequence:

```
1.  HOLD_INTERRUPTS              (no more cancel/die)
2.  Disable transaction timeout
3.  AtAbort_Memory + AtAbort_ResourceOwner  (sanity baseline)
4.  LWLockReleaseAll             (might re-grab when cleaning)
5.  WaitLSNCleanup
6.  pgstat_report_wait_end + pgstat_progress_end_command
7.  pgaio_error_cleanup
8.  UnlockBuffers                (content locks)
9.  XLogResetInsertion           (in-flight WAL record state)
10. ConditionVariableCancelSleep
11. LockErrorCleanup             (waiting-for-lock state)
12. RESUME_INTERRUPTS
13. CallXactCallbacks(XACT_EVENT_ABORT)
14. Smgr cleanup: smgrDoPendingDeletes, smgrDoPendingSyncs(false)
15. State transition → TRANS_ABORT
16. RecordTransactionAbort       (WAL record, CLOG update)
17. ResourceOwnerRelease         (regular locks)
18. ProcArrayEndTransaction
```

The difference from commit ordering — **early lock release**
(LW + buffer + condition variable + WAL insertion state) —
is because the abort path needs to *clean up* state, and
holding those locks would prevent cleanup helpers from
working.

## HOLD_INTERRUPTS — the cancel guard

[verified-by-code `xact.c:2858`]

```c
HOLD_INTERRUPTS();
```

The very first action: disable cancel/die interrupts.
Reason: if abort itself were interrupted by a SIGINT, the
backend could leave inconsistent state. Re-enabled at step
12 once the dangerous cleanup is done.

This is paired with the longjmp arrival from `PG_CATCH`:
the error context already disabled most things, but
AbortTransaction reasserts.

## LWLockReleaseAll — early release

[verified-by-code `xact.c:2877`]

```c
LWLockReleaseAll();
```

> Release any LW locks we might be holding as quickly as
> possible. (Regular locks, however, must be held till we
> finish aborting.) Releasing LW locks is critical since
> we might try to grab them again while cleaning up!

Heavyweight regular locks stay held — other backends must
not see partially-undone state. LW locks (buffer content,
LWLock-protected shared state) are short-lived and
re-acquired during cleanup helpers; releasing all of them
upfront is safer than tracking per-call state.

## XLogResetInsertion — discard in-flight record

[verified-by-code `xact.c:2892`]

```c
XLogResetInsertion();
```

If the abort interrupted a `XLogBeginInsert` …
`XLogInsert` sequence, partial-construction state must be
cleared. Otherwise the *next* WAL insertion would inherit
the garbage.

## XACT_EVENT_ABORT — extension hook

```c
CallXactCallbacks(XACT_EVENT_ABORT);
```

Extensions get one shot to clean up. They cannot call user
code (interrupts held, may already be in transient state),
must be defensive.

FDW abort, custom-resource cleanup, audit logging hooks
run here.

## smgrDoPendingDeletes — file rollback

```c
smgrDoPendingDeletes(false);
```

For tables/indexes created in this aborted transaction,
the on-disk files get unlinked. The `false` argument means
"rollback" (vs commit's `true` for "make permanent").

Symmetric with commit's `smgrDoPendingSyncs(true)`:
commit syncs newly-created files; abort deletes them.

## RecordTransactionAbort — the WAL record

Distinct from commit:
- Written to WAL but **not flushed by default** — the
  reasoning is that crash recovery would mark this xid
  aborted anyway via CLOG default.
- CLOG entry updated to `TRANSACTION_STATUS_ABORTED`.

This is why aborts are cheaper than commits — no forced
WAL flush.

## ProcArrayEndTransaction — visibility cutover

Same call as commit. From other backends' point of view,
this xid is now "no longer running" — and visibility tests
will check CLOG, see ABORTED, and treat its tuples as
dead.

## Subtransaction (SAVEPOINT) abort

`RollbackToSavepoint` / `AbortSubTransaction` is a smaller
sibling — same defensive pattern but scoped to subxact.
Subxact aborts can occur many times within one top-level
transaction; only the top-level's abort calls
`AbortTransaction`.

## When AbortTransaction is called

[from-code `errfinish` + `xact.c` callers]

- Via `PG_TRY` / `PG_CATCH` after ereport(ERROR).
- Via explicit `AbortCurrentTransaction()` from
  high-level loops (e.g., postmaster main loop after
  catching an error).
- NOT called directly from user SQL — `ROLLBACK` statements
  go through `EndTransactionBlock` first.

## Parallel-worker abort

```c
is_parallel_worker = (s->blockState == TBLOCK_PARALLEL_INPROGRESS);
```

Workers signal the leader; leader's abort includes
`AtEOXact_Parallel(false)` which terminates workers. The
worker's own AbortTransaction is mostly local cleanup.

## Common review-time concerns

- **Abort cannot run user code** — no triggers, no
  callbacks beyond XACT_EVENT_ABORT.
- **LW locks released BEFORE regular locks** — opposite
  order from "naive" cleanup.
- **WAL insertion state must be reset** — leftover
  partial-records corrupt next write.
- **Abort is cheap** — no forced WAL flush.
- **smgrDoPendingDeletes** rolls back file creates.
- **Subxact abort is scoped** — different function.

## Invariants

- **[INV-1]** HOLD_INTERRUPTS during cleanup; resume
  before callbacks.
- **[INV-2]** LW locks released early; regular locks
  held till end.
- **[INV-3]** XLogResetInsertion clears in-flight records.
- **[INV-4]** Abort WAL record not flushed by default.
- **[INV-5]** smgrDoPendingDeletes(false) unlinks
  newly-created files.

## Useful greps

- The main function:
  `grep -n 'AbortTransaction\|AbortSubTransaction' source/src/backend/access/transam/xact.c | head -10`
- WAL record:
  `grep -n 'RecordTransactionAbort\|XLOG_XACT_ABORT' source/src/backend/access/transam/xact.c | head -10`
- Smgr rollback:
  `grep -n 'smgrDoPendingDeletes' source/src/backend/catalog/storage.c | head -10`

## Cross-references

- `knowledge/idioms/commit-transaction-sequence.md` —
  the success path (mirror).
- `knowledge/idioms/prepare-transaction-2pc.md` — 2PC
  prepare variant.
- `knowledge/idioms/error-context-callbacks.md` —
  ereport(ERROR) jumps to PG_CATCH → AbortCurrentTransaction.
- `knowledge/idioms/subtransaction-stack.md` — subxact
  abort scope.
- `knowledge/data-structures/pgproc-fields.md` —
  ProcArray entry updated.
- `knowledge/subsystems/access-transam.md` — xact.c
  subsystem.
- `.claude/skills/error-handling/SKILL.md` — companion.
- `source/src/backend/access/transam/xact.c:2853` —
  AbortTransaction entry.
