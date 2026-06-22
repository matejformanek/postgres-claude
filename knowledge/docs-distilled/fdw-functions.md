---
source_url: https://www.postgresql.org/docs/current/fdw-functions.html
chapter: "58.1 Foreign Data Wrapper Functions"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# FDW handler + validator entry points — §58.1

The §58 parent ([[knowledge/docs-distilled/fdwhandler.md]]) frames the FDW
author's job; this short leaf nails down the **two SQL-declared C functions**
that bootstrap a wrapper: the *handler* and the (optional) *validator*. The
exhaustive callback list lives one section over in
[[knowledge/docs-distilled/fdw-callbacks.md]].

## Non-obvious claims

- The **handler** is declared to take **no arguments** and return the
  pseudo-type **`fdw_handler`**. It returns a palloc'd struct of function
  pointers — `FdwRoutine` — not data. [from-docs §58.1]
- Both functions **must be written in a compiled language (C) using the
  version-1 interface**; they are *plain C functions, not visible or
  callable at the SQL level* — `fdw_handler` / the validator signature
  exist only so `CREATE FOREIGN DATA WRAPPER ... HANDLER / VALIDATOR` can
  name them. [from-docs §58.1]
- The **validator is optional.** If omitted, options on `CREATE`/`ALTER`
  of the FDW, server, user mapping, and foreign table are **not checked at
  definition time** — a silent-acceptance footgun for typo'd options.
  [from-docs §58.1]
- Validator signature: **two args** — a `text[]` of the options to validate,
  and an **`Oid` naming the catalog the object belongs to**. The validator
  switches on that OID to apply the right rule set. [from-docs §58.1]
- The catalog OIDs the validator must distinguish are concrete constants:
  `ForeignDataWrapperRelationId`, `ForeignServerRelationId`,
  `UserMappingRelationId`, `ForeignTableRelationId`, and
  `AttributeRelationId` (the last for **per-column** options on a foreign
  table). [from-docs §58.1]
- The handler/validator split mirrors other pluggable providers (index AM
  `amhandler` → `IndexAmRoutine`, table AM `table_am_handler` →
  `TableAmRoutine`): one SQL-callable C function returning a static-ish
  pointer table is the PG-wide idiom for "register a provider". [inferred]

## Links into corpus

- Parent chapter: [[knowledge/docs-distilled/fdwhandler.md]].
- The callback table this handler returns:
  [[knowledge/docs-distilled/fdw-callbacks.md]] +
  [[knowledge/files/src/include/foreign/fdwapi.h.md]] (`FdwRoutine`).
- The helper functions a validator/handler reaches for live in
  [[knowledge/docs-distilled/fdw-helpers.md]] +
  [[knowledge/files/src/backend/foreign/foreign.c.md]].
- Sibling provider with the same handler-returns-pointer-table shape:
  [[knowledge/docs-distilled/custom-scan.md]].

## Caveats / verification

- All claims `[from-docs §58.1]`. The exact `FdwRoutine` shape and the
  `fdw_handler` pseudo-type registration are verifiable against
  `source/src/include/foreign/fdwapi.h` and `pg_pseudo_type` entries at
  anchor `b78cd2bda5b1a306e2877059011933de1d0fb735`.
