# prepare.h

- **Source path:** `source/src/include/commands/prepare.h`
- **Lines:** 62
- **Last verified commit:** `ef6a95c7c64`

Defines `PreparedStatement` (dynahash entry: name + `CachedPlanSource*` + creation timestamp + xact flag). Prototypes: `PrepareQuery`, `ExecuteQuery`, `DeallocateQuery`, `DeallocateAllQuery`, `StorePreparedStatement`, `FetchPreparedStatement`, `FetchPreparedStatementResultDesc`, `DropPreparedStatement`, `DropAllPreparedStatements`, `ExplainExecuteQuery`.
