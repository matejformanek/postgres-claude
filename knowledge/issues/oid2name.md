# Issues — `contrib/oid2name`

Per-subsystem issue register for **oid2name**, the libpq frontend
CLI that maps PG on-disk file/OID numbers back to table/database
names. Created 2026-06-11 by A21 sweep.

**Parent doc:** `knowledge/files/contrib/oid2name/oid2name.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/oid2name/oid2name.c:286 | style | nit | Uses legacy PQescapeString instead of PQescapeStringConn | open | knowledge/files/contrib/oid2name/oid2name.c.md §Potential issues |
| 2026-06-11 | contrib/oid2name/oid2name.c:518 | correctness | maybe | Hardcoded +80-byte SQL syntax headroom for sprintf'd qualifiers | open | knowledge/files/contrib/oid2name/oid2name.c.md §Potential issues |
| 2026-06-11 | contrib/oid2name/oid2name.c:539 | question | nit | `-t` uses LIKE-pattern match (~~), not exact; undocumented in --help | open | knowledge/files/contrib/oid2name/oid2name.c.md §Potential issues |
| 2026-06-11 | contrib/oid2name/oid2name.c:306-343 | undocumented-invariant | nit | No -w/no-password mode; always prompts when server requests | open | knowledge/files/contrib/oid2name/oid2name.c.md §Potential issues |
| 2026-06-11 | contrib/oid2name/oid2name.c:391-395 | style | nit | Exits process on first DB query error; no per-DB recovery | open | knowledge/files/contrib/oid2name/oid2name.c.md §Potential issues |
| 2026-06-11 | contrib/oid2name/oid2name.c:213 | doc-drift | nit | --help text for -S says "show system objects too" without naming schemas | open | knowledge/files/contrib/oid2name/oid2name.c.md §Potential issues |

## Notes

oid2name is largely superseded by `SELECT pg_relation_filepath(…)`
and `\d+`. The legacy escape style and the lack of `-w` flag suggest
it hasn't seen modernization in many years. Low priority for upstream
fixes; mostly a static reference.
