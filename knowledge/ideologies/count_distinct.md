# count_distinct — the *exact* member of the custom-aggregate family: it replaces core's sort-based COUNT(DISTINCT) with an in-context partially-sorted dedup array, computing a precise count, not an estimate

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tvondra/count_distinct` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's relationship to core idioms. Cites verified against the
> files fetched 2026-07-08 (see Sources footer). Author Tomas Vondra is a core
> PostgreSQL committer. This is the sibling of tdigest / topn / hll /
> datasketches / timescaledb-toolkit — but it is the one member of that family
> that computes an **exact** answer: its divergence from core is purely the
> *algorithm* (hash/array dedup vs. sort) and the memory-context discipline, not
> approximation.

## Domain & purpose

count_distinct provides drop-in alternatives to the built-in `COUNT(DISTINCT
x)` aggregate that avoid the sort core forces. Core PG evaluates `COUNT(DISTINCT
x)` by **sorting all input rows then counting adjacent-unequal runs** — O(n log
n) with a spill to disk once the sort exceeds `work_mem`; the README shows this
is ~90% of the runtime on a 10M-row test and that it also blocks parallelism
(`README.md:47-79`, `README.md:105-116`) `[from-README]`. The extension instead
accumulates elements into a dynamically-grown, periodically-compacted array held
in the aggregate's own memory context, so the final function just counts the
survivors (`count_distinct.c:35-91`, `count_distinct.c:516-532`)
`[verified-by-code]`. It ships four polymorphic aggregates: `count_distinct`,
`array_agg_distinct` (elements passed by value), and the `*_elements` variants
that take `anyarray` and dedup the array *contents* (`README.md:14-27`)
`[from-README]`. The pitch: with `HashAggregate` it skips the sort entirely and
wins on low-cardinality / high-redundancy groups, at the cost of keeping
everything in RAM.

## How it hooks into PG

`PG_MODULE_MAGIC` and nothing else at load time — **no `_PG_init`, no GUC, no
planner/executor hook, no `shared_preload_libraries`** (`count_distinct.c:20`)
`[verified-by-code]`. The extension is a flat set of `PG_FUNCTION_INFO_V1` C
functions (`count_distinct.c:126-137`) wired into aggregates by the install SQL.

- **Polymorphic `anyelement` signature, `internal` transition state.** The
  aggregate is `count_distinct(anyelement)` with `SFUNC = count_distinct_append`,
  `STYPE = internal`, `FINALFUNC = count_distinct`
  (`count_distinct--3.0.2.sql`, `CREATE AGGREGATE count_distinct`)
  `[verified-by-code]`. The `internal` state is an opaque
  `element_set_t *` (`count_distinct.c:92-108`) — never a first-class type, so
  (unlike tdigest) it cannot be stored, dumped, or read by eye.
- **Element-type discovery at runtime via fmgr.** Since the arg is polymorphic,
  the transition function calls `get_fn_expr_argtype(fcinfo->flinfo, 1)` and
  `get_typlenbyvalalign()` to learn the concrete type's `typlen/typbyval/typalign`
  on first call, caching them in the state (`count_distinct.c:155`,
  `count_distinct.c:186`, `count_distinct.c:832-834`) `[verified-by-code]`.
- **Aggregate-context discipline.** Both transition functions gate on
  `AggCheckCallContext` (via the `GET_AGG_CONTEXT` macro) and `elog(ERROR)` if
  called outside an aggregate, then `MemoryContextSwitchTo(aggcontext)` so the
  growing array lives in the per-group aggregate context rather than the
  transient per-tuple context (`count_distinct.c:25-33`,
  `count_distinct.c:174-176`, `count_distinct.c:192`) `[verified-by-code]`.
- **Full parallel-aggregate contract — present and load-bearing.** Every
  aggregate declares `COMBINEFUNC = count_distinct_combine`, `SERIALFUNC =
  count_distinct_serial`, `DESERIALFUNC = count_distinct_deserial`, and
  `PARALLEL = SAFE` (`count_distinct--3.0.2.sql`, all four `CREATE AGGREGATE`
  blocks) `[verified-by-code]`, backed by the three C functions at
  `count_distinct.c:320-514` `[verified-by-code]`. Per the README this is the
  extension's *remaining* advantage over modern core: built-in `COUNT(DISTINCT)`
  still cannot parallelize and can block parallel aggregation for other
  aggregates in the same query (`README.md:117-120`) `[from-README]`. This is
  the sharp contrast against the rest of the family and against core.

## Where it diverges from core idioms

### 1. Hash/array dedup instead of the guaranteed sort — but still EXACT

This is the whole point, and the axis that separates count_distinct from its
approximate siblings. tdigest, topn, hll, datasketches and
timescaledb-toolkit all trade exactness for a bounded/mergeable sketch;
count_distinct trades *only the sort*. `compact_set` sorts the unsorted tail
with `qsort_arg`, strips duplicates, and merge-sorts it into the already-sorted
prefix (`count_distinct.c:611-766`), and the final function returns the exact
survivor count `eset->nall` (`count_distinct.c:531`) `[verified-by-code]`. The
answer is identical to core's, per the README ("produces exactly the same
results (but unsorted)", `README.md:75`) `[from-README]`. So its divergence is
algorithmic, not semantic.

### 2. Amortized in-context accumulation vs. streamed sort

The state array is split three ways — `sorted | unsorted | free`
(`count_distinct.c:56-91`) `[from-comment]`. New values are `memcpy`'d raw into
the free region with no per-value dedup (`count_distinct.c:808-824`); dedup is
deferred and batched only when the array fills, which the header comment
justifies as an L2/L3 cache-locality and palloc-header-overhead win over the old
hash-table implementation (`count_distinct.c:41-54`) `[from-comment]`. Core's
sort node streams and spills; this keeps a single big palloc'd buffer live in
the aggregate context.

### 3. Fixed-length by-value types only — an explicit narrowing

Both transition functions hard-reject varlena and by-reference types:
`if ((typlen < 0) || (! typbyval)) elog(ERROR, "count_distinct handles only
fixed-length types passed by value")` (`count_distinct.c:189-190`,
`count_distinct.c:276-277`) `[verified-by-code]`. Elements are compared as raw
bytes via `memcmp` (`count_distinct.c:866-870`) and copied with `store_att_byval`
into a properly-aligned local `Datum` before insertion (to stay endian-correct,
`count_distinct.c:296-305`) `[verified-by-code]`. Core's `COUNT(DISTINCT)`
handles any sortable type; this handles only int2/int4/int8/float and similar
≤8-byte by-value types.

