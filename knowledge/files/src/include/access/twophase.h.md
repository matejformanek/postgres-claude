# twophase.h

- **Source path:** `source/src/include/access/twophase.h`
- **Lines:** 75
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `twophase.c`, `twophase_rmgr.h`.

## Purpose

Public interface to `twophase.c`. Declares the opaque
`GlobalTransaction` handle, `max_prepared_xacts` GUC extern, and the
backend / recovery / 2PC API. [from-comment] `twophase.h:3-4`.

## Top-of-file comment (verbatim)

```
twophase.h
   Two-phase-commit related declarations.
```
[verified-by-code] `twophase.h:3-4`.

## Key types

- `GlobalTransaction` — `typedef struct GlobalTransactionData *`,
  fully defined only in `twophase.c`. [verified-by-code]
  `twophase.h:28-31`.

## Public surface

- GUC extern `max_prepared_xacts`. [verified-by-code] `twophase.h:34`.
- xact hooks: `AtAbort_Twophase`, `PostPrepare_Twophase`.
  [verified-by-code] `twophase.h:36-37`.
- Lookup: `TwoPhaseGetXidByVirtualXID`, `TwoPhaseGetDummyProc`,
  `TwoPhaseGetDummyProcNumber`. [verified-by-code]
  `twophase.h:39-42`.
- Prepare path: `MarkAsPreparing`, `StartPrepare`, `EndPrepare`,
  `StandbyTransactionIdIsPrepared`. [verified-by-code]
  `twophase.h:44-50`.
- Recovery: `PrescanPreparedTransactions`,
  `StandbyRecoverPreparedTransactions`,
  `RecoverPreparedTransactions`. [verified-by-code]
  `twophase.h:52-55`.
- Checkpoint: `CheckPointTwoPhase(redo_horizon)`. [verified-by-code]
  `twophase.h:57`.
- Finish: `FinishPreparedTransaction(gid, isCommit)`. [verified-by-code]
  `twophase.h:59`.
- Redo: `PrepareRedoAdd(fxid, buf, start_lsn, end_lsn, origin_id)`,
  `PrepareRedoRemove(xid, giveWarning)`. [verified-by-code]
  `twophase.h:61-64`.
- Boot: `restoreTwoPhaseData`. [verified-by-code] `twophase.h:65`.
- Logical-replication helpers: `LookupGXact`,
  `TwoPhaseTransactionGid`, `LookupGXactBySubid`,
  `TwoPhaseGetOldestXidInCommit`. [verified-by-code]
  `twophase.h:66-73`.

## Cross-references

- `twophase.c` is the implementation.
- `twophase_rmgr.h` declares the per-rmgr 2PC callback machinery.

## Confidence tag tally

- `[verified-by-code]`: 18
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
