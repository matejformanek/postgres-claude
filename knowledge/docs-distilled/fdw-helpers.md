---
source_url: https://www.postgresql.org/docs/current/fdw-helpers.html
chapter: "58.4 Foreign Data Wrapper Helper Functions"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# FDW helper functions — §58.4

These are the **core-supplied** functions an FDW callback calls to fetch its
own catalog metadata: given an OID handed to a callback, recover the
`ForeignTable` / `ForeignServer` / `ForeignDataWrapper` / `UserMapping`
objects and their option lists. Declared in
`src/include/foreign/foreign.h`, implemented in
[[knowledge/files/src/backend/foreign/foreign.c.md]].

## Non-obvious claims

- **The `*Extended` / non-`Extended` pairing is the missing-OK switch.**
  `GetForeignDataWrapperExtended(Oid, bits16 flags)` and
  `GetForeignServerExtended(Oid, bits16 flags)` take a flags word; passing
  `FDW_MISSING_OK` / `FSV_MISSING_OK` returns **NULL instead of erroring**
  on an undefined object. The plain `GetForeignDataWrapper(Oid)` /
  `GetForeignServer(Oid)` are thin wrappers that pass flags = 0 (i.e.
  error-on-missing). [from-docs §58.4]
- **`GetUserMapping(Oid userid, Oid serverid)` has a two-step fallback:**
  it looks for the user-specific mapping, falls back to the **PUBLIC**
  mapping if none exists, and only then **throws** if neither is defined.
  An FDW must be ready for the row it gets back to be the PUBLIC one.
  [from-docs §58.4]
- **`GetForeignColumnOptions(Oid relid, AttrNumber attnum)` returns a
  `List *` of `DefElem`** (the per-column FDW options), or **NIL** when the
  column has none — not NULL-the-pointer-error. Column options are the
  §58.1 `AttributeRelationId` validator case surfacing at runtime.
  [from-docs §58.4]
- **Name-based lookups exist and take an explicit `missing_ok`:**
  `GetForeignDataWrapperByName(const char *name, bool missing_ok)` and
  `GetForeignServerByName(const char *name, bool missing_ok)` — note these
  use a plain `bool`, *not* the `bits16` flags word the OID-based
  `*Extended` variants use. [from-docs §58.4]
- `GetForeignTable(Oid relid)` returns the `ForeignTable` object for a
  foreign table's relation OID; from there `ftoptions` /
  `serverid` chain out to the server and wrapper. [from-docs §58.4]
- These helpers are **catalog-cache reads**, not allocations the FDW owns —
  treat the returned structs as belonging to the current memory context the
  helper allocated them in, and don't pfree across a context reset.
  [inferred — confirm against `foreign.c`]

## Links into corpus

- Implementation + struct definitions:
  [[knowledge/files/src/backend/foreign/foreign.c.md]] +
  [[knowledge/files/src/include/foreign/foreign.h.md]].
- The callbacks that call these helpers:
  [[knowledge/docs-distilled/fdw-callbacks.md]].
- Planning-side helpers (a distinct §58.3 set):
  [[knowledge/docs-distilled/fdw-planning.md]].
- Parent: [[knowledge/docs-distilled/fdwhandler.md]].

## Caveats / verification

- All claims `[from-docs §58.4]`. The `FDW_MISSING_OK` / `FSV_MISSING_OK`
  flag bits and the exact return types (`ForeignTable *`, `List *`) are
  verifiable in `source/src/include/foreign/foreign.h` and `foreign.c` at
  anchor `b78cd2bda5b1a306e2877059011933de1d0fb735`.
