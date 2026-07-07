---
name: toast-storage
description: PostgreSQL's TOAST (The Oversized-Attribute Storage Technique) — out-of-line + compressed storage for large `varlena` values (text, bytea, jsonb, arrays, xml, tsvector). Covers `src/backend/access/common/toast_*.c` + `src/backend/access/table/toast_helper.c` + the compression backends (pglz, lz4). Loads when the user asks about TOAST semantics, `pg_toast_<oid>` tables, storage strategies (PLAIN / EXTERNAL / EXTENDED / MAIN), inline vs out-of-line thresholds (2 KB / 8 KB rules), TOAST pointers, sliced access (`substring` optimization), or lz4 vs pglz. Skip when the ask is about `pg_toast_pg_class` etc. as objects (that's catalog metadata) or about specific varlena types' semantics (that's their type's skill).
when_to_load: Debug why a value did/didn't TOAST; work with TOAST pointers in extensions; extend the compression algorithm registry; optimize sliced-access code paths for large values; audit VACUUM's TOAST interaction.
companion_skills:
  - access-method-apis
  - vacuum-autovacuum
  - jsonpath-and-jsonb
---

# toast-storage — how PG stores large values

PG pages are 8 KB. A single column value larger than ~2 KB is a problem — it wouldn't fit. TOAST solves this by:

1. **Compressing** the value in-place if that fits.
2. If still too large, **moving it out-of-line** to a hidden per-relation TOAST table.
3. **Storing a pointer** in the main relation instead of the value.

Every type marked with a variable-length `typlen = -1` (a varlena) can be TOASTed. The main relation's tuple carries either an inline value, an inline-compressed value, or a "TOAST pointer" — all indistinguishable to callers via the `VARSIZE_ANY` / `PG_DETOAST_DATUM` macros.

## The file map

| File | Role |
|---|---|
| `access/common/toast_internals.c` | Core `toast_compress_datum` / `toast_save_datum` / `toast_delete_datum`. The write side. |
| `access/common/detoast.c` | `detoast_attr` / `detoast_attr_slice` / `detoast_external_attr`. The read side. |
| `access/table/toast_helper.c` | Bulk helpers: `toast_tuple_init` / `toast_tuple_try_compression` / `toast_tuple_flatten`. Called by heap-insert. |
| `access/common/heaptuple.c` | Tuple I/O — the entry point for a lot of TOAST decisions. |
| `include/access/toast_compression.h` | Compression method dispatch — pglz vs lz4. |
| `access/common/toast_compression.c` | Compression backend registry — the two currently-supported algorithms. |
| Per-relation TOAST table | Auto-created as `pg_toast.pg_toast_<oid>`. 3-column schema: `(chunk_id, chunk_seq, chunk_data)`. Indexed on `(chunk_id, chunk_seq)`. |

## Storage strategies

Each column has a `storage` attribute (see `pg_attribute.attstorage`):

- **`p` PLAIN** — never TOAST. Fixed-length types + user-requested. Attempting to store > 8 KB fails.
- **`e` EXTERNAL** — allowed out-of-line, but NO compression.
- **`x` EXTENDED** (default for most varlena types) — both compression AND out-of-line allowed.
- **`m` MAIN** — try to keep inline; compress if needed; only move out-of-line as last resort.

Set via `ALTER TABLE t ALTER COLUMN c SET STORAGE <strategy>`. Default determined by the type's `typstorage`.

## The 2 KB rule + TOAST_INDEX_TARGET

When heap_insert (or heap_update, or copy) needs to store a tuple:

1. If the tuple fits inline (< 2 KB usable per page after headers) — do nothing.
2. If not — pick the biggest attribute; try compression on it. Re-check size. Repeat.
3. If still not fitting — pick the biggest attribute; move it out-of-line. Re-check. Repeat.
4. If the tuple STILL doesn't fit — error out.

The 2 KB threshold (roughly BLCKSZ / 4) balances "fewer TOAST references means faster reads" against "smaller inline means more rows per page".

## Out-of-line storage

An out-of-line value is broken into `TOAST_MAX_CHUNK_SIZE` (~2000 bytes) chunks:

