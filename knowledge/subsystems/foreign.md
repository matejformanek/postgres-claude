# foreign (FDW dispatch + catalog accessors)

- **Source path:** `source/src/backend/foreign/`
- **Header path:** `source/src/include/foreign/`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchor:** none in source; user docs are `doc/src/sgml/fdwhandler.sgml`.

## 1. Purpose

Catalog accessors and the `FdwRoutine` dispatch table that connect a
foreign table to its FDW implementation. Tiny subsystem — one `.c`
file (`foreign.c`) and two headers (`foreign.h`, `fdwapi.h`). The
actual FDW logic (postgres_fdw, file_fdw) lives in
`contrib/`; this file is just the trampoline.

## 2. Mental model

- **Three catalog rows make an FDW callable.**
  - `pg_foreign_data_wrapper` row (`ForeignDataWrapper`): name +
    handler function OID + validator function OID + connection
    function OID + options.
  - `pg_foreign_server` row (`ForeignServer`): name + FDW OID +
    options.
  - `pg_foreign_table` row (`ForeignTable`): table OID + server OID
    + options.
  - Optional `pg_user_mapping` row (`UserMapping`): per-user
    options (typically credentials).
- **The `FdwRoutine` struct is the API surface.** It's a 30+ field
  struct of callbacks (`fdwapi.h:208-286` [verified-by-code]), got by
  calling the FDW's *handler function* via the fmgr — the handler
  returns a `palloc`'d, `makeNode(FdwRoutine)`-initialized struct.
- **Two ways to obtain it.** `GetFdwRoutineByRelId(relid)` for one-off
  use; `GetFdwRoutineForRelation(rel, makecopy)` for relcache-cached
  reuse ([verified-by-code] `foreign.c:473-504`).
- **Options are name/value DefElem lists.** Pulled out of the
  catalog via `untransformRelOptions` and passed to FDW callbacks.

## 3. Key files

- `foreign.c` (~22 KB) — every accessor and the FDW dispatch.
- `src/include/foreign/foreign.h` — `ForeignDataWrapper`,
  `ForeignServer`, `UserMapping`, `ForeignTable` structs (89 lines).
- `src/include/foreign/fdwapi.h` — typedefs for every callback +
  the `FdwRoutine` struct (299 lines, [verified-by-code]).

## 4. Key data structures

- **`ForeignDataWrapper`** (`foreign.h:24-33`). Fields `fdwid`,
  `owner`, `fdwname`, `fdwhandler`, `fdwvalidator`, `fdwconnection`,
  `options`.
- **`ForeignServer`** (`foreign.h:35-44`). `serverid`, `fdwid`,
  `owner`, `servername`, `servertype`, `serverversion`, `options`.
- **`UserMapping`** (`foreign.h:46-52`). `umid`, `userid`,
  `serverid`, `options`. `userid == InvalidOid` means PUBLIC mapping
  (the fallback when no per-user mapping is found —
  [verified-by-code] `foreign.c:231-279`).
- **`ForeignTable`** (`foreign.h:54-59`). `relid`, `serverid`,
  `options`.
