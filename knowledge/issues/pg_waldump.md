# Issues — `pg_waldump`

Per-subsystem issue register for the `src/bin/pg_waldump`
utility. See `knowledge/issues/README.md` for the tag
convention.

**Parent subsystem doc:** _none yet_ (covered only at file level
under `knowledge/files/src/bin/pg_waldump/`).

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c:37 | doc-drift | maybe | Banner comment acknowledges pg_walinspect mirrors much of this logic; real risk of divergent bug fixes between pg_waldump and contrib/pg_walinspect | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c (record format) | correctness | maybe | pg_waldump decodes WAL using current-source rmgr description tables; cross-version WAL with same `XLOG_PAGE_MAGIC` but evolved record layout can be misdecoded silently | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/archive_waldump.c:842 | leak | likely | Hash entry key `fname` (pnstrdup'd at line 842) is never `pfree`d on entry deletion or `ArchivedWAL_destroy`; small leak per WAL segment processed in tar mode | open | knowledge/files/src/bin/pg_waldump/archive_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/rmgrdesc.c:42 | correctness | maybe | `custom###` naming assumes ≤ 999 custom rmgrs; raising `RM_N_CUSTOM_IDS` past 999 silently breaks both directions of the name↔ID mapping | open | knowledge/files/src/bin/pg_waldump/rmgrdesc.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c:1100 | correctness | nit | `-r custom###` parser doesn't reject trailing garbage; `custom123abc` either succeeds silently or fails with confusing message | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c:1040,1071,1196 | correctness | nit | Several `sscanf("%u", ...)` calls accept trailing garbage silently (`-B`, `-n`, `-x`) | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c:374-388 | undocumented-invariant | nit | `--follow` retry budget hard-coded at 5 s (10 × 500 ms); no flag to extend | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c:152 | stale-todo | maybe | XXX comment flags `split_path` as forward-slash only; potentially wrong on Windows backslash paths | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/archive_waldump.c:614 | security | nit | TOCTOU window between `fopen` and `chmod` on temp spill file; low impact for user-owned temp dir | open | knowledge/files/src/bin/pg_waldump/archive_waldump.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/compat.c:55 | correctness | nit | `localtime()` return value not NULL-checked; out-of-range TimestampTz could crash on subsequent `strftime` | open | knowledge/files/src/bin/pg_waldump/compat.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/compat.c:42-46 | stale-todo | nit | Two XXX comments: static-buffer reuse hazard in `timestamptz_to_str`, and "should move timestamp infrastructure to src/common" | open | knowledge/files/src/bin/pg_waldump/compat.c.md §Potential issues |
| 2026-06-11 | src/bin/pg_waldump/pg_waldump.c:1175 | undocumented-invariant | maybe | `-t/--timeline` uses `strtoul` base 0; leading-zero values silently parse as octal | open | knowledge/files/src/bin/pg_waldump/pg_waldump.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- The PG18 addition of tar-archive reading (`archive_waldump.c`)
  introduced a fair amount of new state (cur_file, hash table of
  segments, temp-spill directory). The pointer-revalidation
  pattern after every `ArchivedWAL_insert`/`_delete_item` is
  easy to get wrong; the file comments call this out explicitly.
- WAL record version compatibility is the highest-impact
  concern: pg_waldump is often used to inspect WAL from older
  servers. The `pg_walinspect` mirror noted in the banner comment
  is the same risk doubled.
- The `custom###` numeric-naming scheme for unloaded custom
  rmgrs is a workable workaround but worth noting as an
  invariant tied to `RM_N_CUSTOM_IDS`.
