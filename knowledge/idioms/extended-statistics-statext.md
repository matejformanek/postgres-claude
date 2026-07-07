# Extended statistics — `CREATE STATISTICS` and the four kinds

The single-column statistics built by `std_typanalyze`
(see [[analyze-mcv-histogram-correlation]]) treat columns as
independent.  This breaks badly when reality says otherwise:
selectivity of `WHERE zip = 94103 AND city = 'San Francisco'`
isn't `P(zip) × P(city)` because zip determines city.

`CREATE STATISTICS` is PG's tool for telling the planner about
exactly this kind of dependence.  Four statistic *kinds* are
defined; each gets its own build function and its own
selectivity contribution in `clauselist_selectivity`.

This doc covers the build path (what ANALYZE writes into
`pg_statistic_ext_data`) and the structure of each kind.  The
selectivity-estimation side belongs to a separate doc on
`clauselist_selectivity`.

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/statistics/extended_stats.c` — `BuildRelationExtStatistics` dispatcher
- `source/src/backend/statistics/dependencies.c` — `STATS_EXT_DEPENDENCIES`
- `source/src/backend/statistics/mvdistinct.c` — `STATS_EXT_NDISTINCT`
- `source/src/backend/statistics/mcv.c` — `STATS_EXT_MCV`
- `source/src/backend/statistics/README` — overview
- `source/src/backend/statistics/README.dependencies` — soft dep algorithm
- `source/src/backend/statistics/README.mcv` — multivariate MCV

## The four kinds

From `pg_statistic_ext.h:88-91` [verified-by-code]:

```c
#define STATS_EXT_NDISTINCT     'd'
#define STATS_EXT_DEPENDENCIES  'f'
#define STATS_EXT_MCV           'm'
#define STATS_EXT_EXPRESSIONS   'e'
```

Each is a single-character `char` stored in `pg_statistic_ext.stxkind[]`
(an array, because one statistics object can ask for multiple
kinds at once).

| Kind | Purpose | What clause types it estimates |
|---|---|---|
| `d` ndistinct | combined `n_distinct(a, b, ...)` for groups of columns | GROUP BY, DISTINCT row counts |
| `f` dependencies | soft functional dependencies `a => b` with degree ∈ [0,1] | AND of equality clauses |
| `m` MCV | multivariate most-common-value list | AND/OR of equality and inequality |
| `e` expressions | per-expression `std_typanalyze` slots for indexed expressions | same as single-column stats, but on `(a + b)` etc. |

The README §Types of statistics (lines 12-22) [from-README] is
the authoritative summary.

## The build dispatcher — `BuildRelationExtStatistics`

`extended_stats.c:111-247` [verified-by-code].  Called from
`do_analyze_rel` after `acquire_sample_rows` has produced the
sample rows.  The shape:

```c
foreach(lc, statslist)
{
    StatExtEntry *stat = ...
    MVNDistinct *ndistinct = NULL;
    MVDependencies *dependencies = NULL;
    MCVList    *mcv = NULL;
    Datum exprstats = (Datum) 0;

    stats = lookup_var_attr_stats(stat->columns, stat->exprs,
                                  natts, vacattrstats);

    /* compute statistics target for this statistics object */
    stattarget = statext_compute_stattarget(stat->stattarget,
                                            bms_num_members(stat->columns),
                                            stats);

    if (stattarget == 0) continue;

    data = make_build_data(onerel, stat, numrows, rows, stats, stattarget);

    foreach(lc2, stat->types)
    {
        char t = (char) lfirst_int(lc2);

        if (t == STATS_EXT_NDISTINCT)
            ndistinct = statext_ndistinct_build(totalrows, data);
        else if (t == STATS_EXT_DEPENDENCIES)
            dependencies = statext_dependencies_build(data);
        else if (t == STATS_EXT_MCV)
            mcv = statext_mcv_build(data, totalrows, stattarget);
        else if (t == STATS_EXT_EXPRESSIONS)
        {
            /* per-expression std_typanalyze slots */
            exprdata = build_expr_data(stat->exprs, stattarget);
            compute_expr_stats(onerel, exprdata, nexprs, rows, numrows);
            exprstats = serialize_expr_stats(exprdata, nexprs);
        }
    }

    statext_store(stat->statOid, inh,
                  ndistinct, dependencies, mcv, exprstats, stats);
}
```

[verified-by-code at lines 152-239]

Three things to notice:

1. **The sample rows are shared** with single-column ANALYZE —
   no second pass over the table.  This is what makes
   `CREATE STATISTICS` no more expensive than ordinary ANALYZE
   in I/O terms.
2. **Per-statistics-object memory context.**
   `BuildRelationExtStatistics` allocates a child memcontext at
   line 132-134 and `MemoryContextReset(cxt)` at line 238 after
   each object.  Each object can allocate freely; everything
   gets freed in one shot.
3. **`statext_store` writes one row to `pg_statistic_ext_data`
   per object**, with one column per kind serialized as `bytea`.

### Per-statistics target — three-level fallback

`statext_compute_stattarget` at `extended_stats.c:378-419`
[verified-by-code] (signature only shown above) resolves the
target as:

1. `stat->stattarget` if explicitly set on the statistics object
2. else the **max** `attstattarget` across the columns in the object
3. else `default_statistics_target` (100 default)
4. **0** means "don't build" — the object is skipped without
   error (analyze.c:194-195).

### Sample size — explicitly higher than per-column

`ComputeExtStatisticsRows` at `extended_stats.c:296-356`
[verified-by-code] is called by `do_analyze_rel` to figure out
how many sample rows it needs to feed the extended-stats
builders.  The formula at line 355:

```c
return (300 * result);
```

— so a stat object with target N triggers `300 * N` extra
sample rows beyond the per-column `targrows`.

The README §Size of sample in ANALYZE (lines 82-101)
[from-README] candidly acknowledges this is an unsolved
problem:

> Papers analyzing estimation errors all use samples proportional
> to the table (usually finding that 1-3% of the table is enough
> to build accurate stats). … This however merits further
> discussion, because collecting the sample is quite expensive and
> increasing it further would make ANALYZE even more painful.

## Kind `d` — multivariate ndistinct

`mvdistinct.c:84-138` [verified-by-code] — `statext_ndistinct_build`.

For a statistics object on `N` columns, the result is a list of
**every combination of 2..N columns**, each with an
ndistinct estimate.  Count is `2^N - (N+1)` — the
`num_combinations` function at `mvdistinct.c:565-569`
[verified-by-code]:

```c
static int
num_combinations(int n)
{
    return (1 << n) - (n + 1);
}
```

Why "subtract N+1"?  Each single-column ndistinct already lives
in `pg_statistic`, and the empty combination is degenerate.

The combination generator — `n_choose_k` at `mvdistinct.c:540-559`
[verified-by-code] — is a numerically careful binomial:

```c
k = Min(k, n - k);
r = 1;
for (d = 1; d <= k; ++d)
{
    r *= n--;
    r /= d;
}
```

Symmetry trick (`Min(k, n-k)`) cuts the loop count in half for
high `k`; the in-loop division by `d` keeps the running product
bounded so 32-bit `int` is enough for realistic column counts
(N <= 8 in `CREATE STATISTICS`).

### The Duj1 estimator

`mvdistinct.c:512-533` [verified-by-code] — `estimate_ndistinct`:

```c
numer = (double) numrows * (double) d;
denom = (double) (numrows - f1) +
        (double) f1 * (double) numrows / totalrows;
