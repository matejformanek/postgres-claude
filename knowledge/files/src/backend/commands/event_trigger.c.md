# event_trigger.c

- **Source path:** `source/src/backend/commands/event_trigger.c`
- **Lines:** 2424
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"PostgreSQL EVENT TRIGGER support code." [from-comment, event_trigger.c:3-4] DDL-level triggers that fire on `ddl_command_start`, `ddl_command_end`, `table_rewrite`, `sql_drop`, and `login` events.

## Public surface

- `CreateEventTrigger`, `AlterEventTrigger`, `RemoveEventTriggerById` — DDL.
- `EventTriggerDDLCommandStart`, `EventTriggerDDLCommandEnd`, `EventTriggerSQLDrop`, `EventTriggerTableRewrite`, `EventTriggerOnLogin` — **firing entry points** called from `ProcessUtility`, AlterTable's rewrite hook, and InitPostgres.
- `EventTriggerAlterTableStart` / `EventTriggerAlterTableEnd` / `EventTriggerCollectAlterTableSubcmd` / `EventTriggerCollectSimpleCommand` / `EventTriggerCollectGrant` / etc. — accumulate the "command stash" that user functions retrieve via `pg_event_trigger_ddl_commands()` and `pg_event_trigger_dropped_objects()`.
- `pg_event_trigger_ddl_commands`, `pg_event_trigger_dropped_objects`, `pg_event_trigger_table_rewrite_oid`, `pg_event_trigger_table_rewrite_reason` — SQL-callable functions that read the per-event stash.

## Login event triggers (PG 17+)

The `login` event fires once per backend after authentication, inside the connection-startup xact. Use case: enforce session-level GUCs based on role. There's a special catalog flag `pg_database.dathasloginevt` to avoid the per-login pg_event_trigger scan when no login triggers exist anywhere.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
