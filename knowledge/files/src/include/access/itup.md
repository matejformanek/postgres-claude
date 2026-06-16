# `access/itup.h` — IndexTuple on-disk format + accessors

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/itup.h`)

## Role
Defines the on-disk IndexTupleData header (TID + 16-bit info word) plus
the format conventions for the optional null-bitmap and the attribute
payload. Provides `index_getattr` (inline) and `index_form_tuple` /
`index_deform_tuple` for round-tripping between Datum array and
on-disk form.

## Public API
- `IndexTupleData` struct (`itup.h:35`): `t_tid` (ItemPointer to heap row)
  + `t_info` (uint16 bit-packed: 1 bit hasNulls, 1 bit hasVarwidths, 1 bit
  AM-reserved, 13 bits size).
- `IndexAttributeBitMapData` (`itup.h:55`) — fixed-size null bitmap sized
  for `INDEX_MAX_KEYS` (default 32). Note: size does **not** vary with
  natts.
- `INDEX_SIZE_MASK = 0x1FFF`, `INDEX_AM_RESERVED_BIT = 0x2000`,
  `INDEX_VAR_MASK = 0x4000`, `INDEX_NULL_MASK = 0x8000`
  (`itup.h:65`-`69`).
- `IndexTupleSize(itup)` (`itup.h:71`).
- `IndexTupleHasNulls(itup)` (`itup.h:77`).
- `IndexTupleHasVarwidths(itup)` (`itup.h:83`).
- `index_form_tuple(tupleDescriptor, values, isnull)` (`itup.h:91`).
- `index_form_tuple_context(tupleDescriptor, values, isnull, context)`
  (`itup.h:93`).
- `nocache_index_getattr(tup, attnum, tupleDesc)` (`itup.h:96`).
- `index_deform_tuple(tup, tupleDesc, values, isnull)` (`itup.h:98`).
- `index_deform_tuple_internal(...)` (`itup.h:100`).
- `CopyIndexTuple(source)` (`itup.h:103`).
- `index_truncate_tuple(sourceDescriptor, source, leavenatts)` (`itup.h:104`).
- `IndexInfoFindDataOffset(t_info)` (`itup.h:112`) — returns 0-attr offset
  past header (and bitmap if hasNulls).
- `index_getattr(tup, attnum, tupleDesc, isnull)` (`itup.h:131`) — inline
  hot-path with attcacheoff shortcut.
- `MaxIndexTuplesPerPage` macro (`itup.h:182`).

## Invariants
- `INDEX_SIZE_MASK = 0x1FFF` — **size field caps an index tuple at 8191
  bytes** (13 bits). `[verified-by-code]` (`itup.h:65`).
- Bit 13 (`INDEX_AM_RESERVED_BIT`) is **AM-defined**; e.g., btree uses it
  for the pivot-tuple flag. `[from-comment]` (`itup.h:66`-`67`).
- Null bitmap is fixed-size at `INDEX_MAX_KEYS` bits (`itup.h:30`-`32`) —
  not variable. Saves a header byte but wastes a few bytes for sparse
  indexes. `[from-comment]`.
- Data begins at MAXALIGN(sizeof(IndexTupleData) + optional bitmap) —
  `IndexInfoFindDataOffset` does this math. `[verified-by-code]`
  (`itup.h:112`-`119`).
- `index_getattr` is FRONTEND-disabled (uses fmgr / tupdesc). `[from-comment]`
  (`itup.h:121`).
- `MaxIndexTuplesPerPage` does not include special space; conservative.
  `[from-comment]` (`itup.h:175`-`180`).
- For btree non-leaf pages, the first tuple has no key — breaks the
  "at least 1 byte bigger" assumption, but always offset by special-space.
  `[from-comment]` (`itup.h:176`-`180`).

## Notable internals
- Index tuple = `IndexTupleData` (8 bytes: 6-byte TID + 2-byte info) +
  optional `IndexAttributeBitMapData` (4 bytes for INDEX_MAX_KEYS=32) +
  MAXALIGNed attribute data.
- The 8191-byte cap is well below `BLCKSZ` (8192) — by design, an index
  tuple must fit on a page.
- `index_form_tuple_context` lets the caller pick the memory context
  (introduced for the deduplication path).

## Trust-boundary / Phase D surface

The 16-bit info word is the load-bearing trust point: any code reading an
index page must trust `t_info` to compute boundaries.

**[ISSUE-correctness: a corrupted `t_info` with size=0 trips infinite scan loops
(low)]** — Callers that advance by `IndexTupleSize(itup)` and land on a
zero-size tuple loop forever. Defenders: page-level sanity checks (in
`bufpage.c`), amcheck. `itup.h:65`-`75`.

**[ISSUE-correctness: hasNulls bit set with bogus bitmap → OOB read in
`att_isnull` (low)]** — If `t_info & INDEX_NULL_MASK` is set but the bitmap
is corrupt (or the tuple was crafted to claim hasNulls without bitmap
storage), `index_getattr` reads `(uint8 *)tup + sizeof(IndexTupleData)`
as the bitmap. `itup.h:154`. Defense: amcheck validates this; on-page
sanity in `_bt_check_natts` etc.

**[ISSUE-resource: 8191-byte index-tuple cap is an attacker-supplied bound
(informational)]** — A 13-bit size field caps the tuple, but `index_form_tuple`
ereports on overflow (caller's path). Reading code must defend if the
tuple came from disk. `itup.h:65`.

**[ISSUE-api-shape: null bitmap fixed-size at INDEX_MAX_KEYS (informational)]** —
Compile-time constant (default 32). Changing INDEX_MAX_KEYS requires
rebuilding everything against the new header — no catversion guard.
`itup.h:30`-`32`, `:55`-`58`.

## Cross-refs
- `knowledge/files/src/include/access/tupmacs.h` — `att_isnull`, `fetchatt`
  used by `index_getattr`.
- `knowledge/files/src/include/access/itup.h` (this file).
- `knowledge/subsystems/access-nbtree.md` (not yet written) — btree consumer.
- A14 amcheck: validates IndexTuple structure on-page.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-correctness: size=0 in corrupted t_info loops scans (low)]**
   — `itup.h:65`-`75`.
2. **[ISSUE-correctness: hasNulls-without-bitmap OOB read (low)]**
   — `itup.h:154`.
3. **[ISSUE-resource: 8191-byte cap is disk-trust boundary (informational)]**
   — `itup.h:65`.
4. **[ISSUE-api-shape: INDEX_MAX_KEYS=32 compile-time, no catversion guard (informational)]**
   — `itup.h:30`-`32`, `:55`-`58`.
