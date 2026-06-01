# nodeAgg.c

- **Source:** `source/src/backend/executor/nodeAgg.c` (≈4900 lines; 149 KB)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (entry points + HashAgg spill + transition build)

## Purpose

Executes both **sorted Group Aggregation** and **Hash Aggregation**, including
the GROUPING SETS / CUBE / ROLLUP combinations and DISTINCT/ORDER-BY-inside-aggregate
variants. Also supports **partial aggregation** (combine/serialize/deserialize)
for parallel and FDW partial aggregation. [from-comment] `:3-50`

## Aggregate algorithm

The 4-line pseudocode at the top of the file is the canonical reference:

    transvalue = initcond
    foreach input_tuple do
        transvalue = transfunc(transvalue, input_value(s))
    result = finalfunc(transvalue, direct_argument(s))

## `aggsplit` modes

- `AGGSPLIT_SIMPLE` — normal.
- `AGGSPLIT_INITIAL_SERIAL` — run transfunc, skip finalfunc, serialize. (Partial
  aggregation, lower half.)
- `AGGSPLIT_FINAL_DESERIAL` — deserialize input, use combinefunc instead of
  transfunc, run finalfunc. (Partial aggregation, upper half.)

The planner picks compatible pairs and inserts a Gather (or similar) in
between. [from-comment] `:16-32`

## Two run modes per Agg node

### Sorted/Plain (`AGG_PLAIN`, `AGG_SORTED`)

`ExecAgg` `:2247` → `agg_retrieve_direct` `:2283`. Reads input rows in
sorted order. On each PARTITION boundary (or single group for plain) it
finalizes the current group's transvalues, emits one output row, then starts
a new group. For GROUPING SETS with sorted strategy, multiple parallel
"phases" alternate via Sort nodes between phases.

### Hashed (`AGG_HASHED`, `AGG_MIXED`)

`ExecAgg` → `agg_fill_hash_table` `:2629` (one-time pass through input,
populating a TupleHashTable per grouping set), then `agg_retrieve_hash_table`
`:2837`. Each entry has its transition values inline via the
`additionalsize` mechanism of execGrouping.c. AGG_MIXED combines one
sorted grouping set with hashed grouping sets in a single Agg node.

#### Spilling

If `work_mem` is exceeded during the build pass, `lookup_hash_entries` `:2184`
detects it and **partition-spills** rows whose groups didn't yet exist into
N output tapes via `hashagg_spill_init` `:2986`. After the in-memory groups
are emitted, we recurse: re-open each spill tape and re-aggregate, possibly
spilling further (depth tracked, partitions doubled). This is PG 13+ behavior;
older PGs would OOM. [from-comment around spill init]

## Per-aggregate state

For each Aggref in the targetlist, an `AggStatePerTrans` records the
transfn/combinefn/serialfn/finalfn, initial value, transition type, strict
flags, DISTINCT/ORDER BY handling. Built in `build_pertrans_for_aggref`
`:4131`. **Multiple Aggrefs sharing the same transition function and
arguments share a single PerTrans** — this is what makes
`AVG(x), SUM(x)` only do the SUM transition once.

## The hot per-row work is in an ExprState

`ExecBuildAggTrans` (in execExpr.c, see that doc) compiles one ExprState that
walks every active Aggref's transition for the current input row. ExecAgg
calls `ExecEvalExpr` on it once per input row — there is no Aggref-tree-walk
at runtime. This is a major performance win circa PG 12.

## Parallel

- `ExecAggEstimate / InitializeDSM / InitializeWorker` `:4781+` — DSM
  parameters for the shared hash table when **parallel hashagg with shared
  hashtable** is in use (PG 16+; the patch added a barrier-based spill
  protocol). For partial agg (combine functions), nodes are independent.
- `ExecAggRetrieveInstrumentation` — merge worker stats.

## Grouping sets implementation

GROUPING() in expressions becomes an `EEOP_AGG_GROUPED_COL_*` reading the
current phase's grouping mask. Sorted GROUPING SETS use multiple phases
each with its own sort order; HashAgg with grouping sets builds one hash
table per set in parallel.

## Tags

- [verified-by-code] entry points + the build/retrieve split.
- [from-comment] the aggsplit modes + spilling rationale.
- [inferred] perf rationale for shared PerTrans.
