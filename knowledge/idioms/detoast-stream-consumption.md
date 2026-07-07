# detoast_attr / detoast_attr_slice — reading TOASTed values

`detoast_attr` is the universal "give me a plain in-line varlena
no matter what shape this Datum is" entry point. It branches on
the four header shapes (`EXTERNAL_ONDISK`, `EXTERNAL_INDIRECT`,
`EXTERNAL_EXPANDED`, plain `COMPRESSED`, `SHORT`) and returns a
freshly-allocated 4-byte-header uncompressed result. `detoast_attr_slice`
is the partial-fetch variant: for non-compressed external datums
it fetches only the requested byte range from the TOAST table; for
compressed it fetches enough to decompress the prefix that covers
the slice. Both paths funnel into `toast_fetch_datum[_slice]`,
which uses the table-AM's `relation_fetch_toast_slice` callback to
read chunks.

Anchors:
- `source/src/backend/access/common/detoast.c:116` — detoast_attr
  [verified-by-code]
- `source/src/backend/access/common/detoast.c:205` —
  detoast_attr_slice [verified-by-code]
- `source/src/backend/access/common/detoast.c:343` —
  toast_fetch_datum [verified-by-code]
- `source/src/backend/access/common/detoast.c:396` —
  toast_fetch_datum_slice [verified-by-code]
- `source/src/backend/access/common/detoast.c:254-263` —
  pglz_maximum_compressed_size partial decompression
  [verified-by-code]
- `knowledge/data-structures/varatt-varlena.md` — companion
- `knowledge/idioms/toast-chunk-write.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## detoast_attr — the five-arm switch

[verified-by-code `detoast.c:116-191`]

```c
varlena *
detoast_attr(varlena *attr)
{
    if (VARATT_IS_EXTERNAL_ONDISK(attr)) {
        attr = toast_fetch_datum(attr);
        if (VARATT_IS_COMPRESSED(attr)) {
            varlena *tmp = attr;
            attr = toast_decompress_datum(tmp);
            pfree(tmp);
        }
    }
    else if (VARATT_IS_EXTERNAL_INDIRECT(attr)) {
        /* dereference + recurse */
    }
    else if (VARATT_IS_EXTERNAL_EXPANDED(attr)) {
        attr = detoast_external_attr(attr);  /* type-specific flatten */
    }
    else if (VARATT_IS_COMPRESSED(attr)) {
        attr = toast_decompress_datum(attr);
    }
    else if (VARATT_IS_SHORT(attr)) {
        /* short → 4-byte header expansion */
    }
    return attr;
}
```

Post-condition: the returned varlena is always 4-byte-header
uncompressed and pfree-able (most callers assume this).

## The four "extended" cases

| Shape | First fetch | Then maybe | Final result |
|---|---|---|---|
| ONDISK | `toast_fetch_datum` from TOAST table | decompress if compressed | plain 4-byte |
| INDIRECT | dereference pointer | recurse on pointed-to | plain 4-byte |
| EXPANDED (RO/RW) | type-specific flatten via `detoast_external_attr` | — | plain 4-byte (asserted non-extended) |
| COMPRESSED (inline) | decompress | — | plain 4-byte |
| SHORT (≤126 bytes) | header re-encode | — | plain 4-byte |

The `INDIRECT` recursion guard [verified-by-code line 144]
forbids nested indirect pointers — a producer would have flattened
them away.

## toast_fetch_datum — the chunk reassembly

[verified-by-code `detoast.c:343-382`]

```c
static varlena *
toast_fetch_datum(varlena *attr)
{
    /* Memcpy unaligned varatt_external out of the tuple */
    VARATT_EXTERNAL_GET_POINTER(toast_pointer, attr);
    attrsize = VARATT_EXTERNAL_GET_EXTSIZE(toast_pointer);

    result = (varlena *) palloc(attrsize + VARHDRSZ);

    if (VARATT_EXTERNAL_IS_COMPRESSED(toast_pointer))
        SET_VARSIZE_COMPRESSED(result, attrsize + VARHDRSZ);
    else
        SET_VARSIZE(result, attrsize + VARHDRSZ);

    toastrel = table_open(toast_pointer.va_toastrelid, AccessShareLock);
    table_relation_fetch_toast_slice(toastrel, toast_pointer.va_valueid,
                                     attrsize, 0, attrsize, result);
    table_close(toastrel, AccessShareLock);

    return result;
}
```

Key points:
- Allocates one buffer for the entire reassembled value up front.
- Sets `SET_VARSIZE_COMPRESSED` if the on-disk data is still
  compressed (the caller will decompress).
- Delegates the chunk scan to the table-AM's
  `relation_fetch_toast_slice` — the heapam impl walks the TOAST
  table's PK index for matching (chunk_id, chunk_seq) tuples,
  memcpy'ing payloads into `result`.

## detoast_attr_slice — partial reads

[verified-by-code `detoast.c:205-333`]

The slice path optimizes two cases:

**Non-compressed external** [verified-by-code lines 232-234]:
```c
if (!VARATT_EXTERNAL_IS_COMPRESSED(toast_pointer))
    return toast_fetch_datum_slice(attr, sliceoffset, slicelength);
