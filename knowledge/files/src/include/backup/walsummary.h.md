# `src/include/backup/walsummary.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~49
- **Source:** `source/src/include/backup/walsummary.h`

API for the WAL-summary directory `$PGDATA/pg_wal/summaries/`.
A summary file lists, for one `(tli, start_lsn..end_lsn)` window,
which relation blocks were modified by WAL in that window
(block-reference table format from `common/blkreftable.c`). Drives
incremental backup. [inferred]

## Types

- `WalSummaryFile` — `{ start_lsn, end_lsn, tli }`. Filename on
  disk encodes all three. [verified-by-code]
- `WalSummaryIO` — `{ File file, off_t filepos }`. The cursor
  passed to `ReadWalSummary` / `WriteWalSummary`. [verified-by-code]

## API / entry points

- `GetWalSummaries(tli, start_lsn, end_lsn)` — list summaries
  overlapping the window. `tli == 0` matches any TLI;
  `Invalid*` LSNs widen the range. [verified-by-code]
- `FilterWalSummaries(wslist, tli, start, end)` — filter an
  existing list to a specific TLI and range; used by
  `basebackup_incremental.c` to avoid re-reading the directory.
  [verified-by-code]
- `WalSummariesAreComplete(wslist, start, end, *missing_lsn)` —
  true iff the union of `wslist` covers `[start, end)`; otherwise
  `*missing_lsn` is set to the first uncovered position.
  [verified-by-code]
- `OpenWalSummaryFile(ws, missing_ok)` — open by `(tli, start, end)`
  via `BasicOpenFile` (returns a `File`, not an FD). [inferred]
- `RemoveWalSummaryIfOlderThan(ws, cutoff_time)` — used by the WAL
  summarizer to age out summaries past `wal_summary_keep_time`.
  [inferred]
- `ReadWalSummary(io, data, len)` / `WriteWalSummary(io, data, len)`
  — callbacks plugged into `BlockRefTableReader` /
  `BlockRefTableWriter`. [verified-by-code]
- `ReportWalSummaryError(arg, fmt, ...)` — `pg_attribute_printf`
  error helper. [verified-by-code]
