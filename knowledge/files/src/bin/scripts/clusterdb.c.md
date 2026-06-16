# `src/bin/scripts/clusterdb.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~295
- **Source:** `source/src/bin/scripts/clusterdb.c`

CLI wrapper that issues `CLUSTER [VERBOSE] [<table>]` per
database. With `-a/--all`, iterates every connectable database in
`pg_database` and clusters each. With `-t/--table`, clusters
specific tables (resolved via `appendQualifiedRelation`).
[verified-by-code]

## API / entry points

- `main(argc, argv)` — option parsing + dispatch to
  `cluster_one_database` or `cluster_all_databases`.
  [verified-by-code]
- `cluster_one_database(cparams, table, ...)` — opens one
  connection, builds `CLUSTER [VERBOSE] [tablename];`, runs via
  `executeMaintenanceCommand`. [verified-by-code]
- `cluster_all_databases(cparams, tables, ...)` — connects to
  maintenance db, queries
  `SELECT datname FROM pg_database WHERE datallowconn AND
  datconnlimit <> -2 ORDER BY 1`, then per-db calls
  `cluster_one_database`. [verified-by-code]

## Notable invariants / details

- The all-databases query excludes `datconnlimit = -2`, which is
  the marker for unused/disabled-databases (used by template0
  etc.). `datallowconn` excludes template0 too. [verified-by-code]
- Cancel handler is installed at startup (line 143) so Ctrl-C
  sends a query-cancel to the active connection rather than
  killing the process mid-CLUSTER. [verified-by-code]
- Table-name resolution uses `appendQualifiedRelation` (from
  `common.c`) which RESET search_paths, resolves
  `'<user-input>'::pg_catalog.regclass`, then restores secure
  search path. [verified-by-code]
- Multiple `-t` flags accumulate into a `SimpleStringList`, each
  clustered in turn (line 169-181). [verified-by-code]
- DB-name resolution defaults to `$PGDATABASE`, `$PGUSER`, then
  OS user — same pattern as createdb (line 157-165).
  [verified-by-code]

## Potential issues

- Line 148: `cannot cluster all databases and a specific one at
  the same time` rejects `-a` plus a dbname arg. But `-a` plus
  `-t TABLE` is allowed; the table is clustered in EVERY
  database that has it. If a table by that name doesn't exist in
  some db, `appendQualifiedRelation` exits with an error,
  aborting the entire `-a` loop mid-stream. [verified-by-code]
  [ISSUE-correctness: -a -t TABLE aborts entire run if TABLE
  missing in any single database (likely)]
- Per-database connection includes a new password prompt unless
  `-w` was specified. For `-a` across many dbs, the user may be
  prompted many times. [verified-by-code]
- The `--quiet` flag only suppresses the per-database "clustering
  database X" message (line 245-249); CLUSTER itself doesn't
  produce per-table output unless `-v`. [verified-by-code]
- Memory: each call to `cluster_one_database` runs
  `initPQExpBuffer(&sql)` (line 198) and `termPQExpBuffer(&sql)`
  (line 222), but the cleanup happens AFTER `PQfinish`. If the
  PQfinish path runs an error exit the buffer is leaked — but
  process is exiting anyway. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `scripts`](../../../../issues/scripts.md)
<!-- issues:auto:end -->
