# BRIN tuple format — BrinTuple on disk, BrinMemTuple in memory, the dual-null bitmap

A BRIN summary tuple compresses an entire heap page range (default
128 heap pages = 1 MB) into a single index tuple. The contents depend
on the opclass: a `minmax` opclass stores `(min_value, max_value)`,
`bloom` stores a bloom filter, `inclusion` stores a bounding box,
etc. The format is **deliberately flexible** so opclasses can store
N>1 datums per indexed column (e.g. minmax stores 2: min and max).

This doc walks the `BrinTuple` on-disk header, the `BrinMemTuple` /
`BrinValues` in-memory representation, the **dual-length null
bitmap** (separate `allnulls` and `hasnulls` regions), the four
`bt_info` flag bits, the `brin_form_tuple` serialize-and-pack flow
including the TOAST-compression detour, and the `brin_form_placeholder_tuple`
race-protection variant.

Companion docs:
- [[brin-revmap]] — what indexes the tuples written here.
- [[brin-summarize-and-scan]] — the producer/consumer of these tuples.

## Anchors

- `source/src/include/access/brin_tuple.h:1-112` — full file; structs + macros.
- `source/src/backend/access/brin/brin_tuple.c:100-380` — `brin_form_tuple` (serialize).
- `source/src/backend/access/brin/brin_tuple.c:388-427` — `brin_form_placeholder_tuple`.
- `source/src/backend/access/brin/brin_tuple.c:482-552` — `brin_new_memtuple`.
- `source/src/backend/access/brin/brin_tuple.c:553-650` — `brin_deform_tuple`.
- `source/src/backend/access/brin/brin_minmax.c` — minmax opclass (2 stored datums per column).
- `source/src/backend/access/brin/brin_bloom.c` — bloom opclass (1 stored bloom filter per column).
- `source/src/backend/access/brin/brin_inclusion.c` — inclusion (bounding-box) opclass.

## On-disk format — BrinTuple

```c
/* brin_tuple.h:63-78 */
typedef struct BrinTuple {
    BlockNumber  bt_blkno;        /* first heap block of the range */
    uint8        bt_info;         /* flags + data offset */
    /* (no other fields; followed by null bitmap then datums) */
} BrinTuple;

#define SizeOfBrinTuple  (offsetof(BrinTuple, bt_info) + sizeof(uint8))  /* 5 bytes */
```

The header is tiny — 4-byte block number + 1-byte info. Everything
else is variable: null bitmap (if any nulls present) then the
opclass-managed datums.

The `bt_info` byte packs four pieces of information:

| Bits | Macro                    | Mask  | Meaning                              |
|------|--------------------------|-------|--------------------------------------|
| 7    | `BRIN_NULLS_MASK`        | 0x80  | this tuple has the null bitmap       |
| 6    | `BRIN_PLACEHOLDER_MASK`  | 0x40  | placeholder (concurrent summarize)   |
| 5    | `BRIN_EMPTY_RANGE_MASK`  | 0x20  | range covers zero heap tuples        |
| 0-4  | `BRIN_OFFSET_MASK`       | 0x1F  | data offset (header size, max 31)    |

[verified-by-code] (`brin_tuple.h:85-93`).

The 5-bit "data offset" field caps at 31 — but the actual header plus
null bitmap typically fits well under that. The offset is
**MAXALIGN'd**, so on a 64-bit machine it's a multiple of 8: valid
values are 8, 16, 24. Beyond that the column count would have to be
absurd (the null bitmap is `BITMAPLEN(natts * 2)` bytes = 2 bits per
column). [verified-by-code] (`brin_tuple.c:280-291`).

`BrinTupleDataOffset(tup)` extracts the offset; `BrinTupleHasNulls`,
`BrinTupleIsPlaceholder`, `BrinTupleIsEmptyRange` extract the flag
bits.

## The dual-length null bitmap

Following the `BrinTuple` header (when `BRIN_NULLS_MASK` is set) is a
**two-segment** null bitmap of `BITMAPLEN(natts * 2)` bytes:

