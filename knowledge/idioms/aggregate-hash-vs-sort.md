# Aggregate strategies — AGG_HASHED / AGG_SORTED / AGG_MIXED / AGG_PLAIN with hash-spill

`nodeAgg.c` implements four aggregation strategies, chosen by the
planner based on cardinality estimates, sort cost, and `work_mem` /
`hash_mem_multiplier`:

| Strategy   | When                                              | Cost                                  |
|------------|---------------------------------------------------|---------------------------------------|
| `AGG_PLAIN`| No GROUP BY (single result row)                   | O(input tuples) memory ≈ trans-state  |
| `AGG_SORTED` | Input already sorted on GROUP BY columns        | O(1) memory per group (streaming)     |
| `AGG_HASHED` | Input unsorted, hash-mem cap willing             | O(groups) memory; may spill to disk   |
| `AGG_MIXED`  | GROUPING SETS with both hashed + sorted sets    | Combination — see [[aggregate-grouping-sets]] |

This doc covers the **hash spill machinery** added in PG 13 — when
the hash table outgrows `hash_mem`, AGG_HASHED enters **spill mode**:
new groups get written to a partitioned set of LogicalTapes;
existing groups continue accumulating; after the input is exhausted,
each partition is read back and aggregated as a fresh sub-batch
(possibly recursively).

The AGG_SORTED path is simpler — one group at a time in memory,
flushed on input boundary. AGG_PLAIN is just AGG_SORTED with one
group.

Companion docs:
- [[aggregate-trans-state]] — transfunc/finalfunc + transvalue mechanics.
- [[aggregate-grouping-sets]] — AGG_MIXED + multi-phase processing.
- [[aggregate-partial-finalize]] — parallel decomposition.
- `knowledge/idioms/expression-evaluator-flow.md` — `ExecBuildAggTrans` builds a single mega-expression for trans-fn invocation.

## Anchors

- `source/src/backend/executor/nodeAgg.c:1-247` — banner with all four strategies + spill-to-disk explanation.
- `source/src/backend/executor/nodeAgg.c:281-360` — `HashAggSpill` struct + partition constants.
- `source/src/backend/executor/nodeAgg.c:1467-1506` — `build_hash_tables` / `build_hash_table`.
- `source/src/backend/executor/nodeAgg.c:1807-1908` — `hash_agg_set_limits` / `hash_agg_check_limits`.
- `source/src/backend/executor/nodeAgg.c:1910-2180` — `hash_agg_enter_spill_mode` + partition layout.
- `source/src/backend/executor/nodeAgg.c:2184-2625` — `lookup_hash_entries` (the hot path for hashed aggregation).
- `source/src/backend/executor/nodeAgg.c:2629-2858` — `agg_fill_hash_table` / `agg_retrieve_hash_table` (output).
- `source/src/backend/executor/nodeAgg.c:298-321` — `HASHAGG_PARTITION_FACTOR`, `HASHAGG_MIN/MAX_PARTITIONS`, `HASHAGG_HLL_BIT_WIDTH`.
- `source/src/include/executor/nodeAgg.h` — `AggState` struct definitions.
- `source/src/include/utils/logtape.h` — `LogicalTape` set used for spill.

## The four strategies — choosing one

The planner emits an Agg node with one of:

- **AGG_PLAIN**: no GROUP BY. Single group; trans-state in one
  ExprContext, no hash table, no sort.
- **AGG_SORTED**: input is already sorted (planner placed a Sort
  below, or the input is naturally ordered, e.g. from a Sort node
  feeding ORDER BY). Stream: read tuple, compare GROUP BY columns to
  previous; if same group, advance trans-state; if changed, emit
  result + reset trans-state.
- **AGG_HASHED**: build a hash table keyed by GROUP BY columns;
  each entry stores trans-state. After input exhausted, emit
  results by iterating the hash table.
- **AGG_MIXED**: GROUPING SETS where some sets are best handled by
  hashing and others by sorting. The "real" Agg node is AGG_MIXED;
  the chained nodes describe additional sorted phases. See
  [[aggregate-grouping-sets]].

