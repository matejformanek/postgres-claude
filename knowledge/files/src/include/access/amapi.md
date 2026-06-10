# `access/amapi.h` — Index access-method API (extension surface)

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/amapi.h`)

## Role
Defines `IndexAmRoutine`, the function-pointer table that every index AM
(btree, hash, gist, gin, brin, spgist, plus third-party AMs) fills in.
A CREATE ACCESS METHOD … HANDLER references a SQL handler function that
returns a pointer to a statically-allocated `IndexAmRoutine`. This header
is the load-bearing extension boundary for index AMs.

## Public API
- `IndexAMProperty` enum — properties exposed to `pg_index_has_property`,
  `pg_indexam_has_property`, `pg_index_column_has_property`
  (`source/src/include/access/amapi.h:38`).
- `OpFamilyMember` struct — used during opclass/opfamily build to track
  pending members and their dependency strength (`amapi.h:88`).
- Function-pointer typedefs (`amapi.h:107`-`227`): `amtranslate_strategy_function`,
  `amtranslate_cmptype_function`, `ambuild_function`, `ambuildempty_function`,
  `aminsert_function`, `aminsertcleanup_function`, `ambulkdelete_function`,
  `amvacuumcleanup_function`, `amcanreturn_function`, `amcostestimate_function`,
  `amgettreeheight_function`, `amoptions_function`, `amproperty_function`,
  `ambuildphasename_function`, `amvalidate_function`, `amadjustmembers_function`,
  `ambeginscan_function`, `amrescan_function`, `amgettuple_function`,
  `amgetbitmap_function`, `amendscan_function`, `ammarkpos_function`,
  `amrestrpos_function`, `amestimateparallelscan_function`,
  `aminitparallelscan_function`, `amparallelrescan_function`.
- `IndexAmRoutine` struct (`amapi.h:233`) — boolean capability flags
  (amcanorder, amcanunique, amcanmulticol, amcanparallel, amcanbuildparallel,
  amusemaintenanceworkmem, ampredlocks, amsummarizing, …) plus 24 function
  pointers; `NodeTag type` is the first field for `IsA` dispatch.
- `GetIndexAmRoutine(Oid amhandler)` (`amapi.h:330`) — invokes the handler
  fmgr function and casts the returned `Datum` to `IndexAmRoutine *`.
- `GetIndexAmRoutineByAmId(Oid amoid, bool noerror)` (`amapi.h:331`) — looks
  up handler from `pg_am` by AM OID.
- `IndexAmTranslateStrategy` / `IndexAmTranslateCompareType` (`amapi.h:332`-`333`).

## Invariants
- Routines are **statically allocated by the AM**; core code never copies
  or frees them. `[from-comment]` (`amapi.h:230`-`231`)
- Type tag must be `T_IndexAmRoutine`; `GetIndexAmRoutine` enforces this via
  `IsA(routine, IndexAmRoutine)` and errors otherwise. `[verified-by-code]`
  (`source/src/backend/access/index/amapi.c:41`-`42`)
- Required callbacks (ambuild, ambuildempty, aminsert, ambulkdelete,
  amvacuumcleanup, amcostestimate, amoptions, amvalidate, ambeginscan,
  amrescan, amendscan) are checked **only via `Assert`** in production —
  see Phase D below. `[verified-by-code]` (`amapi.c:45`-`56`)
- Optional callbacks (NULL allowed): aminsertcleanup, amcanreturn,
  amgettreeheight, amproperty, ambuildphasename, amadjustmembers,
  amgettuple, amgetbitmap, ammarkpos, amrestrpos, parallel triplet,
  amtranslatestrategy, amtranslatecmptype. `[from-comment]` (`amapi.h:299`-`325`)
- `amstrategies = 0` means "no fixed set of strategy assignments" — used by
  GiST, GIN, etc. `[from-comment]` (`amapi.h:240`-`241`)
- Property API mirrors the booleans in `IndexAmRoutine`; the header notes
  property additions should also update `utils/adt/amutils.c`. `[from-comment]`
  (`amapi.h:289`-`293`)

## Notable internals
- `IndexAMProperty` has 18 enum values; `AMPROP_UNKNOWN=0` is the fallback
  for AM-defined custom properties matched by string name (`amapi.h:40`).
- `OpFamilyMember.ref_is_hard` toggles NORMAL+INTERNAL dependency vs.
  AUTO+AUTO (`amapi.h:71`-`82`); affects whether `ALTER OPERATOR FAMILY DROP`
  is permitted.
- The function-pointer table has **24 function pointers** total, of which
  **11 are required**; 13 may be NULL.
- `amparallelvacuumoptions` is a `uint8` bitmask — see `vacuum.h` for flags
  (`amapi.h:284`-`285`).

## Trust-boundary / Phase D surface

This header is the canonical "load arbitrary index AM" extension surface, the
parallel to A8's output_plugin "load arbitrary code". The handler is a
SQL-callable fmgr function (typically C, but `LANGUAGE C` is the de-facto
expectation since the returned pointer must be to server-static memory).

**[ISSUE-defense-in-depth: `GetIndexAmRoutine` validates required callbacks
only via `Assert`, not `ereport` (medium)]** — In a non-cassert production
build, a malformed handler returning an `IndexAmRoutine` with NULL `ambuild`
or NULL `aminsert` will pass `IsA` and reach the caller, where a NULL deref
becomes a SIGSEGV in the postmaster child. `source/src/backend/access/index/amapi.c:45`-`56`.
Defense-in-depth: convert the Asserts to `if (!routine->ambuild) ereport(ERROR, …)`.

**[ISSUE-api-shape: no version/magic field on `IndexAmRoutine` (low)]** —
Unlike `OutputPluginCallbacks` / `TableAmRoutine` / `IndexAmRoutine`, none
include a `magic` integer or API-version field. A third-party AM compiled
against a future PG with extra fields appended to `IndexAmRoutine` will
silently have garbage in the new slots if loaded into the older PG. The
`NodeTag` discriminates struct kind, not version. `amapi.h:233`-`326`. The
mitigation is PG_MODULE_MAGIC at the .so level — but that's a coarser check.

**[ISSUE-audit-gap: no hook for runtime verification of AM contract (low)]** —
amcheck is the de-facto verifier (A14), but it operates on a per-AM ad-hoc
basis (only btree + gin/gist coverage). No `amselfcheck` slot in
`IndexAmRoutine` means there's no standard way for an AM to expose
"verify this index" as a first-class operation that amcheck or VACUUM
could call. `amapi.h:233`-`326`.

**[ISSUE-correctness: trust that `routine` pointer points to server-lifetime
memory (low)]** — Handler contract requires static allocation
(`amapi.h:230`-`231`). A buggy handler that `palloc`s into a transient
context yields use-after-free; no enforcement. `[inferred]`.

## Cross-refs
- `knowledge/subsystems/access-heap.md`, `knowledge/subsystems/access-nbtree.md`
  (not yet written).
- `knowledge/files/src/include/access/genam.h` — generic AM wrappers that
  call into the function pointers here.
- `knowledge/files/src/include/access/amvalidate.h` — helper for
  `amvalidate_function` implementations.
- A8 corpus finding: output_plugin "load arbitrary code" — amapi.h is the
  parallel index-AM surface.
- A14 amcheck: amcheck is the canonical "verify AM honors contract" tool;
  no hook here for it.

## Issues
1. **[ISSUE-defense-in-depth: required callbacks only Assert-checked (medium)]**
   — `source/src/backend/access/index/amapi.c:45`-`56`.
2. **[ISSUE-api-shape: no IndexAmRoutine version/magic field (low)]**
   — `amapi.h:233`-`326`.
3. **[ISSUE-audit-gap: no AM-side self-verification slot (low)]**
   — `amapi.h:233`-`326`.
4. **[ISSUE-correctness: relies on handler returning server-lifetime pointer (low)]**
   — `amapi.h:230`-`231`.
