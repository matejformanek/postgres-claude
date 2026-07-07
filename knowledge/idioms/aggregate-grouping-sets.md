# GROUPING SETS / ROLLUP / CUBE — phases array + multi-sort tuplesort chaining

`GROUPING SETS ((a), (a,b), (a,b,c))` (and its sugar variants
`ROLLUP(a,b,c)` = `((), (a), (a,b), (a,b,c))` and `CUBE(a,b,c)` =
all subsets) ask for **multiple GROUP BY computations in a single
pass**. PostgreSQL's executor handles this via the **phases array**:
each Agg node decomposes the requested sets into N phases, where
each phase has a different sort ordering, and the executor runs N
passes over the data — except instead of N actual table scans, it
**chains tuplesorts** so phase K+1 reads phase K's tuplesort output
as its input.

The decomposition rules:

- Sets within a single sort-friendly group (e.g. ROLLUP's nested
  prefix sets) become **one phase**: the executor keeps N parallel
  trans-state arrays, advances all of them per input tuple, resets
  the appropriate states at group boundaries.
- Sets needing different sort orders become **separate phases**.
- Hashed sets (small-cardinality, e.g. `GROUPING SETS ((country))`
  where countries are few) become **phase 0**, processed alongside
  whichever sort phase happens to also be running. This is the
  AGG_MIXED strategy.

This doc walks the phases array structure, `initialize_phase`'s
tuplesort chaining, `select_current_set` for per-set state
selection, the per-grouping-set memory contexts, the GROUPING()
SQL function's bitmap, and the chain-field for stacking multiple
Agg nodes.

Companion docs:
- [[aggregate-hash-vs-sort.md]] — single-strategy execution.
- [[aggregate-trans-state]] — transvalue/transfunc/finalfunc.

## Anchors

- `source/src/backend/executor/nodeAgg.c:113-148` — banner section "Grouping sets".
- `source/src/backend/executor/nodeAgg.c:149-179` — banner section "Plan structure" (chain field).
- `source/src/backend/executor/nodeAgg.c:180-196` — banner "Memory and ExprContext usage".
- `source/src/backend/executor/nodeAgg.c:458-470` — `select_current_set`.
- `source/src/backend/executor/nodeAgg.c:472-539` — `initialize_phase` (tuplesort chaining).
- `source/src/backend/executor/nodeAgg.c:549-570` — `fetch_input_tuple`.
- `source/src/backend/executor/nodeAgg.c:1249-1282` — `prepare_projection_slot` (NULL out non-grouped cols).
- `source/src/include/executor/nodeAgg.h` — `AggStatePerPhaseData`, `AggStatePerGroupData`.
- `source/src/include/nodes/plannodes.h` — `Agg.groupingSets`, `Agg.chain`.

## The `Agg.chain` — multiple Agg nodes for one query

A GROUPING SETS query produces **one Agg node plus a chain of
auxiliary Agg nodes** for sets that need different processing
strategies:

```c
/* nodeAgg.c:149-165 (paraphrased from banner) */
typedef struct Agg {
    Plan          plan;
    AggStrategy   aggstrategy;     /* PLAIN / SORTED / HASHED / MIXED */
    AggSplit      aggsplit;        /* SIMPLE / INITIAL_SERIAL / FINAL_DESERIAL */
    int           numCols;
    AttrNumber   *grpColIdx;
    Oid          *grpOperators;
    long          numGroups;
    List         *groupingSets;
    List         *chain;           /* chained Agg nodes for OTHER sets */
    ...
} Agg;
```

Chain rules:
- The "real" Agg node is the first in the chain.
- The chain must order **hashed nodes before sorted/plain nodes**.
- If the real node is `AGG_MIXED`: hashed sets in the real node +
  this real node also processes the first sort phase; chained
  AGG_HASHED nodes for other hashed sets may follow, then
  AGG_SORTED nodes for the remaining sort orderings, then
  optionally one AGG_PLAIN.
- If the real node is `AGG_HASHED` or `AGG_SORTED`: all chained
  nodes must be the same strategy.
- If real is `AGG_PLAIN`: no chained nodes possible (a single
  grouping set covers the whole query).

