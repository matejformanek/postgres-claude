# `pg_freespacemap/pg_freespacemap.c` — FSM byte-per-page peek

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_freespacemap/pg_freespacemap.c`)

## Role

Single-function module: returns the free-space byte (a `category` value
in the FSM tree) for a given block of a given relation. Used by
ops/diagnostics tooling to spot under-packed pages and FSM corruption.

## Public API

- `pg_freespace(regclass, bigint) -> int2` — `source/contrib/pg_freespacemap/pg_freespacemap.c:27`

SQL gating: `REVOKE ALL FROM PUBLIC`
(`pg_freespacemap--1.1.sql:11-12`), then `GRANT EXECUTE … TO
pg_stat_scan_tables` in `pg_freespacemap--1.1--1.2.sql:4-5`
[verified-by-code].

## Invariants

- Rejects relkinds without storage [verified-by-code]
  (`source/contrib/pg_freespacemap/pg_freespacemap.c:37-42`).
- Block-number range checked `[0, MaxBlockNumber]` [verified-by-code]
  (`source/contrib/pg_freespacemap/pg_freespacemap.c:44-47`).
- Uses `AccessShareLock` only; `GetRecordedFreeSpace` reads via the FSM
  fork's normal buffer-manager path (no direct page locking here).

## Notable internals

This is the smallest file in the slice (53 LOC); the heavy lifting lives
in `src/backend/storage/freespace/freespace.c`. Single-shot, no SRF, no
critical section, no WAL.

## Trust-boundary / Phase D surface

1. No C-side privilege check. The whole defense is the SQL grant to
   `pg_stat_scan_tables`. [ISSUE-audit-gap: no superuser/has_privs check
   in C; if DB owner re-grants past pg_stat_scan_tables, callers get
   per-block FSM readout — fairly low-sensitivity (the value is a
   "free-bytes category", not tuple data) but still a relation-existence
   oracle (nit)]
   (`source/contrib/pg_freespacemap/pg_freespacemap.c:27-53`).
2. Does NOT call `CHECK_FOR_INTERRUPTS()` — but it's single-shot, so
   N/A.

## Cross-refs

- `knowledge/subsystems/storage-buffer.md` — FSM fork location
- `knowledge/files/contrib/pg_visibility/pg_visibility.c.md` — companion VM-byte peek
- `src/backend/storage/freespace/README` — FSM tree shape (would explain the int2 return)

<!-- issues:auto:begin -->
- [Issue register — `pg_freespacemap`](../../../issues/pg_freespacemap.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-audit-gap: no C-side privilege check, only SQL grant to pg_stat_scan_tables (nit)] — `source/contrib/pg_freespacemap/pg_freespacemap.c:27-53`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_freespacemap.md](../../../subsystems/contrib-pg_freespacemap.md)
