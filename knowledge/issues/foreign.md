# Issues — `foreign`

Per-subsystem issue register for `src/backend/foreign/` — the
foreign-data-wrapper catalog lookup and FDW routine plumbing.

**Parent subsystem docs:**
- `knowledge/files/src/backend/foreign/*.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | foreign/foreign.c:607-624 | doc-drift | likely | `libpq_conninfo_options[]` hard-coded list is stale — includes `tty` (removed from libpq) and lacks `channel_binding`, `target_session_attrs`, `keepalives_*`, `tcp_user_timeout`, `gssencmode`, `sslnegotiation`, etc. Used by deprecated-but-still-callable `postgresql_fdw_validator` | open | knowledge/files/src/backend/foreign/foreign.c.md §Potential issues |
| 2026-06-11 | foreign/foreign.c:497-499 | undocumented-invariant | nit | When `makecopy = true`, `GetFdwRoutineForRelation` does plain `memcpy` of the cached `FdwRoutine`. If a future FDW added a palloc'd subsidiary field, this would silently share pointers between caller-context and CacheMemoryContext | open | knowledge/files/src/backend/foreign/foreign.c.md §Potential issues |
| 2026-06-11 | foreign/foreign.c:885-890 | question | nit | `GetExistingLocalJoinPath` returns NULL when no usable local path exists; callers `ereport(ERROR)` with their own messages. Could surface a structured "why" (parameterized? unsupported join type?) | open | knowledge/files/src/backend/foreign/foreign.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- This file is almost entirely "look up an OID → palloc a struct
  from syscache → return it" for FDW, server, user-mapping, foreign
  table, foreign column. The only non-trivial helpers are
  `GetExistingLocalJoinPath` (planner-side EPQ fallback for
  pushed-down joins) and the deprecated `postgresql_fdw_validator`.
- The validator deprecation has stood since postgres_fdw landed with
  its own validator — but the function is still callable as
  `CREATE FOREIGN DATA WRAPPER ... VALIDATOR postgresql_fdw_validator`,
  which means user-visible breakage every time libpq adds an option.
