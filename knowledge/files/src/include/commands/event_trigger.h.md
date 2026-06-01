# event_trigger.h

- **Source path:** `source/src/include/commands/event_trigger.h`
- **Lines:** 97
- **Last verified commit:** `ef6a95c7c64`

Public surface of event triggers. Defines `EventTriggerData` (the fmgr context for an event-trigger function: `event` name, `parsetree`, `tag`). Declares the firing entry points called from `ProcessUtility` and elsewhere: `EventTriggerDDLCommandStart/End`, `EventTriggerSQLDrop`, `EventTriggerTableRewrite`, `EventTriggerOnLogin`, plus the per-AT bookkeeping (`EventTriggerAlterTableStart`/`End`/`CollectAlterTableSubcmd`), `EventTriggerInhibitCommandCollection`, and SQL-callable helpers `pg_event_trigger_*`. Also `CALLED_AS_EVENT_TRIGGER` macro analogous to `CALLED_AS_TRIGGER`.
