# `src/bin/scripts/reindexdb.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~925
- **Source:** `source/src/bin/scripts/reindexdb.c`

CLI wrapper that issues `REINDEX [DATABASE|SCHEMA|TABLE|INDEX|
SYSTEM] [CONCURRENTLY] [TABLESPACE <ts>] [VERBOSE] <name>`.
Largest of the bin/scripts because it manages parallel reindex
across multiple connections via `fe_utils/parallel_slot.h`. The
fundamental trick: REINDEX DATABASE expands to a list of tables
which can then run in parallel jobs, but REINDEX INDEX must be
batched per-underlying-table so that two concurrent connections
don't try to rebuild indexes on the same table (server would
serialize and we'd waste a connection). [verified-by-code]

## API / entry points

- `main(argc, argv)` — option parsing; with `--all`,
  `reindex_all_databases`; else picks a `ReindexType` from flags
  (`-s` SYSTEM, `-S` SCHEMA, `-i` INDEX, `-t` TABLE) and calls
  `reindex_one_database` per type. [verified-by-code]
- `reindex_one_database(cparams, type, user_list, ..., concurrentCons,
  tablespace)` — connects, version-gates `CONCURRENTLY` (PG12+)
  and `TABLESPACE` (PG14+), builds a list of names to process,
  spins up `ParallelSlotArray` of size `concurrentCons`, dispatches
  REINDEX commands. [verified-by-code]
- `reindex_all_databases(...)` — iterates `pg_database` where
  `datallowconn AND datconnlimit <> -2`, runs the per-type list
  (system catalogs, schemas, indexes, tables, or whole db if
  none of those given). [verified-by-code]
- `gen_reindex_command(conn, type, name, echo, verbose, concurrently,
  tablespace, sql)` — assembles the SQL with the right
  parenthesised options-list since PG14.
- `run_reindex_command(conn, type, name, echo, sql)` — sends one
  REINDEX via `PQsendQuery` to a parallel slot.
- `get_parallel_tables_list(conn, type, user_list, echo)` — for
  parallel DATABASE/SCHEMA mode, materialises a sorted-by-relpages
  list of table identifiers using a pg_catalog-safe query.
- `get_parallel_tabidx_list(conn, index_list, &table_list, echo)`
  — for parallel INDEX mode, looks up the owning table OID for
  each user-supplied index name so the scheduler can batch by
  table.

## Notable invariants / details

- `-j > 1` + `-s` (system) is rejected at startup (line 217):
  reindexing pg_catalog must be serial because of catalog-table
  locking dependencies. [verified-by-code]
- Per-type concurrency strategies (line 313-391):
  - DATABASE/SCHEMA single-job: pass the db/schema name as a
    single-item list, let the server expand internally.
  - DATABASE/SCHEMA multi-job: fetch the full table list via
    catalog query, then dispatch as parallel REINDEX TABLE.
  - INDEX multi-job: fetch the owning-table OID per index and
    use that to serialise indexes-on-same-table to the same
    slot.
  - SYSTEM multi-job: forbidden (Assert at line 384, defensive
    after the startup check). [verified-by-code]
- Parallel slot adoption: `ParallelSlotsAdoptConn(sa, conn)` (line
  413) gives the initial connection to the pool; new connections
  for the other N-1 slots are made by `ParallelSlotsSetup` from
  `cparams`. The initial conn pointer is then nulled to prevent
  double-close. [verified-by-code]
- `setup_cancel_handler(NULL)` (line 214) — Ctrl-C sends a
  cancel to every connection in the parallel pool.
  [verified-by-code]
- DB/schema/index/table priority order when both are given (line
  244-272): SYSTEM first, then SCHEMA, then INDEX, then TABLE,
  then whole-db ONLY if nothing else was specified. This means
  `-s -i myidx` does BOTH system reindex AND specific index
  reindex. [verified-by-code]
- Per-database password prompt: like clusterdb, each connection
  in the parallel pool may prompt independently unless `-w`.
  [from-comment]

## Potential issues

- Parallel DATABASE mode with a very large catalog: the
  `get_parallel_tables_list` query materialises every reindexable
  table OID up-front, which can be memory-heavy on
  multi-million-table clusters. [verified-by-code]
- Line 218: `cannot use multiple jobs to reindex system catalogs`
  is a hard error rather than a downgrade to single-job mode.
  Slightly user-hostile. [verified-by-code] [ISSUE-style:
  `-s -j N` could be silently downgraded to single-job rather
  than fatal (nit)]
- The `--concurrently` flag with `--system` is allowed at the
  client level but the server rejects REINDEX SYSTEM CONCURRENTLY
  (can't concurrently rebuild catalog indexes that are needed
  during the rebuild). The client emits the SQL and lets the
  server's error message inform the user. [verified-by-code]
  [ISSUE-correctness: --system --concurrently is sent to server
  to discover incompatibility; could be caught client-side (nit)]
- `--tablespace` to move indexes to a different tablespace: the
  server's privileges check applies, but reindexdb doesn't
  verify the user has CREATE on that tablespace before issuing
  N parallel REINDEXes. Standard wrapper behaviour, but a
  surprise if half the indexes fail mid-run.
  [verified-by-code]
- The `concurrentCons = Min(concurrentCons, items_count)`
  clamping (line 407) — if `items_count == 0` we hit
  `Assert(concurrentCons > 0)`. The earlier `if (process_list ==
  NULL) { ...; return; }` (line 353-357) covers the genuinely
  empty case; if `process_list` is non-NULL but empty, the
  assert fires in cassert builds. [verified-by-code]
  [ISSUE-correctness: assert at line 408 assumes items_count>0;
  empty-list path may slip through if process_list non-NULL but
  empty (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `scripts`](../../../../issues/scripts.md)
<!-- issues:auto:end -->
