# src/include/tcop/deparse_utility.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 108 [verified-by-code]

## Role

Internal representation for **collected DDL commands** awaiting
deparse-and-publish to event-trigger handlers (and, optionally, to
logical-replication subscribers). Captures the structured form of
each DDL the backend executes so it can be reconstituted as a
canonical string in `pg_event_trigger_ddl_commands()`.

## Public API

- `CollectedCommandType` enum (`:24-33`):
  - `SCT_Simple` — most commands.
  - `SCT_AlterTable` — special-cased because of subcommand list.
  - `SCT_Grant`, `SCT_AlterDefaultPrivileges`,
    `SCT_AlterOpFamily`, `SCT_CreateOpClass`,
    `SCT_AlterTSConfig` — also each need their own union arm.
- `CollectedATSubcmd` — `(ObjectAddress address, Node
  *parsetree)` (`:38-42`).
- `CollectedCommand` — discriminated union:
  - `type`, `in_extension`, `parsetree`, anonymous union with
    per-type payload, `parent` link for nested cmds (`:44-106`).

## Invariants

- INV-COLLECTED-PARSETREE-RETAINED: `parsetree` field MUST stay
  alive for the lifetime of the trigger-firing context.
  Collected during ProcessUtility; consumed in
  `EventTriggerCollect*` family.
- INV-OBJADDR-VALID: `ObjectAddress` references must remain
  valid (target object existed at collection time). Drop of
  the target between collection and deparse is the typical
  problematic case — `pg_get_xxx_def()` consults catalog at
  deparse time.
- INV-PARENT-CHAIN: `parent` non-NULL when the command was
  emitted from within another command (e.g. CREATE TABLE → its
  subcommands for indexes / constraints; CREATE SCHEMA AUTH
  with sub-CREATEs).
- INV-IN-EXTENSION-FLAG: `in_extension` true means the command
  was executed while CreateExtension was active — the event
  trigger sees a different filter (DDL inside extension is
  often suppressed from triggers).

## Notable internals

- `alterTable.subcmds` is a `List<CollectedATSubcmd>` — one
  per `ALTER TABLE ... , ...` clause.
- `atscfg.dictIds` + `ndicts` — variable-length array; manual
  memory management.
- `defprivs.objtype` — captures the object class targeted by
  `ALTER DEFAULT PRIVILEGES FOR ROLE ... GRANT ... ON
  <objtype>`.

## Trust boundary / Phase D surface

- **A8 logical-replication NAME-vs-OID echo (HIGH-IMPACT).**
  When DDL replication is added (custom extensions like
  pglogical, or upstream prototypes), `CollectedCommand` is
  the structure sent over the wire. The subscriber side then
  re-deparses it. Trust pitfalls:
  - `ObjectAddress` is `(classid, objid, objsubid)` — the
    PUBLISHER's OID. Sending it raw is meaningless on the
    SUBSCRIBER; deparse-side must re-resolve by NAME.
  - During name re-resolution, the SUBSCRIBER may bind to a
    DIFFERENT object of the same name (e.g. a same-name
    table in a different schema, depending on search_path).
    Classic A8 NAME-vs-OID confusion.
  - `parsetree` is a node tree — round-tripped via
    out/readfuncs. Hostile publisher → A14 deserializer
    surface (see `readfuncs.h` doc).
- **A12 ruleutils echo.** Deparse of CollectedCommand uses
  `ruleutils.c` machinery; security-clause (RLS) loss bugs
  there leak into the deparsed DDL.
- **A11 cleartext echo.** `CREATE USER foo PASSWORD 'secret'`
  → CollectedCommand with `parsetree` containing the
  `CreateRoleStmt` with the password string. Event-trigger
  handlers see this. Mitigation: pg_stat_statements jumble
  doesn't store, but event triggers do. (Verify in
  `event_trigger.c`.)
- **Privilege bracket.** Event triggers fire as the **target
  role** (per `ALTER EVENT TRIGGER ... ENABLE ALWAYS`
  options); a handler installed by a privileged user but
  fired by an unprivileged user sees the full DDL.

## Cross-references

- `commands/event_trigger.h` — consumer.
- `utils/aclchk_internal.h` — `InternalGrant`.
- `catalog/objectaddress.h` — `ObjectAddress`.
- `backend/utils/adt/ruleutils.c` — deparse implementations.
- `tcop/cmdtaglist.h` — drives which CMDTAGs collect.
- A8 phase-D notes on logical-replication DDL NAME-vs-OID.

## Issues / drift

- `[ISSUE-TRUST: A8 — CollectedCommand carries publisher-side OIDs; downstream re-resolution by name can bind wrong object (high)] — source/src/include/tcop/deparse_utility.h:44-106`
- `[ISSUE-TRUST: A11 echo — parsetree retains PASSWORD literals; event-trigger handlers see cleartext (medium)] — source/src/include/tcop/deparse_utility.h:49`
- `[ISSUE-DOC: no comment on how to keep parsetree alive — implicit MemoryContext discipline (medium)] — source/src/include/tcop/deparse_utility.h:44-49`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/ddl-deparse-via-event-triggers.md](../../../../idioms/ddl-deparse-via-event-triggers.md)
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