The plan-tree representation:

> What we get from the planner is actually one "real" Agg node …
> which optionally has an additional list of Agg nodes hung off the
> side via the "chain" field. … The chain must be ordered such that
> hashed entries come before sorted/plain entries; the real node is
> marked AGG_MIXED if there are both types present.

[from-comment] (`nodeAgg.c:150-165`).

## The hash table — TupleHashTable + tupletable

Each grouping set gets its own `TupleHashTable` (`utils/hashutils`'s
hash table specialized for tuples). The table:

- **Key**: the GROUP BY columns of one input tuple, hashed via
  per-column hash functions from pg_amop.
- **Value**: an `AggStatePerGroup` array — one per aggregate, each
  storing the trans-value + isnull flag for that aggregate in that
  group.

`build_hash_tables` (`nodeAgg.c:1467`) creates one table per
hashed grouping set; `lookup_hash_entries` (`nodeAgg.c:2184`) is
called per input tuple to find-or-create the entry for that
tuple's GROUP BY columns.

The hash table uses **separate chaining** with `simplehash.h`-style
linear probing internally. Keys are stored as full minimum-format
heap tuples (no compressed key encoding — bytewise compare for
collisions).

## `hash_agg_set_limits` — establishing the memory cap

At `ExecInitAgg` time, `hash_agg_set_limits` computes:

```c
/* nodeAgg.c:1807-1862 (paraphrased) */
void hash_agg_set_limits(double hashentrysize, double input_groups,
                         int used_bits,
                         Size *mem_limit, uint64 *ngroups_limit,
                         int *num_partitions)
{
    /* Mem limit is hash_mem (default = work_mem * hash_mem_multiplier) */
    *mem_limit = get_hash_memory_limit();

    /* Ngroups limit: how many entries fit in mem_limit at hashentrysize per entry */
    *ngroups_limit = *mem_limit / hashentrysize;
    /* Apply a floor so tiny hash_mem doesn't force a 0-group limit */

    /* Partitions for spill: chosen by estimated total groups and remaining bits */
    npartitions = ceil(input_groups / *ngroups_limit) * HASHAGG_PARTITION_FACTOR;
    npartitions = clamp(npartitions, HASHAGG_MIN_PARTITIONS, HASHAGG_MAX_PARTITIONS);

    /* Cap at what's representable with remaining hash bits */
    if (used_bits + bits_for(npartitions) > 32)
        npartitions = 1 << (32 - used_bits);

    *num_partitions = npartitions;
}
```

[verified-by-code] (`nodeAgg.c:1807-1862`).

Key constants:

- **`HASHAGG_PARTITION_FACTOR = 1.5`** — overshoot the partition
  count by 50% so each batch comfortably fits in memory.
- **`HASHAGG_MIN_PARTITIONS = 4`** — floor; below this, recursion
  is more expensive than just re-partitioning.
- **`HASHAGG_MAX_PARTITIONS = 1024`** — ceiling; each partition is
  a tape with a buffer, so too many wastes memory on buffers.
- **`HASHAGG_HLL_BIT_WIDTH = 5`** — per-partition cardinality
  estimator (HyperLogLog with 32-byte sketches, ~18% error).

## `hash_agg_check_limits` — the spill-decision point

Called before inserting each new hash table entry:

```c
/* nodeAgg.c:1866-1908 (paraphrased) */
void hash_agg_check_limits(AggState *aggstate)
{
    uint64 ngroups = aggstate->hash_ngroups_current;
    Size meta_mem = MemoryContextMemAllocated(aggstate->hash_metacxt, true);
    Size hash_mem = MemoryContextMemAllocated(aggstate->hashcontext->ecxt_per_tuple_memory, true);

    if (ngroups > aggstate->hash_ngroups_limit
        || meta_mem + hash_mem > aggstate->hash_mem_limit) {
        hash_agg_enter_spill_mode(aggstate);
    }
}
```

[verified-by-code] (`nodeAgg.c:1866-1908`).

