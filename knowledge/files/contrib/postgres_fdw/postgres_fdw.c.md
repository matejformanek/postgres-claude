# postgres_fdw.c

## One-line summary

The 8 837-LOC FDW core that wires PostgreSQL's `FdwRoutine` interface to libpq-backed remote PostgreSQL servers: scan / join / upper-rel pushdown, foreign-modify (INSERT/UPDATE/DELETE incl. batch), direct-modify (UPDATE/DELETE that bypass the local execution), async-execution callbacks, EXPLAIN integration, IMPORT FOREIGN SCHEMA, ANALYZE sampling, and remote-statistics restore — every entry point is driven by `postgres_fdw_handler()`'s `FdwRoutine` struct.

## Public API / entry points

SQL-callable:
- `postgres_fdw_handler() → fdw_handler` (line 769, `PG_FUNCTION_INFO_V1`) — returns a populated `FdwRoutine` (lines 770-830).

FDW callback routines installed by `postgres_fdw_handler`:

Scanning:
- `postgresGetForeignRelSize(root, baserel, foreigntableid)` (line 840) — populates `PgFdwRelationInfo`; calls `apply_server_options` + `apply_table_options`; partitions baserestrictinfo via `classifyConditions`; computes `attrs_used`; optionally connects to remote for EXPLAIN-based estimates (line 955) when `use_remote_estimate=true`.
- `postgresGetForeignPaths(root, baserel, foreigntableid)` (line 1232) — creates one simple `ForeignPath` via `create_foreignscan_path`, plus pathkey-aware paths and parameterized paths (only when `use_remote_estimate=true`, lines 1272).
- `postgresGetForeignPlan(root, baserel, ...)` (line ~1414) — builds the ForeignScan Plan node.
- `postgresBeginForeignScan(node, eflags)` (line 1714) — opens connection via `GetConnection`, assigns cursor number, sets up param processing, picks `async_capable`.
- `postgresIterateForeignScan(node)` (line 1819) — lazy `create_cursor` + `fetch_more_data`; returns next tuple from in-memory batch.
- `postgresReScanForeignScan(node)` (line 1864) — `MOVE BACKWARD ALL` (PG<15) or CLOSE+recreate (PG>=15) or just rewind in-memory.
- `postgresEndForeignScan(node)` (line 1938).
- `postgresRecheckForeignScan(node, slot)` (line 2571) — for EvalPlanQual; for join-relids, runs the local outerPlan.

Modify:
- `postgresAddForeignUpdateTargets(root, rtindex, target_rte, target_relation)` (line 1963) — adds the ctid resjunk Var.
- `postgresPlanForeignModify(root, plan, resultRelation, subplan_index)` (line 1991) — picks target attrs; deparses INSERT / UPDATE / DELETE.
- `postgresBeginForeignModify`, `postgresExecForeignInsert / Update / Delete`, `postgresExecForeignBatchInsert`, `postgresGetForeignModifyBatchSize`, `postgresEndForeignModify` (lines ~4220+).
- `postgresBeginForeignInsert / EndForeignInsert` — partition-row-movement variants.
- `postgresIsForeignRelUpdatable(rel)` (line 2528) — respects per-server and per-table `updatable` option, returns bitmask of `(1<<CMD_INSERT) | (1<<CMD_UPDATE) | (1<<CMD_DELETE)` if updatable.
- `postgresPlanDirectModify(root, plan, resultRelation, subplan_index)` (line 2664) — decides if the UPDATE/DELETE can be done entirely remotely (no local row pull); if so rewrites the subplan.
- `postgresBeginDirectModify` (line 2862), `postgresIterateDirectModify` (line 2978), `postgresEndDirectModify` (line 3022).
- `postgresExecForeignTruncate(rels, behavior, restart_seqs)` (line 3199) — respects per-server and per-table `truncatable` option; emits remote TRUNCATE.

EXPLAIN:
- `postgresExplainForeignScan / ForeignModify / DirectModify` (lines 3045, 3152, 3180).

ANALYZE:
- `postgresAnalyzeForeignTable` (line ~5106) → `postgresAcquireSampleRowsFunc` (line 5225) — uses remote `random()` or `TABLESAMPLE` per `analyze_sampling` option.
- `postgresImportForeignStatistics` (line 5591) — `pg_restore_relation_stats` + `pg_restore_attribute_stats` SQL on local, fetched from remote `pg_stats`. Gated by `restore_stats` option.