```
+--------------------+-----------+-----------+
| BrinTuple header   | allnulls  | hasnulls  |
| (5 bytes)          | (natts    | (natts    |
|                    |  bits)    |  bits)    |
+--------------------+-----------+-----------+
                     | data offset (header end)
                     ↓
                     | natts bits  |  natts bits
                     | first half  |  second half
```

[from-comment] (`brin_tuple.c:272-279`).

- `allnulls[i] = true` → column i is **all NULL** in the page range.
  No actual value is stored for this column (it's all NULL, no point).
- `hasnulls[i] = true` → column i has **at least one NULL** in the
  range but is not all-null. A real value is still stored (so the
  scan can prune ranges based on non-null values); the flag tells
  the consistent-fn that NULL must also be considered visible.

The two-bit encoding is the precision needed for SQL three-valued
logic: a `WHERE col = X` predicate can prune a range only if `col`
is known to never be NULL there *and* never match X. The
`hasnulls` flag is the "we can't fully exclude NULL" signal.

The bitmap is **packed by attribute**: bit `i` in the first half is
allnulls for column i; bit `i` in the second half is hasnulls. Set
to all-allnulls is `brin_form_placeholder_tuple`'s pattern (see
below).

## Per-column datum storage

After the null bitmap is the per-column data. The opclass declares
how many datums it stores per column via `oi_nstored`:

```
minmax    : 2 datums per column (min, max)
inclusion : varies (typically a single bounding box)
bloom     : 1 datum (the filter)
minmax_multi: variable (multiple ranges)
```

[verified-by-code] (`brin_form_tuple` walks `brdesc->bd_info[keyno]->oi_nstored`,
`brin_tuple.c:177`).

The datums are packed via `heap_fill_tuple` — same layout as a regular
heap tuple, but with the **summary's** tuple descriptor
(`brtuple_disk_tupdesc(brdesc)`), which expands each indexed column
into `oi_nstored` columns. For a 3-column minmax index, the on-disk
datum layout is `(min1, max1, min2, max2, min3, max3)`.

## In-memory format — BrinMemTuple + BrinValues

```c
/* brin_tuple.h:29-56 */
typedef struct BrinValues {
    AttrNumber     bv_attno;        /* index attribute number */
    bool           bv_hasnulls;
    bool           bv_allnulls;
    Datum         *bv_values;       /* accumulated values (oi_nstored long) */
    Datum          bv_mem_value;    /* "expanded" form */
    MemoryContext  bv_context;
    brin_serialize_callback_type bv_serialize;
} BrinValues;

typedef struct BrinMemTuple {
    bool           bt_placeholder;
    bool           bt_empty_range;
    BlockNumber    bt_blkno;
    MemoryContext  bt_context;
    /* output arrays used by brin_deform_tuple */
    Datum         *bt_values;
    bool          *bt_allnulls;
    bool          *bt_hasnulls;
    BrinValues     bt_columns[FLEXIBLE_ARRAY_MEMBER];
} BrinMemTuple;
```

In-memory form is much more verbose than on-disk — it carries
explicit per-column allnulls/hasnulls flags rather than packed bits,
and may store an "expanded" Datum (`bv_mem_value`) for opclasses that
need to maintain runtime state (e.g. `brin_minmax_multi` keeps a list
of value ranges that gets serialized down to a smaller on-disk
representation only at form time).

The `bv_serialize` callback fires during `brin_form_tuple` (line 163)
to convert the expanded in-memory form into the compact on-disk
datums.

## The form path — brin_form_tuple

