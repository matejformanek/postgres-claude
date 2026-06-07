---
source_url: https://www.postgresql.org/docs/current/storage-toast.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §65.2: TOAST

The Oversized-Attribute Storage Technique — how PG stores values too big for an
8 KB page. The corpus already has `knowledge/docs-distilled/storage.md`; this is
the focused TOAST section, distilled for the **threshold/strategy/varlena-header
mechanics** a backend hacker writing a type's I/O functions must know.

## Trigger + targets

- **TOAST fires only when a row is wider than `TOAST_TUPLE_THRESHOLD`** (~2 KB =
  page/4). It then compresses/moves fields until the row is under
  `TOAST_TUPLE_TARGET` (also ~2 KB, adjustable per-table) or no further gain is
  possible. [from-docs] [verified-by-code, source/src/include/access/heaptoast.h —
  `TOAST_TUPLE_THRESHOLD`, `TOAST_TUPLE_TARGET`]
- **Hard ceiling: 1 GB (2³⁰−1 bytes)** per TOAST-able value, because two bits of
  the varlena length word are stolen for tagging. [from-docs]

## The four per-column storage strategies

`ALTER TABLE ... ALTER COLUMN ... SET STORAGE`: [from-docs]

- **PLAIN** — no compression, no out-of-line. Only choice for non-TOAST-able
  fixed-length types.
- **EXTENDED** — compress first, then push out-of-line if still too big. Default
  for most TOAST-able types.
- **EXTERNAL** — out-of-line, **no** compression. Makes `substr()`/slicing of
  `text`/`bytea` fast (no need to fetch+decompress the whole value).
- **MAIN** — compress in-line; go out-of-line only as a last resort to fit the page.

## On-disk layout

- TOAST table is `pg_toast.pg_toast_<reloid>`, linked from
  `pg_class.reltoastrelid`. Rows: `(chunk_id OID, chunk_seq int, chunk_data
  bytea)` with a unique index on `(chunk_id, chunk_seq)`. [from-docs]
- **`TOAST_MAX_CHUNK_SIZE`** ≈ 2000 bytes — sized so **4 chunk rows fit per 8 KB
  page**. [from-docs] [verified-by-code, source/src/include/access/heaptoast.h]
- **On-disk TOAST pointer = exactly 18 bytes** regardless of value size; carries
  `va_toastrelid` (TOAST table OID), the value's `chunk_id`, logical size,
  physical (compressed) size, and the compression method. [from-docs]

## Varlena header bit-tricks (the part that bites I/O-function authors)

- Two bits of the varlena length word are repurposed: [from-docs]
  - **both zero** → ordinary 4-byte-header uncompressed value, remaining bits =
    total size.
  - **high/low bit set** → **single-byte header** (no alignment padding) for
    values < 127 bytes.
  - **single-byte header with all remaining bits zero** → the datum is actually an
    **out-of-line TOAST pointer**; the second byte gives type/subtype.
  - **the adjacent 4-byte-header bit set** → in-line **compressed** datum;
    remaining bits = compressed size (not original).
- **Therefore C functions taking a TOAST-able arg MUST `PG_DETOAST_DATUM` (or
  `PG_GETARG_*_PP` + `VARDATA_ANY`/`VARSIZE_ANY_EXHDR`) before touching bytes** —
  the raw Datum may be compressed, out-of-line, or short-header. Reading
  `VARDATA`/`VARSIZE` on an un-detoasted short-header value is a classic backend
  bug. [from-docs] [cross: knowledge/idioms/fmgr.md]

## Compression method

- Per-column via the `COMPRESSION` option; absent that, the
  **`default_toast_compression`** GUC at insert time picks `pglz` (default) or
  `lz4` (if built with `--with-lz4`). The method is recorded in the TOAST pointer,
  so a single column can hold a mix. [from-docs]

## In-memory pointer subtypes (never persisted)

- **Indirect** pointers (point at an in-memory varlena; used in logical decoding
  to avoid materializing >1 GB tuples) and **expanded** pointers (a deconstructed
  computational form, e.g. expanded arrays, with read-write vs read-only
  variants). Both are flattened to ordinary varlena before any disk write.
  [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/storage.md]] — the parent page-layout chapter.
- [[knowledge/data-structures/heap-tuple-layout.md]] — where the varlena header
  bits sit relative to the tuple header.
- [[knowledge/idioms/fmgr.md]] — `PG_DETOAST_DATUM` / `PG_GETARG_*_PP` discipline.
- [[knowledge/subsystems/access-heap.md]] — heap_toast.c lives in the heap AM.
- wal-and-xlog skill — TOAST writes are WAL-logged like any heap insert.

## Gaps / follow-ups

- No per-file corpus doc yet for `src/backend/access/common/toast_internals.c`,
  `heaptoast.c`, or `detoast.c`; the threshold/macro cites above are header-level.
