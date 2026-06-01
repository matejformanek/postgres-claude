# twophase_rmgr.h

- **Source path:** `source/src/include/access/twophase_rmgr.h`
- **Lines:** 42
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `twophase_rmgr.c`, `twophase.c`.

## Purpose

Defines the dispatch tables and IDs for 2PC-aware subsystems. Each
subsystem registers per-prepare state via `RegisterTwoPhaseRecord` and
implements the four callbacks (recover / postcommit / postabort /
standby_recover). [from-comment] `twophase_rmgr.h:3-4`.

## Top-of-file comment (verbatim)

```
twophase_rmgr.h
   Two-phase-commit resource managers definition
```
[verified-by-code] `twophase_rmgr.h:3-4`.

## Key types / constants

- `TwoPhaseCallback = void (*)(FullTransactionId fxid, uint16 info,
  void *recdata, uint32 len)`. [verified-by-code] `twophase_rmgr.h:19-20`.
- `TwoPhaseRmgrId = uint8`. [verified-by-code] `twophase_rmgr.h:21`.
- Built-in IDs: `TWOPHASE_RM_END_ID=0`, `_LOCK_ID=1`, `_PGSTAT_ID=2`,
  `_MULTIXACT_ID=3`, `_PREDICATELOCK_ID=4`,
  `_MAX_ID = _PREDICATELOCK_ID`. [verified-by-code]
  `twophase_rmgr.h:26-31`.

## Public surface

- `twophase_recover_callbacks[]`,
  `twophase_postcommit_callbacks[]`,
  `twophase_postabort_callbacks[]`,
  `twophase_standby_recover_callbacks[]` — declared as
  `PGDLLIMPORT const TwoPhaseCallback []`.
  [verified-by-code] `twophase_rmgr.h:33-36`.
- `RegisterTwoPhaseRecord(rmid, info, data, len)` — `twophase_rmgr.h:39`
  [verified-by-code]

## Key invariants

1. **Closed registry.** The five built-in IDs are fixed at compile
   time; extensions cannot add new 2PC rmgrs.
   [verified-by-code] (see `twophase_rmgr.c` for the constant tables).

## Cross-references

- `twophase_rmgr.c` defines the four callback tables.
- `twophase.c` dispatches through these on
  `RecoverPreparedTransactions` / `FinishPreparedTransaction`.

## Confidence tag tally

- `[verified-by-code]`: 8
- `[from-comment]`: 1
