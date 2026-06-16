# `src/bin/scripts/vacuuming.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1052
- **Source:** `source/src/bin/scripts/vacuuming.c`

The brains behind `vacuumdb`. Three responsibilities: (1) given a
set of object filters, build a catalog query that resolves them
to a fully-qualified list of relations to process; (2) emit the
right `VACUUM (...) tablename` SQL for the target server version
(many options were added in different PG versions); (3) dispatch
those commands across N parallel connections via
`fe_utils/parallel_slot.h`. [verified-by-code]

## API / entry points

- `vacuuming_main(cparams, dbname, maintenance_db, vacopts, objects,
  tbl_count, concurrentCons, progname)` — top-level dispatcher.
  Clamps concurrentCons to tbl_count. With `--all`, iterates
  `pg_database`; else single-db. Special-cases
  `MODE_ANALYZE_IN_STAGES`, which is a loop of 3 stages with
  successively-more-accurate statistics targets. [verified-by-code]
- `vacuum_one_database(...)` — connects, fetches/uses the object
  list via `retrieve_objects`, sets up the
  `ParallelSlotArray`, dispatches `VACUUM`/`ANALYZE` commands.
  Tracks "found_objs" for analyze-in-stages so the catalog query
  isn't redone for each stage. [verified-by-code]
- `vacuum_all_databases(...)` — same shape as
  `cluster_all_databases`: pull `datname` list from `pg_database`,
  then per-db call `vacuum_one_database`. [verified-by-code]
- `retrieve_objects(conn, vacopts, objects)` — builds a big
  catalog query that returns the rows-to-process. Handles
  `--table`, `--schema`, `--exclude-schema`, `--min-xid-age`,
  `--min-mxid-age`, `--missing-stats-only`. Returns a
  `SimpleStringList` of properly-quoted relation names (+ column
  list per row).
- `prepare_vacuum_command(conn, sql, vacopts, table)` — builds
  the SQL string with per-option version gates (`Assert(serverVersion
  >= NNN)` for each flag that needs a minimum PG version).
- `run_vacuum_command(slot, vacopts, sql, table)` — sends via
  `PQsendQuery` to the slot's connection (or just prints in
  `--dry-run`).
- `escape_quotes(src)` — public; wraps `escape_single_quotes_ascii`
  and pg_fatal's on OOM.

## Notable invariants / details

- Analyze-in-stages: 3 stages, each producing increasingly
  accurate statistics, allowing tools like `pg_upgrade` to get
  a quick first pass and then refine. Implementation: loop
  `for stage in 0..ANALYZE_NUM_STAGES` calling
  `vacuum_one_database(stage=N)`. The `found_objs` argument lets
  the catalog query happen once and be reused.
  [verified-by-code]
- Version gates in `prepare_vacuum_command`:
  - parenthesised VACUUM grammar — v9.0
  - DISABLE_PAGE_SKIPPING — v9.6
  - parenthesised ANALYZE grammar — v11
  - SKIP_LOCKED, INDEX_CLEANUP, TRUNCATE, PARALLEL — v12, v12,
    v12, v13
  - PROCESS_TOAST — v14
  - PROCESS_MAIN, SKIP_DATABASE_STATS, BUFFER_USAGE_LIMIT — v16
  All gated by `Assert(serverVersion >= NNN)` plus an outer
  check that the option was actually requested. Pre-9.0 servers
  get the old unparenthesised `VACUUM FULL FREEZE ...` form
  (line 989-997). [verified-by-code]
- `--missing-stats-only` (PG18 addition) generates a 70-line
  catalog WHERE clause (line 703-777) that finds relations
  missing: (a) regular column stats, (b) extended stats, (c)
  expression-index stats, and the corresponding inheritance
  variants. [verified-by-code]
- Sort by `c.relpages DESC` (line 784) so the largest tables
  start first — better parallel utilisation than alphabetical.
  [verified-by-code]
- `RESET search_path; <query>; <ALWAYS_SECURE_SEARCH_PATH_SQL>`
  pattern (line 785-788): same trick as `common.c` — user-typed
  table names resolve against the default search path, but
  surrounding catalog queries run against a locked path.
  [verified-by-code]
- `setup_cancel_handler(NULL)` at the top of `vacuuming_main`
  (line 61). [verified-by-code]
- Per-row column-list pass-through (line 802-803): if
  `objects_listed` and column 2 isn't NULL, append the column
  list verbatim. The column list was produced by
  `splitTableColumnsSpec` in `common.c`. [verified-by-code]
- `run_vacuum_command` only PRINTS the SQL in `--dry-run` mode
  (line 1017-1021); it still goes through the parallel slot
  setup (which holds open the connection) — this is mostly
  benign. [verified-by-code]

## Potential issues

- Line 800-803: the column list from
  `splitTableColumnsSpec` is passed straight through to the
  emitted SQL. As noted in `common.c.md`, this is a SQL
  injection vector if `--table` is fed an attacker-controlled
  value. Same issue applies here.
  [verified-by-code] [ISSUE-security: --table column list flows
  unescaped from splitTableColumnsSpec into VACUUM SQL (likely)]
- The `--all` + `--table` combination: if a table doesn't exist
  in a given database, the catalog query returns no row and
  vacuumdb silently skips it. Friendlier than clusterdb's hard
  failure, but a typo can be silently ignored.
  [verified-by-code]
- Line 781-787: the catalog query runs over LIBPQ wire — large
  databases with hundreds of thousands of tables can produce
  very large result sets here. Not paginated.
  [verified-by-code]
- `escape_single_quotes_ascii` (called from `escape_quotes`,
  line 1045-1051) is single-byte aware only. For
  `--buffer-usage-limit` this is fine (the value is something
  like "256MB"). [verified-by-code]
- The dry-run mode (line 1020-1021) marks the slot idle without
  sending anything. If many tables were queued, the wall time
  is dominated by parallel-slot bookkeeping rather than actual
  work. Not a bug, just expected.
  [verified-by-code]
- Line 64-65: `if (tbl_count > 0 && (concurrentCons > tbl_count))
  concurrentCons = tbl_count;` — silently clamps `-j` to the
  number of tables. Slightly surprising but the help text
  doesn't promise otherwise. [verified-by-code]
- Each `pg_log_error` in `run_vacuum_command` (line 1029-1036)
  reports the failure but the function returns regardless;
  `ParallelSlotsWaitCompletion` (driven from the caller) tracks
  any non-zero exit status. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `scripts`](../../../../issues/scripts.md)
<!-- issues:auto:end -->
