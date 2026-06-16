# postgres_fdw.h

## One-line summary

Internal header for postgres_fdw: declares `PgFdwRelationInfo` (the `fdw_private` carried on every postgres_fdw RelOptInfo through planning), `PgFdwConnState` (per-connection state, currently just the pending async request), the `PgFdwSamplingMethod` enum used by remote ANALYZE, and the cross-file API surface among `postgres_fdw.c`, `connection.c`, `deparse.c`, `option.c`, and `shippable.c`.

## Public API / entry points

The header is internal to the extension — none of these symbols are SQL-callable. All are `extern` for use only between the five .c files in `contrib/postgres_fdw/`.

- `PgFdwRelationInfo` struct (lines 30-132) — fdw_private body for every base / join / upper rel pushed through postgres_fdw. Holds:
  - `pushdown_safe`, `qp_is_pushdown_safe` — gating flags. [verified-by-code]
  - `remote_conds`, `local_conds`, `final_remote_exprs` — qual partition.
  - `attrs_used` Bitmapset — which local cols must be projected from the remote scan.
  - Cost cache: `rows`, `width`, `startup_cost`, `total_cost`, plus `retrieved_rows`, `rel_startup_cost`, `rel_total_cost` (the latter triplet is the per-rel cache so `estimate_path_cost_size()` skips re-EXPLAINing) (lines 62-76). [verified-by-code]
  - Cached options: `use_remote_estimate`, `fdw_startup_cost`, `fdw_tuple_cost`, `shippable_extensions` (List of extension OIDs), `async_capable`, `fetch_size`.
  - Cached catalog handles: `ForeignTable *table`, `ForeignServer *server`, `UserMapping *user` (only set in `use_remote_estimate` mode — see line 88 comment). [from-comment]
  - Join scaffolding: `outerrel`, `innerrel`, `jointype`, `joinclauses`, `lower_subquery_rels`, `hidden_subquery_rels`, `make_outerrel_subquery`, `make_innerrel_subquery`.
  - Upper scaffolding: `stage` (UpperRelationKind), `grouped_tlist`.
  - `relation_name`, `relation_index` for EXPLAIN.
- `PgFdwConnState` struct (lines 137-140) — `AsyncRequest *pendingAreq` only. Lives inside each `ConnCacheEntry` (see `connection.c:75`). [verified-by-code]
- `PgFdwSamplingMethod` enum (lines 145-152) — ANALYZE_SAMPLE_OFF / AUTO / RANDOM / SYSTEM / BERNOULLI.
- From `postgres_fdw.c`:
  - `set_transmission_modes()` / `reset_transmission_modes()` — GUC stack wrapper to force `datestyle=ISO`, `intervalstyle=postgres`, `extra_float_digits=3`, `search_path=pg_catalog` for the duration of one deparse, restored on error via `AtEOXact_GUC` (`postgres_fdw.c:4108`, `:4144`). [verified-by-code]
  - `process_pending_request(AsyncRequest *areq)` — drain a pending async fetch before reusing the connection (`postgres_fdw.c:8373`).
- From `connection.c`:
  - `GetConnection(UserMapping *user, bool will_prep_stmt, PgFdwConnState **state)` — main hash-cache entry point (`connection.c:216`).
  - `ReleaseConnection(PGconn *conn)` — no-op (`connection.c:1020`). Reference counting is via `xact_depth`, not refcounts. [verified-by-code]
  - `GetCursorNumber`, `GetPrepStmtNumber` — monotonic per-backend counters (`connection.c:1042`, `:1056`).
  - `do_sql_command`, `pgfdw_exec_query`, `pgfdw_get_result` — libpq wrappers w/ wait-event integration.
  - `pgfdw_report_error` (`pg_noreturn`) / `pgfdw_report` — translate a remote `PGresult` into a local `ereport()` preserving SQLSTATE + primary/detail/hint/context, AND adding `errcontext("remote SQL command: %s", sql)` (`connection.c:1111`, `:1118`, `:1126`). [verified-by-code]
- From `option.c`:
  - `ExtractConnectionOptions(defelems, keywords, values)` — filters libpq-vs-FDW options.
  - `ExtractExtensionList(extensionsString, warnOnMissing)` — `extensions` server option → List of OIDs.
  - `process_pgfdw_appname(appname)` — `%a/%c/%C/%d/%p/%u` expansion for `postgres_fdw.application_name`.
  - `pgfdw_application_name` GUC.