- `chunk_id` — a value-level unique ID (assigned per TOAST'd value).
- `chunk_seq` — the sequence number within one value's chunks.
- `chunk_data` — the actual bytes (post-compression if compressed).

An index on `(chunk_id, chunk_seq)` lets `detoast_attr` fetch chunks efficiently.

The main-relation tuple stores a **TOAST pointer** in place of the value:

- `va_extsize` — total size (post-compression).
- `va_rawsize` — original size (pre-compression).
- `va_valueid` — the chunk_id in the TOAST table.
- `va_toastrelid` — the TOAST relation OID.

Pointer size: 18 bytes. Much smaller than the value.

## Compression algorithms

Two supported since PG 14:

- **`pglz`** — historical, in-tree. Fast to compress + decompress; low ratio; portable.
- **`lz4`** — added PG 14. Faster to decompress; better ratios on most data; requires `--with-lz4` at build time.

Set via GUC `default_toast_compression = 'pglz' | 'lz4'` OR per-column `SET COMPRESSION lz4`.

The compressed value stores which algorithm was used in the varlena header, so mixed-compression columns work.

## Detoasting on read

`PG_DETOAST_DATUM(x)` — the macro every varlena-consuming function calls. Effects:

- If x is uncompressed inline: no-op.
- If x is inline-compressed: decompresses in place.
- If x is out-of-line: fetches all chunks from the TOAST table + concatenates + decompresses if needed.
- Returns a "fully materialized" varlena.

For substring / slice access:

- `PG_DETOAST_DATUM_SLICE(x, offset, len)` — fetches only the needed chunks. Big optimization for `substring(long_text, 100, 50)`.
- `detoast_attr_slice` in `detoast.c` implements this.

## What triggers TOAST activity

- **Heap insert / update** — `toast_helper.c` runs the 2 KB rule.
- **VACUUM** on the main relation — VACUUMs the TOAST relation too (automatic).
- **VACUUM FULL / CLUSTER** — rewrites the main relation; TOAST references are re-linked.
- **DROP TABLE** — cascades: TOAST table is dropped alongside.
- **User query with a TOASTable column** — reads trigger detoasting on any function that operates on the value.

## Common patch shapes

### Add a new compression algorithm

- Add case in `include/access/toast_compression.h` — new algorithm ID byte.
- Implement compressor + decompressor in `toast_compression.c`.
- Add config-time detection (like `--with-lz4`).
- Update SetToastCompression + column-level `SET COMPRESSION` syntax.
- Regress test with the new codec.
- Consider backport safety — new codec bytes need to be safe in older PGs' storage.

### Adjust TOAST thresholds

- `TOAST_TUPLE_TARGET` in `toast_internals.h`.
- Very platform-specific — test with pgbench + a value-heavy workload.

### Debug "my value isn't TOASTing"

- Check storage strategy: `\d+ t` shows per-column.
- Check tuple size — `pg_column_size(row)` before + after — if inline size < 2 KB, no TOAST needed.
- Check compression — some data doesn't compress well; can force with SET COMPRESSION.

## Pitfalls

- **`PG_DETOAST_DATUM` is expensive if repeated** — materializes the whole value. If you'll call it multiple times, cache the result. Common perf bug in extensions.
- **`PG_DETOAST_DATUM_SLICE` requires the type to support slicing** — some types don't (only ones where slice-access is meaningful).
- **TOAST tables are auto-created + dropped** — you can't drop a TOAST table independently.
- **VACUUM FULL on TOAST tables is separate** — automatic when done on the main relation, but standalone VACUUM FULL on a TOAST table is restricted.
- **Compression can INCREASE size for small/random data** — hence the check that compressed value must be smaller than original.
- **`pg_column_size` returns the STORAGE size** — post-compression + toast pointer size for TOASTed values. Not raw value size. Use `PG_DETOAST_DATUM_COPY` + length for raw.
- **TOAST chunk_id can wrap** — 32-bit, cluster-lifetime. Very rarely hit but has caused production incidents at the largest sites. Only real issue on extremely churny TOAST tables.
- **Replication decodes TOAST too** — logical replication decoding must fetch old TOAST values for UPDATE/DELETE. On slots with retained catalog_xmin, the TOAST table can grow.
- **`pg_repack` and TOAST** — pg_repack rebuilds the main table but has to re-link the TOAST references. Historical bug source.
- **Custom types with detoast in their I/O function** — if `type_in` calls `PG_DETOAST_DATUM` (rare), you may double-detoast on read paths.

## Related corpus

- **Idioms** (4 direct hits): `toast-chunk-write`, `toast-storage-strategies`, `detoast-stream-consumption`, `heap-tuple-decompression-pattern`.
- **Subsystems**: `access-heap` (the primary caller — heap_insert / heap_update path), `access-transam` (WAL logging of TOAST changes).
- **Related planning**: `planning/cb1-pgcrypto-bomb/` — a TOAST-related decompression amplification concern.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom toast-chunk-write
python3 scripts/corpus-chain.py --file src/backend/access/common/detoast.c
```

## Boundary

**Use this skill** for TOAST semantics + storage strategies + compression.

**Don't use** for:
- **Specific varlena types** — jsonb / hstore / xml have their own semantics on top of TOAST. See the type's own skill.
- **Compression algorithms as libraries** — pglz + lz4 have their own code but the integration is what this skill covers.
- **Extension `varlena_out` etc.** — I/O functions live in the type's code, not toast_*.
- **`pg_repack`** — external contrib; touches TOAST but isn't of it.
