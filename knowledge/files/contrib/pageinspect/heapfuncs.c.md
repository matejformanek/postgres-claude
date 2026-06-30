# heapfuncs.c

Covers `source/contrib/pageinspect/heapfuncs.c` (625 lines): heap-page
decoder — line pointers, tuple headers, raw tuple data, and the
"split into columns without input functions" path.

## One-line summary

`heap_page_items` walks the line-pointer array of a heap page and emits
one row per item; `tuple_data_split` splits a raw heap tuple bytea
into its column-level bytea pieces using the relation's tupledesc but
*without* invoking the per-type input function — a deliberate bypass
of type-input validation that the file documents as the reason
everything in here is superuser-only.

## Public API / entry points

- `heap_page_items(bytea page)` — `source/contrib/pageinspect/heapfuncs.c:131`,
  SRF returning one row per line pointer with (lp_off, lp_flags, lp_len,
  xmin, xmax, cmin/cmax/xvac, ctid, infomask2, infomask, t_hoff,
  t_bits, oid, raw_tuple_data).
- `tuple_data_split(oid relid, bytea raw_data, int2 t_infomask, int2
  t_infomask2, text t_bits, bool do_detoast)` —
  `source/contrib/pageinspect/heapfuncs.c:429`. Returns
  `bytea[]` of per-column raw bytes; optional `do_detoast` (1.x SQL
  signature) follows external TOAST pointers.
- `heap_tuple_infomask_flags(int2 t_infomask, int2 t_infomask2)` —
  `source/contrib/pageinspect/heapfuncs.c:513`, decodes the bitmask
  into `text[]` of HEAP_HASNULL/HEAP_XMIN_COMMITTED/… names plus a
  second array of combined flags (HEAP_XMIN_FROZEN etc.).

## Key invariants

- INV-1: All three SQL entry points start with `if (!superuser())`
  (`:137, :450, :527`). The comment at `:12-16` motivates this:
  "fear of introducing security holes if the input checking isn't as
  water-tight as it should be." [from-comment]
- INV-2: Decoder is **defensive against corruption** but **does not
  claim to be safe against adversarial input**. The block-comment at
  `:7-10` says: "we check the input for corrupt pointers etc. that
  might cause crashes, but at the same time we try to print out as
  much information as possible, even if it's nonsense." That's a
  best-effort policy, not a security boundary. [from-comment]
- INV-3: Line-pointer validity gate at `:202-205`: `ItemIdHasStorage`
  AND `lp_len >= MinHeapTupleSize` AND `lp_offset == MAXALIGN(lp_offset)`
  AND `lp_offset + lp_len <= BLCKSZ` — only then does the decoder
  dereference `PageGetItem(page, id)`. [verified-by-code]
- INV-4: Tuple-header offset check at `:227-229`: `t_hoff >=
  SizeofHeapTupleHeader` AND `t_hoff <= lp_len` AND `t_hoff ==
  MAXALIGN(t_hoff)`. Without this, a corrupted `t_hoff` could push
  reads of `t_bits` past the line-pointer extent.
- INV-5: Null-bitmap length is double-checked: `bitmaplen <= t_hoff -
  SizeofHeapTupleHeader` (`:241`). Prevents reading past the t_bits
  region. [verified-by-code]

## Notable internals

**Two-tier validity check.** Line-pointer first (`:202`), then
tuple-header (`:227`). If LP is invalid, columns 4-13 are NULL. If LP
is valid but t_hoff is bogus, columns 4-10 come from the tuple header
but t_bits/oid/raw_data are NULL (`:267-271`). The page-passed-in is
trusted to be exactly BLCKSZ (came from `get_page_from_raw`), so all
checks are local to the in-page offsets.

**Raw tuple-data extraction.** `:256-264`: `tuple_data_len = lp_len -
t_hoff`; `memcpy` into a fresh bytea. This is the surface that exposes
raw tuple bytes — including TOAST pointers — but does NOT follow them.