```c
/* brin_tuple.c:100-380 (skeleton) */
BrinTuple *brin_form_tuple(BrinDesc *brdesc, BlockNumber blkno,
                            BrinMemTuple *tuple, Size *size)
{
    values = palloc(brdesc->bd_totalstored × sizeof(Datum));
    nulls  = palloc0(brdesc->bd_totalstored × sizeof(bool));
    anynulls = false;

    idxattno = 0;
    for (keyno = 0; keyno < brdesc->bd_tupdesc->natts; keyno++) {
        if (tuple->bt_columns[keyno].bv_allnulls) {
            for (datumno = 0; datumno < bd_info[keyno]->oi_nstored; datumno++)
                nulls[idxattno++] = true;
            anynulls = true;
            continue;
        }
        if (tuple->bt_columns[keyno].bv_hasnulls)
            anynulls = true;

        /* Opclass serialize callback (if any) */
        if (tuple->bt_columns[keyno].bv_serialize)
            bv_serialize(brdesc, bv_mem_value, bv_values);

        for (datumno = 0; datumno < oi_nstored; datumno++) {
            value = bv_values[datumno];

#ifdef TOAST_INDEX_HACK
            /* For varlena types: detoast external, then maybe compress */
            if (atttype->typlen == -1 /* varlena */) {
                if (VARATT_IS_EXTERNAL(value))
                    value = detoast_external_attr(value);            /* must materialize */
                if (VARSIZE(value) > TOAST_INDEX_TARGET && compressible)
                    value = toast_compress_datum(value, compression);
            }
#endif
            values[idxattno++] = value;
        }
    }

    /* Size computation */
    len = SizeOfBrinTuple;                                   /* 5 bytes */
    if (anynulls)
        len += BITMAPLEN(brdesc->bd_tupdesc->natts * 2);    /* dual bitmap */
    len = hoff = MAXALIGN(len);
    data_len = heap_compute_data_size(brtuple_disk_tupdesc(brdesc), values, nulls);
    len += data_len;
    len = MAXALIGN(len);

    rettuple = palloc0(len);
    rettuple->bt_blkno = blkno;
    rettuple->bt_info = hoff;                                /* offset stored in low 5 bits */

    /* Write null bitmap + datums */
    heap_fill_tuple(brtuple_disk_tupdesc(brdesc), values, nulls,
                    (char *)rettuple + hoff, ...,
                    &phony_infomask, phony_nullbitmap);

    /* Patch the dual bitmap from per-column flags */
    for (i = 0; i < brdesc->bd_tupdesc->natts; i++) {
        if (tuple->bt_columns[i].bv_allnulls) SET_BIT(allnulls_segment, i);
        if (tuple->bt_columns[i].bv_hasnulls) SET_BIT(hasnulls_segment, i);
    }

    if (anynulls)
        rettuple->bt_info |= BRIN_NULLS_MASK;
    if (tuple->bt_placeholder)
        rettuple->bt_info |= BRIN_PLACEHOLDER_MASK;
    if (tuple->bt_empty_range)
        rettuple->bt_info |= BRIN_EMPTY_RANGE_MASK;

    *size = len;
    return rettuple;
}
```

[verified-by-code] (`brin_tuple.c:100-380`).

### The TOAST detour

BRIN summary values can be large (bloom filters can be tens of KB).
The `TOAST_INDEX_HACK` block handles two cases:

1. **External-stored value**: a heap-side value may have been
   TOASTed before reaching us. We must `detoast_external_attr` to
   materialize the actual bytes, because the BRIN tuple is stored in
   the index and shouldn't depend on heap-side TOAST chunks.
   [from-comment] (`brin_tuple.c:200-207`).
2. **Compressible value**: if the value exceeds `TOAST_INDEX_TARGET`
   (2 KB by default) and is compressible, run `toast_compress_datum`
   inline to save index space. Use the same compression method as
   the heap column if the types match; otherwise default.
   [verified-by-code] (`brin_tuple.c:219-251`).

The variable name `untoasted_values[]` tracks which datums need to
be `pfree`'d after the tuple is formed (because we created them
during detoast/compress and can't leak them).

## The placeholder tuple — concurrent summarize protection

When a backend wants to summarize a range that's currently
unsummarized, it first writes a **placeholder** BrinTuple via
`brin_form_placeholder_tuple` and points the revmap at it. This
locks the slot so concurrent inserters know "someone is summarizing
this range; just leave heap data alone for now."