### 4. No `work_mem` ceiling — OOM risk vs. core's disk-spilling sort

Core bounds the distinct-sort at `work_mem` and spills to disk beyond it. This
extension has no such valve: the README is blunt that "there's no reasonable way
to enforce `work_mem` for user aggregates" and that a high distinct-count group
can OOM, the state being kept entirely in RAM (`README.md:87-102`,
`README.md:29-33`) `[from-README]`. The mitigation is external: for many groups
the planner picks `GroupAggregate`, keeping only one group live at a time
(`README.md:180-186`) `[from-README]`.

## Notable design decisions

- **Deferred batch compaction with a 20%-free hysteresis.** `add_element` only
  triggers `compact_set` when the array is full; compaction requires ≥20% free
  space afterward (`ARRAY_FREE_FRACT`) to avoid oscillation — a compaction that
  freed one slot then re-compacting on the next insert
  (`count_distinct.c:118-119`, `count_distinct.c:770-800`,
  `count_distinct.c:808-824`) `[verified-by-code]` `[from-comment]`.
- **Growth strategy tuned to AllocSet internals.** Below
  `ALLOCSET_SEPARATE_THRESHOLD` the array simply doubles ("that's what AllocSet
  will give us anyway"); above it, it grows by `/0.8` to target exactly 20% slack
  and avoid wasting large separate blocks (`count_distinct.c:794-799`)
  `[from-comment]`. Initial size is a deliberate 32B, sized against the ~40B
  struct overhead and the 8B AllocSet minimum chunk (`count_distinct.c:110-116`)
  `[from-comment]`.
- **Serialize forces compaction so workers do the sort.** `count_distinct_serial`
  calls `compact_set` before emitting the `bytea` — both to serialize the
  minimum bytes and to push the sort work into the parallel workers rather than
  the leader (`count_distinct.c:333-356`) `[verified-by-code]` `[from-comment]`.
  The wire format is just the `element_set_t` header (up to `data`) plus the raw
  sorted element bytes (`count_distinct.c:343-353`) `[verified-by-code]`.
- **Combine is a dup-eliminating merge of two sorted states.** `count_distinct_combine`
  compacts both inputs, then merge-walks them into a fresh
  `MemoryContextAlloc`'d buffer keeping only unique values, all in the aggregate
  context (`count_distinct.c:387-514`) `[verified-by-code]`. Null-state handling
  copies the survivor via `copy_set` (`count_distinct.c:414-423`,
  `count_distinct.c:845-863`) `[verified-by-code]`.
- **NULL inputs are skipped, not counted.** Matching `COUNT(DISTINCT)` semantics,
  a NULL value returns the prior state untouched and NULL elements inside arrays
  are ignored (`count_distinct.c:166-169`, `count_distinct.c:284-290`)
  `[verified-by-code]`.
- **`array_agg_distinct` reuses the identical state**, differing only in the
  final function (`build_array` via `construct_array`) and `FINALFUNC_EXTRA` for
  polymorphic result typing (`count_distinct.c:574-600`,
  `count_distinct--3.0.2.sql`) `[verified-by-code]`.

## Links into corpus

Custom-aggregate family (position count_distinct as the **exact** member; the
rest are approximate/sketch aggregates): [[tdigest]] (parallel-safe flat
centroid varlena), [[topn]] (JSONB mergeable state), [[postgresql-hll]] (opaque
register varlena), [[datasketches]] (live C++ object behind an `internal` ptr),
[[timescaledb-toolkit]] (flat_serialize). count_distinct shares their
`internal`-state + SERIALFUNC/DESERIALFUNC/COMBINEFUNC parallel machinery but
computes a precise distinct count rather than an estimate.

Corpus idioms/subsystems:
- `knowledge/idioms/aggregate-partial-finalize.md` — the COMBINE/SERIAL/DESERIAL
  partial-aggregate contract this extension implements in full.
- `knowledge/idioms/aggregate-trans-state.md` — `internal` transition-state
  conventions.
- `knowledge/idioms/aggregate-hash-vs-sort.md` — the HashAggregate-vs-sort choice
  that is the extension's entire performance thesis.
- `knowledge/idioms/memory-contexts.md` + `memory-context-allocset-internals.md`
  — the AggCheckCallContext / aggregate-context discipline and the AllocSet
  block-threshold growth tuning.
- `knowledge/idioms/fmgr.md` — `get_fn_expr_argtype` / `get_typlenbyvalalign`
  runtime polymorphic type discovery.
- `knowledge/subsystems/executor.md`, `knowledge/subsystems/optimizer.md` — the
  aggregate executor nodes and the HashAggregate/GroupAggregate path selection
  the README leans on.

## Sources

- `https://raw.githubusercontent.com/tvondra/count_distinct/master/count_distinct.control` @ 2026-07-08 → HTTP 200 (`default_version = '3.0.2'`, `relocatable = true`).
- `https://raw.githubusercontent.com/tvondra/count_distinct/master/README.md` @ 2026-07-08 → HTTP 200 (read fully).
- `https://raw.githubusercontent.com/tvondra/count_distinct/master/count_distinct.c` @ 2026-07-08 → HTTP 200 (870 lines, read fully).
- `https://raw.githubusercontent.com/tvondra/count_distinct/master/sql/count_distinct--3.0.2.sql` @ 2026-07-08 → HTTP 200 (first attempt 429 rate-limited, succeeded on retry). Confirms `PARALLEL = SAFE` + COMBINE/SERIAL/DESERIAL on all four aggregates.
- No 404 gaps. GitHub trees API / get_file_contents deliberately not used (403 for external repos per session scope); all files fetched via raw.githubusercontent.com.