Two trigger conditions — either the **group count** exceeds the
limit (estimated worst-case per-group memory exceeded) OR the
**actual allocated memory** exceeds `hash_mem`. The dual check
handles the case where trans-state grows unexpectedly large
(e.g. `array_agg` accumulating big arrays).

## `hash_agg_enter_spill_mode` — flip the bit

```c
/* nodeAgg.c:1910 (skeleton) */
void hash_agg_enter_spill_mode(AggState *aggstate)
{
    aggstate->hash_spill_mode = true;

    /* For each grouping set's hash table:
     * - Allocate a HashAggSpill struct
     * - Create num_partitions LogicalTapes
     * - Each tape gets a 1-shot writer buffer of BLCKSZ
     */
    for each hashtable hashtable:
        hashtable->spill = allocate_HashAggSpill(num_partitions);
        for i in 0..num_partitions:
            hashtable->spill->partitions[i] = LogicalTapeCreate(tapeset);
}
```

Once in spill mode, `lookup_hash_entries`'s behavior changes:

- **If group already in table**: advance its trans-state normally.
- **If group not in table**: instead of inserting (which would
  exceed `hash_mem`), **route the tuple to a spill partition**
  based on its hash value, write the tuple to that partition's
  tape.

[verified-by-code] (`nodeAgg.c:2184-2300`).

## The spill — partitioned by hash bits

The hash value of the GROUP BY columns is used twice:

1. **For hash table probe**: low bits index into the bucket array.
2. **For partition selection** (in spill mode): a **different bit
   range** selects which spill partition the tuple goes to.

The `HashAggSpill.shift` and `mask` fields compute the partition:

```c
partition_no = (hash >> shift) & mask;
```

The `shift` reserves the low bits for the in-memory probe; the
mask selects from the partition count. When recursing on a spilled
partition (subbatch), the next level uses **the next bit range
above** — `used_bits` increments. This is what
`hash_agg_set_limits`'s `used_bits` parameter tracks: "how many
hash bits have been consumed by ancestor partition decisions."

[verified-by-code] (`HashAggSpill.shift`/`mask` usage,
`nodeAgg.c:333-341`).

## Reading back the spill — recursion until in-memory

After the main input is exhausted and the in-memory hashtable's
entries are emitted, the spill partitions are processed one at a
time:

```c
/* Inside agg_retrieve_hash_table (paraphrased) */
foreach partition in hashtable->spill->partitions:
    /* Re-initialize the in-memory hashtable */
    rebuild_hashtable_for_subbatch();

    /* Read tuples from this partition's tape, run aggregation
     * just as we did for the original input */
    LogicalTapeRewind(partition_tape);
    while ((tuple = read_from_tape(partition_tape))) {
        agg_one_tuple_into_hashtable(tuple);   /* may also spill recursively */
    }

    /* Emit the in-memory hashtable's entries */
    emit_hashtable_entries();
```

[verified-by-code] (`agg_retrieve_hash_table` calls
`agg_refill_hash_table` for sub-batches).

### Cardinality estimation via HLL

Before spilling a tuple, the partition's HyperLogLog sketch
(`HashAggSpill.hll_card[partition]`) is updated. When we later
process the partition as a subbatch, the HLL gives us an estimated
distinct-group count → we pick a fresh `num_partitions` for the
subbatch's potential re-spill.

The 5-bit HLL (`HASHAGG_HLL_BIT_WIDTH = 5`) gives ~32-byte sketches
and ~18% error — good enough for "choose between 4 and 1024
partitions next time." [from-comment] (`nodeAgg.c:311-317`).

### LogicalTape — buffer management

Each spill partition is a `LogicalTape` (`logtape.h`), not a
`BufFile`. The reasons:

> Spilled data is written to logical tapes. These provide better
> control over memory usage, disk space, and the number of files
> than if we were to use a BufFile for each spill.

[from-comment] (`nodeAgg.c:209-220`).

Logical tapes share a single underlying tape set, so 1024
partitions don't mean 1024 OS files — they're logical streams
within one or a few files, multiplexed by `logtape.c`. Recycling
disk space as tapes are read is also handled by logtape.