[from-comment] (`nodeAgg.c:149-165`).

## The phases array — per-strategy execution

The executor's `AggState` carries a **phases array**:

```c
/* From AggState in nodeAgg.h (paraphrased) */
typedef struct AggState {
    ...
    AggStatePerPhase phase;             /* current phase pointer */
    int              numphases;
    AggStatePerPhaseData *phases;       /* array indexed by phase number */
    int              current_phase;
    int              num_hashes;
    int              numtrans;

    /* Per-grouping-set state */
    AggStatePerGroup *pergroups;        /* sorted sets: pergroups[setno] */

    /* Hashed-set state */
    AggStatePerHash perhash;            /* one per hashed grouping set */
    AggStatePerGroup *hash_pergroup;    /* current entries in hash tables */

    /* Sorting chain */
    Tuplesortstate *sort_in;            /* phase K's INPUT (from K-1's output) */
    Tuplesortstate *sort_out;           /* phase K's OUTPUT (for K+1) */

    /* Memory contexts */
    ExprContext   *hashcontext;          /* for hash tables */
    ExprContext  **aggcontexts;          /* one per grouping set */
    ExprContext   *tmpcontext;           /* per-tuple */
    ...
} AggState;

typedef struct AggStatePerPhaseData {
    AggStrategy strategy;
    Sort       *sortnode;                /* sort to apply at the END of this phase */
    int        *gset_lengths;            /* size of each set in this phase */
    Bitmapset **grouped_cols;            /* indexed by setno in this phase */
    Bitmapset  *all_grouped_cols;        /* union across sets in this phase */
    ...
    int         numsets;                 /* sets handled in this phase */
} AggStatePerPhaseData;
```

[verified-by-code] (`nodeAgg.c:373-401`, `nodeAgg.h`).

Phase 0 is **always reserved for hashing**, allocated even if there
are no hashed sets (unused in that case). Phases 1..n are sorted
phases. So a query with only AGG_HASHED has numphases = 1, only
phase 0 used; a query with only AGG_SORTED has numphases = 2 with
phase 0 empty and phase 1 used.

## A worked example — ROLLUP(a, b, c)

`SELECT a, b, c, sum(x) FROM t GROUP BY ROLLUP(a, b, c)`:

The grouping sets are `{(), (a), (a,b), (a,b,c)}`. All four can be
satisfied by **one sort order** on `(a, b, c)` and **parallel
trans-state arrays**:

- After tuple `(a=1, b=1, c=1)`: advance set (), (a), (a,b),
  (a,b,c) trans-states.
- When `c` changes (tuple `(a=1, b=1, c=2)`): emit `(a,b,c)`'s
  result, reset its trans-state.
- When `b` changes: emit `(a,b)`'s result + reset, also reset
  `(a,b,c)`.
- When `a` changes: emit `(a)` + reset, also reset `(a,b)` and
  `(a,b,c)`.
- At end of input: emit `()` (covers entire input).

This becomes **one phase** with `numsets = 4`, all sharing the
sort order `(a, b, c)`. The four trans-state arrays live in
`pergroups[setno]` indexed 0..3. `select_current_set(aggstate,
setno, false)` switches `current_set` and `curaggcontext` for the
trans-fn invocation.

[from-comment] (`nodeAgg.c:113-122` discusses this ROLLUP-style
processing).

## `select_current_set` — switch between sets

```c
/* nodeAgg.c:458-470 */
static void select_current_set(AggState *aggstate, int setno, bool is_hash)
{
    if (is_hash)
        aggstate->curaggcontext = aggstate->hashcontext;
    else
        aggstate->curaggcontext = aggstate->aggcontexts[setno];
    aggstate->current_set = setno;
}
```

Called from the per-tuple loop **once per grouping set the tuple
contributes to**. Sets the memory context that trans-fns will use
via `AggCheckCallContext`. The `is_hash` parameter routes to the
single shared `hashcontext` (since hash tables all share their
underlying memory) vs the per-set `aggcontexts[setno]` (for sorted
sets, where each set's trans-states get reset at group boundaries
independently).

