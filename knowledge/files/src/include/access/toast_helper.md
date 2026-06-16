# `access/toast_helper.h` — TOAST insert/update state machine

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/toast_helper.h`)

## Role
Helper functions and state for table AMs implementing compressed/out-of-line
varlena storage. Drives the per-column decisions inside
`heap_toast_insert_or_update`: which attrs to compress, which to move
out of line, which to leave alone.

## Public API
- `ToastAttrInfo` struct (`toast_helper.h:30`): `tai_oldexternal` (the
  previous external pointer, for UPDATE), `tai_size`, `tai_colflags`,
  `tai_compression` (method code).
- `ToastTupleContext` struct (`toast_helper.h:41`): `ttc_rel`, `ttc_values`,
  `ttc_isnull`, `ttc_oldvalues`, `ttc_oldisnull`, `ttc_flags`, `ttc_attr`
  (parallel array of ToastAttrInfo, length = natts).
- Tuple-level flags (`toast_helper.h:78`-`81`): `TOAST_NEEDS_DELETE_OLD`,
  `TOAST_NEEDS_FREE`, `TOAST_HAS_NULLS`, `TOAST_NEEDS_CHANGE`.
- Column-level flags (`toast_helper.h:99`-`102`): `TOASTCOL_NEEDS_DELETE_OLD`,
  `TOASTCOL_NEEDS_FREE`, `TOASTCOL_IGNORE`, `TOASTCOL_INCOMPRESSIBLE`.
- `toast_tuple_init(ttc)` (`toast_helper.h:104`).
- `toast_tuple_find_biggest_attribute(ttc, for_compression, check_main)`
  (`toast_helper.h:105`).
- `toast_tuple_try_compression(ttc, attribute)` (`toast_helper.h:108`).
- `toast_tuple_externalize(ttc, attribute, options)` (`toast_helper.h:109`).
- `toast_tuple_cleanup(ttc)` (`toast_helper.h:111`).
- `toast_delete_external(rel, values, isnull, is_speculative)`
  (`toast_helper.h:113`).

## Invariants
- `tai_size` is **only valid** for varlena attrs whose `toast_action` is
  neither `' '` (default) nor `TYPSTORAGE_PLAIN`. Reading it for a PLAIN
  column is undefined. `[from-comment]` (`toast_helper.h:27`-`28`).
- Caller must populate `ttc_values`, `ttc_isnull`, `ttc_oldvalues`,
  `ttc_oldisnull`, `ttc_attr` before `toast_tuple_init`. For an INSERT
  (no old tuple), `ttc_oldvalues` and `ttc_oldisnull` are NULL.
  `[from-comment]` (`toast_helper.h:43`-`53`).
- `ttc_attr` array length must equal `ttc_rel->rd_att->natts`. `[from-comment]`
  (`toast_helper.h:45`-`46`).
- Column-level `_NEEDS_DELETE_OLD` and `_NEEDS_FREE` numerical values
  intentionally **match** tuple-level versions (so they can be OR'd
  together). `[verified-by-code]` (`toast_helper.h:99`-`100`).

## Notable internals
- `tai_colflags` is a `uint8` bitmask; with 4 defined flags there's room
  for more (`TOASTCOL_INCOMPRESSIBLE` = 0x20).
- The state machine: init → find_biggest → try_compression OR externalize
  → repeat until below target → cleanup.
- `toast_tuple_find_biggest_attribute` is the cost-driver: O(natts) per
  iteration, and the toast loop runs until under TOAST_TUPLE_TARGET.

## Trust-boundary / Phase D surface

State-machine helpers, not directly attacker-facing. They consume a
prepared `ToastTupleContext` that the caller assembled from a tuple
about to be written.

**[ISSUE-correctness: caller must size `ttc_attr` to `natts`; no Assert (low)]** —
A miswritten table AM could allocate a short array. The helper functions
will read past it. `toast_helper.h:55`-`62`. Mitigation: callers in heap
always go through `heap_toast_insert_or_update` which sets up the context
correctly.

**[ISSUE-memory: TOAST_NEEDS_FREE / TOASTCOL_NEEDS_FREE requires manual cleanup
(low)]** — `toast_tuple_cleanup` must be called or compressed datums leak
in CurrentMemoryContext. `toast_helper.h:71`, `:111`.

## Cross-refs
- `knowledge/files/src/include/access/heaptoast.h` —
  `heap_toast_insert_or_update` is the canonical caller.
- `knowledge/files/src/include/access/toast_internals.h` —
  `toast_compress_datum`, `toast_save_datum` are the workhorses underneath.
- `knowledge/idioms/memory-contexts.md` (not yet written) — TOAST temp
  allocations.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-correctness: ttc_attr size contract is documented-only (low)]**
   — `toast_helper.h:55`-`62`.
2. **[ISSUE-memory: cleanup required to avoid leaks (low)]**
   — `toast_helper.h:71`, `:111`.
