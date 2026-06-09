# `src/include/access/rmgrlist.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**51 lines.**

## Role

Canonical X-macro / "INCLUDE-trick" file: enumerates every WAL resource
manager (rmgr) in a single ordered list. Callers `#define PG_RMGR(...)`
to whatever they need (build an enum, build a dispatch table, build
documentation) and then `#include "access/rmgrlist.h"`. The header
deliberately omits `#ifndef RMGRLIST_H` (line 16) so it can be included
multiple times in one translation unit with different `PG_RMGR`
expansions.

This is the **second canonical X-macro site in the corpus**, alongside
`storage/lwlock/lwlocklist.h` (A15). Both share the discipline: one
ordered list, multiple expansions, append-only.
[verified-by-code] `source/src/include/access/rmgrlist.h:16-26`

## Public API

A single macro contract: `PG_RMGR(symname, name, redo, desc, identify,
startup, cleanup, mask, decode)` — nine fields per entry (line 27).

22 rmgrs currently registered, IDs 0-21 in list order (lines 28-50):
`XLOG`, `Transaction`, `Storage`, `CLOG`, `Database`, `Tablespace`,
`MultiXact`, `RelMap`, `Standby`, `Heap2`, `Heap`, `Btree`, `Hash`,
`Gin`, `Gist`, `Sequence`, `SPGist`, `BRIN`, `CommitTs`,
`ReplicationOrigin`, `Generic`, `LogicalMessage`, `XLOG2`.

The numeric `RM_*_ID` symbols themselves are declared in
`access/rmgr.h` (which `#define`s `PG_RMGR` to extract symname into an
enum, then includes this file).

## Invariants

- **INV-rmgr-id-stable:** "order of entries defines the numerical
  values of each rmgr's ID, which is stored in WAL records. New
  entries should be added at the end, to avoid changing IDs of
  existing entries." [verified-by-code] line 19-22. Reordering breaks
  on-disk WAL compatibility.
- **INV-rmgr-magic-bump:** "Changes to this list possibly need an
  `XLOG_PAGE_MAGIC` bump." [verified-by-code] line 24. Adding an rmgr
  is a WAL-format change.
- **INV-rmgr-three-edits:** adding an rmgr requires THREE coordinated
  edits — (1) append a `PG_RMGR` line here, (2) implement the nine
  callbacks (redo / desc / identify / startup / cleanup / mask /
  decode plus the `RM_*_ID` consumers), (3) bump `XLOG_PAGE_MAGIC` in
  `access/xlog_internal.h`. [inferred] from the contract; lwlocklist
  has the analogous discipline.
- **INV-rmgr-no-ifndef:** the header MUST NOT use an include guard,
  because the X-macro pattern depends on re-inclusion. [verified-by-code]
  line 16.
- **NULL slots are permitted** for `startup`/`cleanup`/`mask`/`decode`
  when the rmgr doesn't need that callback (most rmgrs leave
  `startup`/`cleanup` NULL; only btree/gin/gist/spgist install them).

## Notable internals

The nine callback slots split by purpose:

- `redo` — applied during crash/standby replay (mandatory).
- `desc`, `identify` — used by `pg_waldump` to print records.
- `startup`, `cleanup` — bracket each replay session (used by index AMs
  that maintain per-replay state, e.g. btree incomplete splits).
- `mask` — buffer-content masking for `wal_consistency_checking` (see
  `bufmask.h`).
- `decode` — logical-decoding entry point; only set for rmgrs that
  produce logically-visible side effects.

`heap_mask` is shared between `RM_HEAP_ID` and `RM_HEAP2_ID`
[verified-by-code] lines 37-38. Same for `xlog_decode` consumed by
both `XLOG` and `XLOG2`.

## Trust-boundary / Phase D surface

**Adding a custom rmgr** is done via `RegisterCustomRmgr()` (see
`access/xlog_internal.h`), NOT by editing this file. Custom rmgrs live
in the reserved ID range above the built-ins. An extension can install
a custom redo callback that runs **inside the startup process during
recovery** with full filesystem access; the WAL stream is fully trusted
at replay, so a malicious rmgr ID in WAL replayed on a standby could
execute arbitrary code via the registered handler.

The per-entry `mask` callback is privacy-relevant: it determines which
byte ranges in a page are exempt from `wal_consistency_checking`. A
bug in `heap_mask` could either (a) cause spurious replay failures
(false positive) or (b) hide a real corruption (false negative).

## Cross-refs

- `access/rmgr.h` — the consumer that builds `RM_*_ID` enum from this list.
- `access/xlog_internal.h` — `XLOG_PAGE_MAGIC` and `RegisterCustomRmgr`.
- `storage/lwlock/lwlocklist.h` (A15) — the OTHER canonical X-macro site.
- `access/bufmask.h` — shared mask helpers consumed by per-rmgr `*_mask`.
- `access/heapam_xlog.h`, `access/gistxlog.h`, etc. — per-rmgr WAL record formats.
- `subsystems/wal-and-xlog.md` — replay/redo subsystem narrative.

## Issues

- **ISSUE-doc**: the header comment doesn't mention `RegisterCustomRmgr`
  as the extension hook; new contributors editing this file may not
  realize built-in vs custom is a hard split.
- **ISSUE-fragility**: removing an rmgr (even an unused one) silently
  shifts every downstream ID. There's no compile-time check that IDs
  are stable across versions; only `XLOG_PAGE_MAGIC` discipline catches it.
