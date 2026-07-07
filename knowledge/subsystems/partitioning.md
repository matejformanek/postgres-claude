# partitioning (declarative partitioning support)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Alexander Korotkov (9), Peter Eisentraut (7), Amit Langote (4), Tom Lane (3)
- **Top reviewers (last 24mo):** Alexander Korotkov (6), Tomas Vondra (4), Robert Haas (4), Jian He (3)
- **Recent landmark commits (12mo):**
  - `0392fb900eb (Alexander Korotkov, 2026-05-20): Revert "Reject degenerate SPLIT PARTITION with DEFAULT partition"`
  - `8a27d418f8f (Peter Eisentraut, 2025-10-31): Mark function arguments of type "Datum *" as "const Datum *" where possible`
  - `7724cb9935a (Peter Eisentraut, 2026-03-19): Add some const qualifiers enabled by typeof_unqual change on copyObject`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/partitioning/`
- **Header path:** `source/src/include/partitioning/`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchor:** none in source; user docs are
  `doc/src/sgml/ddl.sgml` "Table Partitioning".

## 1. Purpose

Two distinct but tightly-coupled jobs:
1. **Partition-bound representation** (`partbounds.c`): canonicalize
   a `PartitionBoundSpec` (the parse-time `FOR VALUES …` AST) into
   a sortable `PartitionBoundInfo`, support comparing/merging
   bound sets, and provide O(log n) binary searches for finding
   which partition owns a given key.
2. **Partition pruning** (`partprune.c`): turn `WHERE` clauses into
   "pruning steps" that, at plan time *and* at exec time, eliminate
   partitions that can't satisfy the query.

`partdesc.c` is a thin relcache-attached cache of the bound info
plus the partition OIDs in bound order.

## 2. Mental model

- **One `PartitionBoundInfo` per partitioned table.** It collapses
  list / range / hash bounds into a sorted `datums[][]` array plus
  a parallel `indexes[]` mapping each "slot" to the partition that
  owns it ([from-comment] `partbounds.h:22-78`).
  - For **list**: each datum maps to one partition; `nindexes == ndatums`.
  - For **range**: each "datum" is an upper bound; `nindexes ==
    ndatums + 1` (the extra slot is "above all bounds"). `-1`
    in `indexes[]` means a gap.
  - For **hash**: each datum is a `(modulus, remainder)` pair;
    `nindexes == greatest_modulus`, indexed by
    `hash(key) mod greatest_modulus`.
  - **NULL handling** is via `null_index` (list NULL partition);
    **DEFAULT partition** is `default_index`. Both `-1` if absent.
  - **Interleaved list partitions**: `interleaved_parts` Bitmapset
    flags list partitions whose value set isn't disjoint from its
    neighbors (or that coexists with a DEFAULT). Used to disable
    ordering-dependent optimizations ([from-comment]
    `partbounds.h:65-77`).
- **The three bsearches all have the same shape.** They all return
  "greatest bound index ≤ probe, or -1". The loop is canonical:
  `lo=-1; hi=ndatums-1; while lo<hi: mid=(lo+hi+1)/2; cmp;
  if cmp<=0: lo=mid (early-break if ==0) else hi=mid-1; return lo`
  ([verified-by-code] `partbounds.c:3599-3631, 3645-3677,
  3730-3763`).
- **Pruning is steps, not predicates.** A `WHERE` clause is reduced
  to a list of `PartitionPruneStep*`. Base steps are tests on
  partition-key columns (with operator+strategy+expr triples).
  Combine steps are AND/OR of previous steps. The exec-time engine
  walks the steps, evaluates exprs, and intersects/unions
  bitmapsets of partition indexes ([from-comment]
  `partprune.c:1-35`).
- **Three pruning targets.** `PARTTARGET_PLANNER` (use only what's
  evaluable now), `PARTTARGET_INITIAL` (executor startup,
  parameters known), `PARTTARGET_EXEC` (per-rescan; e.g. nested
  loop with parameterized inner) ([verified-by-code]
  `partprune.c:92-97`).
- **`PartitionDesc` lifetime is relcache-coupled but snapshot-aware**
  ([from-comment] `partdesc.c:62-68`). Two descriptors are cached:
  `rd_partdesc` (includes detached) and
  `rd_partdesc_nodetached` (which omits some), with a
  `pg_inherits.xmin` snapshot check on the latter.

## 3. Key files

- `partbounds.c` (~179 KB, 6025 lines) — by far the biggest. Owns
  bound creation, sorting comparators, merging two bound sets for
  partitionwise join, all the bsearches, and the equality check
  used for partition matching.
- `partprune.c` (~117 KB, 3830 lines) — step generation
  (`gen_partprune_steps_internal`), step execution
  (`get_matching_partitions`), planner entry
  (`make_partition_pruneinfo`,
  `prune_append_rel_partitions`), exec-time setup, and the per-
  strategy step interpreters.
- `partdesc.c` (~16 KB, 508 lines) — `RelationGetPartitionDesc`,
  `RelationBuildPartitionDesc`, partition-directory machinery
  used during planning to keep multiple lookups consistent.

## 4. Key data structures

- **`PartitionBoundInfoData`** (`partbounds.h:79-96`). Fields:
  `strategy` (HASH/LIST/RANGE), `ndatums`, `datums[][]`, `kind[][]`
  (range-bound kind = MINVALUE/finite/MAXVALUE), `interleaved_parts`,
  `nindexes`, `indexes[]`, `null_index`, `default_index`.
  Macros `partition_bound_accepts_nulls(bi)` and
  `partition_bound_has_default(bi)` test the two latter fields
  ([verified-by-code] `partbounds.h:98-99`).
- **`PartitionDescData`** (`partdesc.h:29-64`). `nparts`,
  `detached_exist`, `oids[]`, `is_leaf[]`, `boundinfo`, plus a
  one-slot cache for repeated `get_partition_for_tuple` lookups
  (`last_found_datum_index`, `last_found_part_index`,
  `last_found_count` for streak detection on COPY/INSERT).
- **`PartitionHashBound`** / **`PartitionListValue`** /
  **`PartitionRangeBound`** (private to `partbounds.c:65-71`) —
  qsort-time intermediate representations used while building the
  bound info from the parser's `PartitionBoundSpec **`.
- **`PartClauseInfo`** (`partprune.c:63-72`). One partition-key
  clause: `keyno`, `opno`, `op_is_ne`, `expr`, `cmpfn`,
  `op_strategy`.
- **`PartClauseMatchStatus`** (`partprune.c:78-86`). Six outcomes
  including `PARTCLAUSE_MATCH_CLAUSE`, `PARTCLAUSE_MATCH_NULLNESS`,
  `PARTCLAUSE_MATCH_CONTRADICT`, `PARTCLAUSE_UNSUPPORTED`.
- **`PartClauseTarget`** (`partprune.c:92-97`). The three targets
  above.
- **`PartitionPruneContext`** (`partprune.h:49-62`). Runtime
  pruning state: `strategy`, `partnatts`, `nparts`, `boundinfo`,
  `partcollation`, `partsupfunc`, `stepcmpfuncs`, `ppccontext`,
  `planstate`, `exprcontext`, `exprstates[]`. The
  `PruneCxtStateIdx(partnatts, step_id, keyno) =
  partnatts*step_id + keyno` macro indexes per-(step, key) slots
  ([verified-by-code] `partprune.h:64-71`).
- **`PartitionDirectory`** (opaque; `partdesc.c:35-47`) — keeps
  every `PartitionDesc` pinned for the duration of a planning
  run so detach-concurrency doesn't change them mid-plan.

## 5. Control flow — the common paths

### 5.1 Building the bound info (DDL time)
`partition_bounds_create(boundspecs, nparts, key, mapping)`
[verified-by-code] `partbounds.c:300-…` is called from
`RelationBuildPartitionDesc` in `partdesc.c` whenever the relcache
entry for a partitioned table is built. It dispatches by
`key->strategy` into `create_hash_bounds`,
`create_list_bounds`, `create_range_bounds`, each of which:
- Allocates the per-strategy intermediate (`PartitionHashBound[]` etc.).
- Sorts via `qsort_partition_*_cmp` (the file's static comparators).
- Materializes a `PartitionBoundInfo` with `ndatums`, `datums[][]`,
  `indexes[]`, `null_index`, `default_index`.
- Writes `*mapping` so callers can translate "input ordering of
  partitions" → "ordering in bound info".

### 5.2 Locating a partition for a tuple (DML / COPY hot path)
The fast path goes through `get_partition_for_tuple` (in
`executor/execPartition.c`, not this dir), which calls the
appropriate `partition_*_bsearch` in this file:

#### List `partition_list_bsearch` [verified-by-code] `partbounds.c:3599-3631`
- Binary searches `datums[][0]` for the greatest bound ≤ value
  using `FunctionCall2Coll(&partsupfunc[0], partcollation[0], …)`.
- Sets `*is_equal` true on exact hit (and breaks early).
- Returns -1 if value < smallest bound.

#### Range `partition_range_bsearch` (static) /
`partition_range_datum_bsearch` (public) [verified-by-code]
`partbounds.c:3645-3722`
- Same loop shape; comparator is `partition_rbound_cmp` /
  `partition_rbound_datum_cmp` which walks all `partnatts` columns
  and handles MINVALUE/MAXVALUE per-column.
- Returned `*cmpval` (range_bsearch) gives both ordering sign and
  1-based column number where the mismatch was found — used by
  callers to decide gap-vs-hit semantics ([from-comment]
  `partbounds.c:3639-3643`).

#### Hash `partition_hash_bsearch` [verified-by-code]
`partbounds.c:3730-3763`
- Searches `(modulus, remainder)` pairs using
  `partition_hbound_cmp` which sorts by modulus then remainder
  ([verified-by-code] `partbounds.c:3580-3588`).

The single-slot cache in `PartitionDescData`
(`last_found_*_index`/`last_found_count`) skips the bsearch when
the previous tuple landed in the same partition — important for
COPY where tuples often arrive sorted.

### 5.3 Plan-time pruning
`prune_append_rel_partitions(rel)` (public entry,
`partprune.c`):
1. Collect baserestrictinfo for the partitioned rel.
2. `gen_partprune_steps(rel, clauses, PARTTARGET_PLANNER, &context)`
   — walks AND/OR tree, matching clauses to partition keys.
3. `get_matching_partitions(&context, steps)` — runs the steps,
   returning the Bitmapset of surviving partition indexes.
4. Caller (planner) discards `RelOptInfo->part_rels[i]` for
   pruned-out partitions.

### 5.4 Exec-time pruning
`make_partition_pruneinfo(root, parentrel, subpaths, prunequal)`
builds a `PartitionPruneInfo` that gets serialized into the plan.
At exec time, `ExecInitPartitionPruning` (`execPartition.c`) calls
back into `partprune.c:get_matching_partitions` with steps that
reference run-time `Param`s; the resulting Bitmapset is used by
`Append`/`MergeAppend` to skip subnodes per rescan.

## 6. Locking and invariants

- **bsearch invariant (all three):** returns the index of the
  *greatest* bound that is ≤ probe, or -1 if probe < all bounds.
  Caller must inspect `*is_equal` / `*cmpval` to distinguish
  "exact hit" vs. "in the gap immediately after this bound"
  ([verified-by-code] all three bsearch headers).
- **`datums[]` is sorted** by the strategy-specific comparator.
  Bound-info equality (`partition_bounds_equal`) relies on this
  ordering and the parallel `indexes[]` array.
- **`PartitionDesc` pointers are stable** while the relation is
  open *and* a strong-enough lock is held (`AccessShareLock` at
  minimum); the relcache hacks in `RelationClose`,
  `RelationClearRelation`, and `RelationBuildPartitionDesc` defer
  freeing until refcount → 0 ([from-comment] `partdesc.c:62-68`).
- **Two-descriptor caching:** `rd_partdesc` always exists if any
  partdesc has been built; `rd_partdesc_nodetached` is rebuilt
  per call when the active snapshot's `xmin` differs from
  `rd_partdesc_nodetached_xmin` ([from-comment] `partdesc.c:53-66`).
- **`interleaved_parts` is only-set-for-baserel** (`partbounds.h:75-77`).
  Don't read it on join rels.
- **Default partition** containment is rechecked by
  `check_default_partition_contents` whenever a new sibling is
  added; this is why ATTACH PARTITION can be expensive when a
  DEFAULT exists.
- **`PartitionDirectory`** is the planning-time pinning mechanism
  that ensures every reference to the same partitioned table sees
  the same `PartitionDesc` even if a concurrent DETACH commits
  mid-plan.

## 7. Interactions with other subsystems

- **catalog/partition.c, catalog/pg_partitioned_table.c** — read
  the catalog rows that drive `partition_bounds_create`.
- **utils/cache/partcache.c** — owns `PartitionKey` (sort/cmp
  functions, collations, partattrs).
- **utils/cache/relcache.c** — `rd_partdesc{,_nodetached}`,
  `rd_pdcxt`/`rd_pddcxt` memory contexts.
- **executor/execPartition.c** — caller of all bsearches for
  tuple routing; also drives runtime pruning.
- **executor/nodeAppend.c, nodeMergeAppend.c** — consume the
  exec-time pruning result to skip subplans.
- **optimizer/path/allpaths.c** — calls
  `prune_append_rel_partitions` during set_append_rel_size.
- **commands/tablecmds.c** — DDL paths (ATTACH/DETACH/SPLIT/MERGE)
  call into `partbounds.c` validators
  (`check_new_partition_bound`, `check_default_partition_contents`,
  `check_partitions_for_split`,
  `calculate_partition_bound_for_merge`).

## 8. Tests

- `src/test/regress/sql/partition_*.sql` — `partition_aggregate`,
  `partition_join`, `partition_prune`, `partition_info`,
  `partition_split`, `partition_merge`. Heavy EXPLAIN-driven
  coverage of pruning.
- `src/test/isolation/specs/partition-*.spec` — concurrent
  attach/detach semantics.
- `partition_prune.sql` is the canonical place to verify a pruning
  change.

## 9. Open questions / unverified claims

1. The merge logic in `partbounds.c` (~thousands of lines for
   `partition_bounds_merge` and its helpers) is read only at the
   struct level (`PartitionMap`). The exact merging algorithm
   for partitionwise join is unverified.
2. The interaction between `last_found_count` streak detection
   and parallel COPY workers — does each worker have its own
   `PartitionDesc`? Inferred-yes but not traced.
3. `get_matching_partitions` step interpreter walkthrough not
   done; only the data structures around it are documented.
4. The "single -1 in `indexes[]` means a gap" convention for range
   partitioning vs. the "extra slot above last bound" rule
   — both are stated in the header comment but not cross-checked
   against a concrete example.
5. `interleaved_parts` set-construction logic in
   `partbounds.c` (used to disable run-time ordering optimizations
   for ORDER BY on a list partition key with overlapping values)
   not read in detail.

## 10. Glossary

- **Partition key** — the column list + opclass + collation used
  to decide which partition owns a row.
- **PartitionBoundSpec** — parser representation of `FOR VALUES …`.
- **PartitionBoundInfo** — canonical, sorted representation built
  from all sibling `PartitionBoundSpec`s.
- **PartitionDesc** — `PartitionBoundInfo` + ordered OID list +
  per-partition leaf flag. Cached on the relcache entry.
- **PartitionDirectory** — planning-time pin of multiple
  `PartitionDesc`s so concurrent DETACH can't change them mid-plan.
- **Pruning step** — a planner artifact representing either a
  base test on partition keys or a Boolean combine of earlier
  steps; survives into the plan for run-time pruning.
- **PARTTARGET_{PLANNER,INITIAL,EXEC}** — the three pruning
  *targets*; differ in which exprs are evaluable.
- **Greatest modulus** — for hash partitioning, the LCM-ish
  modulus that all partition moduli divide; defines `nindexes`.
- **Default partition** — catches rows no other partition wants.
  Tracked by `default_index`; constrains future ATTACHes.
- **Detached partition** — currently being concurrently detached;
  visibility depends on snapshot, hence the two-descriptor cache.
- **Interleaved partition** — list partition whose value set
  isn't disjoint enough from its neighbors to allow ordering
  optimizations.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**7 files.**

| File |
|---|
| [`src/backend/partitioning/partbounds.c`](../files/src/backend/partitioning/partbounds.c.md) |
| [`src/backend/partitioning/partdesc.c`](../files/src/backend/partitioning/partdesc.c.md) |
| [`src/backend/partitioning/partprune.c`](../files/src/backend/partitioning/partprune.c.md) |
| [`src/include/partitioning/partbounds.h`](../files/src/include/partitioning/partbounds.h.md) |
| [`src/include/partitioning/partdefs.h`](../files/src/include/partitioning/partdefs.h.md) |
| [`src/include/partitioning/partdesc.h`](../files/src/include/partitioning/partdesc.h.md) |
| [`src/include/partitioning/partprune.h`](../files/src/include/partitioning/partprune.h.md) |

<!-- /files-owned:auto -->
