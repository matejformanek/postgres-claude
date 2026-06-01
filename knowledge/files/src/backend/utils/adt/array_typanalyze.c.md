# `src/backend/utils/adt/array_typanalyze.c`

- **File:** `source/src/backend/utils/adt/array_typanalyze.c` (807 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The custom `ANALYZE` per-column statistics gatherer for **array columns**.
Produces the MCE (Most Common Elements) and the DECHIST (Distinct
Element Count Histogram) statistics in `pg_statistic`, which feed the
selectivity estimators in `selfuncs.c` for `&&`, `@>`, `<@`, `= ANY`
operators on arrays.

## Algorithm — Lossy Counting

For a column of arrays, ANALYZE could naïvely count every (element,
frequency) pair across the sample — but that's unbounded in the number
of distinct elements. Instead, this file implements the
**Lossy Counting algorithm** (Manku & Motwani 2002) to maintain an
approximate top-K element frequency table in bounded memory.

### `TrackItem` (`:67-74`)

```c
struct TrackItem {
    Datum key;          /* the element e */
    int   frequency;    /* f — observed count */
    int   delta;        /* max error bound */
    int   last_container; /* dedup within a single array */
};
```

The `delta` field is the LC algorithm's error bound: when the table is
pruned (in `prune_element_hashtable`, `:697`), entries with `frequency
+ delta <= bucket_threshold` are discarded, and remaining entries have
their `delta` lowered to reflect "this is the max we could have missed
before tracking started."

`last_container` is the dedup gate: if a single array contains the same
element twice, the LC algorithm counts it once (per the
**presence-per-array** convention these stats are tuned for — matches
`array @> '{e}'` semantics, not `array_position`).

### `DECountItem` (`:77-81`)

Tracks distribution of "how many distinct elements does each input
array have?" — this drives `array_length` estimates and feeds the
selectivity calculation for `&&` (overlap).

## Entry points

- **`array_typanalyze(stats)`** (`:97`) — the `pg_type.typanalyze`
  function for array types. Calls `std_typanalyze` first to set up the
  normal scalar histogram path (which also runs on arrays for
  null-fraction etc.), then chains in `compute_array_stats` as the
  per-column compute hook.
- **`compute_array_stats(stats, fetchfunc, samplerows, totalrows)`**
  (`:216`) — the actual sample-walker. Pulls each row's array via
  `fetchfunc`, iterates elements, updates the element hash table and
  the DECountItem table. Runs Lossy-Counting pruning whenever the LC
  bucket boundary is crossed.

## Width threshold

```c
#define ARRAY_WIDTH_THRESHOLD 0x10000   /* 64 KB */
```
(`:33`) — arrays wider than this **after detoasting** are skipped. The
comment notes this is "considerably more than the similar
WIDTH_THRESHOLD limit used in analyze.c's standard typanalyze code"
(`:27-32` [from-comment]) — because array elements are typically small
even when arrays are large.

## Element-type discovery

`compute_array_stats` needs the element type's equality op + hash + cmp
funcs. These are pulled from the `typcache` once in `array_typanalyze`
and cached in `ArrayAnalyzeExtraData` (`:36-57`), which is stashed in a
static global `array_extra_data` (`:65`) — comment justifies this with
"compute_array_stats doesn't currently need to be re-entrant" (`:60-64`
[from-comment]).

## Hash-table key operations

Custom hash functions because the keys are typed `Datum`s, not pointers:
- `element_hash` (`:726`) — dispatches through `array_extra_data->hash`
  FmgrInfo.
- `element_match` (`:741`) — dispatches through the type's equality.
- `element_compare` (`:756`) — used for `qsort_arg` over collected
  TrackItems.

Three comparators are exported for stats-table assembly:
- `trackitem_compare_frequencies_desc` (`:772`) — pick top-K MCE.
- `trackitem_compare_element` (`:784`) — sort MCE table by element
  value (so output is deterministic).
- `countitem_compare_count` (`:796`) — distinct-count histogram.

## Output to pg_statistic

`compute_array_stats` fills four `STATISTIC_KIND_*` slots:
- `STATISTIC_KIND_MCELEM` — Most Common Elements (sorted by element).
- `STATISTIC_KIND_DECHIST` — Distinct Element Count Histogram (frequency
  per distinct-count, sorted by count).

Plus the standard NULL-fraction and tuple-count fields populated by
`std_typanalyze` upstream.

## Cross-references

- `source/src/backend/utils/adt/selfuncs.c` — consumer (the
  `mcelem_array_selec`, `arraycontsel`, `calc_arraycontsel` family).
- `source/src/backend/commands/analyze.c` — `std_typanalyze` and the
  `AnalyzeAttrComputeStatsFunc` plumbing.
- `source/src/backend/utils/cache/typcache.c` — element type lookup
  (`lookup_type_cache(elt_id, TYPECACHE_HASH_PROC_FINFO |
  TYPECACHE_CMP_PROC_FINFO)`).
- `source/src/include/catalog/pg_statistic.h` — `STATISTIC_KIND_MCELEM`,
  `STATISTIC_KIND_DECHIST`.

## Confidence tag tally

- `[verified-by-code]` × ~5
- `[from-comment]` × ~3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