The single hashcontext for all hashed sets — vs per-set context for
sorted sets — is a deliberate optimization: hash table entries
don't move between groups (entries are emitted once at end), so
they can share a context. Sorted sets have per-group reset, so
their contexts need to be independent. [from-comment]
(`nodeAgg.c:180-195`).

## More complex example — different sort orders

`GROUP BY GROUPING SETS ((a, b), (c, d))` needs two different sort
orderings — `(a, b)` and `(c, d)`. Can't combine in one phase.

The planner emits:

- Phase 1: AGG_SORTED with sort order `(a, b)`. Phase ends, emits
  results for `(a, b)`.
- Phase 2: AGG_SORTED with sort order `(c, d)`. The phase 1
  tuplesort_putintuple's the input tuples into a fresh tuplesort
  keyed on `(c, d)`, then phase 2 sorts that and aggregates.

`initialize_phase(aggstate, 2)` (`nodeAgg.c:480`) does:

```c
if (aggstate->sort_in) {
    tuplesort_end(aggstate->sort_in);   /* drop phase 1's input */
}

if (newphase <= 1) {
    /* Discard any open output (shouldn't be one at phase 0 or 1) */
} else {
    /* Phase 1's output becomes phase 2's input */
    aggstate->sort_in = aggstate->sort_out;
    aggstate->sort_out = NULL;
    tuplesort_performsort(aggstate->sort_in);    /* materialize */
}

/* For next phase, open a fresh tuplesort to capture our input */
if (newphase > 0 && newphase < aggstate->numphases - 1) {
    Sort *sortnode = aggstate->phases[newphase + 1].sortnode;
    aggstate->sort_out = tuplesort_begin_heap(
        ExecGetResultType(outerPlanState(aggstate)),
        sortnode->numCols, sortnode->sortColIdx,
        sortnode->sortOperators, sortnode->collations,
        sortnode->nullsFirst, work_mem, NULL, TUPLESORT_NONE);
}
```

[verified-by-code] (`nodeAgg.c:480-538`).

So during phase 1, every input tuple is **doubled**: it goes into
phase 1's aggregation (current run), AND `tuplesort_puttupleslot`'s
into `sort_out` for phase 2. At phase 1's end, `sort_out` becomes
phase 2's `sort_in`, `tuplesort_performsort` materializes it,
phase 2 reads sorted-by-(c,d) tuples.

The chain extends: a third phase's output tuplesort is opened
during phase 2, etc.

## `fetch_input_tuple` — the source-switching primitive

```c
/* nodeAgg.c:549-570 */
static TupleTableSlot *fetch_input_tuple(AggState *aggstate)
{
    if (aggstate->sort_in) {
        if (!tuplesort_gettupleslot(aggstate->sort_in, true, false,
                                     aggstate->sort_slot, NULL))
            return NULL;
        slot = aggstate->sort_slot;
    } else {
        slot = ExecProcNode(outerPlanState(aggstate));
    }

    if (!TupIsNull(slot) && aggstate->sort_out)
        tuplesort_puttupleslot(aggstate->sort_out, slot);

    return slot;
}
```

[verified-by-code] (`nodeAgg.c:549-570`).

The function is the **single point of input** for phases. It:

- Reads from `sort_in` if non-NULL (later phases) or
  `outerPlanState` (phase 1).
- Writes to `sort_out` if non-NULL (forwarding to next phase).

The "doubling" — read from outer, write to sort_out — is what
materializes the input once for use across all phases.

## AGG_MIXED — hash sets riding along with phase 1

When a query has both hashed AND sorted sets, the strategy is
AGG_MIXED:

- **Phase 0** (always) holds the hashed sets. The hash tables are
  populated **during phase 1** (the first sorted phase).
- After phase 1, the executor runs additional sorted phases
  normally, then finally reads out the hash tables.

The trick: during phase 1, `agg_fill_hash_table` is called per
tuple to update **both** the sorted-phase trans-states and the
hash tables. The per-tuple cost rises (hash + sorted both updated),
but we avoid a second pass over the data.

[from-comment] (`nodeAgg.c:133-138`).

## `prepare_projection_slot` — NULLing non-grouped columns

