# `src/backend/utils/adt/amutils.c`

- **File:** `source/src/backend/utils/adt/amutils.c` (467 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

SQL-level introspection of index access methods (AM). Backs
`pg_indexam_has_property(amoid, name)`,
`pg_index_has_property(relid, name)`,
`pg_index_column_has_property(relid, attno, name)`, and
`pg_indexam_progress_phasename(amoid, phasenum)` — the user-facing
plumbing for the AM-property model defined in `access/amapi.h`.

## Key functions

- `lookup_prop_name(name)` (`:89-102`) — case-insensitive linear scan
  over the 18-entry `am_propnames[]` table (`:31-87`). Returns
  `AMPROP_UNKNOWN` rather than erroring, so AMs can define their own
  property names. [verified-by-code]
- `test_indoption(tuple, attno, guard, mask, expect, *res)` (`:117-139`)
  — bit-test helper over `pg_index.indoption[attno-1]`. Used for
  `asc`/`desc`/`nulls_first`/`nulls_last`. [verified-by-code]
- `indexam_property(fcinfo, propname, amoid, index_oid, attno)`
  (`:151-403`) — the shared core. Looks up the
  `IndexAmRoutine` via `GetIndexAmRoutineByAmId(amoid, true)` (`:198`,
  missing-OK), gives the AM's own `amproperty` callback first crack
  (`:206-213`), then handles the generic column-level (`:215-351`),
  index-level (`:353-377`), and AM-level (`:383-402`) properties.
  [verified-by-code]
- `pg_indexam_has_property` (`:408`), `pg_index_has_property` (`:420`),
  `pg_index_column_has_property` (`:432`) — thin entry wrappers.
  `pg_index_column_has_property` rejects `attno <= 0` so that the
  `attno > 0` branch in the core identifies a column case
  unambiguously (`:439-441`). [verified-by-code]
- `pg_indexam_progress_phasename(amoid, phasenum)` (`:450-467`) —
  dispatches to `routine->ambuildphasename`, returning text. NULL if
  the AM doesn't implement phase reporting or returns NULL. [verified-by-code]

## Phase D notes

Low-risk; all inputs are OID/int/text and validated through syscache
(`SearchSysCache1(RELOID, …)`, `SearchSysCache1(INDEXRELID, …)`).
`attno` is bounded by `natts` from `pg_class.relnatts` (`:192-193`).

For `AMPROP_RETURNABLE` the generic branch opens the index relation
under `AccessShareLock` (`:319-323`) — comment notes this is the
fallback when the AM doesn't override; cheap but not free.

## Potential issues

- [ISSUE-undocumented-invariant: `am_propnames[]` length must match
  `IndexAMProperty` enum coverage; no compile-time check (maybe)]
- [ISSUE-info-disclosure: index_open under AccessShareLock for the
  RETURNABLE fallback could be visible to other backends as a brief
  share lock; unlikely to matter but worth flagging (low)]

## Cross-references

- `source/src/include/access/amapi.h` — `IndexAmRoutine`,
  `IndexAMProperty` enum.
- `source/src/backend/access/index/amapi.c` —
  `GetIndexAmRoutineByAmId`.
- `source/src/backend/access/index/genam.c` — `index_can_return`.

## Confidence tag tally
- `[verified-by-code]` × 5
