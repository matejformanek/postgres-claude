# `src/include/utils/backend_progress.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Storage layer for `pg_stat_progress_*` views. Holds command-progress
counters in each backend's `PgBackendStatus` slot without ascribing
meaning to them — the meaning lives in `commands/progress.h` and
`system_views.sql` [from-comment: lines 5-7].

## Public API

- `pgstat_progress_start_command(ProgressCommandType, Oid relid)`
- `pgstat_progress_update_param(int index, int64 val)`
- `pgstat_progress_incr_param(int index, int64 incr)`
- `pgstat_progress_parallel_incr_param(int index, int64 incr)`
- `pgstat_progress_update_multi_param(int nparam, ...)`
- `pgstat_progress_end_command(void)`

`ProgressCommandType` enum [verified-by-code: lines 22-32]: INVALID,
VACUUM, ANALYZE, CREATE_INDEX, BASEBACKUP, COPY, REPACK, DATACHECKSUMS.
(REPACK + DATACHECKSUMS are recent additions.)

## Invariants

- **INV** [verified-by-code: line 34] `PGSTAT_NUM_PROGRESS_PARAM = 20`
  — fixed slot count. Adding a progress field for a NEW command type is
  cheap; widening past 20 is an ABI-visible change.
- **INV** [inferred] Updates land in `MyBEEntry->st_progress_param[]`
  guarded by the `st_changecount` write protocol in `backend_status.h`.

## Trust boundary (Phase D)

- **Readable via `pg_stat_progress_*`** to any role that can read
  `pg_stat_activity` — i.e., role-owner or `pg_read_all_stats`.
  Progress params are integers (OIDs, counts, byte totals), so leak
  surface is narrow.
- Custom progress slots from extensions: `pgstat_progress_*` is
  callable from any backend C code; an extension can claim arbitrary
  `(ProgressCommandType, slot)` pairs without registration — risk is
  collision/confusion in views, not privilege escalation.

## Cross-refs

- `backend_status.h` — owning struct (`PgBackendStatus.st_progress_*`).
- `commands/progress.h` — meaning of each slot per command.
- A11 cluster: monitoring as extraction sink.

## Issues

None at header level.
