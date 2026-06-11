# Issues — `contrib/pg_logicalinspect`

Per-subsystem issue register for **pg_logicalinspect**, the PG17+
extension that surfaces on-disk logical-decoding snapshot internals
to SQL. Created 2026-06-11 by A21 sweep.

**Parent doc:** `knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md`

## Headlines

1. **A14-class permission pattern.** Access is gated via SQL-side
   `REVOKE … FROM PUBLIC; GRANT … TO pg_read_server_files` in the
   `.sql` install script. The C functions themselves have **no
   permission check**. A superuser SECURITY DEFINER wrapper
   trivially exposes the primitive to any caller — same anti-
   pattern as pageinspect's per-AM files, except those at least
   have an inner `superuser()` check.

2. **Calls `SnapBuildRestoreSnapshot` from a SQL function context.**
   This API has historically only been driven from the walsender /
   logical decoding startup path. Re-entrancy from arbitrary user
   SQL is not documented as safe; appears to work but the
   invariants aren't enumerated.

3. **Read amplifier for replication internals.** Combining the
   exposed `xmin / xmax / start_decoding_at / committed.xip[]`
   arrays with `pg_stat_replication` gives a `pg_read_server_files`
   member a near-complete picture of decoding state — including
   xids of in-flight transactions.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/pg_logicalinspect/pg_logicalinspect.c:98-207 | security | likely | No C-level permission check; relies on SQL-side GRANT to pg_read_server_files | open | knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md §Potential issues |
| 2026-06-11 | contrib/pg_logicalinspect/pg_logicalinspect.c:118,153 | question | maybe | Re-entrancy of SnapBuildRestoreSnapshot from user SQL undocumented | open | knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md §Potential issues |
| 2026-06-11 | contrib/pg_logicalinspect/pg_logicalinspect.c:155-198 | security | maybe | Exposes active SnapBuild internals; correlator for replication progress | open | knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md §Potential issues |
| 2026-06-11 | contrib/pg_logicalinspect/pg_logicalinspect.c:72-82 | style | nit | sscanf %X parses lower-case hex but round-trip check uses %X uppercase | open | knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md §Potential issues |
| 2026-06-11 | contrib/pg_logicalinspect/pg_logicalinspect.c:166-198 | style | nit | xid array allocation unbounded; catchange.xcnt can be huge | open | knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md §Potential issues |
| 2026-06-11 | contrib/pg_logicalinspect/pg_logicalinspect.c:104-200 | style | nit | i++ counter fragile to column reordering; Assert catches only in debug | open | knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md §Potential issues |

## Notes

This is the **A14-era class of finding** writ explicitly: contrib
extension that gates SQL-callable access via REVOKE+GRANT to a
default role but skips C-level permission enforcement. The
companion pattern lives in `contrib/pg_walinspect` (which has
similar issues per A12-era sweep).

The interaction with logical decoding internals deserves a
dedicated review pass — particularly whether SnapBuildRestoreSnapshot
is safe to invoke from a non-decoding backend while a decoder is
running on the same slot.
