# Heap tuple decompression — TOAST detoasting pattern

PostgreSQL stores varlena columns inline up to a per-page threshold;
beyond that, the column may be compressed in-place and/or moved
out-of-line into a separate TOAST table. Reading the column back
into a usable value is **detoasting** — and there's a canonical
pattern every backend that reads varlenas must follow.

Anchors:
- `source/src/backend/access/common/detoast.c` — `detoast_attr`,
  the dispatcher
- `source/src/include/access/detoast.h` — public API
- `source/src/include/varatt.h` — `VARATT_*` predicates
- `source/src/backend/utils/adt/varlena.c` — many users
- `knowledge/data-structures/heap-tuple-layout.md` — companion:
  the on-disk varlena formats

## The four states of a varlena

When you pull a `Datum` from a tuple via `heap_getattr`, the result
can be in any of these four shapes:

1. **Short-header**, no compression, no external — 1-byte header,
   inline. Length-byte cap = 127 (so payload < 127 bytes).
2. **Long-header**, no compression, no external — 4-byte header,
   inline. Up to ~1 GB minus header.
3. **Compressed in-place** — long-header, compressed-flag set,
   payload is pglz / LZ4 / zstd-compressed bytes. Same page.
4. **External (TOAST pointer)** — long-header, external flag set,
   payload is an `varatt_external` pointer to a row in the relation's
   TOAST table. May ALSO be compressed (compression-via-TOAST).

The four shapes are detected by `VARATT_*` macros in `varatt.h`:

- `VARATT_IS_SHORT(p)` — case 1.
- `VARATT_IS_COMPRESSED(p)` — cases 3 and (sometimes) 4.
- `VARATT_IS_EXTERNAL(p)` — case 4.
- `VARATT_IS_EXTENDED(p)` — anything not case 2 (i.e. needs work).

## The canonical detoast call

```c
Datum    raw = heap_getattr(tuple, attno, tupdesc, &isnull);
struct varlena *attr = (struct varlena *) DatumGetPointer(raw);

if (VARATT_IS_EXTENDED(attr))
    attr = detoast_attr(attr);

/* attr now points to a plain long-header varlena, safe to walk. */
char *data = VARDATA(attr);
int   len  = VARSIZE_ANY_EXHDR(attr);
```

`detoast_attr` handles all three "extended" states (1, 3, 4) and
always returns a freshly-`palloc`'d long-header varlena in
`CurrentMemoryContext`. The input `attr` is unchanged.

[verified-by-code `source/src/backend/access/common/detoast.c:106-160`]

## `detoast_attr` vs `detoast_external_attr`

- `detoast_attr(attr)` — full detoast: short→long, compressed→raw,
  external→fetched. Returns a long-header non-compressed value.
- `detoast_external_attr(attr)` — fetches an external TOAST chunk
  but leaves the result compressed-in-place if it was that way on
  disk. Used when the caller wants to defer decompression or pass
  the still-compressed value through a network protocol.

For 99% of cases, call `detoast_attr`. The other path matters only
in pg_dump / logical-replication / inter-cluster paths.

## The "is it worth detoasting?" predicate

`PG_GETARG_VARLENA_PP(n)` is the typical entry point for SQL-callable
C functions that take a varlena argument:

```c
text *arg = PG_GETARG_TEXT_PP(0);   /* pp = "preserve packed" */
/* arg may be short-header or long-header but is NOT compressed
   or external. fmgr's PG_GETARG_*_PP variants detoast on demand. */
char *data = VARDATA_ANY(arg);
int   len  = VARSIZE_ANY_EXHDR(arg);
```

The `_PP` suffix tells fmgr to detoast through `pg_detoast_datum_packed`,
which handles all three extended states but **preserves** the
short-header form (one byte saved per row vs full detoast).

When you specifically need the long-header form, use `PG_GETARG_TEXT_P`
(no `_PP`) — fmgr fully detoasts.

## Memory context discipline

