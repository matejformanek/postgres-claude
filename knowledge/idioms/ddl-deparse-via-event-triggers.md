# DDL deparse via event triggers — capturing schema changes

The combination of `ddl_command_end` event triggers + the
`pg_ddl_command` opaque type + the deparse infrastructure
provides a path for **capturing DDL as structured data** for
replication, audit logging, or schema-change history. The
event trigger receives a list of executed commands (via
`pg_event_trigger_ddl_commands()`); each entry can be
deparsed into a JSON / text representation suitable for
re-execution or analysis.

Anchors:
- `source/src/backend/commands/event_trigger.c:1679-1690` —
  pg_ddl_command commentary [verified-by-code]
- `source/src/include/tcop/deparse_utility.h` — deparse API
- `source/src/backend/commands/event_trigger.c:2095` —
  deparse Oid-based reconstruction [verified-by-code]
- `knowledge/idioms/event-trigger-firing.md` — companion
- `knowledge/idioms/process-utility-hook-chain.md` — companion
- `.claude/skills/extension-development/SKILL.md` — companion

## The capture pipeline

```
DDL command issued
  ↓
ProcessUtilitySlow
  ↓
EventTriggerDDLCommandStart        [start trigger fires]
  ↓
catalog updates by the DDL handler
  ↓
EventTriggerCollectExecutedCommand [records what happened]
  ↓
EventTriggerDDLCommandEnd          [end trigger fires]
  ↓
end trigger calls pg_event_trigger_ddl_commands()
  ↓
returns list of (command, object, deparsed-tree)
```

The collection happens between start and end events; the end-
event trigger can read the collected list.

## pg_event_trigger_ddl_commands

Built-in function:

```sql
SELECT
    classid, objid, objsubid,
    command_tag,
    object_type, schema_name, object_identity,
    in_extension,
    command   -- pg_ddl_command type
FROM pg_event_trigger_ddl_commands();
```

Available **only inside a `ddl_command_end` event trigger**.
Returns one row per object touched. The `command` column is a
`pg_ddl_command` value — opaque, requires deparse to get
readable form.

## The pg_ddl_command type

[verified-by-code `event_trigger.c:1679-1682`]

> the complete command details are exposed as a column of type
> pg_ddl_command. C-language code can pick the pg_ddl_command
> and transform it into some external, user-visible and/or
> stable representation.

A C-level opaque type. Cannot be cast to text or JSON via SQL
alone; needs:
- A C function that calls `deparse_utility_command(command)`.
- Returns a JSON representation suitable for re-execution.

The deparse infrastructure lives in
`src/include/tcop/deparse_utility.h` + a series of
deparse_<type>.c files (in extensions, not core).

## Why deparse-via-extension

PG core deliberately doesn't ship a "stable deparse to JSON"
path because:
- Stability is the issue — DDL grammar evolves; locking
  format in core would constrain future evolution.
- Extensions can target specific PG versions + specific
  output formats.

The reference extension: `ddl_deparse_extensions` family (BDR,
pglogical historically). They build on PG's deparse helpers
without exposing the format in core.

## The deparse_utility helpers

[from `deparse_utility.h`]

```c
extern char *deparse_utility_command(CollectedCommand *cmd, bool verbose_mode);
```

Walks the `CollectedCommand` (the stored parse tree + Oids of
created objects) and produces a JSON string. Each command type
has its own deparse subroutine.

Used internally for the SQL-level
`pg_get_indexdef`, `pg_get_constraintdef`, etc., as well as
for the experimental deparse extensions.

## CollectedCommand — the recorded shape

```c
typedef struct CollectedCommand
{
    NodeTag      type;
    CollectedCommandType ctype;
    CommandTag   command;
    /* ... fields per type ... */
    /* parse tree + Oid lookups for reconstruction */
} CollectedCommand;
```

Each command type has its own variant: CreateTable,
AlterTable, CreateIndex, etc. The collected form retains
enough to:
- Identify the object (Oid + classid).
- Reconstruct the command text via deparse.

## Use cases

1. **DDL replication** — capture commands on publisher,
   stream to subscriber, re-execute. Required for logical
   replication of DDL (which is otherwise NOT replicated by
   default).
2. **Schema audit log** — every DDL persists to an audit
   table with full re-runnable text.
3. **Migration tracking** — record which DDL ran in which
   transaction.
4. **Cross-version compatibility** — capture in current
   format, replay on older version (with translation).

## Limitations

- **No deparse in core** — only the C-level helpers; SQL
  needs an extension.
- **DDL replication doesn't ship by default** — PG 16+ has
  some pgoutput DDL support but limited.
- **deparse_utility output is not API-stable** — may change
  across PG versions.
- **Some DDL not captured** — TRUNCATE/CREATE EXTENSION/etc.
  have special paths.

## The pgoutput DDL extension

[from PG 16+ pgoutput]

Modern pgoutput supports `publish = 'ddl'` to include DDL in
the logical replication stream. The protocol carries the
deparsed DDL as a string; subscribers parse and re-execute.

Still experimental in some scenarios; the deparse infra is
core but the wiring through pgoutput is recent.

## Common review-time concerns

- **deparse output format isn't stable** — extensions track
  per-version.
- **CollectedCommand is internal** — don't expose via SQL.
- **DDL replication is not transparent** — operator opts in
  via PUBLICATION ... WITH (publish = 'ddl').
- **Some DDL bypasses collection** — bootstrap, internal
  catalog ops, EXTENSION internals.
- **Order matters** — DDL inside a transaction collected in
  execution order; replicated subscribers replay same order.

## Invariants

- **[INV-1]** pg_event_trigger_ddl_commands() only works
  inside ddl_command_end event triggers.
- **[INV-2]** pg_ddl_command is opaque; needs C-level
  deparse.
- **[INV-3]** deparse output format is per-version, not
  cross-version stable.
- **[INV-4]** Core ships deparse helpers; SQL needs an
  extension.
- **[INV-5]** DDL replication is opt-in via PUBLICATION
  flag.

## Useful greps

- The collection:
  `grep -n 'EventTriggerCollect\|CollectedCommand' source/src/backend/commands/event_trigger.c | head -10`
- Deparse helpers:
  `grep -n 'deparse_utility_command\|deparse_CreateTable' source/src/backend | head -10`
- pg_event_trigger_ddl_commands:
  `grep -n 'pg_event_trigger_ddl_commands' source/src/backend/commands/event_trigger.c | head -5`

## Cross-references

- `knowledge/idioms/event-trigger-firing.md` — companion
  (DDL event triggers).
- `knowledge/idioms/process-utility-hook-chain.md` —
  ProcessUtilitySlow drives collection.
- `knowledge/idioms/output-plugin-callbacks.md` — DDL
  replication via pgoutput.
- `knowledge/idioms/apply-worker-loop.md` — subscriber side
  re-executes deparsed DDL.
- `knowledge/idioms/cache-invalidation-registration.md` —
  DDL invalidates caches.
- `knowledge/subsystems/tcop.md` — tcop subsystem.
- `.claude/skills/extension-development/SKILL.md` —
  deparse-extension authoring.
- `source/src/backend/commands/event_trigger.c:1679` —
  pg_ddl_command commentary.
- `source/src/include/tcop/deparse_utility.h` — public API.
