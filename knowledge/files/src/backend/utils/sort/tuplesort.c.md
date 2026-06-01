# `src/backend/utils/sort/tuplesort.c`

- **File:** `source/src/backend/utils/sort/tuplesort.c` (3486 lines)
- **Header:** `source/src/include/utils/tuplesort.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Generalized tuple-sort engine. Variant-agnostic core that supports both
small in-memory sorts and arbitrarily large external sorts using temp-file
"tapes". The per-variant (heap / cluster / index / datum / brin / gin /
hash) callbacks live in `tuplesortvariants.c`; this file owns the state
machine, memory accounting, run generation, k-way merge, and parallel
worker/leader choreography. (`tuplesort.c:1-12` [from-comment])

## Top-of-file comment — algorithm summary (verbatim)

> "Small amounts are sorted in-memory. Large amounts are sorted using
> temporary files and a standard external sort algorithm." The merge is a
> "balanced k-way merge" (pre-PG15 used polyphase merge; replaced because a
> "tape drive" is now cheap — just a few KB of buffer space). Run
> generation is "always quicksort or radix sort" (replacement-selection was
> removed). (`tuplesort.c:6-29` [from-comment])

## The FOUR memory states (the load-bearing state machine)

Defined in the `TupSortStatus` enum at `tuplesort.c:153-161` [verified-by-code]:

1. **`TSS_INITIAL`** — accumulate tuples into the unsorted `memtuples[]`
   array, growing it as long as `availMem >= 0` (`tuplesort.c:1108-1169`).
   - If a bound is set and population trips a heuristic
     (`memtupcount > bound*2`, or `memtupcount > bound && LACKMEM`), we
     transition to **`TSS_BOUNDED`** by calling `make_bounded_heap`
     (`:1138-1149, 2483-2527`) [verified-by-code].
   - If `LACKMEM` and no bound, we transition by calling
     `inittapes(state, true)` → state becomes **`TSS_BUILDRUNS`** and the
     accumulated array is dumped as the first run (`:1160-1169, 1761-1805`)
     [verified-by-code].
   - If the input ends while still in `TSS_INITIAL`, `performsort` sorts
     in place and the state becomes **`TSS_SORTEDINMEM`**
     (`:1276-1281`).

2. **`TSS_BUILDRUNS`** — every time `memtuples[]` fills, sort it, write
   the run to `destTape`, mark run-end, reset `tuplecontext`
   (`dumptuples`, `:2203-2293`). New tapes are created round-robin via
   `selectnewtape` up to `maxTapes`; beyond that we append additional
   runs to existing tapes (`:1844-1872`). When input ends, the final
   dump happens, then `mergeruns` is called (`:1324-1338`).

3. **Tape-merge passes** — inside `mergeruns` (`:1913-2091`):
   - Free the now-stale large `memtuples[]`, switch tuple memory from
     palloc to the **slab allocator** (`init_slab_allocator`,
     `:1877-1905`), allocate a small `memtuples[nOutputTapes]` to serve
     as the merge heap.
   - Per pass: rewind inputs (= previous pass's outputs), allocate new
     outputs, redistribute `tape_buffer_mem` among input tapes via
     `merge_read_buffer_size`, then loop `mergeonerun` until input runs
     are exhausted.
   - **Early-exit final-merge optimization**: when only one run is left
     per input tape AND no random access required AND not a worker, skip
     materializing the last pass and transition to **`TSS_FINALMERGE`** —
     producing tuples on demand from `tuplesort_gettuple_common`
     (`:2051-2061, 1536-1591`) [verified-by-code]. Saves one round of
     write+read.

4. **Terminal states**:
   - **`TSS_SORTEDINMEM`** — return tuples by scanning `memtuples[current]`
     forward or backward (`:1377-1419`).
   - **`TSS_SORTEDONTAPE`** — one frozen tape; supports random access /
     mark-restore (`:1421-1534, 2298-2387`).
   - **`TSS_FINALMERGE`** — final k-way merge driven by gettuple,
     pulling next tuple from `inputTapes[srcTapeIndex]` after every
     output (`:1536-1591`).

The state transitions are summarized in the file header:
"absorb tuples … if we reach the end of the input without exceeding
workMem, we sort the array in memory … If we do exceed workMem, we begin
to emit tuples into sorted runs in temporary tapes … When merging runs,
we use a heap containing just the frontmost tuple from each source run"
(`tuplesort.c:31-50` [from-comment]).

## Public API surface

Lifecycle (declared in `tuplesort.h`):
- `tuplesort_begin_common(workMem, coordinate, sortopt)` (`:546-643`) —
  creates the two long-lived memory contexts (`maincontext` survives reset,
  `sortcontext` is deleted on reset) and the `Tuplesortstate`.
- `tuplesort_begin_batch(state)` (`:652-720`) — creates the per-batch
  `tuplecontext` — **bump context if `TUPLESORT_ALLOWBOUNDED` is OFF, else
  AllocSet** (`tuplesort.h:82` `TupleSortUseBumpTupleCxt` macro;
  `tuplesort.c:672-679` [verified-by-code]). Comment says bump is preferred
  when no pfree is ever needed (non-bounded sort) for compactness.
- `tuplesort_set_bound(state, bound)` (`:734-775`) — must be called before
  any tuples; disables abbreviated-key optimization (`:768-774`).
- `tuplesort_performsort(state)` (`:1259-1357`) — drives the state
  transition out of INITIAL/BOUNDED/BUILDRUNS.
- `tuplesort_gettuple_common` (`:1366-1598`), `tuplesort_skiptuples`
  (`:1606-1666`).
- `tuplesort_rescan` / `markpos` / `restorepos` (`:2298-2387`) — require
  `TUPLESORT_RANDOMACCESS`.
- `tuplesort_reset` (`:915-931`) — deletes per-batch state, keeps
  `maincontext`. `tuplesort_end` (`:847-857`) — deletes everything.
- `tuplesort_get_stats` (`:2395-2434`) — translates `maxSpaceStatus`
  into one of: `top-N heapsort`, `quicksort`, `external sort`, `external
  merge`. EXPLAIN ANALYZE uses this.

Per-variant callback table (`TuplesortPublic`, `tuplesort.h:131-220`):
`comparetup`, `comparetup_tiebreak`, `removeabbrev`, `writetup`,
`readtup`, `freestate`. Plus `sortKeys`, `onlyKey`, `tuples`,
`haveDatum1`, `nKeys`, and the three contexts. Variants set these in
their `tuplesort_begin_*` constructors (in `tuplesortvariants.c`).

Parallel sort:
- `tuplesort_estimate_shared(n)` (`:3227-3239`).
- `tuplesort_initialize_shared(shared, n, seg)` (`:3248-3264`) — leader.
- `tuplesort_attach_shared(shared, seg)` (`:3271-3276`) — workers.
- The 9-step parallel protocol is documented in `tuplesort.h:267-320`
  [from-comment].

## Key data structures

- **`Tuplesortstate`** (`:184-335`) — the (internal) struct. Holds
  `base` (TuplesortPublic), `status`, `memtuples[]`/`memtupcount`/
  `memtupsize`, `availMem`/`allowedMem`/`tupleMem` (memory accounting),
  the slab arena (`slabMemoryBegin`/`End`, `slabFreeHead`), tape arrays
  (`inputTapes[nInputTapes]` / `outputTapes[nOutputTapes]` + run counts),
  `result_tape`, mark/restore position, parallel fields
  (`worker`, `shared`, `nParticipants`), and `abbrevNext` for the
  abbreviated-key abort heuristic.
- **`SortTuple`** (`tuplesort.h:114-121`) — `{ void *tuple; Datum datum1;
  bool isnull1; uint8 curbyte; int srctape; }`. `datum1` is the first
  sort key cached out-of-tuple to avoid `heap_getattr` on every compare —
  or the abbreviated key proxy when abbreviation is in play.
- **`Sharedsort`** (`:341-368`) — DSM-resident; `mutex` (spinlock)
  protects `currentWorker` / `workersFinished`; trailing `tapes[]`
  flex-array holds per-worker `TapeShare` metadata so the leader can
  import the worker output tapes.
- **`SlabSlot`** (`:143-147`) — union of `SlabSlot *nextfree` and
  `char buffer[SLAB_SLOT_SIZE=1024]`. The merge-time fixed-size tuple
  arena; tuples larger than 1KB fall back to `palloc` from `sortcontext`
  (`tuplesort_readtup_alloc`, `:3193-3214`).
- **`SLAB_SLOT_SIZE = 1024`** (`:141`); arena = `nOutputTapes + 1` slots
  (one per heap entry, plus the last-returned slot, `:1953-1965`).

## Key invariants and constants

- **`MINORDER = 6`, `MAXORDER = 500`** (`:175-176`) — merge order. Comment
  warns that high orders are slow due to CPU-cache effects, can be worse
  than multi-pass merge (`:1701-1715` [from-comment]).
- **`TAPE_BUFFER_OVERHEAD = BLCKSZ`** (1 block per tape), **`MERGE_BUFFER_SIZE
  = BLCKSZ*32`** (`:177-178`). `tuplesort_merge_order`:
  `M = allowedMem / (2*TAPE_BUFFER_OVERHEAD + MERGE_BUFFER_SIZE)`,
  clamped `[MINORDER, MAXORDER]` (`:1700-1717`).
- **`QSORT_THRESHOLD = 40`** (`:524`) — below this count we don't bother
  with radix sort; just qsort.
- **`INITIAL_MEMTUPSIZE = max(1024, ALLOCSET_SEPARATE_THRESHOLD /
  sizeof(SortTuple) + 1)`** (`:119-120`) — must be > the AllocSet "large
  chunk" boundary so the memtuples array gets its own dedicated block
  and can be `repalloc_huge`'d without bucket churn.
- **`workMem` is forced to at least 64 KB** (`:600` — defense against
  parallel sort callers that subdivide work_mem too aggressively).
- **Memory accounting**: `USEMEM(state,n) → availMem -= n`,
  `FREEMEM`, `LACKMEM(state) → availMem<0 && !slabAllocatorUsed`
  (`:398-401`). Sizes are `GetMemoryChunkSpace`, **not** requested
  sizes, to include palloc overhead.
- **Once the slab allocator is engaged (merge phase), USEMEM/LACKMEM
  stop being meaningful** — see `:243-246, 1961-1963` [from-comment].
- **On-tape tuple framing**: first `unsigned int` of every written
  tuple is its total on-tape length (including itself); 0 marks
  end-of-run. With `TUPLESORT_RANDOMACCESS`, a trailing length word
  duplicates the front length word to support read-backwards
  (`:406-424` [from-comment]).
- **Parallel sort + `TUPLESORT_RANDOMACCESS` is forbidden** (errors at
  `:555-556` [verified-by-code]).
- **Workers always produce exactly one final run** (even if empty) —
  documented invariant at `tuplesort.c:82-88` and `:3417-3418`.

## Specialized sort kernels (template-generated)

`#include "lib/sort_template.h"` is used twice (`:489-508`):

