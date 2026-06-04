# Issues — `contrib/pg_stat_statements`

Per-subsystem issue register for **pg_stat_statements**, the query
telemetry extension touched by virtually every PG installation.
1-file extension (`pg_stat_statements.c`, 2 913 LOC). Note: the
companion jumble code lives in `src/backend/utils/queryjumble.c` and
is OUT of A11's scope.

**Parent doc:** `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`.

**Source:** 9 entries surfaced 2026-06-04 by the A11 foreground sweep
(agent A11-1). Mirrored in the per-file doc's `## Issues spotted`
block.

## Headlines

1. **`track_utility = on` (DEFAULT TRUE) captures `CREATE/ALTER USER
   ... PASSWORD '...'` cleartext in `pg_stat_tmp/pgss_query_texts.stat`**
   and exposes it via the `pg_stat_statements` view to anyone with
   `pg_read_all_stats`. **Exact A4 psql-history cycle repeated at
   cluster scope.** Most DBAs don't realize the cluster-wide
   telemetry extension does this.

2. **`pg_stat_tmp/pgss_query_texts.stat` is readable by anyone with
   `pg_read_server_files` membership.** Combined with A7's
   `genfile.c` bypass (`pg_read_server_files` = total bypass), the
   protected-view's role-ACL filter does NOT extend to the
   underlying file. **Textbook example of the gap A7 documented,
   confirmed at a second concrete site.**

3. **Hash collision lets first-writer dictate displayed text** for a
   given `(userid, dbid, queryid)` triple. Two semantically distinct
   queries that jumble to the same queryid are stored as the first
   one's normalized form.

4. **`pg_stat_statements_info.dealloc`** (visible to PUBLIC) leaks
   coarse cross-user workload signal (eviction rate is workload-
   correlated). Granular but real info-flow channel.

## Cross-sweep references

- **A4 psql-history cycle**: `~/.psql_history` records cleartext
  `CREATE USER ... PASSWORD '...'`. pg_stat_statements does the
  same at cluster scope.
- **A7 `genfile.c` bypass**: `pg_read_server_files` membership = TOTAL
  bypass of the role-filter on `pg_stat_statements` view. The
  underlying file `pg_stat_tmp/pgss_query_texts.stat` is readable by
  any non-superuser in that role.
- **A2 libpq secret-scrub cluster**: pg_stat_statements joins as
  another site where raw passwords linger in process+filesystem
  state without `explicit_bzero`-equivalent discipline.

## Entries

- [ISSUE-security: track_utility=on captures CREATE/ALTER ROLE …
  PASSWORD verbatim in shared-readable view (likely)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:1202` —
  utility ProcessUtility branch stores raw queryString without
  password redaction; same A4 psql-history cycle.
- [ISSUE-security: pg_stat_tmp/pgss_query_texts.stat readable by
  pg_read_server_files bypasses view's role-acl filter (likely)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:85` —
  file path is in PG_STAT_TMP_DIR with 0600, but A7 genfile.c lets
  pg_read_server_files dump it.
- [ISSUE-defense-in-depth: no per-query length cap; near-1GB
  queries can bloat the text file and trigger gc storms (maybe)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:2256` —
  only caps at MaxAllocHugeSize.
- [ISSUE-documentation: silent no-op when compute_query_id=off
  (nit)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:1296` —
  early-exit with no LOG message even if extension is preloaded.
- [ISSUE-audit-gap: entry_reset has no internal ACL check, relies
  entirely on SQL GRANT/REVOKE (nit)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:2678` —
  no superuser() / has_privs_of_role guard in C body.
- [ISSUE-audit-gap: pg_stat_statements_info.dealloc visible to
  PUBLIC leaks coarse cross-user workload signal (nit)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:2210` —
  dealloc is global, view granted SELECT to PUBLIC.
- [ISSUE-correctness: gc_fail path bumps gc_count after wiping all
  texts to query_len=-1; invariant "successful pgss_store ⇒ text
  retrievable" silently violated (nit)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:2605` —
  intentional per comment but subtle.
- [ISSUE-concurrency: qtext_load_file reads with no lock and only
  detects truncation via short-read+errno==0 (nit)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:2366` —
  relies on read-past-truncate semantics not guaranteed by POSIX on
  all FS.
- [ISSUE-api-shape: hash-collision attacker dictates displayed text
  by being first to insert a (userid,dbid,queryid) (nit)] —
  `source/contrib/pg_stat_statements/pg_stat_statements.c:2812` —
  first-writer wins for normalized form.
