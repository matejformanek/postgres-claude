# Event trigger firing — SQL-level DDL hooks

PostgreSQL event triggers are SQL-callable functions that fire
on DDL events: `ddl_command_start`, `ddl_command_end`,
`sql_drop`, `table_rewrite`, and `login` (PG17+). Unlike row-
level triggers (which fire on data changes), event triggers
fire on **schema** changes. The C-side dispatcher
(`EventTriggerDDLCommandStart` and friends in
`commands/event_trigger.c`) walks `pg_event_trigger`, filters by
command tag, and calls the registered PL/pgSQL / C function.

Anchors:
- `source/src/backend/commands/event_trigger.c:727` —
  EventTriggerDDLCommandStart [verified-by-code]
- `source/src/backend/commands/event_trigger.c:778` —
  EventTriggerDDLCommandEnd [verified-by-code]
- `source/src/backend/commands/event_trigger.c:826` —
  EventTriggerSQLDrop [verified-by-code]
- `source/src/backend/commands/event_trigger.c:1013` —
  EventTriggerTableRewrite [verified-by-code]
- `knowledge/idioms/process-utility-hook-chain.md` — companion
- `knowledge/idioms/ddl-deparse-via-event-triggers.md` —
  companion
- `.claude/skills/extension-development/SKILL.md` — companion

## The 5 event types

| Event | When it fires |
|---|---|
| `ddl_command_start` | Before a DDL command's action |
| `ddl_command_end` | After a DDL command's action (catalog rows committed) |
| `sql_drop` | When objects are dropped (during DROP / ALTER ... DROP) |
| `table_rewrite` | Before VACUUM FULL / CLUSTER / certain ALTER TABLE |
| `login` (PG17+) | Once per session at backend start |

Each has its own dispatcher function.

## EventTriggerDDLCommandStart

[verified-by-code `event_trigger.c:727`]

```c
void
EventTriggerDDLCommandStart(Node *parsetree);
```

Called early in `ProcessUtilitySlow` (per `process-utility-
hook-chain`):
1. Identify the command tag (CREATE TABLE, ALTER TYPE, etc.).
2. Walk `pg_event_trigger` for `start` events matching the
   tag (or matching any if tags is empty).
3. For each match, fire the registered function with
   `EventTriggerData` in the context.
4. The function can raise an exception to abort the DDL.

Firing happens in a SECURITY DEFINER context if the function
is so declared.

## EventTriggerDDLCommandEnd

[verified-by-code `event_trigger.c:778`]

Same pattern but fires AFTER the command succeeds. The
catalogs are committed (catalog OIDs assigned). Functions can:
- Read `pg_event_trigger_ddl_commands()` for the list of
  affected objects.
- Walk the DDL parsetree (via `pg_event_trigger_get_creation_commands`).
- React to schema-level changes (e.g., propagate to a logical
  rep stream).

## EventTriggerSQLDrop

[verified-by-code `event_trigger.c:826`]

Fires when objects are about to be dropped. Function can call
`pg_event_trigger_dropped_objects()` to get each affected
object (name, schema, OID, type — table, function, type, ...).

Common use: cascading custom action on DROP (e.g., a custom
audit table tracking lifecycle).

## EventTriggerTableRewrite

[verified-by-code `event_trigger.c:1013`]

Fires when a command rewrites the entire table:
- `VACUUM FULL`
- `CLUSTER`
- `ALTER TABLE SET TABLESPACE`
- `ALTER TABLE ALTER COLUMN ... TYPE` (when type-change forces
  rewrite)

Function receives reason via `pg_event_trigger_table_rewrite_reason()`
+ table OID via `pg_event_trigger_table_rewrite_oid()`.

## EventTriggerData — the function-context shape

```c
typedef struct EventTriggerData
{
    NodeTag      type;
    const char  *event;       /* "ddl_command_start" etc. */
    Node        *parsetree;    /* parse tree of the command */
    CommandTag   tag;          /* CMDTAG_CREATE_TABLE etc. */
} EventTriggerData;
```

The event-trigger function consults `fcinfo->context` for this
struct. From SQL via PL/pgSQL: `TG_EVENT`, `TG_TAG` variables
expose the same info.

## Event trigger registration

```sql
CREATE EVENT TRIGGER name
    ON ddl_command_start
    [WHEN TAG IN ('CREATE TABLE', 'DROP TABLE')]
    EXECUTE FUNCTION my_func();
```

`WHEN TAG` filters by command tag (matched against
`tag_supported_by_command_tag` table). Without it, fires on
ALL events of that type.

