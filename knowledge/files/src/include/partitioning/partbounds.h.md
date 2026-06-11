# `src/include/partitioning/partbounds.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~156
- **Source:** `source/src/include/partitioning/partbounds.h`

The `PartitionBoundInfoData` struct — central data structure
describing a partitioned table's partition bounds (LIST, RANGE, or
HASH) — plus all the comparison, search, copy, merge and
DDL-validation entry points. Used by `PartitionDesc` (one of these
per partitioned relation) and by the planner when reasoning about a
virtual partitioned joinrel. [verified-by-code] [from-comment]

## API / declarations

### PartitionBoundInfoData

```
{
  PartitionStrategy strategy;            /* hash / list / range */
  int               ndatums;
  Datum            **datums;             /* per-partition tuples */
  PartitionRangeDatumKind **kind;        /* range-only; NULL otherwise */
  Bitmapset        *interleaved_parts;   /* LIST-only */
  int               nindexes;
  int              *indexes;             /* partition index per slot */
  int               null_index;          /* -1 if no NULL-accepting part */
  int               default_index;       /* -1 if no DEFAULT part */
}
```

Helpers:
- `partition_bound_accepts_nulls(bi) := bi->null_index != -1`
- `partition_bound_has_default(bi) := bi->default_index != -1`

### Per-strategy datum/index layout (verbatim from comment block)

- **LIST**: `nindexes == ndatums`. Each datum-tuple has `partnatts`
  columns; `indexes[i]` = which partition accepts that value.
- **RANGE**: `nindexes == ndatums + 1`. Datums are upper bounds
  (lower = previous's upper). `indexes[i]` = partition whose upper
  bound is datum[i] (or -1 for gap). The extra final slot
  represents values above the last upper bound.
- **HASH**: `nindexes == greatest_modulus`. Datums are
  `(modulus, remainder)` pairs (2 cols). `indexes[remainder %
  greatest_modulus]` = partition (or -1).

### interleaved_parts (LIST only)

A partition is "interleaved" if it accepts multiple values AND
another partition has a value that lies between two of them. E.g.
`IN(3,5)` is interleaved given another `IN(4)`. Same for DEFAULT.
"This field only serves as proof that a particular partition is NOT
interleaved, not proof that it IS interleaved." — set conservatively.
Only populated for `RELOPT_BASEREL` and `RELOPT_OTHER_MEMBER_REL`,
NULL for joinrels. [from-comment]

### Functions

- `get_hash_partition_greatest_modulus(bound)` → int.
- `compute_partition_hash_value(partnatts, partsupfunc, partcollation,
  values, isnull)` → uint64.
- `get_qual_from_partbound(parent, spec)` → List of quals.
- `partition_bounds_create(boundspecs, nparts, key, **mapping)` —
  initial construction; `mapping` returns the permutation applied to
  preserve a canonical sorted order.
- `partition_bounds_equal(partnatts, parttyplen, parttypbyval, b1,
  b2)` → bool.
- `partition_bounds_copy(src, key)`.
- `partition_bounds_merge(...)` — partitionwise-join machinery.
- `partitions_are_ordered(boundinfo, live_parts)` — predicate for
  ordered-append optimizations.
- `check_new_partition_bound(relname, parent, spec, pstate)`,
  `check_default_partition_contents(parent, default_rel, new_spec)` —
  DDL-side validation.
- `partition_rbound_datum_cmp(...)` — compare range bound vs tuple
  values, int32 comparator semantics.
- bsearch helpers: `partition_list_bsearch`,
  `partition_range_datum_bsearch`, `partition_hash_bsearch`.
- SPLIT/MERGE support: `check_partitions_for_split`,
  `calculate_partition_bound_for_merge`.

## Notable invariants / details

- LIST partitioning never stores NULL in `datums[]`; NULL is tracked
  only in `null_index`. [from-comment]
- For RANGE, "a partition's upper bound and the next partition's
  lower bound are the same in most common cases, and we only store
  one of them (the upper bound)." — hence `ndatums << 2*nparts` in
  the no-gap case. [from-comment]
- Comparison ordering provided by `qsort_partition_rbound_cmp`,
  `qsort_partition_list_value_cmp`, `qsort_partition_hbound_cmp`
  (defined in `backend/partitioning/partbounds.c`).
- HASH partitioning's `nindexes = greatest modulus`, which is a
  common multiple of all partition moduli — guarantees a single
  flat lookup table indexed by `hash mod greatest_modulus`.
  [from-comment]
- `interleaved_parts` is a "false-negative-safe" optimization: when
  uncertain, mark as interleaved. The planner uses absence as proof
  of non-interleaving to enable certain runtime-pruning paths.

## Potential issues

- `interleaved_parts` is documented as one-way (proof of NOT
  interleaved); a future patch that treats presence as proof of
  interleaving introduces correctness bugs. [ISSUE-undocumented-invariant:
  interleaved_parts is conservative-only (likely)]
- `partition_bounds_create` mutates a caller-allocated `**mapping`
  out-param; the header doesn't say whether `*mapping` must be
  pre-allocated. [ISSUE-doc-drift: mapping out-param ownership (nit)]
- HASH layout assumes `nindexes <= INT_MAX`; for a partitioned table
  with extreme modulus values this could overflow. The header
  doesn't state the cap. [ISSUE-question: greatest_modulus upper
  bound (nit)]
- `check_default_partition_contents` is invoked when adding a
  partition that may have stolen rows from DEFAULT; failure mode
  on a huge DEFAULT partition (scan time) is not flagged.
  [ISSUE-question: DEFAULT-partition rescan cost on ATTACH (nit)]
