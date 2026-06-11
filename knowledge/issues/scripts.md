# Issues — `scripts`

Per-subsystem issue register for the `src/bin/scripts/`
collection (`createdb`, `dropdb`, `createuser`, `dropuser`,
`clusterdb`, `reindexdb`, `vacuumdb`, `pg_isready`). See
`knowledge/issues/README.md` for the tag convention.

**Parent subsystem doc:** _none yet_ (covered only at file
level under `knowledge/files/src/bin/scripts/`).

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/bin/scripts/common.c:117 | security | likely | `appendQualifiedRelation` appends trailing `(COLUMNS)` verbatim with no syntax check; SQL injection vector via `--table='foo(); DROP DATABASE x'` | open | knowledge/files/src/bin/scripts/common.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/vacuuming.c:802-803 | security | likely | `vacuuming.c` flows the same unescaped column-list straight into the constructed VACUUM SQL — same injection vector | open | knowledge/files/src/bin/scripts/vacuuming.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/createuser.c (newpassword) | security | maybe | Plaintext password buffer (`newpassword`) is never explicitly `memset(0)` before exit; core-dump captured during invocation could leak the plaintext | open | knowledge/files/src/bin/scripts/createuser.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/createuser.c:243-256 | security | nit | `--interactive` prompt grants SUPERUSER on a single 'y' with no confirmation; cascade silently also grants CREATEDB + CREATEROLE | open | knowledge/files/src/bin/scripts/createuser.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/createuser.c:214-227 | undocumented-invariant | maybe | Zero-arg `createuser` creates a role for the OS user; surprising default that's easy to trigger via typo | open | knowledge/files/src/bin/scripts/createuser.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/createuser.c:274-278 | style | nit | `--interactive` prompts for createdb/createrole/superuser but silently defaults replication/bypassrls to NO; inconsistent UX | open | knowledge/files/src/bin/scripts/createuser.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/clusterdb.c (alldb + table) | correctness | likely | `-a -t TABLE` aborts entire all-db run if TABLE missing in any single database (via `appendQualifiedRelation` fatal) | open | knowledge/files/src/bin/scripts/clusterdb.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/reindexdb.c:218 | style | nit | `-s -j N` is fatal rather than silently downgraded to single-job mode | open | knowledge/files/src/bin/scripts/reindexdb.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/reindexdb.c:408 | correctness | maybe | `Assert(concurrentCons > 0)` assumes items_count > 0; empty-list edge case may slip past the earlier NULL check | open | knowledge/files/src/bin/scripts/reindexdb.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/reindexdb.c:244 | correctness | nit | `--system --concurrently` is sent to server to discover incompatibility; could be caught client-side | open | knowledge/files/src/bin/scripts/reindexdb.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/vacuumdb.c:305-308 | doc-drift | maybe | `--missing-stats-only` error message omits `--analyze` as a valid enabler | open | knowledge/files/src/bin/scripts/vacuumdb.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/vacuuming.h | style | nit | Adding a new VACUUM option requires synchronised edits in 3 places (vacuumdb.c, vacuuming.h, vacuuming.c); easy to miss | open | knowledge/files/src/bin/scripts/vacuuming.h.md §Potential issues |
| 2026-06-11 | src/bin/scripts/pg_isready.c | doc-drift | nit | Help text doesn't list exit status meanings (PGPing enum values); users must read man page | open | knowledge/files/src/bin/scripts/pg_isready.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/pg_isready.c:138-141 | correctness | nit | When `--dbname` contains embedded `host=`, displayed `host:port` may not match what libpq actually connects to | open | knowledge/files/src/bin/scripts/pg_isready.c.md §Potential issues |
| 2026-06-11 | src/bin/scripts/pg_isready.c | leak | nit | `PQconninfoFree(defs)` and `PQconninfoFree(opts)` not called before exit; process-exit cleanup masks it | open | knowledge/files/src/bin/scripts/pg_isready.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- The single biggest concern in this directory is the
  unescaped column-list pass-through in `common.c` (used by
  vacuumdb and clusterdb). The CLI scripts trust the user not
  to feed adversarial `--table` values, but that's only OK if
  the scripts are always invoked by trusted callers. Shell
  scripts that build `--table` from external input (e.g. a
  scheduler reading from a database) would inherit the
  injection vulnerability.
- `createuser --interactive` granting SUPERUSER on a single 'y'
  is a footgun. A double-confirmation for SUPERUSER and similar
  high-privilege flags would be cheap to add.
- The triple-edit footprint for adding a new VACUUM option is a
  meta-issue: as PG keeps adding flags (PROCESS_TOAST, PROCESS_MAIN,
  BUFFER_USAGE_LIMIT, MISSING_STATS_ONLY...) the chance of
  missing one of the three edits grows.
- The `pg_isready` exit-status convention (PGPing enum values
  as direct exit codes) is documented behaviour but commonly
  misunderstood — shell users see "non-zero == bad" and don't
  realise 1 == REJECT (server is up but rejecting) is
  qualitatively different from 2 == NO_RESPONSE.