1. **`qsort_tuple`** — comparator chosen at runtime
   (`ST_COMPARE_RUNTIME_POINTER`) — generic per-variant sort using
   `base.comparetup`.
2. **`qsort_ssup`** — comparator inlined to `ApplySortComparator(datum1,
   isnull1, …)` — used when `onlyKey` is set (single-key MinimalTuple or
   Datum sort), the cheap fast path.

Plus **radix sort** (`radix_sort_tuple` / `radix_sort_recursive`,
`:2618-2976`). Trigger conditions in `tuplesort_sort_memtuples`
(`:2996-3038`): `memtupcount >= QSORT_THRESHOLD` AND the leading
SortSupport comparator is one of `ssup_datum_unsigned_cmp` /
`ssup_datum_signed_cmp` / `ssup_datum_int32_cmp` (`:3011-3021`
[verified-by-code]). Sorts pass-by-value Datums byte-wise MSB-first;
nulls partitioned out via Lomuto partition by `isnull1`, then
quicksort on tiebreaks (`:2618-2976`). Adapted from Malte Skarupke's
`ska_sort` (BSL-1.0, `:2622-2660`).

## Heap (priority-queue) routines — Knuth Alg. 5.2.3H

- `tuplesort_heap_insert` (`:3049-3075`) — sift-up.
- `tuplesort_heap_replace_top` (`:3108-3141`) — single sift-down to
  re-establish the min-heap after replacing root (used heavily during
  merge: `mergeonerun` calls it for every output tuple, `:2115-2142`).