```
Fetches only the chunks that contain the requested byte range —
saves I/O proportional to `slicelength / total_size`.

**Compressed external, prefix-only** [verified-by-code lines 241-265]:
```c
if (slicelimit >= 0) {
    int32 max_size = VARATT_EXTERNAL_GET_EXTSIZE(toast_pointer);
    if (VARATT_EXTERNAL_GET_COMPRESS_METHOD(toast_pointer) ==
        TOAST_PGLZ_COMPRESSION_ID)
        max_size = pglz_maximum_compressed_size(slicelimit, max_size);
    preslice = toast_fetch_datum_slice(attr, 0, max_size);
}
```
For PGLZ we can bound the compressed prefix needed to decompress
the requested decompressed prefix. **LZ4 has no equivalent API**,
so we fall back to fetching the whole thing
[verified-by-code lines 249-253].

`substring(text, start, len)` for a TOASTed text is the canonical
caller — when `start=0, len=10` it reads at most one or two
chunks from a multi-megabyte value.

## The mid-slice non-prefix gotcha

[verified-by-code `detoast.c:415` Assert]

```c
Assert(!VARATT_EXTERNAL_IS_COMPRESSED(toast_pointer) || 0 == sliceoffset);
```

`toast_fetch_datum_slice` refuses to fetch a non-prefix slice of a
compressed datum — that would require decompressing-and-discarding
the prefix, defeating the purpose. The callers in detoast_attr_slice
guarantee `sliceoffset == 0` for compressed (they fetch the prefix
THEN slice into the decompressed buffer).

## Decompression dispatch

`toast_decompress_datum` (file: detoast.c earlier) reads the
compression-method bits and dispatches:
- `TOAST_PGLZ_COMPRESSION_ID` → `pglz_decompress`
- `TOAST_LZ4_COMPRESSION_ID` → `lz4_decompress_safe`

`toast_decompress_datum_slice` is similar but stops decompression
after enough bytes for the requested prefix. PGLZ supports this
naturally; LZ4 falls through to full decompression.

## Read-locking discipline

[verified-by-code `detoast.c:372, 379`]

- `AccessShareLock` on the TOAST table during the chunk fetch —
  compatible with concurrent writers (RowExclusiveLock) and
  concurrent reads.
- Lock released immediately on close — TOAST reads don't need to
  hold the lock past the fetch.

This is one of the few places in PG where a relation is opened
just for the duration of a single multi-row scan and then closed
without holding the lock to xact end.

## Interaction with `pg_detoast_datum*` macros

The varatt.h public API has `PG_DETOAST_DATUM` (always returns
plain 4-byte) and `PG_DETOAST_DATUM_PACKED` (accepts the result
of `detoast_attr_packed` which can still be SHORT). Most type
input/output functions use the macros; `detoast_attr` is the
underlying engine.

## Common review-time concerns

- **The returned varlena is pfree'able** for ONDISK / COMPRESSED /
  INDIRECT-recurse-and-copy paths. Callers free it.
- **Result is fresh; don't alias the input** — even for SHORT
  expansion a new allocation is returned.
- **Slice of compressed mid-value is forbidden** — slice with
  offset > 0 on a compressed external value will assert-fail.
- **LZ4 has no partial-decompression API** — slice optimization
  on LZ4 compressed external fetches the whole thing.
- **AccessShareLock is released at fetch end** — be careful if
  building tools that need to hold TOAST data for the xact;
  re-read from the pointer is the convention.
- **Indirect pointers must not nest** — assertion violation.

## Invariants

- **[INV-1]** `detoast_attr` always returns a plain 4-byte-header
  uncompressed varlena.
- **[INV-2]** ONDISK fetch uses table_relation_fetch_toast_slice
  → table-AM callback; heap-AM walks the TOAST PK index.
- **[INV-3]** Compressed external slicing requires sliceoffset =
  0 (asserted in toast_fetch_datum_slice).
- **[INV-4]** Indirect pointers cannot nest (asserted in
  detoast paths).
- **[INV-5]** LZ4 compressed external slice falls back to full
  fetch — no partial-decompress API.

## Useful greps

- The reader entry:
  `grep -n 'detoast_attr\|detoast_attr_slice\|toast_fetch_datum' source/src/backend/access/common/detoast.c | head -10`
- Table-AM callback:
  `grep -RIn 'relation_fetch_toast_slice\|heap_fetch_toast_slice' source/src/backend/access/heap | head -10`
- Decompression entry:
  `grep -n 'toast_decompress_datum\|pglz_decompress\|lz4_decompress' source/src/backend/access/common/detoast.c | head -10`
- substring on text as canonical caller:
  `grep -n 'detoast_attr_slice\|text_substring' source/src/backend/utils/adt/varlena.c | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | 116 | detoast_attr |
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | 205 | detoast_attr_slice |
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | 254 | pglz_maximum_compressed_size partial decompression |
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | 343 | toast_fetch_datum |
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | 396 | toast_fetch_datum_slice |
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | — | full reader |
| [`src/backend/utils/adt/varlena.c`](../files/src/backend/utils/adt/varlena.c.md) | — | text_substring + other toast-slice consumers |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/data-structures/varatt-varlena.md` — the
  header shapes detoast_attr branches on.
- `knowledge/idioms/toast-chunk-write.md` — the write side
  producing varatt_external.
- `knowledge/idioms/expanded-objects.md` — how
  detoast_external_attr flattens VARTAG_EXPANDED.
- `knowledge/idioms/tableam-vtable.md` —
  relation_fetch_toast_slice callback.
- `knowledge/subsystems/access-common.md` — TOAST module.
- `knowledge/idioms/heap-page-format.md` — chunks live in heap
  pages of the TOAST table.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/access/common/detoast.c` — full reader.
- `source/src/backend/utils/adt/varlena.c` — text_substring
  + other toast-slice consumers.
