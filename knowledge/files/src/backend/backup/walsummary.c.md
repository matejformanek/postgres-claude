# `src/backend/backup/walsummary.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~310
- **Source:** `source/src/backend/backup/walsummary.c`

## Purpose

Filesystem-level management for WAL summary files (PG17+ incremental
backup feature). Summaries live in `$PGDATA/pg_wal/summaries/` with
filenames `<TLI:8>-<startlsn-hi:8>-<startlsn-lo:8>-<endlsn-hi:8>-<endlsn-lo:8>.summary`
encoding the LSN range and timeline they cover. Each summary is a
serialized `BlockRefTable` from `blkreftable.c` recording which blocks
of which relation forks were touched between `start_lsn` and `end_lsn`.
[from-comment]

## API

- `GetWalSummaries(tli, start_lsn, end_lsn)` (`walsummary.c:42`) —
  scan `pg_wal/summaries/`, parse each filename, return all summaries
  overlapping the LSN range (and TLI if non-zero). `start_lsn=0`
  means "no lower bound", same for `end_lsn`.
- `FilterWalSummaries` (`walsummary.c:99`) — same predicate as above
  but over an in-memory list.
- `WalSummariesAreComplete(wslist, start_lsn, end_lsn, *missing_lsn)`
  (`walsummary.c:137`) — sort by start_lsn, sweep forward; if a gap
  is found, return false and `*missing_lsn = current_lsn` (the first
  uncovered LSN). Tolerates overlapping summaries.
- `OpenWalSummaryFile(ws, missing_ok)` (`walsummary.c:204`) — opens
  the file with `PathNameOpenFile` (uses VFD).
- `RemoveWalSummaryIfOlderThan(ws, cutoff_time)` — for the
  `walsummarizer` background process to prune old summaries based on
  `wal_summary_keep_time`.
- `WriteWalSummary(...)` (called by the walsummarizer at end-of-segment)
  serializes a `BlockRefTable` into the file.

## Filename encoding

Five `%08X` fields: `tli`, `start_lsn_high`, `start_lsn_low`,
`end_lsn_high`, `end_lsn_low`. `IsWalSummaryFilename` validates the
24-hex-digit + `.summary` shape. (`walsummary.c:61-65`, `:210-214`)

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
