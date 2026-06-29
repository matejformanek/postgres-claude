# `src/backend/partitioning/partbounds.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~6025
- **Source:** `source/src/backend/partitioning/partbounds.c`

The big one. Canonicalises partition bounds for HASH / LIST /
RANGE, builds the runtime `PartitionBoundInfo` from catalog
`PartitionBoundSpec` nodes, performs partition-wise-join bound
merging, converts bound specs to executable predicate expressions
("partition constraint"), and supports MERGE/SPLIT/ATTACH validation.
[verified-by-code]

## API / entry points (selected — 25+ extern functions)

### Catalog → in-memory bounds

- `partition_bounds_create(boundspecs[], nparts, key, **mapping)`
  (line 299) — dispatch on `key->strategy` to
  `create_hash_bounds` / `create_list_bounds` /
  `create_range_bounds`. `*mapping[]` is set so the caller can
  translate "input position" → "canonical position".
  [verified-by-code]
- `partition_bounds_copy(src, key)` (line 994) — deep copy without
  catalog access. Used by relcache to put the bound info under
  `CacheMemoryContext` once stable. [from-comment]
- `partition_bounds_equal(partnatts, parttyplen, parttypbyval, b1,
  b2)` (line 888) — used by relcache "keep" logic in
  `RelationClearRelation` to decide whether a relcache flush can
  reuse the existing bounds. Walks `datums[]` + `kind[]` arrays.
  [from-comment]
- `partitions_are_ordered(boundinfo, live_parts)` (line 2845) —
  decides if an Append over the listed live partitions can deliver
  rows in partition-key order (RANGE without a live default
  partition; LIST without interleaved live partitions; HASH always
  unordered). [verified-by-code]

### Validation (DDL side)

- `check_new_partition_bound(relname, parent, spec, pstate)`
  (line 2888) — overlap check on ATTACH/CREATE PARTITION. Sets
  `overlap_location` to the parser cursor of the offending token
  for the error message. [verified-by-code]
- `check_default_partition_contents(parent, default_rel,
  new_spec)` (line 3243) — after ATTACH of a new non-default
  partition, scan the default partition for rows that would belong
  to the new partition; ERROR if found. [verified-by-code]
- `check_two_partitions_bounds_range(...)` (line 4998),
  `check_partitions_not_overlap_list(...)` (line 5258),
  `check_partition_bounds_for_split_range(...)` (line 5324) —
  MERGE/SPLIT PARTITION validators (PG17+ SQL feature).
  [verified-by-code]
- `calculate_partition_bound_for_merge(parent, partNames, partOids,
  spec, pstate)` (line 5098) — compute the bounds of the new
  partition that results from a MERGE. [verified-by-code]

### Spec → SQL predicate

- `get_qual_from_partbound(parent, spec)` (line 249) — entry. Calls
  `get_qual_for_hash` (line 3975) / `get_qual_for_list` (line 4058)
  / `get_qual_for_range` (line 4267). Output is a list of
  executable Exprs forming the partition constraint, used by
  `RelationGetPartitionQual` and by ATTACH-validation scans.
  [verified-by-code]
- `get_partition_operator(key, col, strategy, *need_relabel)`
  (line 3824) — look up the right opfamily operator OID for a
  bound comparison.

### Binary search & comparators

- `partition_list_bsearch(partsupfunc, partcollation, boundinfo,
  value, *is_equal)` (line 3599) — finds the offset of the LIST
  bound matching `value`.
- `partition_range_bsearch` (line 3646) — RANGE equivalent for a
  whole rbound.
- `partition_range_datum_bsearch` (line 3687) — RANGE with a
  partial key (prefix of columns), used by pruning.
- `partition_hash_bsearch` (line 3730) — HASH search by `(modulus,
  remainder)`.
- `partition_rbound_cmp` (line 3481) — full range-bound vs.
  range-bound comparator (returns three-way int32).
- `partition_rbound_datum_cmp` (line 3549) — range-bound vs.
  datums-from-tuple comparator.
- `partition_hbound_cmp` (line 3580) — `(modulus1, remainder1)` vs.
  `(modulus2, remainder2)`. Encodes the HASH partition compatibility
  rule.

### Partition-wise join bound merging

(All of section ~1100-2470 is partwise-join machinery, used by
`generate_partitionwise_join_paths` in the planner.)

- `partition_bounds_merge(partnatts, partsupfunc, partcollation,
  outer_rel, inner_rel, jointype, *outer_parts, *inner_parts)`
  (line 1112) — top entry. Dispatches to
  `merge_list_bounds` / `merge_range_bounds`. HASH partitionwise
  join works without bound merging (modulus equality is sufficient).
  [verified-by-code]