- From `deparse.c`: `classifyConditions`, `is_foreign_expr`, `is_foreign_param`, `is_foreign_pathkey`, the family of `deparseInsertSql`/`deparseUpdateSql`/`deparseDeleteSql`/`deparseDirectUpdateSql`/`deparseDirectDeleteSql`/`deparseSelectStmtForRel`/`deparseTruncateSql`/`deparseAnalyzeSql`/`deparseAnalyzeSizeSql`/`deparseAnalyzeInfoSql`, plus `rebuildInsertSql` (batch INSERT), `deparseStringLiteral`, `find_em_for_rel`, `find_em_for_rel_target`, `build_tlist_to_deparse`, `get_jointype_name`.
- From `shippable.c`: `is_builtin(Oid)`, `is_shippable(Oid objectId, Oid classId, PgFdwRelationInfo *fpinfo)`.

## Key invariants

- INV-FDWPRIV-SHAPE: every postgres_fdw RelOptInfo (base, join, upper) has `fdw_private` pointing to a freshly `palloc0_object(PgFdwRelationInfo)`. Code reads `(PgFdwRelationInfo *) rel->fdw_private` unconditionally — null only before `GetForeignRelSize` runs. [verified-by-code at `postgres_fdw.c:852`]
- INV-FPINFO-USER-OPTIONAL: `fpinfo->user` is set ONLY when `use_remote_estimate=true` (lines 86-88 comment + `postgres_fdw.c:883-891`). Other code paths must NOT assume `user` is non-NULL during planning. [verified-by-code]
- INV-SHIPPABLE-EXTS-OID-LIST: `shippable_extensions` carries OIDs, not names. Resolution happens once at planning time (`ExtractExtensionList` calls `get_extension_oid`). If an extension is dropped & re-created mid-query, the cached OID becomes stale — but the connection-cache key would also flip on `pg_foreign_server` cache reset. [inferred]
- INV-CONNSTATE-PER-CONN: `PgFdwConnState` is reachable only via the `ConnCacheEntry.state` field. There is exactly one per cache key (umid). Multiple `PgFdwScanState` / `PgFdwModifyState` / `PgFdwDirectModifyState` instances share the same `PgFdwConnState`. [verified-by-code at `connection.c:75`]

## Notable internals

- The `PgFdwConnState.pendingAreq` field is the choke point for the entire async-execution interaction with the connection cache: only one async fetch may be in flight per cached connection at any moment. Every code path that issues a new query first calls `process_pending_request(state->pendingAreq)` to drain the previous one (see `postgres_fdw.c:300`, `:3953`, `:4313`, `:4740`). [verified-by-code]
- `relation_name` is computed twice: as the bare RT-index string at `GetForeignRelSize`, then rewritten to a human form at EXPLAIN time (see comment at lines 92-100; rewrite happens in `postgresExplainForeignScan`).
- `disabled_nodes` (line 65) is the modern "this path uses a disabled access method" propagation — the planner uses it to prefer non-disabled paths even when costs say otherwise.

## Cross-references

- `source/contrib/postgres_fdw/postgres_fdw.c` — uses every field of `PgFdwRelationInfo`.
- `source/contrib/postgres_fdw/connection.c` — `ConnCacheEntry` embeds `PgFdwConnState state` (line 75).
- `source/src/include/foreign/foreign.h` — `ForeignTable`, `ForeignServer`, `UserMapping` definitions referenced here.
- `source/src/include/foreign/fdwapi.h` — `FdwRoutine` interface that `postgres_fdw_handler` populates.
- A2 libpq sweep — every `PGconn *` here flows through libpq.
- `dblink/dblink.c` — same trust-class extension, parallel pattern.

<!-- issues:auto:begin -->
- [Issue register — `postgres_fdw`](../../../issues/postgres_fdw.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-api-shape: `PgFdwRelationInfo` has no version stamp; an extension subclassing/sharing this private struct (none exists today, but the header is installed in `pkg-include`) would silently break on PG upgrade. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.h:30`.
- [ISSUE-documentation: line 88 says `user` "only set in use_remote_estimate mode" but doesn't say what calling-code paths obey this contract. A grep of `postgres_fdw.c` shows every other place re-fetches via `GetUserMapping(...)` — but a reviewer adding a new use of `fpinfo->user` could easily NPE. (nit)] — `source/contrib/postgres_fdw/postgres_fdw.h:88`.
