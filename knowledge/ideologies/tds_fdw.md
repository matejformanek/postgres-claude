# tds_fdw (tds-fdw/tds_fdw) — a textbook read-only FdwRoutine over FreeTDS (Sybase / MS SQL Server)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tds-fdw/tds_fdw` @ branch `master`. ~428★, language **C**. All
> `file:line` cites below point into that repo (cited as `src/tds_fdw.c:NN`
> etc.), not `source/`, since this doc characterizes an *external* extension.
> Cites verified against the files fetched on 2026-06-17 (see Sources footer).
> Backend target: Sybase ASE and Microsoft SQL Server, reached over the Tabular
> Data Stream (TDS) protocol via a DB-Library implementation, in practice
> **FreeTDS** (`tds_fdw.control:10-15` `[from-comment]`).

This is the **low-divergence foil** in the FDW corpus. Where
`[[knowledge/ideologies/wrappers]]` re-expresses the whole FDW C API as a
safe-Rust trait + a runtime WASM loader, tds_fdw does the boring, correct
thing: it `makeNode(FdwRoutine)`, fills a callback set, and marshals rows into
`TupleTableSlot`s the way `contrib/file_fdw` and `contrib/postgres_fdw` do. Its
value to the corpus is as a *concrete reference* for "what a conformant FDW
actually looks like," and as a measuring stick for the API-abuse extensions.

## Domain & purpose

tds_fdw makes a Sybase/MSSQL table (or an arbitrary remote `query`) appear as a
PostgreSQL foreign table. "The current version does not yet support JOIN
push-down, or write operations. It does support WHERE and column pushdowns when
*match_column_names* is enabled" (`README.md:23-25` `[from-README]`). So it is a
**read-only, single-relation** FDW: `SELECT` from a foreign table issues a
remote TDS query, streams rows back through FreeTDS's db-lib, and reconstructs
each as a heap tuple. It targets PostgreSQL 9.2+ and carries a thick lattice of
`PG_VERSION_NUM` guards to span that range (`include/tds_fdw.h:35-178`
`[verified-by-code]`).

## How it hooks into PG

Standard `CREATE FOREIGN DATA WRAPPER ... HANDLER tds_fdw_handler VALIDATOR
tds_fdw_validator` wiring. Both entry points are declared
`PG_FUNCTION_INFO_V1` (`src/tds_fdw.c:155-156` `[verified-by-code]`), exactly
the `[[knowledge/idioms/fmgr]]` handler pattern: the handler `palloc`s a
`makeNode(FdwRoutine)` and returns it (`src/tds_fdw.c:160` `[verified-by-code]`),
which is precisely what `[[knowledge/subsystems/foreign]]` describes as "the
FDW's handler function ... returns a `palloc`'d, `makeNode(FdwRoutine)`-init'd
struct."

The callback set it installs (`src/tds_fdw.c:169-185` `[verified-by-code]`):

- **Planning:** `GetForeignRelSize` → `tdsGetForeignRelSize`, `GetForeignPaths`
  → `tdsGetForeignPaths`, `GetForeignPlan` → `tdsGetForeignPlan`,
  `AnalyzeForeignTable` → `tdsAnalyzeForeignTable`. (Pre-9.2 it falls back to
  the legacy `PlanForeignScan` → `tdsPlanForeignScan`, `:174`.)
- **Execution:** `ExplainForeignScan`, `BeginForeignScan`, `IterateForeignScan`,
  `ReScanForeignScan`, `EndForeignScan` → the `tds*ForeignScan` functions.
- **DDL:** `ImportForeignSchema` → `tdsImportForeignSchema`, compiled in only
  on PG ≥ 9.5 via the `IMPORT_API` guard (`src/tds_fdw.c:183-185`,
  `include/tds_fdw.h:47-51` `[verified-by-code]`).

The **options validator** is a textbook `valid_options[]` table keyed by
catalog `Relation` OID — `ForeignServerRelationId` (servername, port, database,
tds_version, use_remote_estimate, fdw_startup_cost, …), `UserMappingRelationId`
(username, password), and `ForeignTableRelationId` (query, table, schema_name,
match_column_names, …) (`src/options.c:53-75` `[verified-by-code]`), and
`tdsValidateOptions` dispatches on the passed `context` OID
(`src/options.c:142-165` `[verified-by-code]`). This is the same shape file_fdw
and postgres_fdw use (see `[[knowledge/subsystems/contrib-postgres_fdw]]`,
`[[knowledge/subsystems/contrib-file_fdw]]`).

## Where it conforms to / diverges from core idioms

Framed as the "conformant FDW" reference:

### Callbacks: scan-only, leaning on core defaults for everything else