- Static helpers `init_partition_map`, `merge_matching_partitions`,
  `process_outer_partition`, `process_inner_partition`,
  `merge_null_partitions`, `merge_default_partitions`,
  `merge_partition_with_dummy`, `fix_merged_indexes`,
  `generate_matching_part_pairs`, `build_merged_partition_bounds`
  — the choreography by which join-type-specific NULL and
  DEFAULT handling is grafted onto the merged bounds.

### Hash

- `compute_partition_hash_value(partnatts, partsupfunc,
  partcollation, values, isnull)` (line 4715) — folds each
  partition key column's `hashfn(value, seed)` into a running 64-bit
  hash. `HASH_PARTITION_SEED` is the bound seed; nulls are
  ignored. The result `% modulus == remainder` selects the
  partition. [verified-by-code]

### Compatibility shim

- `get_hash_partition_greatest_modulus(boundinfo)` (line 3407) —
  used to be called from core; comment says "no longer used in the
  core code, but we keep it around in case external modules are
  using it." Effectively `bound->nindexes`. [from-comment]

## Notable invariants / details

- **Canonical ordering matters everywhere.** After
  `partition_bounds_create`, partition indexes in `boundinfo->indexes`
  / `datums` / `kind` are sorted into a deterministic order;
  callers receive a `mapping[]` to translate between "original
  catalog scan order" and "canonical". This invariant is what
  makes `partition_bounds_equal` a meaningful relcache predicate.
  [from-comment]
- **HASH bounds are constrained:** all partitions in a hash-partitioned
  parent must have moduli that are positive divisors of the
  greatest modulus, and remainders must cover `0..gcm-1` exactly
  once. `check_new_partition_bound`'s hash arm enforces this and
  is the single hardest part of ATTACH validation.
  [verified-by-code]
- **NULL handling:** LIST partitioned tables can have a partition
  for NULL (encoded as `null_index`); RANGE NULLs only go to the
  default partition. Hash NULLs hash to a value just like any
  other input. [from-comment in `get_qual_for_*`]
- **Interleaved LIST partitions:** if a LIST partitioned table has
  any partition with multiple distinct list values, ordering by
  the partition key cannot be guaranteed by partition order alone.
  `boundinfo->interleaved_parts` is the bitmap of such partitions,
  consulted by `partitions_are_ordered`. [verified-by-code]
- **Default partition's row-existence check** on ATTACH (line
  3243) is `O(rows_in_default)` — a known performance footgun
  on huge default partitions. Documented in `pg_class` docs.
  [from-comment]
- `get_qual_for_range` is the most subtle of the three quals
  builders: it must produce `(col_a, col_b) >= (lo_a, lo_b) AND
  (col_a, col_b) < (hi_a, hi_b)` semantics while handling
  `UNBOUNDED` and `MINVALUE` / `MAXVALUE` sentinels and operator
  family lookups per column. [inferred]

## Potential issues

- Line 3407 — `get_hash_partition_greatest_modulus` is a known
  compat shim ("no longer used in the core code, but we keep it
  around in case external modules are using it"). Long-term, this
  is dead weight if external uses are gone; worth a CommitFest
  conversation. [ISSUE-stale-todo: get_hash_partition_greatest
  _modulus retained for hypothetical external callers (nit)]
- The file has no top-of-file architectural overview comment
  beyond the one-line "Support routines for manipulating partition
  bounds". For a 6000-line module that mixes catalog
  canonicalisation, qsort comparators, partition-wise-join
  merging, MERGE/SPLIT validation, and predicate generation, this
  is thin. [ISSUE-doc-drift: 6000-line file with no
  architectural-overview comment (maybe)]
- Lines 5057-5500ish — the MERGE/SPLIT helpers
  (`get_partition_bound_spec`, `calculate_partition_bound_for_merge`,
  `check_partitions_not_overlap_list`,
  `check_partition_bounds_for_split_range`) are PG17/18 additions
  and depend on the canonical-ordering invariant of the rest of
  the file. If a future refactor relaxes that invariant (e.g.
  lazy canonicalisation), these helpers will silently produce
  wrong answers. [ISSUE-undocumented-invariant: MERGE/SPLIT
  validators depend on canonical-order invariant being eager
  (likely)]
- The partition-wise-join machinery (`merge_list_bounds`,
  `merge_range_bounds` and helpers, lines 1192-2470) is heavily
  commented but represents an order-of-magnitude cost in code
  complexity for the partition-wise-join feature. Notable open
  question: does it correctly handle FULL OUTER joins with
  default-partition + NULL-partition on both sides? The dedicated
  helpers `merge_null_partitions` + `merge_default_partitions`
  suggest care was taken, but a property-test corpus would help.
  [ISSUE-question: partwise-join + FOJ + (default + null
  partitions) needs property-test coverage (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `partitioning`](../../../../issues/partitioning.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [idioms/partition-bound-comparison.md](../../../../idioms/partition-bound-comparison.md)