Schema import:
- `postgresImportForeignSchema(stmt, serverOid)` (line 6322) — issues a SELECT against remote `pg_class`/`pg_attribute`/`pg_namespace`/`pg_attrdef`/`pg_collation` and synthesizes `CREATE FOREIGN TABLE` commands.

Join + upper:
- `postgresGetForeignJoinPaths` — adds join paths when `foreign_join_ok` (line 6647) approves.
- `postgresGetForeignUpperPaths` (line ~5800+) → `add_foreign_grouping_paths` / `add_foreign_ordered_paths` / `add_foreign_final_paths`.

Async-execution:
- `postgresIsForeignPathAsyncCapable(path)` (line 8136) — returns `fpinfo->async_capable`.
- `postgresForeignAsyncRequest(areq)` (line 8149).
- `postgresForeignAsyncConfigureWait(areq)` (line 8159).
- `postgresForeignAsyncNotify(areq)` (line 8236).
- `process_pending_request(areq)` (line 8372, in header) — drain a pending async fetch.

Internal helpers (selected):
- `estimate_path_cost_size` (line 3304) — central cost-model dispatcher.
- `get_remote_estimate` (line 3818) — runs `EXPLAIN <sql>` remotely, parses `(cost=A..B rows=R width=W)`.
- `apply_server_options` / `apply_table_options` (lines 7092, 7124) — read FDW option lists.
- `create_cursor` (line 3941), `fetch_more_data` (line 4014), `fetch_more_data_begin` (line 8346) — sync + async fetch.
- `make_tuple_from_result_row` (line 8440) — converts a PGresult row to a HeapTuple via `InputFunctionCall`.
- `conversion_error_callback` (line 8597) — adds `attname` / `relname` errcontext.
- `prepare_query_params` / `process_query_params` (lines 5020, 5065) — bind param values to text for libpq.
- `create_foreign_modify` (line 4172), `prepare_foreign_modify` (line ~4380), `execute_foreign_modify` (line ~4400), `finish_foreign_modify`, `deallocate_query`, `store_returning_result`, `execute_dml_stmt`, `build_remote_returning`, `init_returning_filter`, `apply_returning_filter` — modify pipeline.
- `foreign_join_ok` (line 6647), `semijoin_target_ok` (line 6608), `foreign_grouping_ok` — pushdown gate helpers.
- `set_transmission_modes` (line 4108) / `reset_transmission_modes` (line 4144) — GUC stack wrapper, in header.

## Key invariants

- INV-FDWHANDLER-COMPLETE: `postgres_fdw_handler` populates every FdwRoutine pointer the planner/executor may consult (lines 774-829). Any missing one → core code crashes at run time. [verified-by-code]
- INV-USERID-PICK: every callback that opens a connection uses `userid = OidIsValid(<fsplan or rri>->checkAsUser) ? <checkAsUser> : GetUserId()` (lines 1743, 2889, 4199). This matches what `ExecCheckPermissions` does in core. **`checkAsUser` is the table-owner-or-explicit-INVOKER role** — postgres_fdw runs as the row-security/permissions-defining user, NOT necessarily the session user. [verified-by-code]
- INV-PUSHDOWN-SAFE-MONOTONE: `fpinfo->pushdown_safe=true` is the default for base rels (line 856). For joins/uppers it's set to true only after the corresponding `foreign_join_ok` / `foreign_grouping_ok` returns true. A `false` result propagates up — an unsafe inner cannot be joined remotely.
- INV-NO-PARAMETERIZED-WITHOUT-REMOTE-ESTIMATE: parameterized paths are only built when `use_remote_estimate=true` (line 1272 comment + return). Otherwise we have no way to know if pushing the join-clause is worth it.
- INV-CURSOR-LAZY: `cursor_exists` starts false in `postgresBeginForeignScan`. `postgresIterateForeignScan` calls `create_cursor` on first iteration (line 1832). This avoids opening the cursor in EXPLAIN-without-ANALYZE mode (`EXEC_FLAG_EXPLAIN_ONLY` short-circuits Begin at line 1730).
- INV-DEALLOC-ALL-LEAK-DEFENSE: each `PgFdwModifyState.have_prep_stmt` flag — when prepared statements are created (UPDATE/DELETE), connection.c's xact callback issues `DEALLOCATE ALL` after errors (`connection.c:1240`). This file sets `will_prep_stmt=true` (line 4207) when calling `GetConnection`.
- INV-ASYNC-ONE-PENDING-PER-CONN: at most one `pendingAreq` per connection at any time (`PgFdwConnState.pendingAreq`). Every code path that wants to issue a new query first calls `process_pending_request` (lines 301 in connection.c, 3953 in this file).
- INV-CTID-ROW-IDENTITY: UPDATE/DELETE on a foreign table identify the row by `ctid` — emitted in `WHERE ctid = $1` (`deparse.c:2282`, `:2400`). `postgresAddForeignUpdateTargets` (line 1963) makes the ctid available as a resjunk col.

