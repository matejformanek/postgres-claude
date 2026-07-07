# ANALYZE — `std_typanalyze` and the three statistic kinds

Once `acquire_sample_rows` has produced `targrows` rows (see
[[analyze-block-and-reservoir-sampling]] for *how*), the per-column
`stats->compute_stats` callback turns that sample into the actual
`pg_statistic` entries the planner reads.  Most types use one of
three built-in implementations dispatched by **`std_typanalyze`**:
`compute_trivial_stats`, `compute_distinct_stats`, or
`compute_scalar_stats`.

This doc walks the scalar path end-to-end because it's where the
interesting work lives: the MCV cutoff, the evenly-spaced
histogram, and the Pearson correlation.  Distinct-only and trivial
are short variants of the same machinery.

The flip side — extended (cross-column) statistics — is
[[extended-statistics-statext]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/commands/analyze.c` — `std_typanalyze`, all three `compute_*`
- `source/src/include/catalog/pg_statistic.h` — `STATISTIC_KIND_*`
- `source/src/include/commands/vacuum.h` — `VacAttrStats` struct

## The dispatch — `std_typanalyze`

`analyze.c:1949-2017` [verified-by-code] picks one of the three
compute functions based on what comparison operators the column's
type provides:

```c
if (OidIsValid(eqopr) && OidIsValid(ltopr))
{
    /* Seems to be a scalar datatype */
    stats->compute_stats = compute_scalar_stats;
    stats->minrows = 300 * stats->attstattarget;
}
else if (OidIsValid(eqopr))
{
    /* We can still recognize distinct values */
    stats->compute_stats = compute_distinct_stats;
    stats->minrows = 300 * stats->attstattarget;
}
else
{
    /* Can't do much but the trivial stuff */
    stats->compute_stats = compute_trivial_stats;
    stats->minrows = 300 * stats->attstattarget;
}
```

| Operator set | Function | What you get |
|---|---|---|
| `<` and `=` | `compute_scalar_stats` | nullfrac, width, distinct, **MCV + histogram + correlation** |
| `=` only | `compute_distinct_stats` | nullfrac, width, distinct, **MCV** (no histogram, no correlation) |
| Neither | `compute_trivial_stats` | nullfrac, width only |

The `eqopr` and `ltopr` lookups go through
`get_sort_group_operators` (analyze.c:1961-1964) — same path the
planner uses to find ORDER BY / GROUP BY operators.  This
guarantees that whenever the planner can `<` or `=` a value, the
statistics it needs to estimate selectivity exist.

The `extra_data` field (`stats->extra_data = mystats`,
line 1971) is the analyzer's way of stashing the resolved
`eqopr` and `ltopr` OIDs so the compute function doesn't have
to look them up again.

## The `VacAttrStats` 5-slot layout

The struct lives in `vacuum.h` (not shown here) but the key bit
for reading `compute_*` is that **every column gets up to 5
statistic slots** in `pg_statistic`.  Slot `i` is described by:

| Field | Meaning |
|---|---|
| `stakind[i]` | `STATISTIC_KIND_*` constant, see below |
| `staop[i]` | OID of the operator that orders the values in this slot |
| `stacoll[i]` | collation OID (for text-like types) |
| `stanumbers[i]` / `numnumbers[i]` | array of `float4` (frequencies, lengths) |
| `stavalues[i]` / `numvalues[i]` | array of `Datum` (the actual values) |

The kind constants come from `pg_statistic.h:194-281`
[verified-by-code]:

```c
#define STATISTIC_KIND_MCV                   1   /* most common values */
#define STATISTIC_KIND_HISTOGRAM             2   /* equi-depth */
#define STATISTIC_KIND_CORRELATION           3   /* float4 in [-1, 1] */
#define STATISTIC_KIND_MCELEM                4   /* MCV for array elements */
#define STATISTIC_KIND_DECHIST               5   /* distinct element histogram */
#define STATISTIC_KIND_RANGE_LENGTH_HISTOGRAM 6  /* for range types */
```

`compute_scalar_stats` fills slots in this order
(`analyze.c:2783, 2899, 2943`) [verified-by-code]:

1. MCV (always, if there's anything to put in it)
2. Histogram (if `num_hist >= 2` non-MCV distinct values)
3. Correlation (if `values_cnt > 1`)

Slots 4 and 5 are reserved for type-specific analyzers (e.g.
`array_typanalyze` fills `MCELEM` + `DECHIST`); `compute_scalar_stats`
itself never fills more than 3.

## `compute_scalar_stats` — the heavy lifter

The function at `analyze.c:2460-2978` is a 500-line block.  The
shape, in plain English:

### Phase 1 — first scan: classify and accumulate width

`analyze.c:2505-2557` [verified-by-code].  Walk all `samplerows`,
calling the `fetchfunc` for each:

- **Null** → increment `null_cnt`, skip.
- **Variable-length (`varlena`)** → add width, force-detoast (or
  declare "too wide" via `WIDTH_THRESHOLD` and skip without
  detoasting if it's massive).
- **Otherwise** → record into `values[]` for sorting.

The `WIDTH_THRESHOLD` short-circuit at lines 2539-2543 is the
"we are not going to compare a 2GB toasted value 300 times in a
qsort" guard.  Such rows count toward `toowide_cnt`, contribute
no actual data to the sample, and get a synthetic distinct-row
treatment later.

The detoast call `PG_DETOAST_DATUM(value)` happens **once** per
row and the detoasted form lives in the per-relation
`anl_context` (the analyzer's memory context).  Without that,
each comparison in the qsort would re-detoast.

### Phase 2 — qsort with a fancy tupnoLink trick

`analyze.c:2569-2573` [verified-by-code]:

```c
cxt.ssup = &ssup;
cxt.tupnoLink = tupnoLink;
qsort_interruptible(values, values_cnt, sizeof(ScalarItem),
                    compare_scalars, &cxt);
```

The `compare_scalars` comparator at `analyze.c:2989-3015`
[verified-by-code] does the **clever bit**: every time two
items compare equal, it updates `tupnoLink[ta]` and
`tupnoLink[tb]` to remember "this index is part of an
equal-group ending at index X":

```c
if (cxt->tupnoLink[ta] < tb)
    cxt->tupnoLink[ta] = tb;
if (cxt->tupnoLink[tb] < ta)
    cxt->tupnoLink[tb] = ta;
```

Why?  After the qsort, all duplicates are adjacent.  Counting
distinct values normally needs `N-1` extra comparisons (compare
each item to its neighbor).  But qsort *already* did all those
comparisons — it's a sort, after all.  The tupnoLink array
captures the equality information **as a side effect** of the
sort, so the post-sort walk can count duplicates in one pass with
zero additional comparator calls.

The comment at `analyze.c:2581-2592` [from-comment]:

> the sort algorithm must at some point have compared each pair
> of items that are adjacent in the sorted order; otherwise it
> could not know that it's ordered the pair correctly.

The post-sort invariant: `tupnoLink[tupno] == tupno` *iff* this
is the **last item in its duplicate group**.  Equivalently: a
group of `K` duplicates has `K-1` items linked forward and the
last one pointing at itself.

### Phase 3 — second scan: count duplicates, track MCV candidates, accumulate correlation sum

`analyze.c:2597-2685` [verified-by-code].  This walks the
already-sorted `values[]` in order.  Two things happen
simultaneously:

#### Duplicate counting → MCV track list

`dups_cnt` increments on every iteration; when
`tupnoLink[tupno] == tupno` (end of group), we have a candidate
MCV.  The candidate is inserted into a fixed-size `track[]`
array of length `num_mcv = stats->attstattarget` (so by default
100).  The track array is maintained sorted by count
descending; inserting is a bubble-down — `analyze.c:2620-2659`
[verified-by-code].

#### Correlation accumulation

Each iteration adds `((double) i) * ((double) tupno)` to
`corr_xysum`.  `i` is the position in *sorted* order; `tupno` is
the position in *original* (= TID) order.  Pearson correlation
needs `Σxy`, `Σx`, `Σx²`, `Σy`, `Σy²`.  The trick: both `x` and
`y` are permutations of `0..values_cnt-1`, so:

- `Σx = Σy = (n-1)·n/2`
- `Σx² = Σy² = (n-1)·n·(2n-1)/6`

These are constants we compute later from `values_cnt` —
analyze.c:2934-2937 [verified-by-code].  The only sum that
genuinely depends on the data is `corr_xysum`, and we get it for
free during the dup-counting walk.

### Phase 4 — distinct-value estimate via Chao + Bunge formula

`analyze.c:2687-2718` (not shown in the read above) follows the
Chao-Bunge / "small first-order jackknife" form:

```
stadistinct = (samplerows * d) / (samplerows - duprows * samplerows / totalrows + duprows)
```

Where `d = ndistinct` (count of distinct values seen) and
`duprows = values_cnt - ndistinct` (number of rows whose value
appears more than once).  Then we clamp:

- If `stadistinct > 0.1 * totalrows`, the value is stored
  **negative** as `-(stadistinct / totalrows)`.  Per `pg_statistic`
  convention, a negative `stadistinct` is a **scaling factor** —
  "this column has |stadistinct| × N distinct values".  This is
  what the planner uses for "the distinct count probably grows
  with the table".

This is one of the longest-standing PG estimation knobs and
explains why `n_distinct` overrides on `pg_class` are sometimes
needed for unusual data distributions — the formula is just an
estimator, not an oracle.

### Phase 5 — `analyze_mcv_list` chooses how many MCVs to keep

The list of frequency counts goes into `analyze_mcv_list`
(`analyze.c:3038-3149`) [verified-by-code].  The decision is
**statistical**, not "keep top-K":

```c
/* analyze.c:3081-3147 */
sumcount = 0.0;
for (i = 0; i < num_mcv - 1; i++)
    sumcount += mcv_counts[i];

while (num_mcv > 0)
{
    /* Estimated selectivity the least common value would have
     * if it wasn't in the MCV list (c.f. eqsel()). */
    selec = 1.0 - sumcount / samplerows - stanullfrac;
    if (otherdistinct > 1)
        selec /= otherdistinct;

    /* Hypergeometric standard deviation */
    N = totalrows;
    n = samplerows;
    K = N * mcv_counts[num_mcv - 1] / n;
    variance = n * K * (N - K) * (N - n) / (N * N * (N - 1));
    stddev = sqrt(variance);

    if (mcv_counts[num_mcv - 1] > selec * samplerows + 2 * stddev + 0.5)
    {
        /* The value is significantly more common than the
         * non-MCV selectivity would suggest.  Keep it. */
        break;
    }
    else
    {
        /* Discard this value and consider the next least
         * common value */
        num_mcv--;
        sumcount -= mcv_counts[num_mcv - 1];
    }
}
return num_mcv;
```

The criterion is: **"is this value significantly more frequent
than what the non-MCV catch-all bucket would estimate?"**  If
not — drop it.  The 2-stddev plus 0.5 continuity correction
implements roughly a 95% confidence Wald-type interval for the
hypergeometric distribution (the math is in the comment at
`analyze.c:3108-3122`) [from-comment].

The reverse-trim direction (start with all candidates, remove
from the bottom) is deliberate per the comment at
`analyze.c:3073-3079`:

> we deliberately do this by removing values from the full list,
> rather than starting with an empty list and adding values,
> because the latter approach can fail to add any values if all
> the most common values have around the same frequency and make
> up the majority of the table.

A column like `country_code` on a table heavily dominated by one
country would otherwise get zero MCVs.

There's also an "all distinct values fit in the sample and we
think they're all the values that exist" short-circuit at
`analyze.c:2735-2741` [verified-by-code] that bypasses the
filter — typically boolean or low-cardinality enum columns.

### Phase 6 — equal-depth histogram via index arithmetic

`analyze.c:2806-2910` [verified-by-code].  Two distinct steps:

#### Remove the MCV values from `values[]`

Walk `values[]` in TID-position order (which is the array order
since they came out of the sort).  The MCV positions are in
`track[i].first`; the inner loop copies non-MCV stretches forward
and skips MCV stretches.  After this, `nvals` is the count of
non-MCV values still in the array.

#### Pick `num_hist` evenly-spaced values

```c
delta    = (nvals - 1) / (num_hist - 1);
deltafrac = (nvals - 1) % (num_hist - 1);
pos = posfrac = 0;

for (i = 0; i < num_hist; i++)
{
    hist_values[i] = datumCopy(values[pos].value, ...);
    pos += delta;
    posfrac += deltafrac;
    if (posfrac >= (num_hist - 1))
    {
        pos++;
        posfrac -= (num_hist - 1);
    }
}
```

This is a Bresenham-style integer-arithmetic equivalent of
`hist[i] = values[(i * (nvals-1)) / (num_hist-1)]`.  The
comment at `analyze.c:2869-2877` [from-comment] explains why
the direct formula isn't used:

> computing that subscript directly risks integer overflow when
> the stats target is more than a couple thousand.  Instead we
> add (nvals - 1) / (num_hist - 1) to pos at each step, tracking
> the integral and fractional parts of the sum separately.

The output is **equi-depth**: each adjacent pair `(hist[i],
hist[i+1])` covers roughly the same number of sampled rows.
That's what the planner's range-selectivity estimator
(`ineq_histogram_selectivity`) wants.

The `staop` for the histogram is `mystats->ltopr` — the type's
`<` operator — because the histogram is implicitly ordered by
`<` and selectivity probes need that operator to bisect.

### Phase 7 — correlation from a Pearson formula

`analyze.c:2912-2949` [verified-by-code].  The closed-form
constants drop out because both `x` and `y` are permutations of
`0..values_cnt-1`:

```c
corr_xsum  = ((double)(values_cnt - 1)) * ((double) values_cnt) / 2.0;
corr_x2sum = ((double)(values_cnt - 1)) * ((double) values_cnt)
             * (double)(2 * values_cnt - 1) / 6.0;

/* And the correlation coefficient reduces to */
corrs[0] = (values_cnt * corr_xysum - corr_xsum * corr_xsum) /
           (values_cnt * corr_x2sum - corr_xsum * corr_xsum);
```

The correlation value lives in `stanumbers[2][0]` as a
`float4`.  Range is `[-1, 1]`:

- **+1** — sampled rows are in TID order (strongly clustered
  ascending).  An index scan on this column would touch each
  heap page at most once.
- **−1** — TID order is reverse of value order.  Same locality
  benefit, in reverse direction.
- **0** — no monotonic correlation.  Index scans touch many
  random heap pages per scan range.

This is what feeds the planner's `index_pages_fetched` cost
calculation — high `|correlation|` makes an index scan cheap;
low `|correlation|` makes the bitmap heap scan more attractive.

## `compute_distinct_stats` — short version for hash-only types

`analyze.c:2117-2458` [verified-by-code].  Used when the type has
`=` but no `<` (e.g. `xid`, `tid`, `point`).  The shape:

1. Walk the sample, collect values that have hash equality.
2. Maintain a hash table to count occurrences.
3. Estimate distinct values using the same Chao-style formula.
4. Build an MCV list — same `analyze_mcv_list` cutoff as the
   scalar path.
5. **No histogram, no correlation** — there's no `<` to bisect
   with, so equi-depth is meaningless.

The MCV slot for distinct stats uses `STATISTIC_KIND_MCV` with
`staop = mystats->eqopr` (analyze.c:2418).  Selectivity probes
like `WHERE x = 5` use this directly via `eqsel`.

## `compute_trivial_stats` — last resort

`analyze.c:2027-2101` (not fully read above).  Used when even
`=` is missing.  Computes only:

- `stanullfrac` (fraction of nulls)
- `stawidth` (average width)
- `stadistinct = 0` ("unknown")

No `stakind[*]` slots are filled.  The planner falls back to
hardcoded selectivity guesses for predicates on these columns
(typically `DEFAULT_EQ_SEL = 0.005` for `=`).

## Special edge cases handled inline

### All-too-wide

`analyze.c:2951-2963` [verified-by-code].  If every non-null
value exceeded `WIDTH_THRESHOLD`, we have `nonnull_cnt > 0` but
`values_cnt == 0`.  Stats are recorded with:

```c
stats->stadistinct = -1.0 * (1.0 - stats->stanullfrac);
```

— meaning "assume every non-null value is unique"
(the `-1.0` is the scaling-factor convention).

### All nulls

`analyze.c:2965-2974` [verified-by-code].  Empty values plus
zero non-nulls means the column is fully null:

```c
stats->stanullfrac = 1.0;
stats->stadistinct = 0.0;
```

`0.0` means "unknown" per the convention; the planner treats
this as a null-only column and skips selectivity work.

## What gets written to `pg_statistic`

After the compute function returns, `update_attstats`
(`analyze.c:1713-1853`) writes the slots into the catalog.  Each
slot's value array (`stavalues[i]`) is a real-array column
(`anyarray`) of one of two storage types:

- `stavaluesN typid` — the column's own type for histogram /
  MCV / etc.
- `stanumbersN[]` — `float4[]` for frequencies and lengths.

The `pg_statistic` rows are keyed by `(starelid, staattnum, stainherit)`.
Inheritance/partitioning produces two rows per child column: one
with `stainherit = false` (just this table) and one with
`stainherit = true` (this table + descendants).  The planner
chooses based on whether the scan is over just this rel or its
inheritance closure.

## Invariants worth remembering

1. **`std_typanalyze` picks one of three compute functions; never
   call them directly.**  The choice depends on what comparison
   operators the type has.
2. **The `tupnoLink` trick lets the dup-counting pass run in
   O(N) without extra comparator calls.**  Don't refactor it
   away without preserving the side-effect.
3. **MCV cutoff is statistical, not top-K.**  A 100-target
   stats target says "consider 100 candidates"; the actual
   stored count can be 0..100 depending on `analyze_mcv_list`.
4. **Histogram is equi-depth on the values *not in* the MCV
   list.**  This is what makes histogram-based selectivity
   composable with MCV lookup.
5. **Correlation = Pearson on (position-in-TID-order,
   position-in-value-order).**  Uses TID-order from the sort
   we did in `acquire_sample_rows`.  The closed-form Σx, Σx²
   constants make it a single-pass computation.
6. **`stadistinct` can be negative** — that means "scale with
   the row count" (-0.5 = each value appears in 50% of rows on
   average; -1.0 = unique).
7. **Too-wide values are skipped to avoid `O(N²)` detoasting.**
   `WIDTH_THRESHOLD` is the gate.
8. **Slot 0 = MCV, slot 1 = histogram, slot 2 = correlation for
   the scalar path.**  Type-specific analyzers may fill more.
9. **`staop[i]` is the operator the planner uses to walk the
   slot.**  Histogram uses `<`, MCV uses `=`, correlation uses
   `<`.
10. **No stats valid ⇒ planner uses hard-coded defaults.**  If
    `stats->stats_valid == false`, no `pg_statistic` row is
    written and `eqsel`/`scalarltsel` fall back to constants.

## Useful greps

```bash
# The three compute functions
grep -n "compute_trivial_stats\|compute_distinct_stats\|compute_scalar_stats" \
    source/src/backend/commands/analyze.c

# Slot-fill sites — which kinds go where
grep -n "stakind\[.*\] = STATISTIC_KIND" \
    source/src/backend/commands/analyze.c

# MCV cutoff function
grep -n "analyze_mcv_list" \
    source/src/backend/commands/analyze.c

# tupnoLink magic
grep -n "tupnoLink\|compare_scalars" \
    source/src/backend/commands/analyze.c

# The 300× heuristic
grep -n "300 \* stats->attstattarget\|minrows" \
    source/src/backend/commands/analyze.c

# Where the planner reads these slots back
grep -rn "STATISTIC_KIND_MCV\|STATISTIC_KIND_HISTOGRAM\|STATISTIC_KIND_CORRELATION" \
    source/src/backend/utils/adt/selfuncs.c | head
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/analyze.c`](../files/src/backend/commands/analyze.c.md) | — | std_typanalyze, all three compute_ |
| [`src/include/catalog/pg_statistic.h`](../files/src/include/catalog/pg_statistic.h.md) | — | STATISTIC_KIND_ |
| [`src/include/commands/vacuum.h`](../files/src/include/commands/vacuum.h.md) | — | VacAttrStats struct |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md)

<!-- /scenarios:auto -->
## Cross-references

- [[analyze-block-and-reservoir-sampling]] — where the sample
  rows come from; the TID-order invariant feeds the correlation
  here.
- [[extended-statistics-statext]] — the cross-column version.
- [[cost-units-gucs]] — `default_statistics_target` GUC scales
  `minrows = 300 × target`.
- [[planner-pathkeys]] — the planner's correlation cost model
  consumes `STATISTIC_KIND_CORRELATION`.
- [[index-scan-cost]] — `index_pages_fetched` uses the
  correlation slot to estimate physical-page hits.
- [[parallel-aggregate]] — for contrast, parallel paths produce
  their own per-worker stats but don't write `pg_statistic`.
- [[memory-contexts]] — `stats->anl_context` is the per-relation
  memory context; everything stored in `pg_statistic` is copied
  into it before catalog write.