It implements the full **scan** lifecycle plus `ImportForeignSchema` and
`AnalyzeForeignTable`, and **deliberately omits** the modify/direct-modify
callbacks (`AddForeignUpdateTargets`, `PlanForeignModify`, `BeginForeignModify`,
`ExecForeignInsert/Update/Delete`, `EndForeignModify`,
`PlanDirectModify`/`IterateDirectModify`), the JOIN/UPPER-rel pushdown hooks
(`GetForeignJoinPaths`, `GetForeignUpperPaths`), and the async/batch hooks. The
handler simply never sets those fields, so core treats the table as read-only
and never attempts a foreign modify — the README's "no write operations" is
enforced structurally by an absent callback, not a runtime error
(`src/tds_fdw.c:169-185` `[verified-by-code]`; `README.md:23` `[from-README]`).

### Qual pushdown: a near-verbatim port of postgres_fdw's `deparse.c`

`src/deparse.c` is not bespoke — it is postgres_fdw's deparser adapted to TDS
SQL. It carries the identical `classifyConditions` split into
`remote_conds`/`local_conds` (`src/deparse.c:202-224` `[verified-by-code]`),
the same `is_foreign_expr` driven by a `foreign_expr_walker` with the
`FDW_COLLATE_NONE/UNSAFE` collation state machine (`src/deparse.c:262-289`
`[verified-by-code]`), and a `TdsFdwRelationInfo` that the header openly notes
"is similar to PgFdwRelationInfo from postgres_fdw" (`include/tds_fdw.h:74-105`
`[verified-by-code]`). Pushdown scope is conservative: `is_shippable` ships an
operator only if it lives in `pg_catalog` (`oprnamespace ==
PG_CATALOG_NAMESPACE`) and ships nothing else custom (`src/deparse.c:232-257`
`[verified-by-code]`) — the header even comments out the
`shippable_extensions` whitelist that postgres_fdw grew, with "tds_fdw won't
ship any PostgreSQL extensions" (`include/tds_fdw.h:98-99` `[verified-by-code]`).

### No JOIN or aggregate pushdown

It registers neither `GetForeignJoinPaths` nor `GetForeignUpperPaths`, so joins
and aggregates are always executed locally over the streamed rows. The README
states JOIN push-down is unsupported (`README.md:23` `[from-README]`), and the
absence is also visible in the handler's field set (`src/tds_fdw.c:169-185`
`[verified-by-code]`). This is the single sharpest contrast with
postgres_fdw, which does both.

### Connection lifecycle: per-scan, NOT pooled — diverges from postgres_fdw

postgres_fdw caches libpq connections in a hash keyed by user mapping and
reuses them across the session. tds_fdw does **not**: each scan opens and tears
down its own db-lib connection. `tdsBeginForeignScan` calls `dbinit()` then
`tdsSetupConnection` → `dbopen()` (`src/tds_fdw.c:1448`, `:1491`, `:703`
`[verified-by-code]`), and `tdsEndForeignScan` calls `dbclose()`,
`dbloginfree()`, and `dbexit()` (`src/tds_fdw.c:2145-2157` `[verified-by-code]`).
The same open/close bracket recurs independently in `AnalyzeForeignTable` and
the row-estimate path (`src/tds_fdw.c:2264-2343`, `:4140-4203`
`[verified-by-code]`). The FreeTDS `LOGINREC`/`DBPROCESS` are raw db-lib handles
freed by explicit db-lib calls, *outside* PG's `MemoryContext` discipline — the
FDW owns that teardown by hand in `EndForeignScan`. PG-managed memory is scoped
the idiomatic way: a per-scan `AllocSetContextCreate` child of
`estate->es_query_cxt` (`src/tds_fdw.c:1506` `[verified-by-code]`,
`[[knowledge/idioms/memory-contexts]]`).

### Row materialization: the textbook slot path

`tdsIterateForeignScan` does exactly what `[[knowledge/idioms/fdw-iterate-scan]]`
prescribes: `ExecClearTuple(slot)` up front (`src/tds_fdw.c:1717`), `dbnextrow`
to pull the next TDS row (`src/tds_fdw.c:1901` `[verified-by-code]`), per-column
either a raw `dbbind` fast path for type-matched columns
(`src/tds_fdw.c:1851-1876` `[verified-by-code]`) or a generic
`tdsConvertToCString` → `InputFunctionCall` conversion through `AttInMetadata`
(`src/tds_fdw.c:2019-2023` `[verified-by-code]`), then `heap_form_tuple` +
`ExecStoreHeapTuple` (`ExecStoreTuple` pre-PG12) to land the tuple in the slot
(`src/tds_fdw.c:2034-2039` `[verified-by-code]`). Errors are reported with the
correct FDW SQLSTATEs (`ERRCODE_FDW_UNABLE_TO_CREATE_EXECUTION`,
`ERRCODE_FDW_OUT_OF_MEMORY`, `src/tds_fdw.c:1880-2052` `[verified-by-code]`,
`[[knowledge/idioms/error-handling]]`).

## Notable design decisions (cited)

