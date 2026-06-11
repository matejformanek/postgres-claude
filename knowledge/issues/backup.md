# Issues — `backup`

Per-subsystem issue register for `src/backend/backup/` and
`src/include/backup/`. See `knowledge/issues/README.md` for the tag
convention, severity scale, and workflow.

**Parent subsystem docs:**
- (none yet — `knowledge/subsystems/backup.md` not authored)
- `knowledge/files/src/backend/backup/` (per-file)
- `knowledge/files/src/include/backup/` (per-header)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | backup/basebackup_incremental.c:711 | undocumented-invariant | likely | Incremental restore correctness for "file dropped and recreated with same name" depends on WAL replay running afterwards; comment acknowledges but no enforcement | open | knowledge/files/src/backend/backup/basebackup_incremental.c.md §Potential issues |
| 2026-06-11 | backup/basebackup_incremental.c:816 | stale-todo | nit | Hard-coded 90% threshold for "send full file instead of incremental"; comment says "perhaps it ought to be configurable" | open | knowledge/files/src/backend/backup/basebackup_incremental.c.md §Potential issues |
| 2026-06-11 | backup/basebackup_incremental.c:458 | doc-drift | maybe | When `summarize_wal=off`, `WaitForWalSummarization` returns immediately and the subsequent "no summaries exist" error has no errhint pointing at the GUC | open | knowledge/files/src/backend/backup/basebackup_incremental.c.md §Potential issues |
| 2026-06-11 | backup/basebackup_incremental.c:790 | dead-path | nit | Overflow check on `start_blkno`/`stop_blkno` is unreachable given the prior `size <= RELSEG_SIZE * BLCKSZ` bound (defensive belt-and-braces) | open | knowledge/files/src/backend/backup/basebackup_incremental.c.md §Potential issues |
| 2026-06-11 | backup/basebackup_incremental.c:105 | stale-todo | nit | `manifest_files` simplehash memory footprint acknowledged in struct comment but no resolution; "if that turns out to be a problem, we might have to decide not to retain this information" | open | knowledge/files/src/backend/backup/basebackup_incremental.c.md §Potential issues |
| 2026-06-11 | backup/walsummaryfuncs.c:33 | doc-drift | nit | `pg_available_wal_summaries()` row order is unspecified — directory-scan order, not (tli, lsn) sorted | open | knowledge/files/src/backend/backup/walsummaryfuncs.c.md §Potential issues |
| 2026-06-11 | backup/walsummaryfuncs.c:178 | style | nit | `pg_get_wal_summarizer_state` uses magic negative `summarizer_pid` as "not running" sentinel, not a symbolic constant | open | knowledge/files/src/backend/backup/walsummaryfuncs.c.md §Potential issues |
| 2026-06-11 | backup/walsummaryfuncs.c | undocumented-invariant | maybe | Privilege enforcement is implicit via pg_proc catalog ACL; no in-file `has_privs_of_role` check makes "who can call these" non-greppable | open | knowledge/files/src/backend/backup/walsummaryfuncs.c.md §Potential issues |
| 2026-06-11 | include/backup/basebackup_sink.h | undocumented-invariant | maybe | `cleanup` callback ordering (after `end_backup` on success, before destruction on error) relies on per-sink discipline; no central enforcement | open | knowledge/files/src/include/backup/basebackup_sink.h.md §Potential issues |
| 2026-06-11 | include/backup/basebackup_sink.h | style | nit | typedef-on-same-name pattern (`struct bbsink; typedef struct bbsink bbsink;`) flagged by some IDEs as redefinition | open | knowledge/files/src/include/backup/basebackup_sink.h.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- `basebackup_incremental.c` is the highest-risk file in this batch:
  load-bearing logic for PG17+ incremental backup, with multiple
  documented but unenforced invariants (file-dropped-and-recreated
  race, 90% heuristic, summarize_wal GUC interaction). The
  cross-cluster system-identifier check (line 953) is the only
  thing protecting against silent corruption across pg_combinebackup
  inputs from different clusters — worth a dedicated invariant
  doc.
- The `bbsink` chain abstraction (basebackup_sink.h) is clean and
  well-commented; the only real concern is that "always forward
  unhandled callbacks to bbs_next" is a per-implementation
  contract rather than something the type system enforces. Worth
  considering a `bbsink_forward_all` default vtable for sinks
  that only override a subset.
- WAL summarizer state visibility via `pg_get_wal_summarizer_state`
  is sparse: no time-of-last-summary, no error-state surfacing.
  Operators currently rely on log scraping.
