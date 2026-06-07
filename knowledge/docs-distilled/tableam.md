---
source_url: https://www.postgresql.org/docs/current/tableam.html
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 62: Table Access Method Interface Definition

The official entry point for writing a pluggable **table AM** (the storage
engine behind a table). Short chapter — its whole message is "the contract is
the struct comments, go read the header and the heap implementation." This doc
captures that pointer set plus the catalog/GUC wiring, and links it to the
`access-method-apis` skill which carries the callback-by-callback depth.

## The contract

- **The AM is a `TableAmRoutine` struct of C function pointers.** "All the
  callbacks and their behavior is defined in the `TableAmRoutine` structure (with
  comments inside the struct defining the requirements for callbacks)." The
  struct comments — *not* this chapter — are the authoritative spec. [from-docs]
  [verified-by-code, source/src/include/access/tableam.h:321-881 — `typedef
  struct TableAmRoutine` … `} TableAmRoutine;`]
- **A handler function returns a pointer to a (usually `static const`)
  `TableAmRoutine`.** Canonical shape from the chapter:
  ```c
  static const TableAmRoutine my_tableam_methods = {
      .type = T_TableAmRoutine,
      /* ... callbacks ... */
  };
  PG_FUNCTION_INFO_V1(my_tableam_handler);
  Datum my_tableam_handler(PG_FUNCTION_ARGS)
  {
      PG_RETURN_POINTER(&my_tableam_methods);
  }
  ```
  The `.type = T_TableAmRoutine` tag is mandatory (it's how the core validates
  the returned pointer). [from-docs]
  [verified-by-code, source/src/backend/access/table/tableamapi.c — `GetTableAmRoutine`
  checks the node tag; via knowledge/files/src/backend/access/table/tableamapi.c.md]
- **Most callbacks have wrapper functions** documented from the *user's* (not the
  implementor's) point of view — "For details, please refer to the
  `src/include/access/tableam.h` file." So the SQL-visible behavior is described
  by the wrappers in `tableam.h`/`tableam.c`; the callback you implement is the
  thing the wrapper calls. [from-docs]
- **Reference implementation: `heap`.** "Any developer of a new table access
  method can refer to the existing `heap` implementation present in
  `src/backend/access/heap/heapam_handler.c`." That file is the worked example
  for every callback. [from-docs]
  [via knowledge/files/src/backend/access/heap/heapam_handler.c.md]

## Catalog & GUC wiring

- **Each table AM is a row in `pg_am`** with `amtype = 't'` (table) and an
  `amhandler` pointing at the handler function; created/dropped via
  `CREATE ACCESS METHOD` / `DROP ACCESS METHOD`. [from-docs]
- **`default_table_access_method` GUC** picks the AM for `CREATE TABLE` when none
  is named; a table's chosen AM is recorded in `pg_class.relam`. [from-docs]

## Non-obvious requirements the chapter calls out

- **Every tuple needs a TID** (block number + item number within block) for the
  AM to support modification and indexing — even a non-heap store must synthesize
  a (block,offset)-shaped identifier. This is the single hardest constraint for
  non-block storage engines. [from-docs]
- **Tuple slots are AM-specific.** A table AM must provide its own
  `TupleTableSlot` callback type (`slot_callbacks`); see
  `src/include/executor/tuptable.h`. The executor manipulates rows only through
  slots, so the AM's in-memory tuple form is hidden behind the slot vtable.
  [from-docs]
- **Durability is your problem.** WAL integration is via **Generic WAL Records**
  or **Custom WAL Resource Managers** (see `knowledge/docs-distilled` WAL items);
  transactional visibility requires integrating with the xlog/xact machinery in
  `src/backend/access/transam/`. The table AM layer does *not* give you crash
  safety for free. [from-docs] [via knowledge/subsystems/access-transam.md]

## Links into corpus

- [[knowledge/files/src/backend/access/heap/heapam_handler.c.md]] — the worked
  reference implementation the chapter points every AM author at.
- [[knowledge/files/src/backend/access/table/tableamapi.c.md]] — `GetTableAmRoutine`,
  the validation/lookup of a returned `TableAmRoutine`.
- [[knowledge/files/src/backend/access/table/tableam.c.md]] — the wrapper layer
  (`table_*`) the chapter says is the user-facing documentation surface.
- [[knowledge/subsystems/access-heap.md]] — the heap AM as a subsystem.
- [[knowledge/subsystems/access-transam.md]] — the xact/xlog layer an AM must
  integrate with for durability/visibility.
- access-method-apis skill — callback-by-callback contract (`scan_begin`,
  `tuple_insert`, `tuple_insert_speculative`, `slot_callbacks`, …).

## Gaps / follow-ups

- The chapter intentionally enumerates **no** callbacks; the real per-callback
  contract lives in `tableam.h:321-881` struct comments. A focused
  `knowledge/data-structures/tableam-routine.md` mapping each callback to its
  heap implementation in `heapam_handler.c` would be high-value and is not yet
  written.