Stored in `pg_event_trigger` catalog. Multiple triggers fire
in alphabetical order by trigger name.

## Restrictions

[from-comment in event_trigger.c]

- Some commands are NOT triggered: `CREATE EXTENSION`,
  `DROP EXTENSION` partially handled, server-startup
  internal DDL.
- Login event has different rules — fires at session start
  before any other event-trigger event.
- Event triggers fire ONLY at top-level DDL — nested ones
  (e.g., DDL inside a PL/pgSQL function) DO fire.

## How extensions use this

[per `extension-development`]

```c
CREATE EXTENSION audit;
-- In _PG_init:
CREATE EVENT TRIGGER audit_ddl_start
    ON ddl_command_start
    EXECUTE FUNCTION audit.log_ddl();
```

The extension's `--1.0.sql` script can include `CREATE EVENT
TRIGGER` statements. The PL/pgSQL function (or C function via
`CREATE FUNCTION audit.log_ddl() LANGUAGE C AS 'audit.so',
'audit_log_ddl';`) runs on every matching event.

## The supported-command-tags table

```c
/* in src/backend/commands/event_trigger.c */
static event_trigger_support_data event_trigger_support[] = {
    {"ACCESS METHOD", true},
    {"AGGREGATE", true},
    {"ALTER TABLE", true},
    /* ... */
};
```

Lists every command tag that event triggers can match. Adding
a new utility command requires registering it here, or event
triggers won't catch it.

## Common review-time concerns

- **Event triggers run inside the DDL transaction** — failure
  rolls back the whole DDL.
- **Don't issue DDL from inside event triggers** — easy
  recursion.
- **TAG filter is exact match** — no wildcards.
- **Adding a new utility command** requires
  `event_trigger_support` entry.
- **EventTriggerData is the function context** — don't
  poke at it via direct member access; use accessor
  functions.
- **sql_drop fires per-object**, not per-statement —
  multiple invocations per DROP CASCADE.

## Invariants

- **[INV-1]** 5 event types: ddl_command_start /
  ddl_command_end / sql_drop / table_rewrite / login.
- **[INV-2]** Triggers fire in alphabetical order by name.
- **[INV-3]** Event-trigger function runs inside the DDL
  txn; ERROR rolls back DDL.
- **[INV-4]** Tag filtering is exact match.
- **[INV-5]** Some internal DDL (catalog bootstrap, EXTENSION
  internals) bypasses event triggers.

## Useful greps

- The dispatchers:
  `grep -n 'EventTriggerDDLCommand\|EventTriggerSQLDrop\|EventTriggerTableRewrite' source/src/backend/commands/event_trigger.c | head -10`
- Supported tags:
  `grep -n 'event_trigger_support\|EventTriggerSupportTag' source/src/backend/commands/event_trigger.c | head -10`
- Catalog:
  `grep -n 'pg_event_trigger' source/src/include/catalog/pg_event_trigger.h | head -5`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/event_trigger.c`](../files/src/backend/commands/event_trigger.c.md) | 727 | EventTriggerDDLCommandStart |
| [`src/backend/commands/event_trigger.c`](../files/src/backend/commands/event_trigger.c.md) | 778 | EventTriggerDDLCommandEnd |
| [`src/backend/commands/event_trigger.c`](../files/src/backend/commands/event_trigger.c.md) | 826 | EventTriggerSQLDrop |
| [`src/backend/commands/event_trigger.c`](../files/src/backend/commands/event_trigger.c.md) | 1013 | EventTriggerTableRewrite |
| [`src/backend/commands/event_trigger.c`](../files/src/backend/commands/event_trigger.c.md) | — | full module |
| [`src/include/catalog/pg_event_trigger.h`](../files/src/include/catalog/pg_event_trigger.h.md) | — | catalog row |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/process-utility-hook-chain.md` —
  ProcessUtilitySlow fires these.
- `knowledge/idioms/ddl-deparse-via-event-triggers.md` —
  uses pg_event_trigger_ddl_commands() / deparse.
- `knowledge/idioms/cache-invalidation-registration.md` —
  DDL → inval; event triggers see them.
- `knowledge/idioms/trigger-firing-order.md` — row-level
  trigger firing (distinct).
- `knowledge/subsystems/tcop.md` — tcop subsystem.
- `.claude/skills/extension-development/SKILL.md` —
  registering event triggers.
- `source/src/backend/commands/event_trigger.c` — full
  module.
- `source/src/include/catalog/pg_event_trigger.h` —
  catalog row.