When emitting results for a grouping set, the columns **not in**
the set must be NULL in the output:

```c
/* nodeAgg.c:1249-1282 */
static void prepare_projection_slot(AggState *aggstate, TupleTableSlot *slot, int currentSet)
{
    if (aggstate->phase->grouped_cols) {
        Bitmapset *grouped_cols = aggstate->phase->grouped_cols[currentSet];
        aggstate->grouped_cols = grouped_cols;

        if (TTS_EMPTY(slot)) {
            /* Empty grouping set + no input → all NULLs */
            ExecStoreAllNullTuple(slot);
        } else if (aggstate->all_grouped_cols) {
            /* For columns in all_grouped_cols but NOT in this set's grouped_cols,
             * force NULL in the output */
            foreach(lc, aggstate->all_grouped_cols) {
                int attnum = lfirst_int(lc);
                if (!bms_is_member(attnum, grouped_cols))
                    slot->tts_isnull[attnum - 1] = true;
            }
        }
    }
}
```

[verified-by-code] (`nodeAgg.c:1249-1282`).

For `GROUP BY ROLLUP(a, b, c)`, the result for set `(a)` has
`b=NULL, c=NULL` in the output. The slot still contains the actual
`b` and `c` values from the last input tuple, but `tts_isnull`
flags them as NULL in the projection.

`all_grouped_cols` is the union of all grouped columns across all
sets in this phase, in descending order. The loop NULLs out
exactly the columns that are not part of this specific set.

## The `GROUPING()` SQL function

`GROUPING(a, b, c)` returns a bitmask indicating which of its
arguments are NULL due to grouping (vs naturally NULL). For
`ROLLUP(a, b, c)`:

| Result row     | GROUPING(a, b, c) |
|----------------|-------------------|
| (a, b, c)      | 0b000 = 0         |
| (a, b, NULL)   | 0b001 = 1         |
| (a, NULL, NULL)| 0b011 = 3         |
| (NULL, NULL, NULL) | 0b111 = 7    |

The mask is computed from the current set's `grouped_cols`
Bitmapset — bits NOT set in `grouped_cols` are NULL-due-to-grouping.

This lets queries distinguish "row where column c is NULL because
the group set excludes c" from "row where column c is NULL because
the data had a NULL there." [unverified — verified the bitmap
flag mechanism, exact `GROUPING()` evaluation deserves a deeper
read of `parse_agg.c`].

## Memory context layout

```
AggState
  ├── aggcontexts[0]                ← grouping set 0's trans-values
  │     ec_per_tuple_memory          (rescanned at group boundary)
  ├── aggcontexts[1]                ← grouping set 1's trans-values
  │     ec_per_tuple_memory          (rescanned independently)
  ├── ... (one per sorted set)
  ├── hashcontext                    ← all hash tables share this
  │     ec_per_tuple_memory          (lives until end of execution)
  ├── tmpcontext                     ← per-tuple work
  │     ec_per_tuple_memory          (reset per input)
  └── ss.ps.ps_ExprContext           ← per-output-tuple
        ec_per_tuple_memory          (reset per emitted result)
```

[from-comment] (`nodeAgg.c:180-195`).

Critical invariant: `aggcontexts` are **rescanned** (not just
reset) at group boundaries, so that any registered shutdown
callbacks (via `AggRegisterCallback`) run before the trans-state
goes away. The rescan also fires `ExprContextEx_CB` chains for
expanded-Datum tracking.

## Computing the result for one set — the loop

`agg_retrieve_direct` (for sorted modes) loops over grouping sets
per group boundary:

```c
/* Skeleton */
foreach setno in this_phase->numsets:
    select_current_set(aggstate, setno, false);
    prepare_projection_slot(aggstate, firstSlot, setno);
    finalize_aggregates(aggstate, peraggs, aggstate->pergroups[setno]);
    project_aggregates(aggstate);
    /* Emit one output tuple */
```

For hashed sets (in AGG_MIXED), there's a separate loop after all
sort phases finish that walks the hash tables.

## Invariants and races

