# pg_rewind.h

**Source:** `source/src/bin/pg_rewind/pg_rewind.h` (54 lines)

## Purpose

Tiny public header that exposes the global configuration knobs and the
cross-file helpers shared by `pg_rewind.c`, `parsexlog.c`, `filemap.c`,
`timeline.c`, and the `rewind_source` implementations. No data
structures of its own — the substantive types live in
`filemap.h` / `rewind_source.h`. [verified-by-code]

## Role in pg_rewind

Bound together: every other compilation unit `#include "pg_rewind.h"`
to pick up `datadir_target`, `WalSegSz`, `dry_run`, `showprogress`,
`do_sync`, `sync_method`, the target timeline history
(`targetHistory`/`targetNentries`), and the progress counters
(`fetch_size`/`fetch_done`). The `extern` declarations replace what
would otherwise be a private API per file. [inferred]

## Key declarations

- Configuration globals — `datadir_target`, `showprogress`,
  `dry_run`, `do_sync`, `WalSegSz`, `sync_method`
  (`pg_rewind.h:19-24`). [verified-by-code]
- Target timeline state — `targetHistory`, `targetNentries`
  (`pg_rewind.h:27-28`); read by `parsexlog.c` to interpret WAL
  segment file names. [verified-by-code]
- Progress counters — `fetch_size` (denominator) and `fetch_done`
  (numerator) ticked from `file_ops.c:write_target_range()`
  (`pg_rewind.h:31-32`). [verified-by-code]
- `extractPageMap()`, `findLastCheckpoint()`, `readOneRecord()` —
  the three entry points of `parsexlog.c` (`pg_rewind.h:35-44`).
  [verified-by-code]
- `progress_report(bool finished)` — written in `pg_rewind.c`, called
  from `file_ops.c` write paths. [verified-by-code]
- `rewind_parseTimeLineHistory()` — in `timeline.c`, used by both
  source and target history retrieval. [verified-by-code]

## Phase D notes

The header is the seam where every `extern` becomes a process-wide
mutable global. `datadir_target` is set once in `main()` from
`--target-pgdata=` and never refreshed; every callsite in
`file_ops.c` concatenates it with a server-supplied relative path via
`snprintf`. If a future patch threaded a `RewindContext*` instead of
globals, all the path-traversal hardening could live in one place
rather than scattered across `open_target_file`/`create_target_dir`/
`create_target_symlink`/`remove_target_dir`/`remove_target_symlink`.

## Potential issues

- `[ISSUE-undocumented-invariant: WalSegSz is read before it is set by digestControlFile() at pg_rewind.c:1044, so any code path that touches WalSegSz before the first control-file digest sees zero. The order is currently fine but the invariant is implicit (low)]`
- `[ISSUE-undocumented-invariant: progress counters are uint64 globals with no atomicity. pg_rewind is single-threaded so this works, but the header gives no hint (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_rewind`](../../../../issues/pg_rewind.md)
<!-- issues:auto:end -->
