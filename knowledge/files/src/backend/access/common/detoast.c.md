# detoast.c

- **Source path:** `source/src/backend/access/common/detoast.c`
- **Lines:** 646
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `detoast.h`, `toast_internals.c` (storage side), `toast_compression.c`, `heaptoast.c`, `varatt.h`.

## Purpose

Read side of TOAST: given a possibly-EXTERNAL, possibly-COMPRESSED varlena pointer, reassemble the in-memory full value (or a slice). Public entry points `detoast_external_attr`, `detoast_attr`, `detoast_attr_slice`. The "fetch" half (reading chunks from the TOAST table) is here; the "save" half lives in `toast_internals.c`. [from-comment, detoast.c:1-12]

## Top-of-file comment

> "Retrieve compressed or external variable size attributes." [from-comment, detoast.c:3-5]

## Public surface

- `detoast_external_attr` (45) — Reassemble an EXTERNAL pointer into an in-memory varlena that may still be compressed. Used when callers want to handle decompression themselves (e.g. for slicing compressed data).
- `detoast_attr` (116) — Full detoast: external + decompression. The most common entry point.
- `detoast_attr_slice` (205) — Slice variant: returns just `[sliceoffset, sliceoffset+slicelength)` bytes; tries hard to avoid reading more TOAST chunks than necessary, and (for PGLZ) supports streaming decompression that stops early.
- `toast_raw_datum_size` (545), `toast_datum_size` (601) — size of the fully-decompressed / on-disk encoded representation, without actually doing the fetch.

## Static helpers

- `toast_fetch_datum` (343) — Reassemble ALL chunks from the TOAST relation given a `varatt_external` pointer; opens the toast rel+indexes, builds a `SnapshotToast`, runs an index scan over `chunk_id`.
- `toast_fetch_datum_slice` (396) — Same but limited to chunks covering the slice range; uses `ScanKey` lower/upper bounds on `chunk_seq`.
- `toast_decompress_datum` (471) — Switch on `VARATT_EXTERNAL_GET_COMPRESSION_METHOD`: PGLZ → `pglz_decompress_datum`, LZ4 → `lz4_decompress_datum` (gated by `USE_LZ4`).
- `toast_decompress_datum_slice` (503) — Slice-aware decompress; PGLZ supports streaming via `pglz_decompress` with a stop length.

## Key invariants

- After `detoast_attr` the result is `VARATT_IS_4B_U` (uncompressed 4-byte header), self-contained (no external pointers), and palloc'd in `CurrentMemoryContext`. [verified-by-code, detoast.c:116-200]
- Slicing past the actual length silently clamps to the available data — no error. [verified-by-code, detoast.c:205-340]
- TOAST chunks live in a separate toast relation with its own indexes; the index `chunk_id, chunk_seq` ordering is assumed when issuing range scans for slice fetch. [verified-by-code, detoast.c:396-470; from-comment, toast_internals.c]
- A `SnapshotToast` (in `utils/snapmgr.c`, fetched via `get_toast_snapshot` from toast_internals.c) is used so that a long-running query can still see its own TOAST chunks even after their xmin has moved past the user snapshot. [from-comment]
- LZ4 paths `elog(ERROR)` if the binary was built without LZ4 support — gated by `#ifdef USE_LZ4` in toast_compression.c. [verified-by-code]

## Functions of note

1. **`detoast_attr`** (116) — Decision tree: if INDIRECT, follow indirection; if EXTERNAL, `toast_fetch_datum`; if compressed (after fetch, or inline), decompress. Returns a flat varlena. [verified-by-code]
2. **`detoast_attr_slice`** (205) — For PGLZ-compressed externals, requests just enough chunks to feed the streaming decompressor; for LZ4 (no random access), falls back to full decompression then slicing. [verified-by-code, detoast.c:205-340]
3. **`toast_fetch_datum`** (343) — Single-chunk loop using `systable_beginscan_ordered` on the toast index; memcpy each chunk's `chunk_data` into the result buffer; verifies chunk count matches `va_rawsize/TOAST_MAX_CHUNK_SIZE`. [verified-by-code]

## Cross-references

- Called from `heaptuple.c` (when building / deforming), `printtup.c` (via `typoutput` for output), and many SQL functions (substring on text, etc.).
- Calls into: `toast_internals.c` (`toast_open_indexes`, `get_toast_snapshot`), `pg_lzcompress.c`, `lz4.h` (system lib).

## Open questions

- LZ4 slice handling: comment says "no random access", but a recent change may allow chunk-bounded LZ4 slice fetch. [unverified]
- Interaction with INDIRECT TOAST pointers and expanded objects — `detoast_external_attr` handles INDIRECT but the contract for expanded-object callers wasn't deep-read. [unverified]

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/detoast-stream-consumption.md](../../../../../idioms/detoast-stream-consumption.md)
- [idioms/heap-tuple-decompression-pattern.md](../../../../../idioms/heap-tuple-decompression-pattern.md)