- **`FdwRoutine`** (`fdwapi.h:208-286`). The big vtable. Sections:
  - **Mandatory scan**: `GetForeignRelSize`, `GetForeignPaths`,
    `GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`,
    `ReScanForeignScan`, `EndForeignScan`.
  - **Remote join planning**: `GetForeignJoinPaths`.
  - **Upper-relation planning** (agg pushdown etc.):
    `GetForeignUpperPaths`.
  - **DML**: `AddForeignUpdateTargets`, `PlanForeignModify`,
    `BeginForeignModify`, `ExecForeignInsert`,
    `ExecForeignBatchInsert`, `GetForeignModifyBatchSize`,
    `ExecForeignUpdate`, `ExecForeignDelete`, `EndForeignModify`,
    `BeginForeignInsert`, `EndForeignInsert`,
    `IsForeignRelUpdatable`, plus the **direct-modify**
    optimization path (`PlanDirectModify`, `BeginDirectModify`,
    `IterateDirectModify`, `EndDirectModify`).
  - **Row locking / EPQ**: `GetForeignRowMarkType`,
    `RefetchForeignRow`, `RecheckForeignScan`.
  - **EXPLAIN**: `ExplainForeignScan`, `ExplainForeignModify`,
    `ExplainDirectModify`.
  - **ANALYZE**: `AnalyzeForeignTable`, `ImportForeignStatistics`.
  - **IMPORT FOREIGN SCHEMA**: `ImportForeignSchema`.
  - **TRUNCATE**: `ExecForeignTruncate`.
  - **Parallel under Gather**:
    `IsForeignScanParallelSafe`, `EstimateDSMForeignScan`,
    `InitializeDSMForeignScan`, `ReInitializeDSMForeignScan`,
    `InitializeWorkerForeignScan`, `ShutdownForeignScan`.
  - **Path reparameterization**:
    `ReparameterizeForeignPathByChild`.
  - **Async exec**: `IsForeignPathAsyncCapable`,
    `ForeignAsyncRequest`, `ForeignAsyncConfigureWait`,
    `ForeignAsyncNotify`.

## 5. Control flow — the common paths

