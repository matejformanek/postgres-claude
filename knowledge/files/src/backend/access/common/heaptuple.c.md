# heaptuple.c

- **Source path:** `source/src/backend/access/common/heaptuple.c`
- **Lines:** 1549
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `htup.h`, `htup_details.h`, `tupdesc.c`, `heaptoast.c`, `heap/heapam.c` (consumer).

## Purpose

Heap-tuple format helpers used by every table AM, not just heap/. Builds, deforms, copies, modifies and "minimal-form" tuples; computes per-tuple data size; encodes varlena packing rules; provides the missing-attribute (default) cache used for added columns. The file's preamble (60-line block on short varlenas and alignment) is the canonical statement of the post-8.3 tuple-format rules. [from-comment, heaptuple.c:1-46]

## Top-of-file comment

> "This file contains heap tuple accessor and mutator routines, as well as various tuple utilities." Then a 40-line discussion of short (1-byte header) varlenas: when they may be used (`attstorage != PLAIN`), why alignment-pad bytes must now be zero, why catalog C-struct offsets are no longer reliable past the first varlena, and why `oidvector`/`int2vector` are kept PLAIN. [from-comment, heaptuple.c:7-46]

## Public surface (non-static functions)

- **Constructors:** `heap_form_tuple` (1025), `heap_modify_tuple` (1118), `heap_modify_tuple_by_cols` (1186), `heap_form_minimal_tuple` (1390), `heap_copy_tuple_as_datum` (989), `heap_expand_tuple` (974), `minimal_expand_tuple` (962).
- **Deconstruction:** `heap_deform_tuple` (1254), `nocachegetattr` (509), `heap_getsysattr` (633), `heap_attisnull` (456), `varsize_any` (1546).
- **Copy/free:** `heap_copytuple` (686), `heap_copytuple_with_tuple` (712), `heap_freetuple` (1372), `heap_copy_minimal_tuple` (1478), `heap_free_minimal_tuple` (1466), `minimal_tuple_from_heap_tuple` (1523), `heap_tuple_from_minimal_tuple` (1501).
- **Layout helpers:** `heap_compute_data_size` (219), `heap_fill_tuple` (401).
- **Missing-default cache:** `getmissingattr` (151).

## Key static helpers

- `init_missing_cache` (126), `missing_hash` (104), `missing_match` (112) — process-lifetime hash for cached missing-attribute Datums (deep-copied into `CacheMemoryContext`).
- `fill_val` (275) — single-attribute packer; honours `att->attbyval`, varlena 1-byte/4-byte packing, EXTERNAL/COMPRESSED short-cuts, alignment padding rules.
- `expand_tuple` (738) — shared core for `heap_expand_tuple` / `minimal_expand_tuple` (extends a tuple to include cached missing attrs for newly-added columns).

## Key invariants

- `MaxTupleAttributeNumber` cap is enforced in `heap_form_tuple` (1038-1042) and `heap_form_minimal_tuple`. [verified-by-code]
- Short varlenas are produced INLINE by `heap_form_tuple` via `fill_val` — never through `heaptoast.c`; toasting (compression / out-of-line) is the caller's job. [from-comment, heaptuple.c:18-25]
- Alignment-pad bytes between attributes MUST be zero, because that's how a 1-byte-header varlena is distinguished from padding. [from-comment, heaptuple.c:26-36]
- `getmissingattr` returns pass-by-ref values from a process-wide cache: callers must NOT modify or pfree the result. [verified-by-code, heaptuple.c:90-150]
- `heap_form_tuple` always allocates `HEAPTUPLESIZE + len` in one chunk; `t_data` points just past the `HeapTupleData` management header. [verified-by-code, heaptuple.c:1074-1075]
- `heap_form_minimal_tuple` omits the first `MINIMAL_TUPLE_OFFSET` bytes of the header (the parts only meaningful when stored on a page). [verified-by-code, heaptuple.c:1390-1466]

## Functions of note

1. **`heap_form_tuple`** (1025) — Compute null-bitmap length if any null exists, MAXALIGN it as the data offset, sum data size via `heap_compute_data_size`, palloc, set `t_hoff`, set datum-id fields, call `heap_fill_tuple`. [verified-by-code]
2. **`heap_deform_tuple`** (1254) — Walks attributes, decoding alignment and varlena headers. Stops short and zero-fills the tail when fewer attributes are present than the descriptor expects (added-column case). Calls `getmissingattr` for tail attrs that have a recorded default. [verified-by-code]
3. **`heap_modify_tuple`** (1118) — Builds a new tuple by copying old values then overwriting where `doReplace[i]` is true. Used by trigger code, system-catalog updates, and many DDL paths. [verified-by-code]
4. **`getmissingattr`** (151) — Returns the cached "value when column was added later" for a TupleDesc/attnum. Cache key is `(len, value)` so identical missing values shared across descriptors collapse to one entry. [verified-by-code]

## Cross-references

- Called by virtually every backend that builds a HeapTuple: `executor/*`, `catalog/heap.c`, `commands/copy*.c`, `replication/logical/*`, plus all the per-AM files. [verified-by-code]
- Calls into: `tupdesc.c` (CompactAttribute access), `utils/datum.c` (`datumCopy`), `expandeddatum.c`.

## Open questions

- The exact memory-context semantics of `init_missing_cache` when invoked from a parallel worker vs. a leader — comment says `CacheMemoryContext` is used unconditionally. [unverified]

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=1`