- `tuplesort_heap_delete_top` (`:3084-3099`) — move last to root + sift.
- Bounded-sort heap is **max-heap** (sort direction is reversed in
  `make_bounded_heap` so we can drop the largest tuple cheaply), then
  reversed back in `sort_bounded_heap` (`:2483-2565` [from-comment]).
- **Top-N heapsort vs quicksort heuristic**: switch at `memtupcount >
  bound*2` (`:1138-1141`) — comment: "heuristic for where heapsort
  becomes cheaper than a quicksort".

## Abbreviated keys

- Optimization: store a pass-by-value proxy (e.g. a uint64) in `datum1`
  instead of the original pass-by-reference key. Most comparisons resolve
  on the proxy alone; a full comparator (`abbrev_full_comparator`) is
  called only on proxy ties.
- **Abort heuristic** in `consider_abort_common` (`:1215-1254`): probed
  at exponentially growing tuple counts (`abbrevNext *= 2`, starting 10).
  The opclass's `abbrev_abort` callback decides if compression is
  ineffective; if so we revert `comparator <- abbrev_full_comparator` and
  null the converter (`:1239-1252`).
- **Forced disable**: (a) bounded sorts (`tuplesort_set_bound`,
  `:766-774`) — abbreviation doesn't pay when most tuples get discarded;
  (b) multi-run external sorts at start of `mergeruns` (`:1921-1935`) —
  tape representation doesn't carry the abbreviation.