Memory cost: write buffer of BLCKSZ per active partition.
1024 partitions × 8 KiB = 8 MiB of buffer. Reasonable but not
free.

## `lookup_hash_entries` — the per-tuple hot path

```c
/* nodeAgg.c:2184 (skeleton) */
static void lookup_hash_entries(AggState *aggstate)
{
    /* For each hashed grouping set */
    for (setno = 0; setno < aggstate->num_hashes; setno++) {
        hashtable = aggstate->perhash[setno].hashtable;

        /* Compute hash from this tuple's GROUP BY columns */
        hash = TupleHashTableHash(hashtable, slot);

        if (aggstate->hash_spill_mode) {
            /* Try to find an existing entry; don't create */
            entry = TupleHashTableLookup(hashtable, slot, hash);
            if (entry) {
                /* Advance trans-state for this group */
                aggstate->hash_pergroup[setno] = entry;
            } else {
                /* Route to spill partition */
                hash_spill_tuple(hashtable->spill, hash, slot);
                /* Skip this tuple's trans-state advancement */
                continue;
            }
        } else {
            /* Find-or-create */
            entry = TupleHashTableEntry(hashtable, slot, hash, &isnew);
            if (isnew) {
                aggstate->hash_ngroups_current++;
                initialize_aggregate(hashtable, entry, ...);
                /* Check if we should enter spill mode */
                hash_agg_check_limits(aggstate);
            }
            aggstate->hash_pergroup[setno] = entry;
        }
    }
    /* Then ExecBuildAggTrans's compiled expression advances all per-group states */
}
```

The "advance every set's trans-state from one input tuple" pattern
is how AGG_HASHED handles multiple grouping sets in one pass:
compute hashes for each set, look up entries, then a single mega-
expression advances all sets at once. See
[[aggregate-grouping-sets]].

## AGG_SORTED — the simple path

For sorted input, no hash table; just track the previous group:

```c
/* agg_retrieve_direct, simplified */
prev_group_columns = NULL;
while ((tuple = ExecProcNode(outerPlan))) {
    if (prev_group_columns is NULL || group_columns(tuple) != prev_group_columns) {
        if (prev_group_columns != NULL) {
            emit_result();
            reset_pergroup_state();
        }
        initialize_pergroup_state(tuple);
        prev_group_columns = tuple;
    }
    advance_pergroup_state(tuple);
}
emit_result();   /* final group */
```

Memory cost: one trans-state per aggregate, kept in
`aggstate->aggcontexts[setno]->ecxt_per_tuple_memory`. The context
is **rescanned** (not reset) at group boundaries — see banner
comment about `ExprContext_CB` callbacks via
`AggRegisterCallback`. [from-comment] (`nodeAgg.c:73-75`).

For ROLLUP-style nested sets, multiple trans-states are maintained
in parallel (one per nested set); they get reset at their
respective group boundaries.

## Memory context discipline

Three memory contexts per Agg node:

1. **`aggcontexts[setno]`** — long-lived (per-group). Stores
   trans-values. Reset/rescanned at group boundaries.
2. **`tmpcontext`** — short-lived (per-tuple). Used for evaluating
   trans-fn argument expressions. Reset after each input tuple.
3. **`ss.ps.ps_ExprContext`** — per-output-tuple. Used for
   finalfunc and output projection.

The transition function reads its input from `tmpcontext`, produces
its result in `aggcontext`. The trick: when the trans-state is
pass-by-reference, the trans-fn must `pfree` the previous state
and `palloc` the new one in the right context. The
`ExecBuildAggTrans` compiled expression handles this; manual
trans-fns use `AggCheckCallContext()` to identify the right
context. [from-comment] (`nodeAgg.c:80-104`).

## The mega-expression — `ExecBuildAggTrans`

> For performance reasons transition functions, including combine
> functions, aren't invoked one-by-one from nodeAgg.c after
> computing arguments using the expression evaluation engine.
> Instead ExecBuildAggTrans() builds one large expression that
> does both argument evaluation and transition function invocation.

[from-comment] (`nodeAgg.c:229-238`).