## Notable internals

### Pushdown decision tree (planner-side)

- **Scan pushdown**: `GetForeignRelSize` classifies quals (`classifyConditions`); remote_conds go to the remote, local_conds to local.
- **Parameterized scan**: only with `use_remote_estimate`. Each candidate outer-rel gets a separate ForeignPath with the join clause shipped as a `$N` param.
- **Join pushdown** (`foreign_join_ok`, line 6647): supported types are INNER, LEFT, RIGHT, FULL OUTER, SEMI. ANTI is rejected (lines 6660-6666 comment). Joining rels must have `pushdown_safe`. If either has `local_conds`, can't push. PlaceHolderVars that need eval at this join → can't push (lines 6750-6762). Merges shippable_extensions union.
- **Upper-rel pushdown** (`foreign_grouping_ok`): GROUP BY, HAVING, aggregate-pushdown. Constraint: all grouping cols and aggregates must be shippable.
- **Sort pushdown**: `query_pathkeys` pushed wholesale if all `is_foreign_pathkey`. Per-EC pathkeys considered only with `use_remote_estimate`.
- **LIMIT pushdown**: `add_foreign_final_paths` adds a `has_limit` ForeignPath.
- **Direct modify** (`postgresPlanDirectModify`, line 2664): only UPDATE/DELETE; only when the subplan is a single ForeignScan (or Append-child); only if all SET-clause expressions are shippable; only if there are no local quals. If yes, the ModifyTable is bypassed and the ForeignScan emits the UPDATE/DELETE directly.

### Connection-cache key reminder

`GetConnection` is keyed by `user->umid`, populated here at every connection site:
- scan: `userid = checkAsUser-or-GetUserId; user = GetUserMapping(userid, table->serverid)` (lines 1743-1752).
- modify: `userid = ExecGetResultRelCheckAsUser(rri, estate); user = GetUserMapping(...)` (lines 4199-4204).
- direct modify: same as scan (lines 2889-2898).
- TRUNCATE: `user = GetUserMapping(GetUserId(), serverid)` (line 3277).
- ANALYZE: `user = GetUserMapping(relation->rd_rel->relowner, table->serverid)` (line 5269) — **as the TABLE OWNER**, not the session user. Comment line 5263-5266 explicit.
- IMPORT FOREIGN SCHEMA: `mapping = GetUserMapping(GetUserId(), server->serverid)` (line 6362) — session user (must be SERVER user or owner).
- Cost estimation in `estimate_path_cost_size`: `conn = GetConnection(fpinfo->user, ...)` (line 3381) — uses cached `fpinfo->user` set at GetForeignRelSize ONLY when `use_remote_estimate=true`.

### `create_cursor` and the `DECLARE c%u CURSOR FOR <select>` pattern

Line 3976: `appendStringInfo(&buf, "DECLARE c%u CURSOR FOR\n%s", fsstate->cursor_number, fsstate->query);` — cursor number is per-backend-monotonic (`GetCursorNumber`), so two backends won't collide on the SAME remote-side cursor name even when reusing the same PGconn (which can't happen anyway — one PGconn per backend).

Comment at lines 3980-3985 explains why `PQsendQueryParams(..., paramTypes=NULL, ...)` is correct: deparse always casts every param with `::typename`, so the remote infers types trivially. This sidesteps the local-vs-remote OID-mismatch problem for builtins like `int4`.

### `fetch_more_data` (line 4014)

Each fetch is `FETCH <fetch_size> FROM c%u`. Default `fetch_size=100` (line 871). For async, the FETCH was already sent by `fetch_more_data_begin`; just `pgfdw_get_result`. Tuples are stored in `fsstate->batch_cxt` (which is reset before each batch — line 4028).

