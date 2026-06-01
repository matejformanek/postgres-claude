# amapi.c

- **Source path:** `source/src/backend/access/index/amapi.c`
- **Lines:** 214
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `amapi.h` (the IndexAmRoutine struct), every per-AM `*handler` SQL function (`bthandler`, `hashhandler`, `gisthandler`, `gin_handler`, `spghandler`, `brinhandler`).

## Purpose

Index-AM-API plumbing: call an AM's handler function to fetch the `IndexAmRoutine` struct, assert the required callbacks are non-NULL, and provide the SQL-callable `amvalidate(opclass)` entry point that dispatches to the AM's `amvalidate` callback. Also hosts strategy ↔ compare-type translation helpers used by the planner. [from-comment, amapi.c:1-31]

## Top-of-file comment

> "Support routines for API for Postgres index access methods." [from-comment, amapi.c:1-7]

## Public surface

- `GetIndexAmRoutine` (33) — Call the handler OID, expect a `Node(IndexAmRoutine)` back; Assert that every mandatory callback is filled in (`ambuild`, `ambuildempty`, `aminsert`, `ambulkdelete`, `amvacuumcleanup`, `amcostestimate`, `amoptions`, `amvalidate`, `ambeginscan`, `amrescan`, `amendscan`). [verified-by-code, amapi.c:32-59]
- `GetIndexAmRoutineByAmId` (69) — Look up the handler OID in `pg_am` (rejects `amtype != AMTYPE_INDEX`); calls through `GetIndexAmRoutine`. Returns NULL with `noerror=true` if the AM does not exist or is not an index AM.
- `IndexAmTranslateStrategy` (131) — Given (strategy, amoid, opfamily), return the corresponding `CompareType` (the AM-neutral comparison kind). For btree this is the identity (strategy IS the compare-type); other AMs dispatch through `amroutine->amtranslatestrategy`. [verified-by-code]
- `IndexAmTranslateCompareType` (161) — Reverse direction; planner uses it when looking for an opclass that supports e.g. `COMPARE_EQ`.
- `amvalidate` (187, SQL-callable) — Looks up the opclass's AM, calls `amroutine->amvalidate(opclassoid)`, returns the bool result. Used by `--enable-cassert` builds during ALTER OPERATOR FAMILY / opclass DDL.

## Key invariants

- Every index AM's handler function MUST return a statically-allocated `IndexAmRoutine *` (so that callers don't have to free it). `amapi.h` builds this idiom into the handler signature. [from-comment, amapi.c:24-31]
- `GetIndexAmRoutine` enforces non-NULL on the 11 listed callbacks. Adding a new mandatory callback means: add it here AND to every existing handler. [verified-by-code, amapi.c:45-56]
- `GetIndexAmRoutineByAmId` rejects non-index AM types — calling it for a table AM is a programming error. [verified-by-code, amapi.c:87-98]
- The btree shortcut in `IndexAmTranslateStrategy` / `IndexAmTranslateCompareType` (138, 168) avoids the catalog lookup on the hottest path: btree's strategy numbers ARE the compare-type enum values. [verified-by-code]

## Cross-references

- `relcache.c::RelationInitIndexAccessInfo` calls `GetIndexAmRoutine` when building the relcache entry for an index — that's why this code must work without database access in bootstrap mode (the handler must be a builtin function, no catalog lookup required).
- Planner uses `IndexAmTranslateStrategy` / `IndexAmTranslateCompareType` in `optimizer/util/plancat.c` and `equivclass.c`.
- `pg_proc.dat` defines an entry per AM handler (`bthandler`, `hashhandler`, etc.).

## Confidence tag tally
`[verified-by-code]=6 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`