The expression contains one `EEOP_AGG_*_TRANS` step per aggregate
per grouping set. JIT can compile this entire expression into a
single native function, eliminating per-aggregate dispatch
overhead.

## Cost-model choice

The planner picks between hash and sort using:

- **`enable_hashagg`** GUC (force sort if off).
- **Estimated work_mem fit**: if the estimated hash entry count ×
  per-entry size > `hash_mem`, the planner penalizes AGG_HASHED.
  Pre-PG13 this was a hard "fall back to sort" gate; now it's a
  soft penalty because spill is allowed.
- **Required sort order downstream**: if an ORDER BY follows that
  matches the GROUP BY, AGG_SORTED reuses the existing sort.

See `knowledge/idioms/cost-units-gucs.md` for the parameters and
`cost_agg` in `costsize.c` for the implementation.

## Invariants and races

1. **AGG_HASHED can spill to disk** since PG 13; pre-13 it would
   `ereport` if memory exceeded.
2. **AGG_MIXED has hash sets *before* sort sets** in the chain
   ordering. The real node describes the first set in its category.
   [from-comment] (`nodeAgg.c:150-165`).
3. **Hash spill uses LogicalTape**, not BufFile — multiplexed
   storage with better memory control. [from-comment]
   (`nodeAgg.c:209-220`).
4. **`HASHAGG_PARTITION_FACTOR = 1.5`** — overshoot intentional;
   slightly too many partitions is cheaper than too few + recursive
   spill.
5. **HLL cardinality estimation** per partition guides recursive
   re-partitioning. [from-comment] (`nodeAgg.c:311-317`).
6. **`tmpcontext` is reset per input tuple**; trans-fns must move
   their result to `aggcontext` to survive. [from-comment]
   (`nodeAgg.c:66-72`).
7. **`AggCheckCallContext()`** is how trans-fns identify their
   correct memory context; needed because `flinfo` may be reused
   across grouping sets. [from-comment] (`nodeAgg.c:140-146`).
8. **`ExecBuildAggTrans` mega-expression** is what gets JIT-compiled
   for hot aggregate paths. [from-comment] (`nodeAgg.c:229-238`).
9. **Each grouping set has its own hash table** in AGG_HASHED;
   multi-set queries pay parallel memory cost.
10. **`hash_mem = work_mem × hash_mem_multiplier`** (default 2.0
    since PG 16). Older versions just used `work_mem` directly.

## Useful greps

```bash
# Strategy choice + entry points:
grep -nE "AGG_HASHED|AGG_SORTED|AGG_MIXED|AGG_PLAIN|aggsplit|AggStrategy" \
       source/src/include/nodes/plannodes.h \
       source/src/backend/executor/nodeAgg.c | head -20

# Spill machinery:
grep -nE "hash_agg_set_limits|hash_agg_check_limits|hash_agg_enter_spill_mode|HashAggSpill|hash_spill_tuple" \
       source/src/backend/executor/nodeAgg.c

# Hash table building + lookups:
grep -n "build_hash_tables\|lookup_hash_entries\|TupleHashTableEntry" \
       source/src/backend/executor/nodeAgg.c | head

# HLL cardinality:
grep -n "hyperLogLog\|HASHAGG_HLL_BIT_WIDTH" \
       source/src/backend/executor/nodeAgg.c

# Mega-expression construction:
grep -rn "ExecBuildAggTrans\b" source/src/backend/executor/

# Cost model:
grep -n "cost_agg\b" source/src/backend/optimizer/path/costsize.c
```

## Cross-references

- [[aggregate-trans-state]] — transfunc / finalfunc model.
- [[aggregate-grouping-sets]] — AGG_MIXED + phases array.
- [[aggregate-partial-finalize]] — parallel aggregation decomposition.
- [[expression-evaluator-flow]] — `EEOP_AGG_*_TRANS` ops inside the mega-expression.
- [[cost-units-gucs]] — `hash_mem`, `hash_mem_multiplier`, `enable_hashagg`.
- `source/src/backend/utils/sort/logtape.c` — tape multiplexing.
- `source/src/include/lib/hyperloglog.h` — HLL sketch primitives.