ndistinct = numer / denom;

/* Clamp to sane range in case of roundoff error */
if (ndistinct < (double) d) ndistinct = (double) d;
if (ndistinct > totalrows) ndistinct = totalrows;
return floor(ndistinct + 0.5);
```

Where:

- `numrows` — sample size
- `d` — distinct values seen in the sample
- `f1` — number of values seen *exactly once* in the sample
  (singletons)
- `totalrows` — estimated rows in the table

This is the **Duj1** (Duj-1) estimator — the same one
`compute_scalar_stats` uses for single-column ndistinct.  The
header comment at `mvdistinct.c:511`:

> The Duj1 estimator (already used in analyze.c).

Intuition: many singletons in the sample ⇒ likely more distinct
values in the full table.  No singletons ⇒ the sample's `d` is
probably already close to the true distinct count.

### How a combination is counted

`ndistinct_for_combination` (not fully shown above) sorts the
sample lexicographically by the combination's attributes (using
`multi_sort_compare` from `statistics/mvdistinct.c:485-507`),
walks once counting groups (`d`) and singletons (`f1`), then
calls `estimate_ndistinct`.

## Kind `f` — soft functional dependencies

`dependencies.c:341-490` (`statext_dependencies_build`) plus the
core function `dependency_degree` at `dependencies.c:214-323`
[verified-by-code].

### What "soft" means

The README.dependencies §Soft dependencies (lines 39-54)
[from-README] is the rationale:

> Real-world data sets often contain data errors … For this
> reason, extended statistics implement "soft" functional
> dependencies, associating each functional dependency with a
> degree of validity (a number between 0 and 1).

A degree of `1.0` means the dependency held for every row of
the sample; `0.0` means it held for none; intermediate values
weight the dependency proportionally during selectivity
computation.

### The algorithm — sort and count consistent groups

From `dependency_degree` (lines 244-322) [verified-by-code]:

```c
/* (a) sort lexicographically */
items = build_sorted_items(data, &nitems, mss, k, attnums_dep);

