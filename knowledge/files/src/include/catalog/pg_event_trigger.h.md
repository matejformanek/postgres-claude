# pg_event_trigger.h

- **Source path:** `source/src/include/catalog/pg_event_trigger.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'event trigger' system catalog (pg_event_trigger)." `[from-comment]` One row per CREATE EVENT TRIGGER — fires a function on a named DDL event, optionally filtered by command tag.

## Catalog definition

- `CATALOG(pg_event_trigger,3466,EventTriggerRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_event_trigger.h:31`
- `FormData_pg_event_trigger` typedef. Pointer alias: `Form_pg_event_trigger`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| evtname | NameData | — | — |
| evtevent | NameData | — | — (event name, e.g. ddl_command_start) |
| evtowner | Oid | `BKI_LOOKUP` | `pg_authid` |
| evtfoid | Oid | `BKI_LOOKUP` | `pg_proc` |
| evtenabled | char | — | — (firing config WRT `session_replication_role`) |
| evttags | text[1] | (varlena) | — (command TAGs filter) |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_event_trigger, 4145, 4146)`. `[verified-by-code]`
- Indexes: `pg_event_trigger_evtname_index` (3467, unique on evtname); `pg_event_trigger_oid_index` (PK, 3468). `[verified-by-code]`
- Syscaches: `EVENTTRIGGERNAME`, `EVENTTRIGGEROID`. `[verified-by-code]`
- No on-disk char constants are defined in this header — `evtenabled` reuses `pg_trigger`'s `TRIGGER_FIRES_*` constants (defined in `pg_trigger.h`), and `evtevent` is a free-form NameData. `[inferred]`
- No function prototypes here — runtime API lives in `commands/event_trigger.h`.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_trigger.h` (shares `evtenabled` / `tgenabled` char encoding)
- `knowledge/files/src/include/catalog/pg_proc.h` (evtfoid target — function must return `event_trigger`)
- Runtime: `source/src/include/commands/event_trigger.h`, `source/src/backend/commands/event_trigger.c`

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-cross-header-on-disk-coupling: evtenabled chars defined in pg_trigger.h]** `pg_event_trigger.h:39-40` — the comment says "trigger's firing configuration WRT session_replication_role" but the actual `TRIGGER_FIRES_ON_ORIGIN/_ALWAYS/_ON_REPLICA/_DISABLED` characters live in `pg_trigger.h`. Any future split of trigger vs event-trigger firing semantics would silently desync. A `#include` or even a comment cite would help.
- **[ISSUE-undocumented-invariant: evtevent string values are on-disk]** `pg_event_trigger.h:35` — `evtevent` stores event names like `ddl_command_start`, `ddl_command_end`, `table_rewrite`, `sql_drop`, `login` verbatim. Renaming any of those upstream would invalidate existing event triggers on every cluster. The header doesn't list which strings are valid; that's encoded only in `event_trigger.c`'s validator.
- **[ISSUE-ordering-among-event-triggers]** — multiple event triggers on the same event fire in alphabetical order of `evtname` (per `event_trigger.c` ordering). Users naming triggers without a numeric prefix discover this the hard way; the catalog header doesn't mention it.

## Tally

`[verified-by-code]=6 [from-comment]=1 [inferred]=3`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/event-trigger-firing.md](../../../../idioms/event-trigger-firing.md)