**`tuple_data_split` is the dangerous one.** The function header
comment (`:299-303`) admits: "This is a reimplementation of
nocachegetattr() in heaptuple.c simplified for educational purposes."
Translation: it walks the attr offsets, computes per-attribute length
from `attlen` / VARSIZE-of-varlena, and `memcpy`'s out bytea slices.
**No input function runs**, so:

- Output bytea is the **on-disk representation**, not the textual /
  cooked SQL value. E.g. a `numeric` comes out as packed-numeric
  bytes, not "123.456".
- This includes columns whose input function would have rejected the
  bytes. So a corrupted `jsonb` column comes out as its raw bytes
  even though `SELECT col FROM t` would `ereport(ERROR)`.
- The comment at `:13-16` ("you'd need to be superuser to obtain a
  raw page image anyway") is the justification — chain-of-trust from
  `get_raw_page`.

**TOAST handling — opt-in, opt-out-by-default.** `:391-392`: only
when `do_detoast=true` AND `attlen == -1` does it call
`pg_detoast_datum_copy()`. If the on-disk varlena is an external
TOAST pointer, this function dereferences it and reads the TOAST
relation. The validity check at `:371-376` rejects non-on-disk-and-
non-indirect external tags (i.e. `EXTERNAL_EXPANDED`, which would be
nonsensical in an on-disk image), but accepts EXTERNAL_ONDISK and
EXTERNAL_INDIRECT pointers.

**`heap_tuple_infomask_flags` is pure decoding.** No relation
access, no buffer reads. Pure bitmask → text[]. The superuser gate
here (`:527`) is paranoia consistency, not a real boundary.

## Trust boundary / Phase D surface

**Chain-of-trust.** All three functions assume the bytea came from
`get_raw_page` and the (relid, t_infomask, t_infomask2, t_bits) came
from `heap_page_items` on the same bytea. The C code does NOT verify
this — a superuser caller can hand `tuple_data_split` a bytea that
doesn't match `relid`'s tupledesc and get back arbitrary slicings of
the input bytes. The `ereport(ERROR, ERRCODE_DATA_CORRUPTED)` paths
(`:336, :374, :387, :410`) catch some shape mismatches but not
semantic ones.

**Type-input bypass via `tuple_data_split`.** `:357-408`. If the
tupledesc says `attr->attlen == -1`, the code reads VARSIZE_ANY off
the bytea, slices that many bytes, and returns. No `byteaout`-style
post-processing. **This is the deliberate "raw bytes interpreted
without type-input safety" canary** the task brief calls out. Even
without TOAST detoasting, this lets a superuser surface bytes that
were previously rejected by INSERT-time validation (a corrupted
column that exists on-disk but errors on SELECT).
**[ISSUE-security: `tuple_data_split` returns raw per-column bytes
without running type-input functions — surfaces bytes that would
normally `ereport(ERROR)` on SELECT (confirmed, by design)]** —
`source/contrib/pageinspect/heapfuncs.c:357-408`.

**TOAST-pointer arbitrary-read primitive.** With `do_detoast=true`,
`tuple_data_split` calls `pg_detoast_datum_copy()` on whatever
external tag is in the bytea. The validation at `:371-376` makes sure
the tag is "on-disk" or "indirect" — but the TOAST OID + chunk_id
inside the pointer are NOT validated against the relation we
opened. **A superuser-crafted bytea + relid combination can make the
detoaster read from a TOAST relation belonging to a different table.**
This is academic for an actual superuser (they can SELECT directly)
but matters if someone wraps this in SECDEF.
**[ISSUE-security: `do_detoast=true` follows attacker-controlled
TOAST pointers without cross-checking they belong to `relid`'s TOAST
relation — arbitrary cross-table read primitive (likely; would need
SECDEF wrapper to exploit, since base function is superuser-only)]**
— `source/contrib/pageinspect/heapfuncs.c:391-392`.

**Bounds checks against malicious bytea (good).** `:202-205` and
`:227-229` are exhaustive against in-page offsets. `:386-389`:
"unexpected end of tuple data" if `tupdata_len < off + len`.
`:410-413`: "end of tuple reached without looking at all its data"
catches the inverse (extra bytes). A handcrafted bytea cannot trick
the decoder into reading past its end. Heap-tuple-decoder buffer
overflow is well-defended.

**Null bitmap parse.** `text_to_bits` at `:86-114` accepts only
'0'/'1' bytes and `ereport(ERROR)`s on any other char. Length is
double-checked at `:474` against `BITMAPLEN(t_infomask2 &
HEAP_NATTS_MASK) * 8`. No multi-byte UB.

**HEAP_NATTS check.** `:333` rejects `nattrs <
(t_infomask2 & HEAP_NATTS_MASK)` — i.e. tuple header claims more
attrs than tupledesc. The opposite direction (fewer in header) is
treated as ALTER-TABLE-ADD-COLUMN-without-default → trailing NULLs
(`:346-355`). Reasonable, but means a maliciously-low `t_infomask2`
silently truncates output.

**CONCURRENTLY-built index.** N/A — heapfuncs operates on heap pages,
not indexes.

**Auto-vacuum interaction.** N/A — no AccessShareLock on the table.
The bytea is already detached. `tuple_data_split` does
`relation_open(relid, AccessShareLock)` (`:319`) to get a tupledesc
but the tupledesc could disagree with the bytea's actual on-disk
layout if the relation has been ALTERed since the bytea was captured.
**[ISSUE-correctness: between `get_raw_page` and `tuple_data_split`,
ALTER TABLE could change the tupledesc; results decode against the
*current* desc, not the desc at page-capture time (nit, expected)]**.

## Cross-references

- `source/src/include/access/htup_details.h` — HeapTupleHeaderData,
  HEAP_HASNULL/HEAP_HASEXTERNAL/HEAP_XMIN_FROZEN flags decoded at
  `:552-611`.
- `source/src/backend/access/common/heaptuple.c` — `nocachegetattr`,
  the function `tuple_data_split` simplifies.
- `source/src/backend/utils/adt/varlena.c` — `pg_detoast_datum_copy`,
  the TOAST follower at `:392`.
- `knowledge/files/contrib/pageinspect/pageinspect.md` — the upstream
  `get_raw_page` source for the bytea consumed here.
- `knowledge/files/contrib/amcheck/` — amcheck performs deep heap-AM
  invariant checks; pageinspect is the *reading* surface, amcheck
  the *verifying* surface. Complementary.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: `tuple_data_split` bypasses type-input
  validation — known canary for "raw bytes surfaced without per-type
  checks" (confirmed, by design but high-value Phase D entry)]** —
  `source/contrib/pageinspect/heapfuncs.c:357-408`.
- **[ISSUE-security: `do_detoast=true` follows
  attacker-controlled TOAST pointers; no cross-check that the
  pointer's `va_toastrelid` matches `relid`'s TOAST relation (likely;
  requires SECDEF delegation to exploit)]** —
  `source/contrib/pageinspect/heapfuncs.c:391-392`.
- **[ISSUE-correctness: tupledesc fetched fresh at decode time can
  disagree with the bytea's ALTER-TABLE-pre-image layout (nit, no
  silent corruption but confusing output)]** —
  `source/contrib/pageinspect/heapfuncs.c:319-323`.
- **[ISSUE-defense-in-depth: `heap_tuple_infomask_flags` requires
  superuser despite touching no relation or buffer; this is
  consistency, not a real boundary (nit)]** —
  `source/contrib/pageinspect/heapfuncs.c:527-530`.
- **[ISSUE-correctness: `t_infomask2 & HEAP_NATTS_MASK` lower than
  tupdesc natts silently truncates to ADD-COLUMN-style NULL fill
  (maybe)]** — `source/contrib/pageinspect/heapfuncs.c:346-355`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pageinspect.md](../../../subsystems/contrib-pageinspect.md)
