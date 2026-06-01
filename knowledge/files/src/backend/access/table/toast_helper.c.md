# toast_helper.c

- **Source path:** `source/src/backend/access/table/toast_helper.c`
- **Lines:** 337
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `toast_helper.h`, `heap/heaptoast.c` (heap AM consumer), `common/toast_internals.c` (storage), `common/toast_compression.c`.

## Purpose

Reusable helpers for table-AM implementations that need to TOAST varlena attributes. Provides the per-tuple `ToastTupleContext` state machine: classify each attribute (must-detoast, is-EXTERNAL old value, compressible, can-externalize), find the biggest attribute to act on, attempt compression, externalize via `toast_save_datum`, and on UPDATE/DELETE remove the no-longer-referenced EXTERNAL chunks. `heaptoast.c` calls these. [from-comment, toast_helper.c:1-12]

## Top-of-file comment

> "Helper functions for table AMs implementing compressed or out-of-line storage of varlena attributes." [from-comment, toast_helper.c:3-5]

## Public surface

- `toast_tuple_init` (41) — Initialise the per-tuple `ToastTupleContext` from the tuple's `values[]` / `isnull[]` and (for UPDATE) the old values. Classifies each attribute: detoast-needed, is-EXTERNAL (track for possible deletion), eligible-for-compression, eligible-for-externalization. Sets `ttc_flags` to a summary (`TOAST_HAS_NULLS`, `TOAST_NEEDS_*`).
- `toast_tuple_find_biggest_attribute` (181) — Among attributes still eligible for `for_compression` or `for_save` (depending on flag), return the index of the largest. Used in the outer loop "while tuple too big, shrink the biggest thing".
- `toast_tuple_try_compression` (227) — Try compressing one attribute in place; if compression doesn't help, mark it ineligible for future compression attempts. Updates `ttc_flags`.
- `toast_tuple_externalize` (256) — Move one attribute to out-of-line TOAST storage via `toast_save_datum`. Updates `values[]` to the EXTERNAL pointer.
- `toast_tuple_cleanup` (275) — Free any palloc'd intermediates; for UPDATE, delete EXTERNAL chunks that the old tuple referenced but the new one no longer does.
- `toast_delete_external` (318) — Standalone helper used on tuple deletion: walk all attributes and call `toast_delete_datum` on every EXTERNAL pointer.

## Key invariants

- `ToastTupleContext.ttc_attr[i].tai_oldexternal` holds the old EXTERNAL pointer (if any). For UPDATE, this is what `toast_tuple_cleanup` compares against the new values to decide whether to delete the old chunks. Match by `va_valueid` (the chunk_id OID). [verified-by-code, toast_helper.c:275-317]
- A short varlena (1-byte header) is NEVER eligible for compression or externalization — `toast_tuple_init` excludes such attributes from `for_compression` / `for_save`. [verified-by-code, toast_helper.c:41-180]
- An attribute whose `attstorage == PLAIN` is never compressed or externalized; `EXTENDED` allows both; `EXTERNAL` allows only externalization; `MAIN` prefers in-line compression but allows externalization as a last resort. [verified-by-code]
- `toast_tuple_cleanup` only deletes external chunks when the OLD value's `va_valueid` is absent from the NEW value (an externalized attribute may be unchanged across an UPDATE, in which case its EXTERNAL pointer is reused and must NOT be deleted). [verified-by-code, toast_helper.c:275-317]
- `toast_delete_external` is called from the AM's `tuple_delete` callback (heap calls it from `heap_toast_delete`). [verified-by-code]

## Functions of note

1. **`toast_tuple_init`** (41) — Per-attribute classification. On UPDATE, also detoasts the OLD value's externals if they were detoasted-on-the-fly so that comparison against the new value works correctly. [verified-by-code]
2. **`toast_tuple_try_compression`** (227) — Calls `toast_compress_datum` with the column's `attcompression`. On success replaces the datum; on failure marks the attribute as compress-tried (so we won't try again). [verified-by-code]
3. **`toast_tuple_externalize`** (256) — Calls `toast_save_datum`, replaces the datum, sets the EXTERNALIZED-IN-THIS-PASS flag, decrements `ttc_attr[i].tai_size` since the new representation is just the pointer. [verified-by-code]

## Cross-references

- `heaptoast.c::heap_toast_insert_or_update` is the canonical consumer: it loops calling `toast_tuple_find_biggest_attribute` → `toast_tuple_try_compression` (if eligible) → `toast_tuple_externalize` until the tuple fits.
- Calls into: `common/toast_internals.c` (`toast_save_datum`, `toast_delete_datum`), `common/detoast.c`.

## Open questions

- Whether a non-heap AM has ever actually consumed this layer (the comment promises "table AMs implementing compressed or out-of-line storage" but heap is the only in-tree user). [unverified]

## Confidence tag tally
`[verified-by-code]=7 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=1`