/* (b) walk groups by first (k-1) columns */
group_size = 1;
for (i = 1; i <= nitems; i++)
{
    if (i == nitems ||
        multi_sort_compare_dims(0, k - 2, &items[i - 1], &items[i], mss) != 0)
    {
        if (n_violations == 0)
            n_supporting_rows += group_size;
        n_violations = 0;
        group_size = 1;
        continue;
    }
    /* same first (k-1), different last column => contradicting */
    else if (multi_sort_compare_dim(k - 1, &items[i - 1], &items[i], mss) != 0)
        n_violations++;
    group_size++;
}

return (n_supporting_rows * 1.0 / data->numrows);
```

Plain English of the README.dependencies §Mining dependencies
(lines 64-72) [from-README]:

> (a) Sort the data lexicographically, i.e. first by 'a' then 'b'.
> (b) For each group of rows with the same 'a' value, count the
> number of distinct values in 'b'.
> (c) If there's a single distinct value in 'b', the rows are
> consistent with the functional dependency, otherwise they
> contradict it.

The "soft" bit is the degree = `supporting_rows / total_rows`.
A few rows with bad data lower the degree gradually instead of
disqualifying the dependency entirely.

### All directions are tried — N²-many

`statext_dependencies_build` (lines 358-489) [verified-by-code]
loops over `k = 2 .. N` and for each `k`, every ordered
variation (not combination — direction matters) of `k` attributes:

> Generates all possible subsets of columns (variations) and
> computes the degree of validity for each one.

The 3-column example from the comment at line 326-340
[from-comment]:

```
two columns          three columns
-----------          -------------
(a) -> b             (a,b) -> c
(a) -> c             (a,c) -> b
(b) -> a             (b,c) -> a
(b) -> c
(c) -> a
(c) -> b
```

For N=3 that's 9 dependencies; for N=8 it grows fast (the
combinatorial explosion is what caps practical statistics
objects at ~8 columns).

### Selectivity formula

README.dependencies §Clause reduction (lines 75-92)
[from-README] gives the formula the planner uses:

```
P(a=?, b=?) = P(a=?) * (d + (1 - d) * P(b=?))
```

`d` is the degree.  At `d = 0`, this reduces to the
independence-assumption product.  At `d = 1`, it reduces to
just `P(a=?)` — meaning b is fully determined by a so adding
the `b = ?` clause doesn't subdivide further.  Smooth
intermediate behavior.

## Kind `m` — multivariate MCV

`mcv.c:177-554` (`statext_mcv_build`).  This is the most
information-rich extended-stat kind: a list of the most common
**combinations** of values, each with a frequency and a
"base frequency" (what the frequency would be under
independence).

### Why it works

README.mcv §Selectivity estimation (lines 29-47) [from-README]:

> The estimation, implemented in mcv_clauselist_selectivity(),
> is quite simple in principle - we need to identify MCV items
> matching all the clauses and sum frequencies of all those
> items.

For a query like `WHERE a = 1 AND b = 2`, the selectivity is
the sum of frequencies of MCV items where `a == 1 AND b == 2`.
This **exactly** counts the correlated probability mass — no
independence assumption involved.

### What clause types it handles

Lines 36-41 [from-README]:

> (a) equality clauses      WHERE (a = 1) AND (b = 2)
> (b) inequality clauses    WHERE (a < 1) AND (b >= 2)
> (c) NULL clauses          WHERE (a IS NULL) AND (b IS NOT NULL)
> (d) OR clauses            WHERE (a < 1) OR (b >= 2)

The breadth here is why MCV is the *strongest* of the four
kinds — it can replace dependencies for AND-of-equality and
also handle ranges and OR.  Cost: it stores actual values
(potentially large), and the build path runs a full multi-sort
+ frequency analysis.

### Storage — `pg_mcv_list` type

README.mcv §Inspecting the MCV list (lines 72-104) [from-README]
explains the custom on-disk type:

> So instead the MCV lists are stored in a custom data type
> (pg_mcv_list), which however makes it more difficult to
> inspect the contents.  To make that easier, there's a SRF
> returning detailed information about the MCV lists.

The SRF `pg_mcv_list_items(stxdmcv)` returns one row per item
with columns: index, values (string array), nulls (boolean
array), frequency, base_frequency.  Useful for debugging.

The on-disk format de-duplicates values across the list —
since the same value can appear in many items (e.g. value `1`
might be in `(1, 'a')`, `(1, 'b')`, `(1, 'c')`), storing it
once with index references saves a lot of space for low-
cardinality dimensions.

## Kind `e` — per-expression statistics

`extended_stats.c:213-225` [verified-by-code]:

```c
exprdata = build_expr_data(stat->exprs, stattarget);
nexprs = list_length(stat->exprs);
compute_expr_stats(onerel, exprdata, nexprs, rows, numrows);
exprstats = serialize_expr_stats(exprdata, nexprs);
```

For a statistics object created with `CREATE STATISTICS s ON
(a + b) FROM t`, this kind runs **the regular**
`std_typanalyze` pipeline on the *result* of the expression —
producing MCV, histogram, and correlation slots just as
`compute_scalar_stats` would for an ordinary column.

The output is stored as a row of nested `pg_statistic`-like
slots, serialized to `bytea`.  The planner consumes it via
`examine_variable` when it sees a query reference matching the
expression — for example `WHERE (a + b) = 42` would look up the
serialized stats and use them as if `(a + b)` were a real
column.

This kind exists primarily because **expression indexes don't
implicitly produce statistics on the expression unless the index
is on disk**.  Without `STATS_EXT_EXPRESSIONS`, the planner has
to fall back to default constants for expression predicates,
which is often very wrong.

## How `BuildRelationExtStatistics` interacts with autovacuum

The `WARNING` at `extended_stats.c:172-181` [verified-by-code]
is suppressed for autovacuum workers:

```c
if (!stats)
{
    if (!AmAutoVacuumWorkerProcess())
        ereport(WARNING,
                (errcode(ERRCODE_INVALID_OBJECT_DEFINITION),
                 errmsg("statistics object \"%s.%s\" could not be computed..."));
    continue;
}
```

This is the standard pattern: user-driven `ANALYZE` should
warn loudly when something can't be built (typically because
the user analyzed only some columns); autovacuum should stay
quiet because nobody is reading its log output for
informational messages.

## `HasRelationExtStatistics` — the planner's fast probe

`extended_stats.c:252-281` [verified-by-code].  Single `systable_beginscan`
on `pg_statistic_ext` keyed by `stxrelid`:

```c
ScanKeyInit(&skey,
            Anum_pg_statistic_ext_stxrelid,
            BTEqualStrategyNumber, F_OIDEQ,
            ObjectIdGetDatum(RelationGetRelid(onerel)));
scan = systable_beginscan(pg_statext, StatisticExtRelidIndexId, true,
                          NULL, 1, &skey);
found = HeapTupleIsValid(systable_getnext(scan));
systable_endscan(scan);
```

This is what `clauselist_selectivity` calls **first** to decide
whether to attempt the extended-stats path at all.  Skipping
extended-stats logic for relations without any objects is the
common case, and it has to be cheap.

## What lives where on disk

`pg_statistic_ext` holds the *definition* of a statistics object
(name, owner, target, list of kinds requested, list of columns or
expressions).  `pg_statistic_ext_data` holds the actual
serialized data, with one column per kind:

| `pg_statistic_ext_data` column | Stores |
|---|---|
| `stxdndistinct` | serialized `MVNDistinct` |
| `stxddependencies` | serialized `MVDependencies` |
| `stxdmcv` | serialized `MCVList` (`pg_mcv_list` type) |
| `stxdexpr` | serialized per-expression stats |
| `stxdinherit` | `true` for the inheritance-tree row, `false` for own |

Two rows per object: `stxdinherit = false` (just this relation)
and `stxdinherit = true` (this relation + descendants if it's
a partitioned table).  The planner picks based on whether the
scan is over the inheritance tree.

## Invariants worth remembering

1. **Extended stats share sample rows with single-column ANALYZE.**
   No second pass over the table.
2. **Per-object stattarget is `max(stat->stattarget, max attstattarget,
   default_statistics_target)`.**  `stattarget = 0` ⇒ skip the
   object.
3. **`stat->types` is a list of kind characters.**  One stat
   object can request MCV + dependencies + ndistinct
   simultaneously; the build dispatcher calls each builder.
4. **`statext_store` writes one row to `pg_statistic_ext_data`
   per object**, not one row per kind.
5. **Soft dependency degree ∈ [0, 1]; degree = `supporting_rows /
   total_rows`.**  Tolerates data noise.
6. **All `k`-attribute variations are tested for dependencies —
   `O(N!)` in worst case** but capped because PG caps statistics
   objects at modest column counts.
7. **MCV stores actual values plus a deduplication index.**
   Storage cost scales with item-count × value-size, not
   item-count × dimensions.
8. **Expression stats are just `std_typanalyze` slots on the
   expression's output, stored under the stat object.**
9. **Inheritance produces two rows per object** —
   `stxdinherit = false` and `stxdinherit = true`.
10. **`HasRelationExtStatistics` is the planner's gate.**  If
    it returns false, no extended-stats lookup happens; tables
    without `CREATE STATISTICS` pay nothing.

## Useful greps

```bash
# Top-level dispatcher
grep -n "statext_ndistinct_build\|statext_dependencies_build\|statext_mcv_build" \
    source/src/backend/statistics/extended_stats.c

# Per-kind builders
grep -n "^statext_.*build" \
    source/src/backend/statistics/{mvdistinct,dependencies,mcv}.c

# The four kind characters
grep -rn "STATS_EXT_NDISTINCT\|STATS_EXT_DEPENDENCIES\|STATS_EXT_MCV\|STATS_EXT_EXPRESSIONS" \
    source/src/backend/statistics/

# Planner-side consumers
grep -rn "statext_dependencies_load\|statext_ndistinct_load\|statext_mcv_load" \
    source/src/backend/

# Soft-dependency math
grep -n "n_supporting_rows\|dependency_degree" \
    source/src/backend/statistics/dependencies.c

# Duj1 estimator (reused from analyze.c)
grep -n "estimate_ndistinct\|Duj1" \
    source/src/backend/statistics/mvdistinct.c \
    source/src/backend/commands/analyze.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| `src/backend/statistics/README.dependencies` | — | soft dep algorithm |
| `src/backend/statistics/README.mcv` | — | multivariate MCV |
| [`src/backend/statistics/dependencies.c`](../files/src/backend/statistics/dependencies.c.md) | — | STATS_EXT_DEPENDENCIES |
| [`src/backend/statistics/extended_stats.c`](../files/src/backend/statistics/extended_stats.c.md) | — | BuildRelationExtStatistics dispatcher |
| [`src/backend/statistics/mcv.c`](../files/src/backend/statistics/mcv.c.md) | — | STATS_EXT_MCV |
| [`src/backend/statistics/mvdistinct.c`](../files/src/backend/statistics/mvdistinct.c.md) | — | STATS_EXT_NDISTINCT |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[analyze-block-and-reservoir-sampling]] — produces the
  sample rows that extended stats consume.
- [[analyze-mcv-histogram-correlation]] — single-column
  `pg_statistic`; extended stats are a strict superset for the
  cross-column case.
- [[planner-pathkeys]] — `clauselist_selectivity` is where the
  extended-stats math is actually applied during planning.
- [[catalog-conventions]] — `pg_statistic_ext` and
  `pg_statistic_ext_data` follow the standard catalog patterns
  (one defn row + one data row keyed by stxoid).
- [[memory-contexts]] — per-statistics-object child memcontext +
  `MemoryContextReset` after each object is canonical pattern.
- [[fmgr-and-spi]] — `lookup_type_cache(TYPECACHE_LT_OPR)` and
  `multi_sort_add_dimension` cache `<` operators per dimension.
