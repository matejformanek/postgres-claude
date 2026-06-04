# `src/backend/utils/adt/pg_ndistinct.c`

- **File:** `source/src/backend/utils/adt/pg_ndistinct.c` (851 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O support for the **`pg_ndistinct`** pseudo-type — the on-disk format
for **multi-column n-distinct extended statistics**
(`CREATE STATISTICS … (ndistinct)`). Structure mirrors
`pg_dependencies.c`: JSON-text in, JSON-text out, bytea send,
recv-not-supported.

## Key functions

### Parser

The state machine `NDistinctSemanticState` (`:28-37`) accepts:

```
[{"attributes": [a1,a2,...], "ndistinct": k}, ...]
```

Callbacks: `ndistinct_object_start`/`_end`, `ndistinct_array_*`,
`ndistinct_object_field_start`, `ndistinct_scalar`. They flow into
`build_mvndistinct(parse_state, str)` (~`:670+`) which builds
`MVNDistinct *` and calls `statext_ndistinct_serialize` (`:710`).
[verified-by-code]

### fmgr entry points

- `pg_ndistinct_in(PG_FUNCTION_ARGS)` (`:727-790`) — sets up
  semantic state, calls `pg_parse_json`. Soft-errors via `escontext =
  fcinfo->context`. Generic fallback message "Input data must be valid
  JSON". [verified-by-code]
- `pg_ndistinct_out(PG_FUNCTION_ARGS)` (`:791+`) — calls
  `statext_ndistinct_deserialize(data)` (`:795`), formats each item as
  `{"attributes": [a1,a2,...], "ndistinct": k}`. [verified-by-code]
- `pg_ndistinct_recv` (`:831-845`) — rejects with
  `ERRCODE_FEATURE_NOT_SUPPORTED`. [verified-by-code]
- `pg_ndistinct_send` (`:847+`) — delegates to `byteasend`.
  [verified-by-code]

## Phase D notes

- **Trust boundary for forged storage**:
  `statext_ndistinct_deserialize` in `statistics/mvdistinct.c`
  (`:246-326`):
  - Validates magic + type (`:274-279`).
  - Rejects `nitems == 0` (`:280-281`).
  - Pre-checks `VARSIZE_ANY_EXHDR(data) >= MinSizeOfItems(nitems)`
    (`:283-287`).
  - `palloc0(MAXALIGN(offsetof(MVNDistinct, items)) + nitems *
    sizeof(MVNDistinctItem))` (`:293-294`) — `nitems` is uint32 from
    the bytea; if `nitems` is huge, `palloc0` caps at `MaxAllocSize`
    and ereports cleanly. [verified-by-code]
  - **Per-item `nattributes` only `Assert((>= 2) && (<=
    STATS_MAX_DIMENSIONS))`** (`mvdistinct.c:310`) — same pattern as
    `pg_dependencies`. In production builds a crafted value could push
    `nattributes` arbitrarily; the immediate `palloc(item->nattributes
    * sizeof(AttrNumber))` (`:313`) then `memcpy` from `tmp` is
    bounded by the underlying bytea length checked by the
    `MinSizeOfItems` pre-check, but only because that pre-check sums
    a *minimum* per item (the actual per-item layout uses the trusted
    `nattributes`, so an oversized `nattributes` would read past the
    bytea). [verified-by-code]
- **Recv path safety**: disabled (`:831-845`), same as dependencies.
  [verified-by-code]

## Potential issues

- [ISSUE-trust-boundary: `statext_ndistinct_deserialize` per-item
  `nattributes` is Assert-only; a forged
  `pg_statistic_ext_data.stxdndistinct` row with
  `nattributes > STATS_MAX_DIMENSIONS` would `memcpy` past the bytea
  end and read uninitialized memory. The minimum-size check at
  `mvdistinct.c:283-287` uses `MinSizeOfItems(nitems)` which assumes
  the smallest valid per-item layout, so an oversized per-item
  `nattributes` is not pre-validated. `pg_statistic_ext_data` writes
  require ownership of the statistics object, so attack requires
  catalog write privilege. (maybe)]
- [ISSUE-trust-boundary: `nitems` uint32 → `palloc0(MAXALIGN(...) +
  nitems * sizeof(MVNDistinctItem))` could reach `MaxAllocSize` cap;
  bounded by palloc's cap, becomes a clean ereport, not corruption
  (info)]
- [ISSUE-undocumented-invariant: like `pg_dependencies`, the
  `MVNDistinctItem.nattributes ≥ 2 ∧ ≤ STATS_MAX_DIMENSIONS`
  invariant is enforced only via Assert and indirectly via the
  Bitmapset reconstruction in the loader (info)]

## Cross-references

- `source/src/include/statistics/extended_stats_internal.h` —
  `MVNDistinct`, `MVNDistinctItem`.
- `source/src/include/statistics/statistics_format.h` —
  `STATS_NDISTINCT_MAGIC`, `STATS_NDISTINCT_TYPE_BASIC`,
  `STATS_MAX_DIMENSIONS`.
- `source/src/backend/statistics/mvdistinct.c` —
  `statext_ndistinct_{serialize, deserialize}` and the
  ndistinct-estimation logic.
- `source/src/common/jsonapi.c` — `pg_parse_json`.

## Confidence tag tally
- `[verified-by-code]` × 8
