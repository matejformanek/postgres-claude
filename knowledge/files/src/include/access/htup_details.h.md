# htup_details.h

- **Source path:** `source/src/include/access/htup_details.h`
- **Lines:** 909
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `htup.h` (forward typedefs), `heapam_visibility.c` (consumes the infomask bits), `combocid.c` (cmin/cmax helpers)

## Purpose

Defines the on-disk layout of a heap tuple's fixed header (`HeapTupleHeaderData`), the parallel layout for executor-internal `MinimalTupleData`, all `HEAP_*` infomask/infomask2 bit constants, and the static-inline accessor functions used pervasively across the backend. This file is the single source of truth for "what bits mean what on a tuple". [from-comment, htup_details.h:3-13]

## Top-of-file comment
> "POSTGRES heap tuple header definitions." Plus a 70-line struct-level comment block at lines 51-120 explaining the 23-byte header layout, the xmin/cmin/xmax/cmax/xvac overlay trick, the `t_ctid` chain-following rules, the speculative-insertion token, and the nulls-bitmap convention. [from-comment, htup_details.h:50-120]

## Public surface (key groups)

**Compile-time limits:**
- `MaxTupleAttributeNumber = 1664`, `MaxHeapAttributeNumber = 1600`. [verified-by-code, htup_details.h:34, 48]
- `MaxHeapTupleSize = BLCKSZ - MAXALIGN(SizeOfPageHeaderData + sizeof(ItemIdData))`. [verified-by-code, htup_details.h:601]
- `MaxHeapTuplesPerPage` — uses MAXALIGN(SizeofHeapTupleHeader) + ItemId per tuple. [verified-by-code, htup_details.h:615-617]

**`t_infomask` bits (low byte = data shape, high byte = visibility):**
- `HEAP_HASNULL 0x0001`, `HEAP_HASVARWIDTH 0x0002`, `HEAP_HASEXTERNAL 0x0004` (toasted), `HEAP_HASOID_OLD 0x0008`. [verified-by-code, htup_details.h:190-193]
- Lock bits: `HEAP_XMAX_KEYSHR_LOCK 0x0010`, `HEAP_XMAX_EXCL_LOCK 0x0040`, `HEAP_XMAX_LOCK_ONLY 0x0080`. Combined `HEAP_XMAX_SHR_LOCK = EXCL|KEYSHR`. [verified-by-code, htup_details.h:194-203]
- `HEAP_COMBOCID 0x0020` — t_cid is a combo. [verified-by-code, htup_details.h:195]
- Visibility hint bits: `HEAP_XMIN_COMMITTED 0x0100`, `HEAP_XMIN_INVALID 0x0200`, `HEAP_XMIN_FROZEN = both = 0x0300`, `HEAP_XMAX_COMMITTED 0x0400`, `HEAP_XMAX_INVALID 0x0800`. [verified-by-code, htup_details.h:204-208]
- `HEAP_XMAX_IS_MULTI 0x1000`, `HEAP_UPDATED 0x2000`, `HEAP_MOVED_OFF/IN 0x4000/0x8000` (pre-9.0 VACUUM FULL, kept for pg_upgrade). [verified-by-code, htup_details.h:209-217]

**`t_infomask2` bits:**
- Low 11 bits (`HEAP_NATTS_MASK 0x07FF`) = number of attributes. [verified-by-code, htup_details.h:291]
- `HEAP_KEYS_UPDATED 0x2000`, `HEAP_HOT_UPDATED 0x4000`, `HEAP_ONLY_TUPLE 0x8000`. [verified-by-code, htup_details.h:293-296]
- Hash-join scratch overlay: `HEAP_TUPLE_HAS_MATCH = HEAP_ONLY_TUPLE`. [verified-by-code, htup_details.h:306]

**Accessors (static inline):** Get/Set RawXmin, Xmin, RawXmax, Xmax, UpdateXid; XminCommitted/Invalid/Frozen; SetXminFrozen; SetCmin/SetCmax; GetXvac/SetXvac; speculative-token helpers; IsHotUpdated/SetHotUpdated/ClearHotUpdated; IsHeapOnly. [verified-by-code, htup_details.h:312-561]

**Tuple-level inline helpers:** `HeapTupleHasNulls`, `HeapTupleHasExternal`, `HeapTupleIsHotUpdated`, `HeapTupleIsHeapOnly`, `GETSTRUCT(tuple)` returns `(char *) tuple->t_data + tuple->t_data->t_hoff`. [verified-by-code, htup_details.h:716-792]

**Attribute fetch fast path:** `fastgetattr` (inline) and `heap_getattr` (inline) — the hot loop of nearly every executor expression. [verified-by-code, htup_details.h:851-906]

**Externs implemented in `common/heaptuple.c`:** `heap_form_tuple`, `heap_deform_tuple`, `heap_modify_tuple`, `heap_copytuple`, `heap_freetuple`, plus the MinimalTuple equivalents. [verified-by-code, htup_details.h:794-836]