### `make_tuple_from_result_row` (line 8440)

Converts a PGresult row to a HeapTuple:
- Tuple desc from `fsstate->rel` (base scan) or `fsstate->ss_ScanTupleSlot->tts_tupleDescriptor` (join scan).
- For each col in `retrieved_attrs` list:
  - If null → mark null.
  - Else `InputFunctionCall(&attinmeta->attinfuncs[i-1], valstr, attioparams[i-1], atttypmods[i-1])` — local type's input function applied to remote text.
- Sets `errpos.cur_attno` so the `conversion_error_callback` can name the offending column on error.
- At end: `if (j > 0 && j != PQnfields(res)) elog(ERROR, "remote query result does not match the foreign table");`. **Catches column-count mismatch but NOT type mismatch** — type mismatch surfaces as `InputFunctionCall` failure (e.g. invalid input syntax for integer).

### `set_transmission_modes` (line 4108)

Pushes a GUC nestlevel (`NewGUCNestLevel`). Forces `datestyle=ISO`, `intervalstyle=postgres`, `extra_float_digits=3`, `search_path=pg_catalog` for the duration of the deparse. **Reset via `AtEOXact_GUC(true, nestlevel)` (line 4147) — so an error inside the deparse correctly unwinds the GUC stack via xact-end too.** Used at deparse.c:1610 (deparseDirectUpdateSql) and :2339, and also called from postgresExecForeignBatchInsert + Insert/Update/Delete paths for param-value text-output.

### Stats import (`postgresImportForeignStatistics`, line 5591)

Gated by per-server / per-table `restore_stats` boolean option (default false). Issues local `pg_restore_relation_stats(version, schemaname, relname, relpages, reltuples)` and `pg_restore_attribute_stats(... null_frac, avg_width, n_distinct, most_common_vals, most_common_freqs, histogram_bounds, correlation, most_common_elems, most_common_elem_freqs, elem_count_histogram, range_length_histogram, range_empty_frac, range_bounds_histogram ...)` from values fetched from remote `pg_stats`. **Extended statistics objects are not supported** (line 5643 — `HasRelationExtStatistics` → WARNING, return false).

The remote query uses the prepared statements defined in lines 371-498 (`relimport_sql`, `attimport_sql`, `attclear_sql`). Argument types are hard-coded (`relimport_argtypes` etc.) — `INT4OID, TEXTOID, ...`.

### ANALYZE remote sampling (`postgresAcquireSampleRowsFunc`, line 5225)

- Picks method via `analyze_sampling` option: off / auto / random / system / bernoulli.
- If method needs remote `pg_relation_size`-style info, calls `postgresGetAnalyzeInfoForForeignTable`.
- Builds `deparseAnalyzeSql` with sample fraction.
- **Opens connection AS THE TABLE OWNER** (`user = GetUserMapping(relation->rd_rel->relowner, ...)`, line 5269). Comment at 5263-5266 confirms.
- Uses a DECLARE CURSOR / FETCH loop, reservoir-samples into `astate.rows`.

### IMPORT FOREIGN SCHEMA (`postgresImportForeignSchema`, line 6322)

- Validates schema exists on remote.
- Issues a multi-join SELECT on remote `pg_class`/`pg_namespace`/`pg_attribute`/`pg_attrdef` (+`pg_collation` if `import_collate`).
- Per-table: emits `CREATE FOREIGN TABLE <name> (col TYPE OPTIONS (column_name 'name'), ...) SERVER <s> OPTIONS (schema_name '...', table_name '...');`. **Note**: each column gets `OPTIONS (column_name 'attname')` so a future local rename doesn't break the column-name mapping (lines 6543-6549).
- Built-in `format_type(atttypid, atttypmod)` and `pg_get_expr(adbin, adrelid)` emit remote-side type/default strings. **The output is interpolated verbatim into the local DDL** — if a remote pg_get_expr output contained anything that local parser doesn't understand, the CREATE FOREIGN TABLE would fail.

## Trust boundary / Phase D surface

### `checkAsUser` runtime user picking