```c
/* brin_tuple.c:388-427 */
BrinTuple *brin_form_placeholder_tuple(BrinDesc *brdesc, BlockNumber blkno, Size *size)
{
    len = SizeOfBrinTuple;
    len += BITMAPLEN(brdesc->bd_tupdesc->natts * 2);          /* always include nulls */
    len = hoff = MAXALIGN(len);

    rettuple = palloc0(len);
    rettuple->bt_blkno = blkno;
    rettuple->bt_info = hoff |
                        BRIN_NULLS_MASK |
                        BRIN_PLACEHOLDER_MASK |
                        BRIN_EMPTY_RANGE_MASK;

    /* Set allnulls = true for every column; hasnulls = false */
    bitP = (uint8 *)((char *)rettuple + SizeOfBrinTuple) - 1;
    bitmask = HIGHBIT;
    for (keyno = 0; keyno < brdesc->bd_tupdesc->natts; keyno++) {
        if (bitmask != HIGHBIT) bitmask <<= 1;
        else { bitP++; *bitP = 0; bitmask = 1; }
        *bitP |= bitmask;                                    /* set allnulls bit */
    }
    /* hasnulls bits all stay zero */
    return rettuple;
}
```

Properties:

- **All `allnulls` set; all `hasnulls` clear.** Semantically equivalent
  to "this range is all NULL in every column" — but with `EMPTY_RANGE`
  also set, the consistent-fn knows the range is unverified.
- **`PLACEHOLDER` + `EMPTY_RANGE` + `NULLS` all set.** A scan that
  encounters this tuple cannot prune the range based on its
  contents; it must include every heap block in the range in its
  output bitmap.
- **No data section** — there's nothing to store; the placeholder is
  pure metadata.

The placeholder is replaced by a real summary tuple at the end of
the summarize-range operation. If the summarizer crashes mid-build,
the placeholder is preserved on disk; the next summarizer (or VACUUM)
detects the leftover placeholder via `BrinTupleIsPlaceholder` and
re-runs the summarization. [from-comment] (`brin_tuple.c:381-386`).

## The empty-range flag

`BRIN_EMPTY_RANGE_MASK` (bit 5) is **separate** from `allnulls`. The
distinction:

- `BRIN_EMPTY_RANGE` true → the range was scanned but contained zero
  heap tuples (e.g. a fresh-but-not-yet-populated range at end of
  table; or pages that were all-deleted-and-removed).
- `allnulls` true → tuples exist in the range, but every value of
  this column is NULL.

A new range starts as `EMPTY_RANGE` (via placeholder) and may
transition to `non-empty` as heap inserts arrive. Once non-empty, it
stays non-empty until desummarized. [unverified — exact transitions
deserve a deeper read of `brin_doupdate` / `brin_xlog.c` to confirm].

## The deform path — brin_deform_tuple

```c
/* brin_tuple.c:553-650 (skeleton) */
BrinMemTuple *brin_deform_tuple(BrinDesc *brdesc, BrinTuple *tuple,
                                 BrinMemTuple *dMemtuple)
{
    if (dMemtuple == NULL)
        dMemtuple = brin_new_memtuple(brdesc);

    dMemtuple->bt_blkno = tuple->bt_blkno;
    dMemtuple->bt_placeholder = BrinTupleIsPlaceholder(tuple);
    dMemtuple->bt_empty_range = BrinTupleIsEmptyRange(tuple);

    tp = (char *)tuple + BrinTupleDataOffset(tuple);

    if (BrinTupleHasNulls(tuple)) {
        /* Read dual bitmap segments */
        for (keyno = 0; keyno < natts; keyno++) {
            dMemtuple->bt_columns[keyno].bv_allnulls = TEST_BIT(allnulls_segment, keyno);
            dMemtuple->bt_columns[keyno].bv_hasnulls = TEST_BIT(hasnulls_segment, keyno);
        }
    }

    /* Extract per-column datums via heap_deform_tuple */
    heap_deform_tuple(...);

    return dMemtuple;
}
```

The output `BrinMemTuple` is the input the opclass consistent-fn
sees during a scan. The opclass can inspect `bt_columns[i].bv_values[]`
(the per-column datum array, sized `oi_nstored`) and the
`bv_allnulls`/`bv_hasnulls` flags to decide whether the range
matches the scan keys.

## brin_tuples_equal — bitwise comparison

