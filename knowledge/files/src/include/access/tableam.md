# `access/tableam.h` — Table access-method API (extension surface)

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/tableam.h`)

## Role
Defines `TableAmRoutine`, the function-pointer table for every table AM.
`heap` is the only in-tree implementation; cstore_fdw, Hydra Columnar,
ZomboDB, and other third-party AMs hang here. Provides the static-inline
`table_*` wrapper functions every backend call site uses; direct callback
calls are explicitly discouraged (`tableam.h:315`-`317`).

## Public API
- `ScanOptions` flag enum (`tableam.h:47`) — `SO_TYPE_SEQSCAN`,
  `SO_TYPE_BITMAPSCAN`, `SO_TYPE_SAMPLESCAN`, `SO_TYPE_TIDSCAN`,
  `SO_TYPE_TIDRANGESCAN`, `SO_TYPE_ANALYZE`, plus `SO_ALLOW_*` and hint bits.
- `SO_INTERNAL_FLAGS` mask (`tableam.h:84`) — the set of flags only the
  table-scan wrappers may pass; user callers asserted clean of these.
- `TM_Result` (`tableam.h:94`) — `TM_Ok`, `TM_Invisible`, `TM_SelfModified`,
  `TM_Updated`, `TM_Deleted`, `TM_BeingModified`, `TM_WouldBlock`.
- `TU_UpdateIndexes` (`tableam.h:132`) — `TU_None`, `TU_All`, `TU_Summarizing`.
- `TM_FailureData` (`tableam.h:169`) — ctid, xmax, cmax, traversed.
- `TM_IndexDelete` / `TM_IndexStatus` / `TM_IndexDeleteOp` (`tableam.h:232`,
  `:238`, `:266`) — bottom-up index deletion coordination state.
- Insert/delete/update/lock option flag macros (`tableam.h:283`-`299`).
- `IndexBuildCallback` typedef (`tableam.h:303`).
- `TableAmRoutine` struct (`tableam.h:321`) — ~40 function pointers across
  six sections (slot, scan, parallel, index-fetch, non-modifying, modifying,
  DDL, miscellaneous, planner, executor).
- Static-inline `table_*` wrappers (`tableam.h:894`+): `table_beginscan`,
  `table_beginscan_strat`, `table_beginscan_bm`, `table_beginscan_sampling`,
  `table_beginscan_tid`, `table_beginscan_analyze`, `table_beginscan_tidrange`,
  `table_endscan`, `table_rescan`, `table_scan_getnextslot`,
  `table_index_fetch_*`, `table_tuple_*`, `table_relation_*`.
- GUCs declared: `default_table_access_method`, `synchronize_seqscans`
  (`tableam.h:32`-`33`); `DEFAULT_TABLE_ACCESS_METHOD = "heap"`.

## Invariants
- `TableAmRoutine` must be allocated in **server-lifetime** storage
  (typically `static const`), returned by `pg_am.amhandler`. `[from-comment]`
  (`tableam.h:312`-`313`).
- `NodeTag type` must be `T_TableAmRoutine`. `[from-comment]` (`tableam.h:323`).
- Only one `SO_TYPE_*` may be set per scan; multiple `SO_ALLOW_*` may be
  combined. `[from-comment]` (`tableam.h:53`).
- `SO_INTERNAL_FLAGS` may **not** be passed by user callers; enforced by
  Assert in `table_beginscan_common` (`tableam.h:921`-`922`).
- Scans cannot be started while `CheckXidAlive` is valid (except for
  `systable_beginscan` and friends marked via `bsysscan`). Enforced at
  `table_beginscan_common` and `table_tuple_fetch_row_version`.
  `[verified-by-code]` (`tableam.h:930`, `:1354`).
- `GetTableAmRoutine()` asserts required callbacks filled — same Assert-only
  pattern as `IndexAmRoutine`. `[from-comment]` (`tableam.h:318`-`319`).
- Scan direction passed to `scan_getnextslot` may not be
  `NoMovementScanDirection` (Assert). `[verified-by-code]` (`tableam.h:1101`-`1102`).
- `relation_fetch_toast_slice` callback is what `heap_fetch_toast_slice`
  ultimately drives; one of two TOAST trust touchpoints (`tableam.h:786`).

## Notable internals
- `TableAmRoutine` has **40+ function pointers**, the largest extension
  surface in the backend.
- `index_fetch_tuple` may set `*call_again = true`, signaling more rows
  for the same TID (HOT-chain semantics) (`tableam.h:482`-`485`).
- `index_delete_tuples` returns the `snapshotConflictHorizon` XID that the
  caller writes into the WAL record for hot-standby conflict resolution
  (`tableam.h:1406`-`1409`).
- `scan_bitmap_next_tuple` updates `lossy_pages` / `exact_pages` counters
  for EXPLAIN ANALYZE (`tableam.h:830`-`834`).
- `relation_toast_am` lets a custom AM delegate TOAST to a different AM
  (`tableam.h:774`-`779`).

## Trust-boundary / Phase D surface

This is **the** canonical "load arbitrary pluggable PG API" target (Hydra
Columnar, ZomboDB, cstore_fdw). The function-pointer table is invoked on
every tuple read, insert, update, delete, and index lookup; misbehavior
manifests across the whole executor.

**[ISSUE-defense-in-depth: required callbacks Assert-only (medium)]** —
Same pattern as amapi.h: `GetTableAmRoutine` (per `tableam.h:318`-`319`)
asserts required callbacks. Non-cassert production trusts a third-party
handler completely. `tableam.h:312`-`319`.

**[ISSUE-api-shape: no version/magic on `TableAmRoutine` (low)]** — Only
the `NodeTag` discriminates. Future PG releases that extend `TableAmRoutine`
with new function-pointer slots will load an old AM library and read
uninitialized memory for the new slots. PG_MODULE_MAGIC catches the
catastrophic case at .so load, but not field-by-field drift. `tableam.h:321`-`881`.

**[ISSUE-security: `index_fetch_tuple` is the integrity boundary between
index and heap (informational)]** — In an unsafe table AM, this callback
could ignore the snapshot, ignore visibility, or return tuples from any
relation — there is no cross-check that the slot's `tts_tableOid` matches
the requested relation. The header documents the contract; enforcement is
purely advisory. `tableam.h:472`-`496`.

**[ISSUE-correctness: scan-during-decoding check uses `elog`, not `ereport`
(low)]** — `table_beginscan_common` and `table_tuple_fetch_row_version` use
`elog(ERROR, ...)` (no errcode, internal-only message) when CheckXidAlive
trips. Per `error-handling` skill, user-facing paths should pick an
ERRCODE; this is an internal invariant though, so elog is arguably correct.
`tableam.h:930`-`931`, `:1354`-`1355`.

**[ISSUE-resource: SO_HINT_REL_READ_ONLY is a hint, not a contract (low)]** —
A caller passes `SO_HINT_REL_READ_ONLY` to signal "I won't modify"; the AM
may ignore. If an AM later mutates buffers based on the hint trusting the
caller, a mistaken hint becomes a correctness bug. `tableam.h:70`-`71`.

## Cross-refs
- `knowledge/files/src/include/access/relscan.h` — `TableScanDescData` host.
- `knowledge/files/src/include/access/table.h` — `table_open` etc.
- `knowledge/files/src/include/access/heaptoast.h` — TOAST routines invoked
  via `relation_fetch_toast_slice`.
- `knowledge/subsystems/access-heap.md` (not yet written).
- A12 `tuple_data_split(do_detoast=true)` finding — `relation_fetch_toast_slice`
  is the bottom of that call stack.

## Issues
1. **[ISSUE-defense-in-depth: required callbacks only Assert-checked (medium)]**
   — `tableam.h:312`-`319`.
2. **[ISSUE-api-shape: no TableAmRoutine version/magic field (low)]**
   — `tableam.h:321`-`881`.
3. **[ISSUE-security: index_fetch_tuple has no cross-check enforcement (informational)]**
   — `tableam.h:472`-`496`.
4. **[ISSUE-error-handling: elog vs ereport in decoding-guard (low)]**
   — `tableam.h:930`-`931`, `:1354`-`1355`.
5. **[ISSUE-resource: SO_HINT_REL_READ_ONLY is advisory only (low)]**
   — `tableam.h:70`-`71`.
