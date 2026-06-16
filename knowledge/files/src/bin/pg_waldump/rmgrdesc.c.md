# `src/bin/pg_waldump/rmgrdesc.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~99
- **Source:** `source/src/bin/pg_waldump/rmgrdesc.c`

Builds a frontend-friendly table of resource managers for use by
`pg_waldump` (and `pg_walinspect` via similar code). For each
built-in rmgr we get `{rm_name, rm_desc, rm_identify}` by
re-`#include`-ing `access/rmgrlist.h` with a custom `PG_RMGR` macro
that strips the redo/startup/cleanup/mask/decode entry points (which
are backend-only). For custom rmgrs (PG16+) the table is filled
lazily on first lookup with synthetic names `customNNN`.
[verified-by-code]

## API / entry points

- `const RmgrDescData *GetRmgrDesc(RmgrId rmid)` — sole public
  entry. Returns a pointer to the static built-in table for
  built-in IDs; lazily initialises and returns the custom-rmgr
  table otherwise. [verified-by-code]

## Notable invariants / details

- `RmgrDescTable[RM_N_BUILTIN_IDS]` is built at compile-time by
  `#include "access/rmgrlist.h"` after locally redefining the
  `PG_RMGR(symname, name, redo, desc, identify, startup, cleanup,
  mask, decode)` macro to expand to `{ name, desc, identify },`.
  This is the same idiom the backend uses to construct its full
  RmgrTable. [verified-by-code]
- `initialize_custom_rmgrs` (line 73): generates `custom###` names
  with width-3 zero-pad. The matching parser in
  `pg_waldump.c:1100` reads them back with `sscanf("custom%03d",
  &rmid)`. The width is `RM_N_CUSTOM_IDS` rmgrs starting at
  `RM_MIN_CUSTOM_ID`. [verified-by-code]
- `default_desc` (line 51) just prints `rmid: %d` — there's no way
  to decode payload for unloaded custom rmgrs. [verified-by-code]
- `default_identify` (line 61) returns NULL; the caller in
  `pg_waldump.c:683` substitutes `UNKNOWN (%x)`. [verified-by-code]
- Uses `#define FRONTEND 1` + `postgres.h` (line 8-9). The
  `RmgrDescData` struct lives in `rmgrdesc.h` and is purely a
  description-layer thing, not the same as backend's `RmgrData`.
  [verified-by-code]

## Potential issues

- The `custom###` format assumes `RM_N_CUSTOM_IDS` < 1000. If a
  future PG version raises this limit, the `snprintf` would
  silently truncate names, and the inverse parser in
  `pg_waldump.c:1100` would silently match the wrong rmgr.
  [verified-by-code] [ISSUE-correctness: custom### naming assumes
  ≤999 custom rmgrs; raising the cap silently breaks parser (maybe)]
- `CustomRmgrDescInitialized` is a plain bool (line 46), not
  atomic. Fine because pg_waldump is single-threaded.
  [verified-by-code]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_waldump`](../../../../issues/pg_waldump.md)
<!-- issues:auto:end -->