1. **Phase 0 is always reserved for hashing**, even if no hashed
   sets exist. [from-comment] (`nodeAgg.c:167-170`).
2. **Phases process sequentially**, sorted-then-hashed. The
   tuplesort_in → tuplesort_out chain materializes the input
   once per phase.
3. **One AggStatePerGroup array per (set, transition)** for sorted
   sets; the hash table entries hold them for hashed sets.
4. **`select_current_set` switches both `current_set` and
   `curaggcontext`** — trans-fns query via
   `AggCheckCallContext()`. [verified-by-code]
   (`nodeAgg.c:464-469`).
5. **`prepare_projection_slot` NULLs columns not in this set's
   `grouped_cols`** — same input tuple yields different output
   tuples for different sets. [verified-by-code]
   (`nodeAgg.c:1262-1280`).
6. **`aggcontexts` is rescanned at group boundaries**, not just
   reset, so `ExprContextEx_CB` callbacks fire. [from-comment]
   (`nodeAgg.c:73-75`).
7. **The chain field organizes nodes by strategy**: hashed before
   sorted, all chained nodes share the real node's strategy unless
   the real is AGG_MIXED. [from-comment] (`nodeAgg.c:156-165`).
8. **GROUPING SETS with non-mergeable sort orders** uses
   tuplesort-chaining (materialize once per output sort).
9. **AGG_MIXED runs hashing concurrently with the first sort
   phase** — single pass over outer plan, multiple hash tables +
   trans-state arrays updated per tuple. [from-comment]
   (`nodeAgg.c:133-138`).
10. **An empty grouping set `()`** is the "grand total" — emits a
    row with all columns NULL and aggregates over the entire input.

## Useful greps

```bash
# Phase + set management:
grep -nE "^initialize_phase|^select_current_set|^fetch_input_tuple|^prepare_projection_slot|AggStatePerPhase" \
       source/src/backend/executor/nodeAgg.c

# Plan-tree representation:
grep -n "Agg.chain\|Agg.groupingSets\|GroupingSet\b" \
       source/src/include/nodes/plannodes.h \
       source/src/backend/optimizer/plan/

# Tuplesort chaining:
grep -nE "sort_in|sort_out|aggstate->phase\b" \
       source/src/backend/executor/nodeAgg.c | head -15

# Grouped-cols bitmaps:
grep -n "grouped_cols\|all_grouped_cols" \
       source/src/backend/executor/nodeAgg.c

# GROUPING() SQL function:
grep -n "GroupingFunc\|GROUPING_ID\|grouping_func" \
       source/src/backend/parser/parse_agg.c \
       source/src/backend/executor/execExpr.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 113 | banner section "Grouping sets" |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 149 | banner section "Plan structure" (chain field) |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 180 | banner "Memory and ExprContext usage" |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 458 | select_current_set |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 472 | initialize_phase (tuplesort chaining) |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 549 | fetch_input_tuple |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 1249 | prepare_projection_slot (NULL out non-grouped cols) |
| [`src/backend/optimizer/plan/planner.c`](../files/src/backend/optimizer/plan/planner.c.md) | — | make_grouping_sets_plans is the planner-side construction |
| [`src/backend/parser/parse_agg.c`](../files/src/backend/parser/parse_agg.c.md) | — | transformGroupingFunc |
| [`src/include/executor/nodeAgg.h`](../files/src/include/executor/nodeAgg.h.md) | — | AggStatePerPhaseData, AggStatePerGroupData |
| [`src/include/nodes/plannodes.h`](../files/src/include/nodes/plannodes.h.md) | — | Agg.groupingSets, Agg.chain |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)
- [`add-new-hook`](../scenarios/add-new-hook.md)
- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)

<!-- /scenarios:auto -->

## Cross-references

- [[aggregate-hash-vs-sort]] — strategy machinery in single-set mode.
- [[aggregate-trans-state]] — transvalue + transfunc.
- [[aggregate-partial-finalize]] — parallel aggregation decomposition.
- `source/src/backend/optimizer/plan/planner.c` — `make_grouping_sets_plans` is the planner-side construction.
- `source/src/backend/parser/parse_agg.c` — `transformGroupingFunc`.
