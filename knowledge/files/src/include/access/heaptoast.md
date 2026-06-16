# `access/heaptoast.h` — heap-side TOAST insert/delete + threshold macros

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/heaptoast.h`)

## Role
The heap AM's TOAST entry points (`heap_toast_insert_or_update`,
`heap_toast_delete`, `heap_fetch_toast_slice`) plus the per-page tuple-count
arithmetic that picks the TOAST threshold and chunk size.

## Public API
- `MaximumBytesPerTuple(tuplesPerPage)` macro (`heaptoast.h:23`) — given
  N tuples-per-page, returns the largest tuple body size that fits.
- `TOAST_TUPLES_PER_PAGE = 4` (`heaptoast.h:46`); `TOAST_TUPLE_THRESHOLD` and
  `TOAST_TUPLE_TARGET` derived from it (`heaptoast.h:48`-`50`).
- `TOAST_TUPLES_PER_PAGE_MAIN = 1` (`heaptoast.h:59`);
  `TOAST_TUPLE_TARGET_MAIN` used when the toaster considers moving MAIN
  storage out of line (`heaptoast.h:61`).
- `TOAST_INDEX_TARGET = MaxHeapTupleSize / 16` (`heaptoast.h:68`).
- `EXTERN_TUPLES_PER_PAGE = 4` (`heaptoast.h:80`); `EXTERN_TUPLE_MAX_SIZE`
  and `TOAST_MAX_CHUNK_SIZE` derive from it (`heaptoast.h:82`-`89`).
- `heap_toast_insert_or_update(rel, newtup, oldtup, options)` (`heaptoast.h:97`).
- `heap_toast_delete(rel, oldtup, is_speculative)` (`heaptoast.h:106`).
- `toast_flatten_tuple(tup, tupleDesc)` (`heaptoast.h:116`).
- `toast_flatten_tuple_to_datum(tup, tup_len, tupleDesc)` (`heaptoast.h:124`).
- `toast_build_flattened_tuple(tupleDesc, values, isnull)` (`heaptoast.h:135`).
- `heap_fetch_toast_slice(toastrel, valueid, attrsize, sliceoffset,
  slicelength, result)` (`heaptoast.h:145`).

## Invariants
- `TOAST_TUPLES_PER_PAGE` and `EXTERN_TUPLES_PER_PAGE` are both **4** — the
  numbers must not be modified without considering `needs_toast_table()`
  in `toasting.c` (and `EXTERN_TUPLES_PER_PAGE` change requires `initdb`).
  `[from-comment]` (`heaptoast.h:41`-`44`, `:78`).
- `TOAST_TUPLE_TARGET ≤ TOAST_TUPLE_THRESHOLD` — TARGET can be smaller, but
  larger is meaningless. `[from-comment]` (`heaptoast.h:34`-`36`).
- `TOAST_INDEX_TARGET` is per-datum (NOT per-tuple) for `index_form_tuple`
  simplicity. `[from-comment]` (`heaptoast.h:64`-`66`).
- `TOAST_MAX_CHUNK_SIZE` is derived to fit `EXTERN_TUPLES_PER_PAGE=4`
  tuples per toast page; changing it requires `initdb` because existing
  on-disk toast chunks would have a different size. `[from-comment]`
  (`heaptoast.h:70`-`78`).
- `heap_fetch_toast_slice` callers must validate `valueid`+`attrsize`
  against the on-disk toast pointer before invoking — see below.
  `[verified-by-code]` (caller pattern in `detoast.c`).

## Notable internals
- The toast pipeline is: large tuple → try compression on EXTENDED/EXTERNAL
  columns → if still oversize, move them out-of-line via toast_save_datum
  → if STILL oversize, try MAIN columns out-of-line (last resort, target
  is the larger `TOAST_TUPLE_TARGET_MAIN`).
- A single toast chunk is at most `TOAST_MAX_CHUNK_SIZE` bytes, with
  4 chunks per toast page typical.
- `MaxHeapTupleSize` is defined in `htup_details.h`; `TOAST_INDEX_TARGET`
  = 1/16 of it = ~512 bytes on default BLCKSZ.

## Trust-boundary / Phase D surface

This header sits on top of two cross-corpus Phase-D hot spots:

**[ISSUE-security: `heap_fetch_toast_slice(valueid, attrsize, sliceoffset, slicelength)`
trusts the on-disk toast pointer (medium)]** — The function is called with
`valueid` extracted from a tuple's `varatt_external` pointer. If a malicious
or corrupted page presents a forged `valueid` pointing to a different
relation's toast table, the function will dutifully fetch chunks from
wherever the toast index says. The trust is *expected* to be enforced by
the caller (the detoast path), but at the API layer there's no cross-check
that `valueid` "belongs to" `toastrel`. `heaptoast.h:145`-`147`.
Cross-corpus: A12 `tuple_data_split(do_detoast=true)` is a documented
cross-table read primitive exploiting precisely this boundary.

**[ISSUE-resource: TOAST decompression has no input-size cap at this header
level (medium)]** — `heap_fetch_toast_slice` returns chunks; decompression
happens at the `detoast.h` layer (pglz / lz4). No per-tuple total size cap
visible here — decompression bomb echo of A11 (pgcrypto pgp-decompression
bomb) and A5 (pg_lzcompress no-cap). `heaptoast.h:145`-`147`.

**[ISSUE-correctness: `TOAST_MAX_CHUNK_SIZE` change requires initdb but is
not enforced (low)]** — A user-built PG with modified `EXTERN_TUPLES_PER_PAGE`
and an old datadir from a stock PG will silently mis-size chunks. No
catversion check covers this. `heaptoast.h:78`. Documented but not
catalog-enforced.

## Cross-refs
- `knowledge/files/src/include/access/toast_helper.h` — insert/update
  state machine.
- `knowledge/files/src/include/access/toast_internals.h` — chunk format
  + compression header.
- `knowledge/files/src/include/access/tableam.h` —
  `relation_fetch_toast_slice` callback (custom AM may use a different
  toast layout).
- A12 corpus finding: `tuple_data_split(do_detoast=true)` cross-table
  read primitive lands here.
- A11 + A5 corpus findings: decompression-bomb echoes.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-security: heap_fetch_toast_slice trusts caller-supplied valueid (medium)]**
   — `heaptoast.h:145`-`147`.
2. **[ISSUE-resource: no input-size cap at API surface for decompression (medium)]**
   — `heaptoast.h:145`-`147`.
3. **[ISSUE-correctness: TOAST_MAX_CHUNK_SIZE initdb-only enforcement (low)]**
   — `heaptoast.h:78`.
