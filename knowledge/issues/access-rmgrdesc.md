# Issues — `access-rmgrdesc`

Per-subsystem issue register for the WAL resource-manager descriptor
routines under `src/backend/access/rmgrdesc/` (the `rm_desc` /
`rm_identify` functions that drive `pg_waldump` and
`pg_get_wal_resource_managers()`). See `knowledge/issues/README.md` for
the tag convention, severity scale, and workflow.

**Parent subsystem doc:** (none yet; per-file docs under
`knowledge/files/src/backend/access/rmgrdesc/`)

These are all **low-severity**: descriptors are read-only renderers over
backend-written WAL, output to `pg_waldump`'s offline text — not a SQL
or replay path. Surfaced during the 2026-06-09 cloud backfill of the 16
per-AM descriptor files.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-09 | gistdesc.c:20 | undocumented-invariant | nit | `out_gistxlogPageUpdate` is an empty function; blank `PAGE_UPDATE` desc line is by design (data in block refs) but uncommented | open | knowledge/files/src/backend/access/rmgrdesc/gistdesc.c.md §Potential issues |
| 2026-06-09 | hashdesc.c:130 | undocumented-invariant | nit | `XLOG_HASH_SPLIT_PAGE` and `_SPLIT_CLEANUP` are in `hash_identify` but have no `hash_desc` case → intentionally empty desc, uncommented | open | knowledge/files/src/backend/access/rmgrdesc/hashdesc.c.md §Potential issues |
| 2026-06-09 | committsdesc.c:45 | style | nit | `commit_ts_identify` switches on raw `info`, not `info & ~XLR_INFO_MASK` like most siblings; correct today, inconsistent. Same pattern in `replorigindesc.c:53`. | open | knowledge/files/src/backend/access/rmgrdesc/committsdesc.c.md §Potential issues |
| 2026-06-09 | logicalmsgdesc.c:33 | question | nit | User-controlled logical-message prefix (`pg_logical_emit_message`) printed raw via `%s` into `pg_waldump`; payload is hex-escaped, prefix is not. Offline-tool sink, not a SQL injection vector. | open | knowledge/files/src/backend/access/rmgrdesc/logicalmsgdesc.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- **Shared convention across the directory:** every `rm_desc` is a
  switch / if-else on `info = XLogRecGetInfo(record) & ~XLR_INFO_MASK`
  with **no `default:`** — an unknown opcode renders an empty
  description rather than erroring, and the paired `rm_identify` returns
  `NULL` (which `pg_waldump` shows as `UNKNOWN`). This is deliberate:
  descriptors must never `ereport` on malformed WAL.
- **Init-page bit asymmetry** (`brindesc.c`, `heapdesc.c`): `rm_desc`
  masks off the init-page bit before dispatch while `rm_identify` keeps
  it (so `INSERT` vs `INSERT+INIT` are distinct identities but render
  the same fields). By design — not an issue.
- **Inverted FPI guard in `gindesc.c`** (`!XLogRecHasBlockImage`, vs the
  heap/btree `XLogRecHasBlockData` form): correct, because GIN's
  recompress stream is only separately renderable when there is no
  full-page image. Documented in the per-file doc as a gotcha, not an
  issue.
