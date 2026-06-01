# brin_tuple.h

- **Source path:** `source/src/include/access/brin_tuple.h` (112 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

BrinMemTuple / BrinValues types and `brin_form_tuple` / `brin_deform_tuple` API. [from-comment, brin_tuple.h:1-8]

## Key types

- `BrinValues` — per-indexed-attribute in-memory state: `bv_attno`, `bv_hasnulls`, `bv_allnulls`, `bv_values[]` (sized by `oi_nstored`), `bv_mem_value`, `bv_context`, `bv_serialize` callback.
- `BrinMemTuple` — `BlockNumber bt_blkno` + `BrinValues bt_columns[FLEXIBLE_ARRAY]`. The in-memory shape consumed by opclass `addValue`/`consistent`/`union` procs.
- `BrinTuple` — on-disk: tiny header (`bt_blkno` + flag byte + length-derivable from item id) + doubled null bitmap + packed Datum bytes.
- `brin_serialize_callback_type` — opclass-supplied hook for opclasses whose in-memory and on-disk shapes differ (e.g. minmax-multi keeps an in-memory sorted Datum array but serializes to a bytea blob).

## Constants

- `SizeOfBrinTuple`, `BRIN_OFFSET_MASK`, `BRIN_NULLS_MASK`, etc. — flag-bit and offset macros.

See `brin_tuple.c.md`.