- **Read-only by omission.** No modify callbacks are ever assigned; "no write
  operations" is structural, not a guard (`src/tds_fdw.c:169-185`,
  `README.md:23` `[verified-by-code]`/`[from-README]`).
- **deparse.c is postgres_fdw's, lightly retargeted.** Reusing the proven
  `foreign_expr_walker`/collation machinery rather than reinventing pushdown
  safety (`src/deparse.c:202-289` `[verified-by-code]`) — a sober choice that
  avoids the "confident-but-wrong pushdown" failure mode.
- **Three row-estimate strategies** selected by the `row_estimate_method`
  option, defaulting to `"execute"`: `tdsGetRowCount`,
  `tdsGetRowCountShowPlanAll`, `tdsGetRowCountExecute`
  (`include/tds_fdw.h:189-191`; default `src/options.c:116`
  `[verified-by-code]`). With `use_remote_estimate` on (default,
  `src/options.c:128`), it actually round-trips to the remote server to size a
  scan — the postgres_fdw `EXPLAIN`-style costing idea, adapted to TDS.
- **`match_column_names` toggles name- vs ordinal-position binding**, default on
  (`src/options.c:122-124` `[verified-by-code]`); column pushdown only happens
  in name-match mode (`README.md:25` `[from-README]`).
- **Raw `dbbind` fast paths for matched types** (int2/4/8, float4/8, text,
  bytea, timestamp) skip the cstring→InputFunctionCall round trip
  (`src/tds_fdw.c:1851-1876` `[verified-by-code]`) — a small per-row
  optimization core FDWs don't get for free.
- **`pqsignal(SIGINT, tds_signal_handler)` installed inside the handler**
  (`src/tds_fdw.c:187` `[verified-by-code]`) so a long-running db-lib call can be
  cancelled; the signal handler is uninstalled once `dbopen()` completes
  (`src/tds_fdw.c:745` `[from-comment]`). Hand-rolled cancellation around a
  blocking third-party library call is a wrinkle core's libpq-based
  postgres_fdw handles differently.

## Links into corpus

- `[[knowledge/subsystems/foreign]]` — the `FdwRoutine` dispatch + catalog
  accessors this extension plugs into; the single most important cross-ref.
- `[[knowledge/subsystems/contrib-postgres_fdw]]` — the upstream FDW tds_fdw's
  `deparse.c` and `TdsFdwRelationInfo` are ported from; the direct comparison
  (tds_fdw = postgres_fdw minus JOIN/agg pushdown, modify, and connection
  caching).
- `[[knowledge/subsystems/contrib-file_fdw]]` — the other "textbook FDW"; same
  `valid_options[]`-by-catalog-OID validator shape.
- `[[knowledge/idioms/fdw-routine-callbacks]]` + `[[knowledge/idioms/fdw-iterate-scan]]`
  — the callback set and the `ExecClearTuple`/`heap_form_tuple`/`ExecStoreHeapTuple`
  scan loop this extension follows almost verbatim.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` handler/validator
  plumbing.
- `[[knowledge/idioms/memory-contexts]]` — the per-scan `AllocSetContextCreate`
  child of `es_query_cxt`, and the contrast with hand-freed db-lib handles.
- `[[knowledge/idioms/error-handling]]` — the `ERRCODE_FDW_*` SQLSTATE usage.
- `[[knowledge/ideologies/wrappers]]` — the high-divergence Rust FDW *framework*
  (trait + runtime WASM loader); tds_fdw is the conformant-C foil to it, and to
  `[[knowledge/ideologies/cstore_fdw]]` (FDW-as-storage).

## Sources

Fetched 2026-06-17 (branch `master`), all via
`https://raw.githubusercontent.com/tds-fdw/tds_fdw/master/<path>`:

- `README.md` @ 2026-06-17T00:00Z → HTTP 200 (135 lines).
- `tds_fdw.control` @ 2026-06-17T00:00Z → HTTP 200 (21 lines).
- `include/tds_fdw.h` @ 2026-06-17T00:00Z → HTTP 200 (205 lines;
  `TdsFdwRelationInfo`, `TdsFdwExecutionState`, callback decls).
- `include/deparse.h` @ 2026-06-17T00:00Z → HTTP 200 (157 lines).
- `src/tds_fdw.c` @ 2026-06-17T00:00Z → HTTP 200 (4334 lines; the FdwRoutine +
  scan lifecycle + connection setup/teardown).
- `src/deparse.c` @ 2026-06-17T00:00Z → HTTP 200 (2069 lines; classifyConditions /
  is_foreign_expr / is_shippable — ported from postgres_fdw).
- `src/options.c` @ 2026-06-17T00:00Z → HTTP 200 (1071 lines; valid_options table,
  defaults, tdsValidateOptions).

No 404 gaps — all seven requested paths returned HTTP 200. Not deep-read:
`tdsImportForeignSchema` body, the `tdsConvertToCString` type-conversion table,
the db-lib message/error handlers, and the per-version compatibility shims
beyond the cited guards.