```c
/* brin_tuple.c:464-472 */
bool brin_tuples_equal(const BrinTuple *a, Size alen,
                       const BrinTuple *b, Size blen) {
    if (alen != blen) return false;
    if (memcmp(a, b, alen) != 0) return false;
    return true;
}
```

Used by the update path to skip the WAL emit if a re-summarization
produced the same bytes. Strictly memcmp — no semantic comparison.
This works because `brin_form_tuple` is deterministic given the
same inputs.

## Invariants and races

1. **`BRIN_OFFSET_MASK` = 5 bits** caps the header+bitmap size at
   31 bytes. In practice always 8-24 (MAXALIGN'd). [verified-by-code]
   (`brin_tuple.h:85`).
2. **No null bitmap if `BRIN_NULLS_MASK` is clear** — saves
   `BITMAPLEN(natts * 2)` bytes for ranges with no NULLs.
3. **Placeholder tuples have `allnulls` set for every column** —
   pure metadata, no data section. [verified-by-code]
   (`brin_tuple.c:408-422`).
4. **External varlena values must be detoasted** before being stored
   in a BrinTuple. Index tuples cannot reference heap-side TOAST
   chunks because the index file is independent. [from-comment]
   (`brin_tuple.c:198-213`).
5. **`brin_tuples_equal` is bytewise.** Don't compare two BrinTuples
   semantically — same min/max may compress differently.
6. **`bv_serialize` is the opclass hook** for any in-memory →
   on-disk transformation (e.g. minmax_multi compresses its range
   list). [verified-by-code] (`brin_tuple.c:163-167`).
7. **`oi_nstored` may exceed 1** per column. The opclass declares
   how many on-disk datums a column needs; `brdesc->bd_totalstored`
   sums them. [from-comment] (`brin_tuple.h:24-28`).

## Useful greps

```bash
# All flag-bit predicates:
grep -nE "BrinTupleHasNulls|BrinTupleIsPlaceholder|BrinTupleIsEmptyRange|BrinTupleDataOffset" \
       source/src/backend/access/brin/

# Opclass declarations of stored datum count:
grep -rn "oi_nstored" source/src/backend/access/brin/

# The form/deform pair:
grep -n "brin_form_tuple\|brin_deform_tuple\|brin_new_memtuple\|brin_form_placeholder_tuple" \
       source/src/backend/access/brin/brin_tuple.c

# Per-opclass storage layouts:
grep -A 20 "static const BrinOpcInfo" source/src/backend/access/brin/brin_*.c | head -40
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/brin/brin_bloom.c`](../files/src/backend/access/brin/brin_bloom.c.md) | — | bloom opclass (1 stored bloom filter per column) |
| [`src/backend/access/brin/brin_inclusion.c`](../files/src/backend/access/brin/brin_inclusion.c.md) | — | inclusion (bounding-box) opclass |
| [`src/backend/access/brin/brin_minmax.c`](../files/src/backend/access/brin/brin_minmax.c.md) | — | minmax opclass (2 stored datums per column) |
| [`src/backend/access/brin/brin_tuple.c`](../files/src/backend/access/brin/brin_tuple.c.md) | 100 | brin_form_tuple (serialize) |
| [`src/backend/access/brin/brin_tuple.c`](../files/src/backend/access/brin/brin_tuple.c.md) | 388 | brin_form_placeholder_tuple |
| [`src/backend/access/brin/brin_tuple.c`](../files/src/backend/access/brin/brin_tuple.c.md) | 482 | brin_new_memtuple |
| [`src/backend/access/brin/brin_tuple.c`](../files/src/backend/access/brin/brin_tuple.c.md) | 553 | brin_deform_tuple |
| [`src/include/access/brin_tuple.h`](../files/src/include/access/brin_tuple.h.md) | 1 | full file; structs + macros |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- [[brin-revmap]] — the index that points at these tuples.
- [[brin-summarize-and-scan]] — `summarize_range` calls `brin_form_tuple`; `bringetbitmap` calls `brin_deform_tuple`.
- `knowledge/idioms/toast-chunk-write.md` — TOAST mechanics referenced by the `TOAST_INDEX_HACK` detour.
- `source/src/backend/access/brin/README` — design overview.
