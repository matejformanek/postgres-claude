# Issues — `bootstrap`

Per-subsystem issue register for `src/backend/bootstrap/` — the
initdb-time BKI-mode backend that fills the initial template
database.

**Parent subsystem docs:**
- `knowledge/files/src/backend/bootstrap/bootstrap.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | bootstrap/bootstrap.c:75-77 | stale-todo | nit | "XXX several of these input/output functions do catalog scans … this obviously creates some order dependencies in the catalog creation process." Order is encoded in `postgres.bki` ordering; fragile but not actionable | open | knowledge/files/src/backend/bootstrap/bootstrap.c.md §Potential issues |
| 2026-06-11 | bootstrap/bootstrap.c:389-392 | stale-todo | nit | "XXX: It might make sense to move this into its own function at some point." The check-only early-exit branch in `BootstrapModeMain` | open | knowledge/files/src/backend/bootstrap/bootstrap.c.md §Potential issues |
| 2026-06-11 | bootstrap/bootstrap.c:1042,1072 | undocumented-invariant | likely | Two near-identical "XXX this logic must match getTypeIOParam()" blocks for the Typ-list and TypInfo-fallback cases in `boot_get_type_io_data`. Any change to `getTypeIOParam` requires updating both | open | knowledge/files/src/backend/bootstrap/bootstrap.c.md §Potential issues |
| 2026-06-11 | bootstrap/bootstrap.c:1138-1141 | stale-todo | nit | "XXX mao 10/31/92" — the oldest XXX in the file. The `nogc` `MemoryContext` for index-register info is never reset; dates from before MemoryContext existed | open | knowledge/files/src/backend/bootstrap/bootstrap.c.md §Potential issues |
| 2026-06-11 | bootstrap/bootstrap.c:803-804 | undocumented-invariant | maybe | `InsertOneProargdefaultsValue` raises ERROR if `array_count > pronargs` but doesn't assert alignment between leading NULLs and non-default args; relies on caller (initdb-generated BKI) to get it right | open | knowledge/files/src/backend/bootstrap/bootstrap.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- Bootstrap mode is the only place in the backend that runs without
  locks — `table_openrv(..., NoLock)`, `index_open(..., NoLock)` and
  `table_open(..., NoLock)` throughout. Safe because the bootstrap
  backend is the only process running.
- `IgnoreSystemIndexes = true` for the entire bootstrap session;
  catalog lookups go via sequential scan since indexes aren't built
  until `build_indices()` at the end.
- The TypInfo[]-vs-Typ-list duality is the single biggest source of
  cognitive load in this file. `gettype` returns an INDEX into
  TypInfo when `Typ == NIL`, or a real OID otherwise — caller must
  check `Typ != NIL`. The comment is honest: "NB: this is really
  ugly".
- All collation-aware catalog columns are forced to `C_COLLATION_OID`
  during `DefineAttr`. This is the cornerstone that lets `template0`
  be cloned to any collation.
