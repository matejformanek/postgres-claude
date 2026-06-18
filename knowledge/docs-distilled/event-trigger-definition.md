---
source_url: https://www.postgresql.org/docs/current/event-trigger-definition.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Overview of Event Trigger Behavior (internals ch. 40.1)

The firing-matrix leaf: *which event fires when, for which command tags, and in
what order relative to the command.* The companion `event-trigger-interface.md`
covers the §40.4 C ABI; this is the §40.1 semantics. Pairs with
`idioms/event-trigger-firing.md`, `idioms/ddl-deparse-via-event-triggers.md`,
and `trigger-interface.md` (row triggers).

## The five events

- **`ddl_command_start`** — fires *just before* a DDL command executes.
  Command tags: `CREATE`, `ALTER`, `DROP`, `COMMENT`, `GRANT`, `REVOKE`,
  `IMPORT FOREIGN SCHEMA`, `REINDEX`, `REFRESH MATERIALIZED VIEW`,
  `SECURITY LABEL`. Also fires before `SELECT INTO` (it is equivalent to
  `CREATE TABLE AS`). **No existence check** of the target object is performed
  before it fires. [from-docs]
- **`ddl_command_end`** — fires *just after* the same set of commands, after the
  actions happened but **before COMMIT**, so the system catalogs read as already
  changed. Use `pg_event_trigger_ddl_commands()` (SRF) to enumerate what
  happened. [from-docs]
- **`sql_drop`** — fires *just before* the `ddl_command_end` trigger for any
  operation that drops objects. Triggered by the obvious `DROP` commands **and**
  by some `ALTER` commands. Enumerate the casualties with
  `pg_event_trigger_dropped_objects()` — but note the objects are already
  deleted from the catalogs, so you cannot look them up by OID anymore; the SRF
  is the only window. [from-docs]
- **`table_rewrite`** — fires *just before* a table is rewritten by some actions
  of `ALTER TABLE` and `ALTER TYPE`. **Not** triggered by `CLUSTER` or `VACUUM`
  even though they also rewrite. Use `pg_event_trigger_table_rewrite_oid()` for
  the table and `pg_event_trigger_table_rewrite_reason()` for the cause.
  [from-docs]
- **`login`** — fires when an authenticated user logs in; **also fires on standby
  servers.** Caveats below. [from-docs]

## Cross-cutting rules

- **Definition requires an `event_trigger`-typed function.** You must first
  `CREATE FUNCTION ... RETURNS event_trigger`; the function "need not (and may
  not) return a value" — the return type is purely a marker. Then
  `CREATE EVENT TRIGGER`. [from-docs]
- **Multiple triggers on one event fire in alphabetical order by trigger name.**
  [from-docs]
- **`WHEN` filter** lets a `ddl_command_start` trigger fire only for chosen
  command tags. [from-docs]
- **Shared/global objects are exempt.** `ddl_command_start` (and the rest) do
  *not* fire for DDL on shared objects: **databases, roles** (definitions and
  memberships), **tablespaces, parameter privileges, and `ALTER SYSTEM`.**
  [from-docs]
- **Event-trigger commands don't trigger themselves** — DDL targeting event
  triggers does not fire these events. [from-docs]
- **Aborted-transaction semantics:**
  - Event triggers cannot run in an aborted transaction.
  - If the DDL command errors, its `ddl_command_end` triggers do **not** run.
  - If a `ddl_command_start` trigger errors, no further event triggers fire and
    the command itself is never attempted.
  - If a `ddl_command_end` trigger errors, the DDL statement's effects are rolled
    back like any aborting transaction. [from-docs]

## `login`-event footguns

- A bug in a `login` trigger **can lock everyone out.** Workarounds: set
  `event_triggers = false` in a connection string or config file; or restart in
  **single-user mode** (event triggers are disabled there). [from-docs]
- On a **standby**, a `login` trigger must avoid writing to the database, or the
  server can become inaccessible. [from-docs]
- Avoid long-running queries in `login` triggers; **canceling the connection in
  psql will not cancel an in-progress `login` trigger.** [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/event-trigger-interface.md]] — §40.4 C ABI
  (EventTriggerData, the context struct).
- [[knowledge/idioms/event-trigger-firing.md]] — where in the DDL path these
  fire (EventTriggerDDLCommandStart/End, EventTriggerSQLDrop).
- [[knowledge/idioms/ddl-deparse-via-event-triggers.md]] — using
  `ddl_command_end` + `pg_event_trigger_ddl_commands()` for logical DDL capture.
- [[knowledge/files/src/backend/commands/event_trigger.c.md]] — implementation
  of the firing points and the SRFs named here.
- [[knowledge/idioms/trigger-during-error.md]] — the aborted-transaction rules
  echo row-trigger error handling.

## Open questions

- Exact `event_trigger.c` line ranges for the five firing points at anchor
  `ab3023ad1e68` (deferred to a per-file re-verify).
