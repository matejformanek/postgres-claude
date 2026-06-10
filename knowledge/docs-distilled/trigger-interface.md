---
source_url: https://www.postgresql.org/docs/current/trigger-interface.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Writing Trigger Functions in C

The calling convention and `TriggerData` contract a C trigger sees. The backend
side that builds this struct and interprets the return value is
`src/backend/commands/trigger.c`; the struct is in `commands/trigger.h`.

## Calling convention

- A C trigger uses the **version-1 fmgr interface** but receives **no normal
  args** — instead `fcinfo->context` points to a **`TriggerData`**. [from-docs]
- Verify with **`CALLED_AS_TRIGGER(fcinfo)`**, which is
  `((fcinfo)->context != NULL && IsA((fcinfo)->context, TriggerData))`. Only
  after this is true may you cast `fcinfo->context` to `TriggerData *`. [from-docs]
  [verified-by-code, via [[knowledge/files/src/include/commands/trigger.h.md]]]

## Return-value rules (the load-bearing part)

- Return a **`HeapTuple` pointer or a NULL pointer** — **never** an SQL null
  (do not set `isNull`). [from-docs]
- **Row-level `BEFORE`:** returning `NULL` **skips the operation** for that row
  (no insert/update/delete happens, later triggers don't fire); returning a tuple
  becomes the row that is actually written — return `tg_trigtuple`/`tg_newtuple`
  unchanged to pass it through untouched. [from-docs]
- **`AFTER` triggers and statement-level triggers:** the return value is
  **ignored** (conventionally return NULL). [from-docs]
- The function **must not alter `TriggerData` or anything it points at**. [from-docs]

## `TriggerData` fields

- **`tg_event`** — the event bitmask, inspected via macros:
  `TRIGGER_FIRED_BEFORE` / `_AFTER` / `_INSTEAD`,
  `TRIGGER_FIRED_FOR_ROW` / `_FOR_STATEMENT`,
  `TRIGGER_FIRED_BY_INSERT` / `_UPDATE` / `_DELETE` / `_TRUNCATE`. [from-docs]
- **`tg_relation`** — the relation; `tg_relation->rd_att` is the tuple
  descriptor, `tg_relation->rd_rel->relname` the name (`NameData`; use
  `SPI_getrelname()` for a `char *` copy). [from-docs]
- **`tg_trigtuple`** — the row being INSERTed/DELETEd (and the *old* row for UPDATE).
- **`tg_newtuple`** — the *new* row for UPDATE; **NULL for INSERT/DELETE**.
- **`tg_trigger`** — the `Trigger` struct (`utils/reltrigger.h`): `tgname`,
  `tgnargs`, `tgargs` (the `CREATE TRIGGER` argument strings).
- **`tg_trigslot` / `tg_newslot`** — `TupleTableSlot`s holding the above tuples (or NULL).
- **`tg_oldtable` / `tg_newtable`** — `Tuplestorestate` transition relations for
  `OLD TABLE` / `NEW TABLE`, else NULL.
- **`tg_updatedcols`** — for UPDATE only, a `Bitmapset` of changed columns;
  test with `bms_is_member(attnum - FirstLowInvalidHeapAttributeNumber,
  trigdata->tg_updatedcols)` (attnum 1-based). NULL otherwise. [from-docs]

## Links into corpus
- [[knowledge/files/src/backend/commands/trigger.c.md]] — fires triggers, interprets the returned tuple.
- [[knowledge/files/src/include/commands/trigger.h.md]] — the `TriggerData` struct + `TRIGGER_FIRED_*` macros.
- [[knowledge/files/src/include/catalog/pg_trigger.h.md]] — the catalog row behind `tg_trigger`.
- [[knowledge/docs-distilled/trigger-datachanges.md]] — what a trigger can *see* (snapshot/visibility).
- [[knowledge/files/src/backend/utils/adt/ri_triggers.c.md]] — RI constraints implemented as C triggers (worked example).
- Skill: `fmgr-and-spi` — the version-1 interface + SPI used inside triggers.

## Gaps / follow-ups
- Event triggers (DDL) use a *different* struct (`EventTriggerData`) and path
  (`commands/event_trigger.c`) — not covered here.
- `INSTEAD OF` view triggers reuse this interface but return the row to apply;
  the rewriter supplies a whole-row var since views have no CTID
  (see [[knowledge/docs-distilled/rules-views.md]]).