## Key types / structs

- `HeapTupleFields` (htup_details.h:122) — `t_xmin`, `t_xmax`, union(`t_cid` | `t_xvac`).
- `DatumTupleFields` (htup_details.h:134) — overlay used when a heap tuple is acting as a composite Datum (varlena header + typmod + typeid).
- `HeapTupleHeaderData` (htup_details.h:153) — 23 fixed bytes: choice-union, `t_ctid`, `t_infomask2`, `t_infomask`, `t_hoff`, then null-bitmap `t_bits[]`. Fields below `t_infomask2` MUST match `MinimalTupleData`. [from-comment, htup_details.h:164]
- `MinimalTupleData` (htup_details.h:667) — `t_len` + padding chosen so `t_infomask2` lines up with the heap header layout; lets executor-internal tuples be accessed through a `HeapTupleHeader*` pointer set `MINIMAL_TUPLE_OFFSET` bytes before the actual struct. [from-comment, htup_details.h:629-665]

## Key invariants and locking

- **Visibility-bit semantics are hints, not authoritative.** `HEAP_XMIN_COMMITTED|HEAP_XMIN_INVALID` (both set) is reused to encode the frozen state. [from-comment, htup_details.h:204-206]
- `HEAP_XMAX_IS_LOCKED_ONLY(im)` returns true if `HEAP_XMAX_LOCK_ONLY` is set, OR if xmax is non-multi and only `HEAP_XMAX_EXCL_LOCK` is set (a pg_upgrade legacy form). [verified-by-code, htup_details.h:229-234]
- `HEAP_LOCKED_UPGRADED(im)` detects a 9.2-era share-lock-only multixact that survived pg_upgrade; such multixacts must not be resolved locally because they may reference XIDs outside the current valid multixact range. [from-comment, htup_details.h:237-261]
- The `t_ctid` self-pointing-or-XMAX-invalid invariant is the rule for "this is the latest version". Following a `t_ctid` chain requires checking that the referenced slot is non-empty AND that the referenced tuple's `xmin` equals the referencing tuple's `xmax` — VACUUM can reclaim the newer tuple before the older. [from-comment, htup_details.h:86-103] **This is the single most-cited invariant for any code that walks update chains.**
- `t_ctid` can also carry a speculative-insertion token (offset = `SpecTokenOffsetNumber`) — never seen on UPDATE chains, only on still-inserting tuples. [from-comment, htup_details.h:105-112]
- `t_hoff` must be MAXALIGN'd. [from-comment, htup_details.h:118-119]
- Cmin/Cmax/Xvac all share one 4-byte slot; combo CIDs handled by `combocid.c`. [from-comment, htup_details.h:73-84]

## Functions of note

- `HeapTupleHeaderGetXmin(tup)` (htup_details.h:328) — returns `FrozenTransactionId` if `HEAP_XMIN_FROZEN`, else raw xmin. Modern code; pre-9.4 actually overwrote xmin to FrozenXid, and such tuples may still be on disk. [from-comment, htup_details.h:314-321]
- `HeapTupleHeaderGetUpdateXid(tup)` (htup_details.h:387) — resolves multi if `XMAX_IS_MULTI` is set without `XMAX_LOCK_ONLY`, by calling `HeapTupleGetUpdateXid` (in `heapam.c`); otherwise returns raw xmax. Comment warns this may force multixact I/O. [from-comment, htup_details.h:380-386]
- `HeapTupleHeaderIsHotUpdated(tup)` (htup_details.h:524) — three-part check: `HEAP_HOT_UPDATED` AND `!HEAP_XMAX_INVALID` AND `!HeapTupleHeaderXminInvalid`. The HOT chain is auto-broken when the updating xact aborts. [from-comment, htup_details.h:519-523]
- `fastgetattr` (htup_details.h:851) — null-fast-path attribute fetch using `attcacheoff`; falls back to `nocachegetattr`. The "hot inner loop" of tuple deconstruction. [verified-by-code]

## Cross-references

- **Consumers:** every visibility check in `heapam_visibility.c`, every tuple modification in `heapam.c`, every catalog read in `utils/cache/*`, every executor expression eval. Effectively universal.
- **Implementations of declared externs:** `common/heaptuple.c` (form/deform), `combocid.c` (Cmin/Cmax with combo handling), `heapam.c` (`HeapTupleGetUpdateXid`).

## Open questions

- The exact alignment story for `MINIMAL_TUPLE_PADDING` on platforms with `MAXIMUM_ALIGNOF != 8` is non-trivial; the macro arithmetic is correct but I did not enumerate every alignof case. [unverified]
- Whether any modern code path can still produce a tuple with `HEAP_MOVED_*` (pre-9.0 VACUUM FULL) — comments suggest only legacy on-disk data. [unverified]

## Confidence tag tally
`[verified-by-code]=18 [from-comment]=11 [from-readme]=0 [inferred]=0 [unverified]=2`
