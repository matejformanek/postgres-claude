# `src/include/utils/tuplesort.h`

- **File:** `source/src/include/utils/tuplesort.h` (447 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Public interface for the generalized tuple-sort engine implemented across
`tuplesort.c` (engine) and `tuplesortvariants.c` (per-variant glue).
Declares the lifecycle API, the per-variant constructors, and the public
data types `Tuplesortstate` / `Sharedsort` / `SortCoordinate` / `SortTuple`
/ `TuplesortPublic`. (`tuplesort.h:1-19` [from-comment])

## Opaque types

- **`Tuplesortstate`** (`:40`) and **`Sharedsort`** (`:41`) are
  forward-declared; their innards live in `tuplesort.c`. Variants reach
  the public sub-struct via `TuplesortstateGetPublic(state)` (`:227`).

## Bit flags (`TUPLESORT_*`)

- `TUPLESORT_NONE = 0` (`:67`).
- `TUPLESORT_RANDOMACCESS = 1<<0` (`:70`) — required for rescan, markpos,
  backward gettuple. **Disallowed under parallel sort** (asserted in
  `tuplesort_begin_common`).
- `TUPLESORT_ALLOWBOUNDED = 1<<1` (`:73`) — also drives the choice of
  tuple memory context: bounded → AllocSet (so individual pfree works),
  non-bounded → BumpContext (cheaper, no individual free). See
  `TupleSortUseBumpTupleCxt(opt)` macro at `:82`.

## Key types

- **`SortCoordinateData`** (`:48-62`) — parallel-sort handshake struct.
  Per-process; holds `isWorker`, `nParticipants` (leader sets, workers
  pass `-1`), and a pointer to the DSM-resident `Sharedsort`.
- **`SortTuple`** (`:114-121`) — the in-memory element type:
  `{ void *tuple; Datum datum1; bool isnull1; uint8 curbyte; int srctape; }`.
  `datum1` caches the leading sort key (or its abbreviated proxy) to
  skip `heap_getattr` on every compare. `curbyte` is the radix-sort
  scratch. `srctape` is used only during merge.
- **`TuplesortPublic`** (`:131-220`) — the per-variant callback table
  embedded as the first field of the private `Tuplesortstate`. Contains:
  - Function pointers: `comparetup`, `comparetup_tiebreak`,
    `removeabbrev`, `writetup`, `readtup`, `freestate`.
  - Three memory contexts: `maincontext` (survives reset),
    `sortcontext` (per-sort), `tuplecontext` (sub-context of
    sortcontext, reset on dump).
  - Sort key state: `nKeys`, `sortKeys` (SortSupport array), `onlyKey`
    (single-key fast path pointer or NULL), `haveDatum1`, `tuples`
    (boolean: can `SortTuple.tuple` ever be set?).
  - `sortopt` (bitmask), `arg` (variant-private data).

## API surface (declarations only)

Engine (in `tuplesort.c`):
- `tuplesort_begin_common`, `tuplesort_set_bound`, `tuplesort_used_bound`,
  `tuplesort_puttuple_common`, `tuplesort_performsort`,
  `tuplesort_gettuple_common`, `tuplesort_skiptuples`, `tuplesort_end`,
  `tuplesort_reset`, `tuplesort_get_stats`, `tuplesort_method_name`,
  `tuplesort_space_type_name`, `tuplesort_merge_order`.
- Parallel: `tuplesort_estimate_shared`, `tuplesort_initialize_shared`,
  `tuplesort_attach_shared`.
- Random-access only: `tuplesort_rescan`, `tuplesort_markpos`,
  `tuplesort_restorepos` (with comment at `:370-375` reminding that
  parallel sorts don't support random access).
- `tuplesort_readtup_alloc` — used by variant `readtup` callbacks to
  get a slab slot or palloc.

Per-variant constructors (in `tuplesortvariants.c`):
`tuplesort_begin_heap`, `tuplesort_begin_cluster`,
`tuplesort_begin_index_btree`, `tuplesort_begin_index_hash`,
`tuplesort_begin_index_gist`, `tuplesort_begin_index_brin`,
`tuplesort_begin_index_gin`, `tuplesort_begin_datum`.

Per-variant put/get accessors: `tuplesort_puttupleslot`,
`tuplesort_putheaptuple`, `tuplesort_putindextuplevalues`,
`tuplesort_putbrintuple`, `tuplesort_putgintuple`, `tuplesort_putdatum`,
and the matching `_get_*`.

## Documented protocols

- **Parallel sort 9-step protocol** at `tuplesort.h:267-320` —
  `tuplesort_estimate_shared` → `_initialize_shared` → workers begin
  → workers `attach_shared` + feed tuples + `performsort` → workers
  `_end` → leader begin + `performsort` + consume → leader `_end`.
- **Variant API distinctions** at `:238-265` — heap stores MinimalTuples
  (no system columns); cluster preserves full HeapTuple including
  visibility info; index_btree stores IndexTuples; index_hash sorts by
  hash code; index_brin sorts by block number.

## Useful macros

- `TupleSortUseBumpTupleCxt(opt)` (`:82`) — bump vs aset selection.
- `TuplesortstateGetPublic(state)` (`:227`) — cast.
- `LogicalTapeReadExact(tape, ptr, len)` (`:230-234`) — ereport on
  short read.
- `PARALLEL_SORT(coordinate)` (`:223-225`) — 0/1/2 code for DTrace.

## Cross-references

- `source/src/backend/utils/sort/tuplesort.c` — engine.
- `source/src/backend/utils/sort/tuplesortvariants.c` — variant glue.
- `source/src/include/utils/sortsupport.h` — required by the
  `SortSupport sortKeys` field in `TuplesortPublic`.
- `source/src/include/utils/logtape.h` — `LogicalTape` opaque, used by
  the writetup/readtup signatures.

## Confidence tag tally

- `[verified-by-code]` × ~5
- `[from-comment]` × ~5