`detoast_attr` allocates in `CurrentMemoryContext`. In a fmgr call,
that's typically the per-tuple `ExprContext` short-lived context —
detoast results live for one tuple cycle, then get freed by context
reset.

If you need the detoast result to outlive the current context (e.g.
caching across rows in a SRF), `palloc` a copy in the longer-lived
context first.

## When the input is already detoasted

`PG_GETARG_*_PP` and `detoast_attr` are idempotent — calling them on
an already-detoasted value is cheap (returns the input or a quick
copy). No need to gate with `VARATT_IS_EXTENDED` for correctness;
just performance.

## The corner case — compression-via-TOAST

A varlena may be both **external AND compressed**. The flow:

1. `detoast_attr` sees external, fetches the chunks from the TOAST
   table.
2. The reconstituted in-memory value may still be compressed (the
   original was stored compressed-in-pieces).
3. `detoast_attr` then decompresses.

So the "external" and "compressed" predicates are not mutually
exclusive. The dispatcher checks external first; if external,
fetches and may recurse to decompress.

## Compression algorithms

[verified-by-code via `VARATT_COMPRESSED_GET_COMPRESS_METHOD`]

| Method | Code | Required at build time |
|---|---|---|
| pglz | 0 | always available |
| LZ4 | 1 | `--with-lz4` |
| (zstd) | 2 | (proposed; not in tree as of anchor) |

The compression method is recorded in 2 bits of the compressed
varlena header. Mismatch — e.g. an LZ4-compressed value read on a
build without `--with-lz4` — produces `ERROR: compressed data is
corrupt` (it's not actually corrupt; the build lacks the decoder).

The relation's column default is governed by the
`default_toast_compression` GUC + per-column `STORAGE` /
`COMPRESSION` settings.

## Common antipatterns

- **Walking `VARDATA(attr)` without checking `VARATT_IS_EXTENDED`** —
  produces garbage for compressed / external values.
- **Detoasting then storing the pointer past the next
  `MemoryContextReset`** — dangling pointer.
- **Calling `pfree` on a detoasted result you didn't allocate** —
  if `detoast_attr` returned the input pointer (no extension
  needed), `pfree` on it frees the original cached value.
  Solution: always `palloc` a fresh copy if you need to `pfree`
  later, or just let context cleanup do it.

## Useful greps

- detoast callers:
  `grep -RIn 'detoast_attr\|pg_detoast_datum' source/src/backend | wc -l`
  (high count; this is a workhorse function)
- VARATT predicates:
  `grep -n 'VARATT_IS_' source/src/include/varatt.h`
- LZ4 conditional code:
  `grep -RIn 'USE_LZ4' source/src/backend`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | 106 | [verified-by-code -160] |
| [`src/backend/access/common/detoast.c`](../files/src/backend/access/common/detoast.c.md) | — | detoast_attr, the dispatcher |
| [`src/backend/access/common/toast_internals.c`](../files/src/backend/access/common/toast_internals.c.md) | — | in-place / external compression paths |
| [`src/backend/utils/adt/varlena.c`](../files/src/backend/utils/adt/varlena.c.md) | — | many users |
| [`src/include/access/detoast.h`](../files/src/include/access/detoast.h.md) | — | public API |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | — | VARATT_ predicates |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `.claude/skills/fmgr-and-spi/SKILL.md` — `PG_GETARG_*_PP` vs `_P` (preserve-packed semantics).
- `.claude/skills/memory-contexts/SKILL.md` — detoast results live in `CurrentMemoryContext`; lifetime extension via fresh `palloc`.
- `.claude/skills/extension-development/SKILL.md` — `--with-lz4` build-time gate; runtime errors when algorithms aren't compiled in.
- `knowledge/data-structures/heap-tuple-layout.md` — varlena on-disk formats (short / long / compressed / external).
- `knowledge/subsystems/access-heap.md` — TOAST table organization (`pg_toast_*`).
- `source/src/backend/access/common/detoast.c` — the dispatcher implementation.
- `source/src/backend/access/common/toast_internals.c` — the in-place / external compression paths.