## Parallel sort choreography

- **Worker path** (`:1282-1291`): even if all data fits memory,
  workers must dump to one tape via `inittapes(false)` + `dumptuples` +
  `worker_nomergeruns` (`:3357-3366`); they end in `TSS_SORTEDONTAPE`.
- **`worker_freeze_result_tape`** (`:3319-3349`) — `LogicalTapeFreeze`,
  then under `shared->mutex` writes the per-worker `TapeShare` and
  increments `workersFinished`.
- **Leader path** (`:1293-1301`): `leader_takeover_tapes`
  (`:3379-3433`) verifies `workersFinished == nParticipants`, builds
  the leader's tapeset from worker `TapeShare`s via
  `LogicalTapeImport`, fakes `status = TSS_BUILDRUNS` with one run per
  worker tape, and then `mergeruns` runs as if those runs came from a
  single backend.

## Cross-references

- **Variants:** `source/src/backend/utils/sort/tuplesortvariants.c` —
  HeapTuple / Cluster / IndexBtree / IndexHash / IndexBrin / IndexGin /
  Datum callbacks.
- **Tapes:** `logtape.c` (`LogicalTapeSetCreate/Create/Read/Write/
  Rewind/Freeze/Import/Close/Backspace/Tell/Seek`).
- **SortSupport:** `source/src/backend/utils/sort/sortsupport.c` and
  `source/src/include/utils/sortsupport.h` — the `SortSupportData`
  struct + `PrepareSortSupportFromOrderingOp` / `…IndexRel` /
  `…GistIndexRel` family.
- **Sort template:** `source/src/include/lib/sort_template.h` — the
  macro-generated quicksort.
- **Planner consumer:** `tuplesort_merge_order` is called by
  `costsize.c` for cost_sort [unverified].

## Open questions

- The exact memory cost of `MERGE_BUFFER_SIZE = 32 * BLCKSZ`: comment
  says "we treat `memtuples[]` as part of MERGE_BUFFER_SIZE workspace"
  (`:1695-1697`) — I did not verify the arithmetic.
- The `radix_sort_tuple` pre-check for "presorted" data
  (`:2951-2966`) — short-circuits when input is already sorted. The
  break-even point vs unconditional radix sort is [unverified].
- The interaction between `tuplesort_reset` and the per-batch `bump`
  tuplecontext: bump can't pfree individual tuples, so a reset must
  rely on whole-context reset semantics — confirmed at `:1941`
  (`MemoryContextResetOnly(tuplecontext)`) but the exact bump
  reset semantics live in `bump.c` [verified-elsewhere].

## Confidence tag tally

- `[verified-by-code]` × ~22
- `[from-comment]` × ~14
- `[unverified]` × 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
