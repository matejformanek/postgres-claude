# tcopprot.h

- **Source:** `source/src/include/tcop/tcopprot.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## What's here

Public prototypes for `tcop/postgres.c`.

- Globals: `whereToSendOutput`, `debug_query_string`, `PostAuthDelay`,
  `client_connection_check_interval`, `Log_disconnections`,
  `log_statement`, `restrict_nonsystem_relation_kind`.
- `LogStmtLevel` enum (NONE / DDL / MOD / ALL).
- Parse / analyze / rewrite / plan helpers (the "pg_*" wrappers around
  the corresponding modules):
  - `pg_parse_query`
  - `pg_rewrite_query`
  - `pg_analyze_and_rewrite_fixedparams` / `_varparams` / `_withcb`
  - `pg_plan_query`, `pg_plan_queries`
- Signal handlers: `die`, `quickdie`, `StatementCancelHandler`,
  `FloatExceptionHandler`, `HandleRecoveryConflictInterrupt`,
  `ProcessClientReadInterrupt`, `ProcessClientWriteInterrupt`.
- `process_postgres_switches` — shared with PostmasterMain for `-c` option
  parsing.
- `PostgresSingleUserMain(argc, argv, username)` — `postgres --single`
  entry.
- **`PostgresMain(dbname, username)`** — the per-backend main loop entry.

`InitPostgres` lives in `utils/init/postinit.c`; its prototype is in
`miscadmin.h` (not here).
