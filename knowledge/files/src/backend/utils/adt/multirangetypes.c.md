# `src/backend/utils/adt/multirangetypes.c`

- **File:** `source/src/backend/utils/adt/multirangetypes.c` (3002 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O and operators for **multirange types** (PG14+). A multirange is an
ordered, non-overlapping collection of ranges over the same subtype;
the on-disk varlena packs them sorted and merged so that adjacency
invariants hold permanently.

Functions: `multirange_in`/`out`/`recv`/`send`, constructors
(`int4multirange()`, `int4multirange(int4range)`, …), set operations
(`multirange_union`, `multirange_intersect`, `multirange_minus`),
predicates against ranges and multiranges (`@>`, `<@`, `&&`),
aggregate transitions (`range_agg`, `multirange_intersect_agg`), plus
conversions to/from arrays.

## Key functions

### I/O

- `multirange_in(str, mltrngtypoid, typmod)` (`:116-296`) — accepts
  the `{r1, r2, ...}` text format. State machine over five states
  (`MULTIRANGE_BEFORE_RANGE`, `IN_RANGE`, `IN_RANGE_QUOTED`,
  `IN_RANGE_ESCAPED`, `IN_RANGE_QUOTED_ESCAPED`, `AFTER_RANGE`,
  `FINISHED`). Grows a `RangeType**` array by doubling capacity
  (`:201-206`), starting at 8 (`:126`). Each captured range substring
  is `pnstrdup`'d and fed to the range type's input function via
  `InputFunctionCallSafe`. **No `check_stack_depth()` directly here**
  — relies on the recursive `range_in` call which has one.
  [verified-by-code]
- `multirange_out` (`:298-330`) — emits `{` then comma-joined
  range_out results then `}`. [verified-by-code]
- `multirange_recv(buf, mltrngtypoid, typmod)` (`:336-375`) — wire
  format is `int32 range_count` then `range_count × (int32 range_len,
  range_bytes)`. **`palloc_array(RangeType *, range_count)` at `:352`**
  relies on the comment "palloc_array will enforce a more-or-less-sane
  range_count value" — i.e. attacker-supplied count is bounded only
  by `MaxAllocSize / sizeof(RangeType*)` ≈ 134M pointers, but each
  iteration also consumes input bytes so the total is bounded by the
  message length. [verified-by-code]
- `multirange_send` (`:377-409`) — reverse of recv. [verified-by-code]

### Constructors + merge

- `make_multirange(mltrngtypoid, rngtyp, range_count, ranges)`
  (further down, ~`:850+`) — sorts ranges, merges overlapping
  adjacent ones, drops empties. The post-condition: the stored
  ranges are pairwise-disjoint, sorted ascending, and non-adjacent
  (subject to the type's canonical function).
- `multirange_serialize` / `multirange_deserialize` — the varlena
  marshallers; deserialize returns a `RangeType **` array and count.
- `multirange_constructor*` aggregate transition (`:946-1025`) — the
  array-style `multirange(VARIADIC anyrange[])` form.

### Set ops

- `multirange_union` (`:1064+`), `multirange_intersect` (`:1306-1335`)
  with internal helper `multirange_intersect_internal` (`:1337+`),
  `multirange_minus` (`:1416+`). All maintain the disjoint-sorted
  invariant via `make_multirange` post-processing.
- `multirange_intersect_agg_transfn` (`:1542-1582`) and other
  aggregate functions support `range_agg`/`multirange_agg`.

## Phase D notes

- **Parser invariants**: the state machine doesn't enforce a maximum
  number of ranges; `range_capacity` doubles up to OOM. A pathological
  input like `{[1,2),[3,4),...}` with 100M tiny ranges would consume
  proportional memory before parsing completes. Bounded by the
  per-statement memory context.
- **Recursion depth**: `multirange_in` does NOT call
  `check_stack_depth()` itself; relies on `range_in`'s check. Each
  parsed range invokes `range_in` once via fmgr, so depth is bounded
  by the per-range recursion (range-of-range subtype). [verified-by-code]
- **`multirange_recv` wire-count trust**: `palloc_array(RangeType *,
  range_count)` at `:352` doesn't pre-validate that `range_count`
  matches the available buffer bytes; if attacker says 2^30 but only
  sends data for 5, the palloc succeeds but the per-iteration
  `pq_getmsgint(buf, 4)` will eventually hit end-of-message and
  ereport. Memory pressure is the real concern. [verified-by-code]
- **Union/intersect/minus**: post-merge via `make_multirange` ensures
  disjointness; no mid-operation states can leak. [inferred]

## Potential issues

- [ISSUE-dos: `multirange_recv` allocates `RangeType*[range_count]`
  from a 4-byte wire-supplied count before consuming any range
  bytes; up to ~134M pointers (~1 GB) can be palloc'd from a
  6-byte message before the per-iteration message-bounds check fires
  (low)]
- [ISSUE-dos: `multirange_in` parser doubles `range_capacity` without
  cap; a 100MB input could allocate proportional memory before parse
  completes (low)]
- [ISSUE-undocumented-invariant: the post-`make_multirange`
  disjoint-sorted-non-adjacent invariant is the contract every
  operator and `multirange_deserialize` relies on; not asserted at
  runtime in non-debug builds (maybe)]

## Cross-references

- `source/src/include/utils/multirangetypes.h` — `MultirangeType`,
  `MultirangeIOData`.
- `source/src/backend/utils/adt/rangetypes.c` — `range_in`/`out`/
  `recv`/`send` are called from here.
- `source/src/backend/utils/cache/typcache.c` —
  `TypeCacheEntry.rngtype` linkage from multirange to its element
  range type.

## Confidence tag tally
- `[verified-by-code]` × 7
- `[from-comment]` × 1
- `[inferred]` × 1