Every connection-open site uses `fsplan->checkAsUser` (resolved by `ExecCheckPermissions` to the table-RLS-owner or the explicit INVOKER). Means: **if a SECURITY DEFINER function reads a foreign table, postgres_fdw opens the conn as the function-definer's user**. The user mapping is looked up under `(checkAsUser, serverid)`. The conn-cache key is the resulting `umid`. If the function-definer has a `password_required=false` mapping, an unprivileged caller of the SECURITY DEFINER func transitively gets remote access. That's the documented pattern — SECURITY DEFINER is opt-in.

### Loopback bypass canonical surface

See `option.c.md` and `connection.c.md`. The chain is:
1. SERVER created with `host=localhost`.
2. USER MAPPING for non-superuser with `password_required=false` (set by superuser).
3. `pg_hba.conf` `local trust` or `host 127.0.0.1 trust` or `peer` → loopback connection authenticates as postgres OS user.
4. `user=` option on the user mapping picks a remote role (could be `postgres`).
5. RLS bypassed on remote because the connection is by `postgres`.

postgres_fdw.c is not the choke point; the option scoping + connection.c's `check_conn_params` + `pgfdw_security_check` are. But this file is the one that drives all these calls and so is the relevant audit surface.

### EXPLAIN VERBOSE remote-SQL exposure

- `postgresExplainForeignScan` prints `"Remote SQL"` when `es->verbose` (line 3144).
- `postgresExplainForeignModify` (line 3164) and `postgresExplainDirectModify` (line 3190) same.
- The SQL contains schema-qualified relation names, column names (with `column_name` mapping applied), and **literal Const values from local WHERE clauses that were pushed down**. So a non-superuser who can run `EXPLAIN VERBOSE` on a query that references a foreign table sees the remote schema topology and remote SQL syntax. **Does NOT leak conninfo, password, remote backend pid, or remote auth method.**

### Async cancel discipline on QUERY_CANCELED

When local backend gets QUERY_CANCELED:
1. `CHECK_FOR_INTERRUPTS` ereports — this happens inside `libpqsrv_get_result_last` typically.
2. xact abort → `pgfdw_xact_callback(XACT_EVENT_ABORT)` → `pgfdw_abort_cleanup`.
3. If `PQtransactionStatus == PQTRANS_ACTIVE`, `pgfdw_cancel_query` sends a libpq cancel.
4. Connection.c handles the wait (30s timeout, 1s recancel).

**For async fetches in flight**, `process_pending_request` is NOT called during the cancel path — the cleanup query mechanism is what eventually drains the pending FETCH result.

### Result tuple-descriptor mismatch handling

`make_tuple_from_result_row` line 8551: `if (j > 0 && j != PQnfields(res)) elog(ERROR, "remote query result does not match the foreign table");`. This catches column-count mismatch (which would happen if the foreign table is locally redefined while a remote prepared statement persists). **It does NOT catch type-mismatch** — the `InputFunctionCall` will throw `invalid input syntax for type %s: "%s"` echoing the offending string. **The remote string value is leaked into the local error.**

### Cross-cluster XID exposure

postgres_fdw does NOT expose remote XIDs in any client-visible way. `parallel_commit` uses local xact callbacks but doesn't carry XID info across. `postgres_fdw_get_connections_1_2` exposes `remote_backend_pid` — that's a PID, not an XID. Info-leak: yes (you can fingerprint remote PID space), but bounded.

### IMPORT FOREIGN SCHEMA: catalog injection?

`postgresImportForeignSchema` emits `CREATE FOREIGN TABLE %s (...)` where `%s = quote_identifier(tablename)`. The `tablename` came from remote `pg_class.relname`. **If a remote attacker can create a table whose `relname` contains `"; DROP SCHEMA ...`, the local generated DDL is run by the LOCAL session that called IMPORT FOREIGN SCHEMA — typically a privileged user.** But `quote_identifier` wraps the bad name in double quotes and doubles internal `"`. Verified safe.

However: column TYPE NAMES come from `format_type(atttypid, atttypmod)` on the remote (line 6409). **Type names are emitted RAW into the local DDL** (line 6541 `appendStringInfo(&buf, "  %s %s", quote_identifier(attname), typename)`). `format_type` output is normally `pg_catalog.text` or `"myschema"."mytype"` (with `format_type` doing its own quoting), but if a remote user created a type with an inventive name and force-cast it to produce odd `format_type` output, the local DDL could mis-parse. The defense is that `format_type` is a well-known-safe function on the remote — assumes remote is not actively hostile.