### 5.1 Planner asks "what FDW handles this table?"
`GetFdwRoutineForRelation(rel, makecopy)` [verified-by-code]
`foreign.c:473-504`:
1. If `rel->rd_fdwroutine` is already set in relcache → return it
   (or a palloc'd copy if `makecopy`).
2. Otherwise: `GetFdwRoutineByRelId(relid)`:
   - `GetForeignServerIdByRelId(relid)` → catalog lookup
     `pg_foreign_table.ftserver`.
   - `GetFdwRoutineByServerId(serverid)`:
     - Look up `pg_foreign_server` to get `srvfdw`.
     - Look up `pg_foreign_data_wrapper` to get `fdwhandler`.
     - If `fdwhandler` is `InvalidOid` → `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` ("FDW has no handler"). ([verified-by-code] `foreign.c:432-437`).
     - `GetFdwRoutine(fdwhandler)`:
       - **Security gate**: if `restrict_nonsystem_relation_kind &
         RESTRICT_RELKIND_FOREIGN_TABLE`, ERROR
         ([verified-by-code] `foreign.c:362-369`). Used by
         `pg_dump --restrict` to block FDW exec.
       - `OidFunctionCall0(fdwhandler)` → datum.
       - Cast + `IsA(routine, FdwRoutine)` check, else `elog(ERROR)`.
3. Cache into `relation->rd_fdwroutine` (`CacheMemoryContext`).

### 5.2 User mapping lookup with PUBLIC fallback
`GetUserMapping(userid, serverid)` [verified-by-code]
`foreign.c:231-279`:
1. `SearchSysCache2(USERMAPPINGUSERSERVER, userid, serverid)`.
2. If miss, try again with `userid = InvalidOid` (PUBLIC).
3. If still miss → `ereport(ERROR)` "user mapping not found".

### 5.3 Connection-string materialization
`ForeignServerConnectionString(userid, server)` [verified-by-code]
`foreign.c:201-222`:
1. Resolve the FDW.
2. `OidFunctionCall3(fdw->fdwconnection, userid, serverid, NULL)` —
   the FDW's own function builds the connection string.
3. If the FDW has no `fdwconnection` function →
   `ERRCODE_FEATURE_NOT_SUPPORTED`. Used by logical-replication
   subscriptions that want to reuse a server definition.

### 5.4 IMPORT FOREIGN SCHEMA filter
`IsImportableForeignTable(tablename, stmt)` [verified-by-code]
`foreign.c:513-545`:
- Switch on `stmt->list_type` of {`FDW_IMPORT_SCHEMA_ALL`,
  `LIMIT_TO`, `EXCEPT`}.

### 5.5 EPQ alternate-local-join path
`GetExistingLocalJoinPath(joinrel)` [verified-by-code]
`foreign.c:772-891` — picks an unparameterized {HashJoin, NestLoop,
MergeJoin} path from `joinrel->pathlist`, shallow-copies it, and if
either child is a `ForeignPath` for a pushed-down join, swaps it for
`foreign_path->fdw_outerpath`. Result is a fully-local plan to use
for `EvalPlanQual` rechecks.

## 6. Locking and invariants

- Strings/lists palloc'd by `GetForeign*` end up in
  `CurrentMemoryContext` (or `CacheMemoryContext` for the cached
  copy in `rd_fdwroutine`).
- `rd_fdwroutine` survives relcache invalidations only as long as
  the relcache entry itself does — caller "shouldn't rely on it
  long" ([from-comment] `foreign.c:467-471`).
- `restrict_nonsystem_relation_kind & RESTRICT_RELKIND_FOREIGN_TABLE`
  is consulted *only* in `GetFdwRoutine`. This is the single
  choke point that `pg_dump --restrict-key` relies on.
- The `FdwRoutine` returned by a handler must satisfy
  `IsA(routine, FdwRoutine)` — handlers are expected to use
  `makeNode(FdwRoutine)` for forward-compat as new callbacks are
  added ([from-comment] `fdwapi.h:198-207`).
- `postgresql_fdw_validator` is **deprecated** — kept only for
  test purposes because its option list isn't kept in sync with
  any real libpq ([from-comment] `foreign.c:644-655`).

## 7. Interactions with other subsystems

- **utils/cache/syscache.c** — every accessor here is just
  `SearchSysCache1/2`.
- **utils/cache/relcache.c** — `rd_fdwroutine` cache slot.
- **executor / planner** — every callback in `FdwRoutine` is invoked
  from there; this file is just a name-resolution layer.
- **commands/foreigncmds.c** — CREATE/ALTER FOREIGN {SERVER, TABLE,
  DATA WRAPPER, USER MAPPING}.
- **contrib/postgres_fdw**, **contrib/file_fdw** — actual FDW impls
  consumed via these accessors.

## 8. Tests

- `src/test/regress/sql/foreign_data.sql` — catalog/DDL behavior.
- `contrib/postgres_fdw/sql/postgres_fdw.sql` — end-to-end FDW
  behavior (queries, joins, DML, EPQ).

## 9. Open questions / unverified claims

- `restrict_nonsystem_relation_kind` is referenced but its definition
  lives elsewhere; the actual bit values not double-checked here.
- `GetExistingLocalJoinPath`'s interaction with
  `merge_path->outer_presorted_keys` / `pathkeys_count_contained_in`
  — read but not deeply traced into the planner.

## 10. Glossary

- **FDW** — Foreign Data Wrapper.
- **Handler function** — SQL function that returns an `FdwRoutine`
  via fmgr. Catalogued as `pg_foreign_data_wrapper.fdwhandler`.
- **Validator function** — optional SQL function that ALTER/CREATE
  invokes to validate options for an FDW/server/UM.
- **Connection function** — optional SQL function that materializes
  a libpq-style connection string for the server (used by logical
  replication subscriptions).
- **User mapping (UM)** — per-(user, server) pair of options, usually
  the credentials. PUBLIC mapping uses `userid = InvalidOid` as
  a fallback.
- **Direct modify** — optimization where INSERT/UPDATE/DELETE bypass
  the executor's per-row callbacks and let the FDW push the whole
  DML to the remote side.
- **EPQ** — `EvalPlanQual`, the row-recheck used after a concurrent
  update; FDWs must supply an alternate-local-plan path.
- **Upper relation** — planner term for post-scan/join layers (agg,
  window). `GetForeignUpperPaths` is the pushdown hook for those.
