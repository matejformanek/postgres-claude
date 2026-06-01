# twophase_rmgr.c

- **Source path:** `source/src/backend/access/transam/twophase_rmgr.c`
- **Lines:** 58
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/twophase_rmgr.h`,
  `twophase.c`, `storage/lmgr/lock.c`, `storage/lmgr/predicate.c`,
  `multixact.c`, `utils/activity/pgstat.c`.

## Purpose

Static dispatch tables mapping `TwoPhaseRmgrId` to the
recover / postcommit / postabort / standby-recover callbacks for
the four 2PC-aware subsystems: Lock, pgstat, MultiXact, PredicateLock.
[verified-by-code] `twophase_rmgr.c:1-58`.

## Top-of-file comment (verbatim)

```
twophase_rmgr.c
   Two-phase-commit resource managers tables
```
[verified-by-code] `twophase_rmgr.c:3-4`.

## Public surface

Four `const TwoPhaseCallback[TWOPHASE_RM_MAX_ID + 1]` arrays
exported via `access/twophase_rmgr.h`:

- `twophase_recover_callbacks` — `twophase_rmgr.c:24-31` [verified-by-code]
- `twophase_postcommit_callbacks` — `twophase_rmgr.c:33-40`
  [verified-by-code]
- `twophase_postabort_callbacks` — `twophase_rmgr.c:42-49`
  [verified-by-code]
- `twophase_standby_recover_callbacks` — `twophase_rmgr.c:51-58`
  [verified-by-code]

## Key types / structs

- `TwoPhaseCallback` (function pointer) — declared in
  `twophase_rmgr.h`.
- `TWOPHASE_RM_MAX_ID` — declared in `twophase_rmgr.h`; values
  observed: END_ID(0), Lock(1), pgstat(2), MultiXact(3),
  PredicateLock(4). [verified-by-code] `twophase_rmgr.c:24-58`.

## Key invariants and locking

1. **Compile-time table.** No runtime registration; the four
   2PC-aware subsystems are baked in. Extensions cannot add their
   own. [verified-by-code] `twophase_rmgr.c:24-58`.

2. **NULL entry means "no action".** END_ID is always NULL.
   PredicateLock has no postcommit/postabort/standby-recover, only
   recover. pgstat has no recover, only postcommit/postabort.
   MultiXact has recover/postcommit/postabort but no standby-recover.

## Functions of note

None — this file is data, not code.

## Cross-references

- `twophase.c:RecoverPreparedTransactions`,
  `StandbyRecoverPreparedTransactions`, `FinishPreparedTransaction`,
  `ProcessRecords` dispatch through these tables.
- Callback implementations live in:
  - `storage/lmgr/lock.c` (`lock_twophase_*`)
  - `storage/lmgr/predicate.c` (`predicatelock_twophase_recover`)
  - `multixact.c` (`multixact_twophase_*`)
  - `utils/activity/pgstat_xact.c` (`pgstat_twophase_*`)

## Open questions

None.

## Confidence tag tally

- `[verified-by-code]`: 8
