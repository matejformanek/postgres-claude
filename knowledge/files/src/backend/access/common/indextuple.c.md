# indextuple.c

- **Source path:** `source/src/backend/access/common/indextuple.c`
- **Lines:** 538
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `itup.h`, `nbtree/*.c` (primary consumer), `gist/*.c`, `hash/*.c`, `spgist/*.c`, `brin/*.c`.

## Purpose

Build, deform and trim `IndexTuple` values. Every index AM uses these helpers (whatever its on-page format, the in-memory `IndexTuple` passed across the genam boundary is always built here). Handles inline detoasting / recompression so the index does not store TOAST pointers (the `TOAST_INDEX_HACK` knob). [from-comment, indextuple.c:1-29]

## Top-of-file comment

> "This file contains index tuple accessor and mutator routines, as well as various tuple utilities." Sets `#define TOAST_INDEX_HACK` — index tuples force a compressed-or-inline representation since VACUUM cannot yet rebuild indexes from scratch when a TOAST table is dropped. [from-comment, indextuple.c:25-29]

## Public surface (non-static functions)

- `index_form_tuple` (44) — convenience wrapper that allocates the result in `CurrentMemoryContext`.
- `index_form_tuple_context` (65) — the workhorse; allocates in the supplied context (used by tuplesort to keep memory accounting tight).
- `nocache_index_getattr` (229) — fallback per-attribute fetch when offsets aren't cached.
- `index_deform_tuple` (364), `index_deform_tuple_internal` (387) — deconstruct into Datum/isnull arrays.
- `CopyIndexTuple` (479) — palloc + memcpy.
- `index_truncate_tuple` (508) — drop trailing attributes (used by btree's "suffix truncation" on internal pages — keeps only enough leading attrs to disambiguate).

## Key invariants

- Index tuples NEVER contain EXTERNAL TOAST pointers. If a value comes in as EXTERNAL, `index_form_tuple_context` either inlines it via `detoast_external_attr` or, if still too large, attempts compression via `toast_compress_datum`. If the result still exceeds `MaxIndexTupleSize`, ereport(ERROR). [verified-by-code, indextuple.c:65-228]
- A 1-byte-header varlena is always written as such — index tuples follow the same packed-varlena rules as heap tuples. [from-comment, indextuple.c:1-29]
- `index_truncate_tuple` is used by btree for INTERNAL keys; the truncated tuple has a smaller `t_info` length but the original opclass interpretation must remain unambiguous. [verified-by-code, indextuple.c:508-538]

## Functions of note

1. **`index_form_tuple_context`** (65) — for each attribute: if EXTERNAL detoast; if compressed but storage class disallows, decompress; if oversize and storage allows, recompress with the tuple's own attcompression. Then computes header size, null bitmap, MAXALIGNs the data area, writes inline varlena headers as appropriate, and rejects if `MaxIndexTupleSize` is exceeded. [verified-by-code]
2. **`index_deform_tuple_internal`** (387) — Walks the null bitmap and per-attribute alignment / varlena rules to populate `values[]` / `isnull[]`. The inline form `index_deform_tuple` is the public entry point (just forwards). [verified-by-code]
3. **`index_truncate_tuple`** (508) — Builds a new `IndexTuple` containing only `nattrs` leading attrs; copies header info but sets `IndexTupleSetNumberOfAttributes` to `nattrs`. Used by `_bt_truncate` in nbtree. [verified-by-code]

## Cross-references

- All index AMs call `index_form_tuple` from their `aminsert` and `ambuild` callbacks.
- Calls into: `detoast.c` (`detoast_external_attr`), `toast_internals.c` (`toast_compress_datum`), `heaptoast.c` indirectly for size-fitting decisions.

## Open questions

- Whether `TOAST_INDEX_HACK` is actually exercised by all current AMs or just legacy ones (the comment hints at "until VACUUM is smart enough"). [unverified]

## Confidence tag tally
`[verified-by-code]=5 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
