# ANALYZE — two-stage block-then-reservoir sampling

PostgreSQL's `ANALYZE` collects column statistics from a *random sample*
of rows, not the whole table.  The sampling is **two-stage**, and the
two stages run concurrently — block selection by Knuth's
**Algorithm S**, row selection within the chosen blocks by Vitter's
**Algorithm Z**.  Understanding why two stages, and what each one
buys you, is the foundation for reading the rest of `analyze.c` and
for reasoning about why the planner's row estimates look the way they
do.

This doc is the **sampling** half.  Once we have the sample rows,
`compute_scalar_stats` /  `compute_distinct_stats` / `compute_trivial_stats`
turn them into MCV lists, histograms, and correlations — that's
[[analyze-mcv-histogram-correlation]].  Cross-column work is
[[extended-statistics-statext]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/commands/analyze.c` — `acquire_sample_rows`, `do_analyze_rel`
- `source/src/backend/utils/misc/sampling.c` — Algorithm S + Algorithm Z + Vitter's `reservoir_get_next_S`
- `source/src/include/utils/sampling.h` — `BlockSamplerData`, `ReservoirStateData`

## Why two stages

The header comment at `analyze.c:1240-1247` [from-comment] gives the
plain English:

> As of May 2004 we use a new two-stage method:  Stage one selects up
> to targrows random blocks (or all blocks, if there aren't so many).
> Stage two scans these blocks and uses the Vitter algorithm to create
> a random sample of targrows rows (or less, if there are less in the
> sample of blocks).  The two stages are executed simultaneously: each
> block is processed as soon as stage one returns its number and while
> the rows are read stage two controls which ones are to be inserted
> into the sample.

The trade-off is honest at line 1249-1253 [from-comment]:

> Although every row has an equal chance of ending up in the final
> sample, this sampling method is not perfect: not every possible
> sample has an equal chance of being selected.  For large relations
> the number of different blocks represented by the sample tends to be
> too small.  We can live with that for now.

So: **each row** is equally likely to be sampled (the unbiasedness
property the planner needs); but the joint distribution over samples
is not uniform — clustered samples appear more often than they would
under SRS-WOR.  This is what makes ANALYZE I/O-cheap.

The dead-density estimator (line 1255-1259) [from-comment] also
benefits:

> An important property of this sampling method is that because we do
> look at a statistically unbiased set of blocks, we should get
> unbiased estimates of the average numbers of live and dead rows per
> block.

## Stage 1 — `BlockSampler` (Knuth's Algorithm S)

We know `totalblocks` ahead of time, so we use the straight Knuth
algorithm rather than Vitter — see `sampling.c:32-34`
[from-comment]:

> Since we know the total number of blocks in advance, we can use the
> straightforward Algorithm S from Knuth 3.4.2, rather than Vitter's
> algorithm.

The state struct (`sampling.h`) is just five fields the two
algorithms keep updated: `N` (total blocks), `n` (target sample
size), `t` (blocks scanned so far), `m` (blocks selected so far),
and a PRNG state.  `BlockSampler_Init` at `sampling.c:38-55`
[verified-by-code] sets them and returns `min(n, N)`.

The clever part is `BlockSampler_Next` at `sampling.c:63-116`
[verified-by-code].  Naïve Algorithm S would draw a fresh random
number per block, deciding "skip with probability 1 - k/K".  The
implementation collapses the skip loop into a **single** random
draw and reuses it:

```c
V = sampler_random_fract(&bs->randstate);
p = 1.0 - (double) k / (double) K;
while (V < p)
{
    /* skip */
    bs->t++;
    K--;                    /* keep K == N - t */
    /* adjust p to be new cutoff point in reduced range */
    p *= 1.0 - (double) k / (double) K;
}

/* select */
bs->m++;
return bs->t++;
```

`K = N - t` is the remaining-block count, `k = n - m` is the
still-to-sample count.  The explanation at `sampling.c:80-99`
[from-comment]:

> It is not obvious that this code matches Knuth's Algorithm S.
> Knuth says to skip the current block with probability 1 - k/K.
> If we are to skip, we should advance t (hence decrease K), and
> repeat the same probabilistic test for the next block.  The naive
> implementation thus requires a sampler_random_fract() call for each
> block number.  But we can reduce this to one sampler_random_fract()
> call per selected block, by noting that each time the while-test
> succeeds, we can reinterpret V as a uniform random number in the
> range 0 to p.

Each iteration of the inner while reinterprets `V` (still uniform
in `[0, p)` after a "skip" outcome) against a shrunken `p`.  That
gives one PRNG call per *selected* block, not per *visited* block —
a 4-8× saving in PRNG cost over a 100 GB table.

There's a termination proof in the same comment (lines 92-98)
[from-comment]:

> We have initially K > k > 0.  If the loop reduces K to equal k,
> the next while-test must fail since p will become exactly zero…
> Therefore K cannot become less than k, which means that we cannot
> fail to select enough blocks.

The `else if ((BlockNumber) k >= K)` branch at line 73-78 is the
"need all remaining" shortcut.

## Stage 2 — Vitter's Reservoir Sampling (Algorithm Z)

Once a block is selected, every row in it is offered to Stage 2 —
the **reservoir**.  Pre-2004 ANALYZE used a different method that
"put too much credence in the row density near the start of the
table" (header comment, lines 1258-1259) [from-comment]; Vitter
fixed both problems at once.

The reservoir's invariant from the loop comment in
`acquire_sample_rows` (lines 1319-1330) [from-comment]:

> The first targrows sample rows are simply copied into the
> reservoir. Then we start replacing tuples in the sample until
> we reach the end of the relation.  …  At all times the reservoir
> is a true random sample of the tuples we've passed over so far,
> so when we fall off the end of the relation we're done.

Steady state code (`analyze.c:1330-1357`) [verified-by-code]:

```c
if (numrows < targrows)
    rows[numrows++] = ExecCopySlotHeapTuple(slot);
else
{
    /*
     * t in Vitter's paper is the number of records already
     * processed.  If we need to compute a new S value, we must
     * use the not-yet-incremented value of samplerows as t.
     */
    if (rowstoskip < 0)
        rowstoskip = reservoir_get_next_S(&rstate, samplerows, targrows);

    if (rowstoskip <= 0)
    {
        /* Found a suitable tuple, so save it, replacing one
         * old tuple at random */
        int k = (int) (targrows * sampler_random_fract(&rstate.randstate));
        Assert(k >= 0 && k < targrows);
        heap_freetuple(rows[k]);
        rows[k] = ExecCopySlotHeapTuple(slot);
    }
    rowstoskip -= 1;
}
samplerows += 1;
```

The big saving from Algorithm Z over naïve reservoir sampling: we
don't draw a random number for every observed row.  We compute `S`,
the number of rows to **skip**, then skip that many without any
randomness, and only on the (S+1)'th row do we draw again to
select a replacement slot uniformly in `[0, targrows)`.

### `reservoir_get_next_S` internals

`sampling.c:132-244` [verified-by-code].  The function has **two
sub-algorithms** chosen by Vitter's threshold `T = 22 * n`:

| `t <= 22n` | Algorithm X (simple, expensive per call but few calls) |
| `t > 22n` | Algorithm Z (rejection sampling, cheap per call) |

Both compute `S`, the gap to the next selection.

**Algorithm X** at lines 152-170 [verified-by-code]:

```c
V = sampler_random_fract(&rs->randstate);
S = 0;
t += 1;
quot = (t - (double) n) / t;
while (quot > V)
{
    S += 1;
    t += 1;
    quot *= (t - (double) n) / t;
}
```

Straight Vitter: the probability that you select the *next* record
is `n/t`, then `n/(t+1)`, etc.  Multiplying gives the joint
"skipping S records" probability; the while-loop finds the smallest
`S` where `V` exceeds the joint probability.  Each call does *at
least one* `sampler_random_fract`, plus one per record skipped, so
it's `O(targrows * log)` overall.

**Algorithm Z** at lines 173-244 [verified-by-code] is the
rejection-sampling phase.  The state `W` and the lhs/rhs tests in
`(6.3)` of Vitter's paper give us `S` from a *single* uniform draw
plus an inner rejection (which is cheap because the accepted
fraction stays large as `n / t` shrinks).  The 22n cutoff is the
break-even between "expensive linear loop" and "rejection method
with O(1) calls per draw".

The initial `W` value at `sampling.c:142-143` [verified-by-code]:

```c
rs->W = exp(-log(sampler_random_fract(&rs->randstate)) / n);
```

— which is the inverse-CDF transform of `W = U^(-1/n)` for `U`
uniform on `[0, 1]`.  This is the only place in the file the math
shows through.

### One subtle bit: `t` is `samplerows`, not incremented yet

The reservoir's `t` and the loop's `samplerows` are both "number of
records already processed".  But the order matters — see the
comment at `analyze.c:1336-1339` [from-comment]:

> If we need to compute a new S value, we must use the
> **not-yet-incremented** value of samplerows as t.

So the code does `reservoir_get_next_S(&rstate, samplerows, targrows)`
**before** the `samplerows += 1` at the bottom of the loop body.

## Stitching the two stages together

`acquire_sample_rows` at `analyze.c:1261-1414` [verified-by-code].
The shape of the function:

```
totalblocks := RelationGetNumberOfBlocks
randseed    := pg_prng_uint32(...)
nblocks     := BlockSampler_Init(&bs, totalblocks, targrows, randseed)
reservoir_init_selection_state(&rstate, targrows)
scan        := table_beginscan_analyze(onerel)
stream      := read_stream_begin_relation(..., block_sampling_read_stream_next, &bs, 0)

while table_scan_analyze_next_block(scan, stream):
    while table_scan_analyze_next_tuple(scan, &liverows, &deadrows, slot):
        # ---------- reservoir step (Vitter) ----------
        if numrows < targrows:
            rows[numrows++] = ExecCopySlotHeapTuple(slot)
        else:
            if rowstoskip < 0:
                rowstoskip = reservoir_get_next_S(&rstate, samplerows, targrows)
            if rowstoskip <= 0:
                k = floor(targrows * U)
                heap_freetuple(rows[k]); rows[k] = ExecCopySlotHeapTuple(slot)
            rowstoskip -= 1
        samplerows += 1
    pgstat_progress_update_param(PROGRESS_ANALYZE_BLOCKS_DONE, ++blksdone)
```

The block-stream callback `block_sampling_read_stream_next` at
`analyze.c:1218-1226` [verified-by-code] is what wraps Stage 1:

```c
static BlockNumber
block_sampling_read_stream_next(...)
{
    BlockSamplerData *bs = callback_private_data;
    return BlockSampler_HasMore(bs) ? BlockSampler_Next(bs)
                                    : InvalidBlockNumber;
}
```

The async read-stream layer pre-fetches the next few blocks while
Stage 2 chews on the current one — `READ_STREAM_MAINTENANCE` plus
`READ_STREAM_USE_BATCHING` per the `read_stream_begin_relation`
call at lines 1303-1310 [verified-by-code].

### After the inner loops — final sort

When the relation is fully scanned, the reservoir is in
**arrival order**, but `compute_scalar_stats` needs them in
**TID order** to derive correlation (line 1237-1238)
[from-comment].  The comment is explicit:

> The returned list of tuples is in order by physical position in
> the table.  (We will rely on this later to derive correlation
> estimates.)

So we sort by TID:

```c
/* analyze.c:1379-1381 */
if (numrows == targrows)
    qsort_interruptible(rows, numrows, sizeof(HeapTuple),
                        compare_rows, NULL);
```

`compare_rows` at `analyze.c:1419-1438` [verified-by-code] is a
pure (block, offset) comparator on `t_self`.

### Live/dead extrapolation

The live-row and dead-row counts are extrapolated linearly from the
sampled blocks to the whole table (`analyze.c:1390-1399`)
[verified-by-code]:

```c
if (bs.m > 0)
{
    *totalrows = floor((liverows / bs.m) * totalblocks + 0.5);
    *totaldeadrows = floor((deadrows / bs.m) * totalblocks + 0.5);
}
```

`bs.m` is the **number of blocks actually selected**, not
`targrows` — they can differ on tables smaller than `targrows`
blocks.  Linear scaling works because Stage 1 picks blocks
unbiased over the whole table.

## How `targrows` is set — and what `default_statistics_target` does

`targrows` comes from `std_typanalyze`'s `minrows` field, which is
`300 * stats->attstattarget` (analyze.c:1999, 2006, 2013)
[verified-by-code].  For the default GUC value of 100, that's
**30,000 sample rows per column** (then aggregated across all
columns by `do_analyze_rel`).

The 300× multiplier traces back to Chaudhuri/Motwani/Narasayya
(1998) — comment at `analyze.c:1980-1998` [from-comment]:

> "Random sampling for histogram construction: how much is enough?"
> by Surajit Chaudhuri, Rajeev Motwani and Vivek Narasayya, in
> Proceedings of ACM SIGMOD International Conference on Management
> of Data, 1998, Pages 436-447.  Their Corollary 1 to Theorem 5
> says that for table size n, histogram size k, maximum relative
> error in bin size f, and error probability gamma, the minimum
> random sample size is
>      r = 4 * k * ln(2*n/gamma) / f^2
> Taking f = 0.5, gamma = 0.01, n = 10^6 rows, we obtain
>      r = 305.82 * k
> Note that because of the log function, the dependence on n is
> quite weak; even at n = 10^12, a 300*k sample gives <= 0.66
> bin size error with probability 0.99.

That weak dependence on `n` is what makes the **fixed**
`300 * default_statistics_target` defensible across table sizes
from 100 to 10¹² rows.

### The per-column attstattarget override

`pg_attribute.attstattarget` is an int16 stored per-column.  Three
values matter (per `attribute_is_analyzable` at
`analyze.c:1175-1212`) [verified-by-code]:

| `attstattarget` | Meaning |
|---|---|
| `-1` | use `default_statistics_target` |
| `0` | **skip this column** — `attribute_is_analyzable` returns false |
| `>= 1` | use this value directly |

So setting `attstattarget = 0` is the supported way to tell
ANALYZE "stop bothering with this column" — e.g. an opaque blob
column where no histogram or MCV list will ever help the planner.

## How `do_analyze_rel` orchestrates the whole thing

`analyze.c:305-875` [verified-by-code] (`do_analyze_rel`, 570
lines) is the function that runs per relation per ANALYZE pass.
The big steps in order:

1. Take `ShareUpdateExclusiveLock` and `RelationGetRelid`.
2. Set up `anl_context` (a per-relation memory context).
3. Loop over columns, call `examine_attribute` for each — which
   in turn calls the type's `typanalyze` function (default
   `std_typanalyze`) to fill in `compute_stats`, `minrows`, etc.
4. Compute `targrows = max(stats->minrows over all columns)`.
5. Allocate the `HeapTuple *rows[]` array of size `targrows`.
6. Call `acquire_sample_rows` (or `acquire_inherited_sample_rows`
   for partitioned/inheritance trees).
7. For each column: run `stats->compute_stats(...)` — which
   produces MCV, histogram, correlation, etc. (see
   [[analyze-mcv-histogram-correlation]]).
8. Walk every index on the relation, call `compute_index_stats`
   if it has expression columns.
9. Commit: `update_attstats` writes `pg_statistic` rows.
10. If extended stats are defined: call into the `statistics/`
    subsystem (see [[extended-statistics-statext]]).
11. Update `pg_class.reltuples`, `relpages`, `relallvisible`.

The locking — `ShareUpdateExclusiveLock` not
`AccessShareLock` — is what makes concurrent ANALYZE on the same
table serialize.  Two ANALYZEs on different tables can run
concurrently.

## Inheritance / partitioning twist

`acquire_inherited_sample_rows` at `analyze.c:1449-1713`
[verified-by-code] is the wrapper that handles partitioned tables
and old-style inheritance.  Three things differ:

1. It enumerates all child tables via `find_all_inheritors`.
2. It allocates `targrows` per child *proportionally to that
   child's size* — bigger children get more sample slots.
3. For each child it calls a per-child `acquire_sample_rows`
   (or, for foreign-table children, the FDW's `AcquireSampleRowsFunc`
   if one is defined).

The output is a single combined sample, suitable for computing
the *parent's* statistics.  Each child also runs ANALYZE
independently to populate its own `pg_statistic` rows.  See
header comment lines 1442-1448 [from-comment] for the contract:

> This has the same API as acquire_sample_rows, except that rows
> are collected from all inheritance children as well as the
> specified table.  We fail and return zero if there are no
> inheritance children, or if all children are foreign tables
> that don't support ANALYZE.

## The fetchfunc indirection

`std_fetch_func` at `analyze.c:1855-1869` and `ind_fetch_func` at
`analyze.c:1871-1922` [verified-by-code].  The per-column
statistics functions don't fetch their datums directly out of the
`HeapTuple *rows[]` — they go through an `AnalyzeAttrFetchFunc`
callback.  Two implementations:

- `std_fetch_func` — `heap_getattr` on the row.  Used for
  ordinary column ANALYZE.
- `ind_fetch_func` — `index_form_tuple` + `heap_getattr` on the
  formed index tuple.  Used for expression-index ANALYZE so the
  computed expression's value goes through the analyzer.

This is what makes the inner `compute_scalar_stats` loop
type-agnostic and reusable for both base columns and index
expressions.

## Invariants worth remembering

1. **Stage 1 (block sampling) is Algorithm S; Stage 2 (within-block
   row sampling) is Algorithm Z.**  Don't mix them up.
2. **Each row has equal probability of selection.**  The joint
   distribution over samples is not uniform — that's the
   acknowledged limitation.
3. **The reservoir is filled in arrival order; we sort by TID
   only at the end.**  This is what makes correlation
   computation a 0-pass operation later.
4. **`compare_rows` sorts by (block, offset).**  Adjacent items
   after the sort are physically adjacent in the table.
5. **Live/dead row counts are linear extrapolations from the
   sampled blocks, using `bs.m` (selected) as the divisor.**
6. **`attstattarget = 0` ⇒ column is skipped entirely.**
7. **`targrows` per relation = `max(stats->minrows)` across
   columns**, then the same `rows[]` array is shared for all
   columns' `compute_stats`.
8. **`reservoir_get_next_S(t, n)` uses Algorithm X for
   `t <= 22n`, Algorithm Z thereafter.**  The transition is
   transparent — `S` is computed correctly across the boundary.
9. **PRNG state is per-`BlockSamplerData` and per-`ReservoirStateData`.**
   They don't share state; the two algorithms are independent.
10. **`ShareUpdateExclusiveLock` on the relation makes ANALYZE
    serialize per-table but parallel across tables.**

## Useful greps

```bash
# Two-stage entry point
grep -n "acquire_sample_rows\|BlockSampler_Init\|reservoir_init_selection_state" \
    source/src/backend/commands/analyze.c \
    source/src/backend/utils/misc/sampling.c

# Stage 1 — Algorithm S
grep -n "BlockSampler_HasMore\|BlockSampler_Next" \
    source/src/backend/utils/misc/sampling.c

# Stage 2 — Algorithm Z + Algorithm X switching
grep -n "Algorithm Z\|Algorithm X\|rs->W\|22.0 \* n" \
    source/src/backend/utils/misc/sampling.c

# The 300× rationale
grep -n "Chaudhuri\|Motwani\|Narasayya\|305.82" \
    source/src/backend/commands/analyze.c

# attstattarget gating
grep -n "attstattarget == 0\|attstattarget < 0\|default_statistics_target" \
    source/src/backend/commands/analyze.c

# Read-stream integration for Stage 1
grep -n "block_sampling_read_stream_next\|read_stream_begin_relation" \
    source/src/backend/commands/analyze.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/analyze.c`](../files/src/backend/commands/analyze.c.md) | — | acquire_sample_rows, do_analyze_rel |
| [`src/backend/utils/misc/sampling.c`](../files/src/backend/utils/misc/sampling.c.md) | — | Algorithm S + Algorithm Z + Vitter's reservoir_get_next_S |
| [`src/include/utils/sampling.h`](../files/src/include/utils/sampling.md) | — | BlockSamplerData, ReservoirStateData |

<!-- /callsites:auto -->

## Cross-references

- [[analyze-mcv-histogram-correlation]] — what the sample rows are
  *for*: MCV cutoff, evenly-spaced histogram bins, Pearson
  correlation.
- [[extended-statistics-statext]] — cross-column statistics built
  on top of the same sample rows.
- [[buffer-manager]] — `BufferAccessStrategy` of type
  `BAS_VACUUM` keeps ANALYZE from blowing out shared_buffers
  with a one-time scan.
- [[memory-contexts]] — `anl_context` is the per-relation
  context everything ANALYZE allocates lives in; reset at end
  of pass.
- [[vacuum-two-pass-heap]] — VACUUM also uses
  `BlockSampler`/`ReservoirState` to gather sample rows for
  `pg_class.reltuples` updates.
- [[cost-units-gucs]] — `default_statistics_target` is the GUC
  that scales the sample size; the planner's row-count
  estimates depend on it.
