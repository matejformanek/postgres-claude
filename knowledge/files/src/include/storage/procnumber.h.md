# `src/include/storage/procnumber.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 56

## Role

`ProcNumber` — PG17 rename of the old `BackendId`. Index into
the proc array; uniquely identifies an active backend or
auxiliary process. Reused immediately after exit.

[verified-by-code] `source/src/include/storage/procnumber.h:17-23`

## Public API

- `typedef int ProcNumber;` — signed int (so -1 sentinel works)
- `INVALID_PROC_NUMBER = -1`
- `MAX_BACKENDS_BITS = 18`, `MAX_BACKENDS = (1U << 18) - 1`
  = 262143
- `extern PGDLLIMPORT ProcNumber MyProcNumber;`
- `extern PGDLLIMPORT ProcNumber ParallelLeaderProcNumber;`
- `ProcNumberForTempRelations()` — leader if in parallel worker,
  else self (lines 53-54). **Critical**: parallel workers must
  use leader's proc number for temp table file naming.

## Invariants

- INV-1: 18-bit limit is locked in by `buf_internals.h` refcount
  layout. [from-comment] lines 29-31. Even lifting that ceiling
  hits 23-bit cap in `inval.c` (3-byte ProcNumber) and INT_MAX/4
  ceiling from `4*MaxBackends` arithmetic elsewhere.
- INV-2: `MAX_BACKENDS` is validated in
  `InitializeMaxBackends()`. [from-comment] line 36.
- INV-3: ProcNumber **reuse is immediate** — a sentinel/old
  ProcNumber cannot be trusted to refer to the original
  backend. Use `BackendXidGetPgProcByNumber` plus liveness check.
  [from-comment] lines 20-22.

## Rename history (PG17)

The rename `BackendId → ProcNumber` (commit cf6402d4f8 series)
touched ~150 files across the backend. Most `BackendId` symbol
references have been migrated; a few aux process startup paths
and some FRONTEND-visible places (pg_basebackup, walreceiver
protocol negotiation) might retain `BackendId` for protocol
compatibility. The `inval.c` 3-byte storage (INV-1) is a
historical artifact of the old `BackendId` shape that the
rename did NOT change.

## Trust boundary (Phase D)

- ProcNumber reuse hazard: an extension caching a ProcNumber
  across an unspecified time window can address the wrong
  backend. Internal users always re-validate via PGPROC
  pointer + `pid`/`xid` cross-check.
- ProcNumber is leaked via `pg_stat_activity`, advisory locks,
  `pg_locks` (VIRTUALTRANSACTION locktag uses ProcNumber as
  field1) — part of A11/A14 monitoring-as-extraction cluster
  in the sense that activity correlation across views uses
  it.

## Cross-refs

- `knowledge/files/src/include/storage/relfilelocator.h.md` —
  `RelFileLocatorBackend.backend` is a `ProcNumber`
- `knowledge/files/src/include/storage/proc.h.md` (existing) —
  the `PGPROC` array that ProcNumber indexes
- `knowledge/files/src/include/storage/procarray.h.md`
  (existing)

## Issues

- ISSUE-DESIGN: 3-byte ProcNumber in `inval.c` (`MAX_BACKENDS <
  2^23 - 1`) hides a ceiling that wouldn't show until MaxBackends
  is pushed past 8M. Not currently a concern but worth noting.
  (Informational.)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-lmgr.md](../../../../subsystems/storage-lmgr.md)