Similarly column DEFAULT exprs come from `pg_get_expr` (line 6411) and are interpolated raw (line 6560). **A remote default expr could contain arbitrary text** — but `pg_get_expr` round-trips through the parser and outputs valid SQL. Trust boundary here: trust that the REMOTE catalog isn't actively crafted to produce malicious `pg_get_expr` output.

### `parallel_commit` (2PC-like)

See connection.c.md INV note. Not 2PC. Local backend can disagree with subset of remotes on commit/abort.

### Connection-reuse across user mappings

Cannot reuse. The cache is keyed by umid — different umids cannot share a PGconn.

### Statistics-import payload trust

`postgresImportForeignStatistics` fetches `most_common_vals`, `histogram_bounds`, etc. from remote `pg_stats` and passes them to local `pg_restore_attribute_stats`. **These are typed values (text representation of the column's type) interpolated via prepared-statement parameters (`pgfdw_exec_prepared` style)**. SQL-injection-safe. But: **the values are inserted into local pg_statistic** — a malicious remote could plant statistical decoys to influence local query planning. Stats import requires `restore_stats=true` opt-in and is only useful to the local DBA's planner — out-of-scope for typical Phase D, but worth noting.

## Cross-references

- `source/contrib/postgres_fdw/connection.c` — every `GetConnection` call leads here.
- `source/contrib/postgres_fdw/deparse.c` — every SQL string sent comes from here.
- `source/contrib/postgres_fdw/shippable.c` — every pushdown check consults this.
- `source/contrib/postgres_fdw/option.c` — every `apply_server_options` / `apply_table_options` reads option DefElems built and validated here.
- `source/src/backend/foreign/foreign.c` — `GetForeignServer`, `GetUserMapping`, `GetForeignTable`.
- `source/src/backend/executor/nodeForeignscan.c` — drives `ExecForeignScan` → `IterateForeignScan`.
- `source/src/backend/executor/nodeModifyTable.c` — drives `ExecForeignInsert / Update / Delete`.
- `source/src/include/foreign/fdwapi.h` — `FdwRoutine` type.
- A2 libpq sweep — every PGconn here.
- `source/contrib/dblink/dblink.c` — same trust class, simpler semantics.

<!-- issues:auto:begin -->
- [Issue register — `postgres_fdw`](../../../issues/postgres_fdw.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `make_tuple_from_result_row` calls `InputFunctionCall` (line 8523) on remote text data using LOCAL type's input function. A type-mismatch (remote `text` containing non-numeric, local `int`) raises `invalid input syntax for type integer: "<remote value>"` echoing the offending string. **Remote data leaks into local error logs** even when the local user lacks RLS access to the offending row. (likely)] — `source/contrib/postgres_fdw/postgres_fdw.c:8523`.
- [ISSUE-correctness: `EXEC_FLAG_EXPLAIN_ONLY` short-circuits `BeginForeignScan` at line 1730. EXPLAIN-without-ANALYZE does NOT open any connection, so remote schema topology is NOT verified at plan time. EXPLAIN VERBOSE may show stale schema cached from earlier sessions. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:1730`.
- [ISSUE-correctness: `postgresAcquireSampleRowsFunc` opens connection as `relation->rd_rel->relowner` (line 5269), NOT the session user running ANALYZE. **A user who can ANALYZE a foreign table (which only requires VACUUM-class privilege) thereby triggers a connection AS the table owner**. The table owner's user mapping is the one consulted. If the owner's mapping has `password_required=false`, ANALYZE bypasses password check on the owner's behalf. Comment at lines 5263-5266 documents the design choice. (likely — Phase D class)] — `source/contrib/postgres_fdw/postgres_fdw.c:5269`.
- [ISSUE-security: `postgresImportForeignSchema` interpolates `format_type` and `pg_get_expr` output RAW into local DDL (lines 6541, 6560, 6568-6569). A malicious or corrupt remote pg_catalog (which requires superuser on remote anyway) could craft type names / default exprs that derail the local DDL parse. Mostly out-of-scope for usual threat model but documented. (maybe defense-in-depth)] — `source/contrib/postgres_fdw/postgres_fdw.c:6539-6577`.
- [ISSUE-correctness: `postgresImportForeignSchema` issues a separate query for schema existence (line 6373) and then a giant join. If the remote catalog changes between those two queries (DDL on remote during IMPORT), local could either miss a table or include a now-dropped one. **No advisory lock**, no `pg_catalog.pg_class` snapshot guarantee. The remote xact is REPEATABLE READ (from `configure_remote_session`), so within the IMPORT statement, snapshot is stable — actually safe. (resolved on re-read)] — `source/contrib/postgres_fdw/postgres_fdw.c:6373,6490`.
- [ISSUE-correctness: `postgresExecForeignTruncate` does not check `truncatable` for each rel before opening connection (lines 3215-3270 do the check, line 3277 opens conn). If the first rel has `truncatable=false`, ERROR is thrown BEFORE the connection is opened. Good. But subsequent rels' check happens per-iteration; an ERROR partway through means earlier-checked rels' permissions were validated for nothing. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:3265`.
- [ISSUE-correctness: `postgresIsForeignRelUpdatable` (line 2528) returns the cached option value at PLAN TIME. If `ALTER FOREIGN TABLE ... OPTIONS (SET updatable false)` runs concurrently, an in-flight query may UPDATE a now-non-updatable table. Inval-callback closes the cached PgFdwRelationInfo but not the live ModifyTable. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:2528`.
- [ISSUE-defense-in-depth: `postgresPlanDirectModify` (line 2664) bypasses local ExecBuildAuxRowMark — but ExecCheckPermissions on the foreign table itself runs at executor start. RLS policies on the LOCAL foreign table (you can create RLS policies on a foreign table since recent PG) would still apply if the local executor's qual-eval doesn't get bypassed... need to verify whether `scan.plan.qual = NIL` requirement at line 2704 catches RLS-policy-derived quals. (maybe)] — `source/contrib/postgres_fdw/postgres_fdw.c:2701-2706`.
- [ISSUE-correctness: `find_modifytable_subplan` (line 2603) only handles ForeignScan-as-immediate-child-of-ModifyTable OR child-of-Append-of-ModifyTable. Other plan shapes (e.g. a Sort between ModifyTable and ForeignScan) silently fall back to non-direct modify — a perf regression, not correctness. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:2625`.
- [ISSUE-correctness: `postgresForeignAsyncConfigureWait` (line 8159) has a non-trivial decision tree about which pending request to drain (lines 8195-8225). The "if there's an in-process request from a different Append, skip vs process" logic is described in comments but has historically been the source of async-execution bugs. (maybe)] — `source/contrib/postgres_fdw/postgres_fdw.c:8159-8229`.
- [ISSUE-error-handling: `process_pending_request` (line 8373) silently calls `fetch_more_data` then checks tuple count. If `fetch_more_data` throws (cancel, remote error), the request is never marked complete — `callback_pending` stays true. Could lead to a wait-set state where postmaster-death is the only wakeup. (nit — likely caught by xact-abort cleanup)] — `source/contrib/postgres_fdw/postgres_fdw.c:8373`.
- [ISSUE-correctness: `get_remote_estimate` (line 3818) parses `(cost=A..B rows=R width=W)` via `sscanf` (line 3844). A future remote PG that changes EXPLAIN format (e.g. EXPLAIN (FORMAT JSON) default, or new columns inside parens) would crash. Mitigated by `strrchr(line, '(')` — last paren, line 3841 — but still fragile. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:3844`.
- [ISSUE-concurrency: `create_cursor` (line 3941) uses `cursor_number` (per-backend monotone). Two ForeignScans on the SAME PGconn (same umid) get distinct numbers. But: a parallel-query worker shares plans with leader; if BOTH would run on the same PGconn (which can't happen because workers can't use cached conns — PgFdwScanState is in private memory), the worker would get its OWN counter starting at 0. Actually: parallel ForeignScan is supported but each worker opens its OWN connection (verified by `connection.c`'s per-backend cache). (resolved)] — `source/contrib/postgres_fdw/postgres_fdw.c:3941`.
- [ISSUE-correctness: line 4031 `Assert(fsstate->conn_state->pendingAreq)` in `fetch_more_data` when `async_capable`. If async-capable is true but no fetch was issued (e.g. ReScan path), the Assert could fire in cassert builds. The code at line 1882-1885 in `postgresReScanForeignScan` explicitly drains pendingAreq before reset, so the invariant holds. (resolved)] — `source/contrib/postgres_fdw/postgres_fdw.c:4031`.
- [ISSUE-security: `postgresImportForeignStatistics` issues local `pg_restore_attribute_stats(...)` with values fetched FROM the remote. The remote can supply ARBITRARY most_common_vals (within the column's type domain). A hostile remote can plant decoy statistics to bias local planner toward bad plans (`SeqScan` instead of `IndexScan`, etc.). Mitigation: requires `restore_stats=true` opt-in, local must trust the remote. (likely — Phase D class)] — `source/contrib/postgres_fdw/postgres_fdw.c:5591`.
- [ISSUE-correctness: `postgresPlanForeignModify` opens the local relation with `NoLock` (line 2014) trusting that "Core code already has some lock". If that contract is ever broken by a refactor in `nodeModifyTable.c`, postgres_fdw silently uses a non-locked relcache entry. Defensive `AccessShareLock` would be cheap insurance. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:2014`.
- [ISSUE-defense-in-depth: `postgres_fdw_handler` (line 769) is the entry — any extension that wraps `FdwRoutine` (e.g. an audit shim) has to call this and copy the pointers. There is no `_PG_init`-time hook for `FdwRoutine_hook` so monitoring extensions cannot intercept. (likely — defense-in-depth)] — `source/contrib/postgres_fdw/postgres_fdw.c:769`.
- [ISSUE-correctness: `apply_server_options` and `apply_table_options` (lines 7092, 7124) read option DefElems linearly per RelOptInfo. For a partition-heavy schema with hundreds of foreign-table partitions, the O(N*M) option-walk repeats per partition. (nit — perf)] — `source/contrib/postgres_fdw/postgres_fdw.c:7092`.
- [ISSUE-correctness: `postgresGetForeignRelSize` line 887 uses `OidIsValid(baserel->userid) ? baserel->userid : GetUserId()` for the remote-estimate user. This matches `ExecCheckPermissions`. But for `fpinfo->user`, used in `estimate_path_cost_size` (line 3381), this user is cached at planning time and a `RESET ROLE` between planning and execution could mean a different exec-time user. The exec-time path uses its own `checkAsUser/GetUserId` (line 1743), so they could be different. (nit — by design)] — `source/contrib/postgres_fdw/postgres_fdw.c:887,3381,1743`.
- [ISSUE-audit-gap: no instrumentation around `pgfdw_security_check` outcomes. A bursty pattern of "non-superuser hits password-required denial" could indicate an attack — not logged. (maybe defense-in-depth)] — `source/contrib/postgres_fdw/connection.c:446` (related to this file's connection-opening sites).
- [ISSUE-correctness: `process_query_params` (line 5065) converts params to TEXT via output functions. For a `bytea` param, the text form is `\x...` hex. The remote receives it as text and re-parses. Round-trip via text is lossy for some types (e.g. floats below `extra_float_digits=3`). The `set_transmission_modes` mitigation forces 3, but only for Const literals via `deparseConst`, not for Param VALUES sent via `PQsendQueryParams`. **A floating-point param could lose precision in transit.** (maybe correctness)] — `source/contrib/postgres_fdw/postgres_fdw.c:5065`.
- [ISSUE-correctness: `postgresExplainDirectModify` (line 3180) only emits "Remote SQL" if `es->verbose`. EXPLAIN without VERBOSE shows nothing — could surprise users debugging direct-modify plans. (nit — UX)] — `source/contrib/postgres_fdw/postgres_fdw.c:3186`.
- [ISSUE-correctness: `postgresExecForeignTruncate` builds a single TRUNCATE command for all rels (line 3281). If `rels` contains tables from DIFFERENT foreign servers, the function `Assert(table->serverid == serverid)` (line 3250) would fail in cassert; in release builds, the wrong server's connection is used. Core normally calls this per-server, so the assert is defensive. (resolved)] — `source/contrib/postgres_fdw/postgres_fdw.c:3247-3250`.
- [ISSUE-defense-in-depth: ForeignScan `fdw_scan_tlist` rebuilt for direct-modify with RETURNING (line 2843) — `rebuild_fdw_scan_tlist`. The remote query's RETURNING is computed against the remote table; local RETURNING is computed by `apply_returning_filter`. **If remote has different columns than expected (e.g. column dropped), the filter returns surprising values**. Validated by `conversion_error_callback` only on type-mismatch. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.c:2843`.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/fdw-iterate-scan.md](../../../idioms/fdw-iterate-scan.md)
- [idioms/fdw-routine-callbacks.md](../../../idioms/fdw-routine-callbacks.md)
