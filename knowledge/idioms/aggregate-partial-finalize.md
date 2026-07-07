# Partial aggregation — AGGSPLIT_* modes with combinefn / serialfn / deserialfn

A single aggregation can be decomposed across two Agg nodes — a
**partial** node that computes per-partition trans-values, and a
**final** node that merges them. The decomposition is the foundation
of:

- **Parallel aggregation**: each parallel worker runs a partial,
  Gather/GatherMerge collects the trans-values, the leader runs the
  final.
- **Partition-wise aggregation**: each partition's child Agg
  computes a partial; an Append + final-Agg above merges.
- **Cross-server aggregation** in postgres_fdw and similar.

The aggregate's pg_aggregate row must declare a **combinefn** (and
optionally serialfn/deserialfn for pass-by-ref trans-states that
need to traverse worker boundaries). Without combinefn, partial
aggregation is impossible — the planner won't generate the split.

This doc covers the `AGGSPLIT_*` enum + bit primitives, the
parallel-aggregation plan shape (PartialAggregate → Gather →
FinalizeAggregate), the serialize/deserialize transition for
pass-by-ref trans-values, the planner's combine-fn validation, and
the "shareable state" rule for FDW aggregate pushdown.

Companion docs:
- [[aggregate-trans-state]] — base transfunc/finalfunc model.
- [[aggregate-hash-vs-sort]] — execution strategies.
- [[aggregate-grouping-sets]] — GROUPING SETS handling.
- [[parallel-gather-merge]] — Gather/GatherMerge consumer.

## Anchors

- `source/src/include/nodes/nodes.h:370-398` — `AggSplit` enum + `AGGSPLITOP_*` bit definitions + `DO_AGGSPLIT_*` predicates.
- `source/src/backend/executor/nodeAgg.c:16-31` — banner: "Other behaviors can be selected by the aggsplit mode."
- `source/src/backend/executor/nodeAgg.c:1148-1198` — `finalize_partialaggregate` (serializefn invocation).
- `source/src/backend/executor/nodeAgg.c:3762-3900` — `ExecInitAgg` serial/deserial fn resolution.
- `source/src/backend/optimizer/plan/createplan.c` — `create_agg_plan` + Path-to-Plan conversion sets `aggsplit`.
- `source/src/backend/optimizer/plan/planner.c` — `make_partial_grouping_target` + parallel-agg path generation.
- `source/src/include/catalog/pg_aggregate.h` — `Form_pg_aggregate` with `aggcombinefn`, `aggserialfn`, `aggdeserialfn`.

## The AggSplit enum — four primitive flags

```c
/* nodes.h:377-381 */
#define AGGSPLITOP_COMBINE      0x01    /* substitute combinefn for transfn */
#define AGGSPLITOP_SKIPFINAL    0x02    /* skip finalfn, return state as-is */
#define AGGSPLITOP_SERIALIZE    0x04    /* apply serialfn to output */
#define AGGSPLITOP_DESERIALIZE  0x08    /* apply deserialfn to input */

/* The three useful combinations */
typedef enum AggSplit {
    AGGSPLIT_SIMPLE         = 0,
    AGGSPLIT_INITIAL_SERIAL = AGGSPLITOP_SKIPFINAL | AGGSPLITOP_SERIALIZE,
    AGGSPLIT_FINAL_DESERIAL = AGGSPLITOP_COMBINE | AGGSPLITOP_DESERIALIZE,
} AggSplit;

#define DO_AGGSPLIT_COMBINE(as)     (((as) & 0x01) != 0)
#define DO_AGGSPLIT_SKIPFINAL(as)   (((as) & 0x02) != 0)
#define DO_AGGSPLIT_SERIALIZE(as)   (((as) & 0x04) != 0)
#define DO_AGGSPLIT_DESERIALIZE(as) (((as) & 0x08) != 0)
```

[verified-by-code] (`nodes.h:370-398`).

The four bits compose into three modes the AM actually supports:

- **`AGGSPLIT_SIMPLE = 0`** — the normal mode: transfn for every
  input, finalfn at end. The default created by the parser.
- **`AGGSPLIT_INITIAL_SERIAL`** = `SKIPFINAL | SERIALIZE` — the
  **partial** node: run transfn as normal, but DON'T run finalfn;
  instead, apply serialfn to convert pass-by-ref trans-value to a
  `bytea`-compatible representation that can cross worker
  boundaries.
- **`AGGSPLIT_FINAL_DESERIAL`** = `COMBINE | DESERIALIZE` — the
  **final** node: deserialize incoming `bytea` to trans-value
  format, then use combinefn (not transfn) to merge with the
  running state. After all inputs, finalfn runs as normal.

The planner sets `Agg.aggsplit` based on its decomposition
strategy. The parser always sets `AGGSPLIT_SIMPLE`. [from-comment]
(`primnodes.h:444`).

## The combinefn — N-way merge of trans-values

`pg_aggregate.aggcombinefn` is declared as:

```sql
combinefn(state1 stype, state2 stype) RETURNS stype
```

Both arguments are trans-values of the aggregate's stype. The
function merges state2 into state1 (which can be modified
in-place per the same "trans-fns own their input" optimization
that transfn uses).

For `sum(int8)`: combinefn is just addition (`int8_avg_combine`
sums the two int8 counts).
For `array_agg`: combinefn appends one array to another.
For `avg(numeric)`: combinefn merges two `(sum, count)` records.
For `min/max`: combinefn picks the lesser/greater of the two.

If pg_aggregate.aggcombinefn is `0` (no combinefn declared), the
aggregate is **not parallel-safe** and the planner won't
decompose. Custom aggregates that want parallel support must
implement combinefn. [verified-by-code] — see `pg_aggregate.dat`
for examples.

## Why serialfn/deserialfn — pass-by-ref trans-values across workers

Parallel workers communicate via shared memory tuplestores (and
DSA segments). A trans-value that's a **pass-by-reference**
in-memory representation (e.g. `internal` type for hash aggregates,
or a complex struct with pointers) **cannot cross** these
boundaries — the receiving backend's pointers would be invalid.

The solution: declare serialfn + deserialfn to convert between
the internal representation and a `bytea` (or another
pass-by-value) representation:

```sql
serialfn(state stype) RETURNS bytea
deserialfn(bytea, internal) RETURNS stype
```

The internal-type trans-value is **never** transmitted; instead:

1. Partial worker runs transfn normally, accumulates the
   internal-state.
2. At the end, partial worker calls **serialfn** to get a `bytea`.
3. The `bytea` is sent to the leader via tuplestore.
4. Leader receives `bytea`, calls **deserialfn** to reconstruct
   the internal-state.
5. Leader's combinefn merges this into its running
   internal-state.
6. At the end of leader's aggregation, finalfn produces the SQL
   result.

For pass-by-value or simple pass-by-ref types (like `int8` or
`numeric`), serialfn/deserialfn aren't needed — the value can be
sent directly. The planner checks: if the trans-type is `internal`
or has its own serialization needs, both serialfn and deserialfn
**must** be declared, else parallel aggregation isn't allowed.

[verified-by-code] (`nodeAgg.c:3818-3850` for resolution + checks).

## `ExecInitAgg` — resolving serial/deserial fns

```c
/* nodeAgg.c:3762-3900 (skeleton) */
for each Aggref:
    if (DO_AGGSPLIT_SKIPFINAL(aggsplit)) {
        /* This is a partial node — skip finalfn */
        finalfn = InvalidOid;
        if (DO_AGGSPLIT_SERIALIZE(aggsplit)) {
            /* Must have a serialfn to convert internal-type out */
            if (!OidIsValid(aggform->aggserialfn))
                elog(ERROR, "no aggserialfn but SERIALIZE option");
            serialfn_oid = aggform->aggserialfn;
        }
    }
    if (DO_AGGSPLIT_DESERIALIZE(aggsplit)) {
        Assert(DO_AGGSPLIT_COMBINE(aggsplit));    /* always paired */
        if (!OidIsValid(aggform->aggdeserialfn))
            elog(ERROR, "no aggdeserialfn but DESERIALIZE option");
        deserialfn_oid = aggform->aggdeserialfn;
    }

    /* Permissions check on all functions (combine/serial/deserial in addition to trans/final) */
    if (OidIsValid(serialfn_oid))   object_aclcheck(...);
    if (OidIsValid(deserialfn_oid)) object_aclcheck(...);
```

[verified-by-code] (`nodeAgg.c:3800-3900`).

The init code resolves the four function OIDs:

- **`transfn_oid`**: the normal transfn (always required).
- **`combinefn_oid`**: substituted for transfn when
  `DO_AGGSPLIT_COMBINE(aggsplit)`. If aggform has no combinefn,
  `AGGSPLIT_FINAL_DESERIAL` fails at init.
- **`serialfn_oid`** / **`deserialfn_oid`**: as described above.
- **`finalfn_oid`**: only invoked if `!DO_AGGSPLIT_SKIPFINAL`.

## The serialize path — `finalize_partialaggregate`

```c
/* nodeAgg.c:1148-1197 (skeleton) */
static void finalize_partialaggregate(AggState *aggstate, AggStatePerAgg peragg,
                                       AggStatePerGroup pergroupstate,
                                       Datum *resultVal, bool *resultIsNull)
{
    /* Switch to per-output-tuple memory context */
    oldContext = MemoryContextSwitchTo(ps_ExprContext->ecxt_per_tuple_memory);

    if (OidIsValid(pertrans->serialfn_oid)) {
        if (pertrans->serialfn.fn_strict && pergroupstate->transValueIsNull) {
            /* Don't call strict serialfn on NULL */
            *resultVal = (Datum) 0;
            *resultIsNull = true;
        } else {
            /* Run serialfn(transvalue) → bytea */
            fcinfo->args[0].value = pergroupstate->transValue;
            fcinfo->args[0].isnull = pergroupstate->transValueIsNull;
            result = FunctionCallInvoke(fcinfo);
            *resultVal = result;
            *resultIsNull = fcinfo->isnull;
        }
    } else {
        /* No serialfn: pass trans-value as-is */
        *resultVal = pergroupstate->transValue;
        *resultIsNull = pergroupstate->transValueIsNull;
    }

    MemoryContextSwitchTo(oldContext);
}
```

[verified-by-code] (`nodeAgg.c:1148-1197`).

Called instead of `finalize_aggregate` when the Agg node is in
`AGGSPLIT_INITIAL_SERIAL` mode. The output column has the trans-
value's type (`stype`) when no serialfn, or `bytea` when serialfn
runs.

## The deserialize path — happens inside the mega-expression

For `AGGSPLIT_FINAL_DESERIAL`, the transfn is replaced by the
combinefn. The combinefn is called once per input row with `(state,
state)` — both arguments are trans-values. But the second
argument arrives from the outer plan as a `bytea` (the
serialized form from the partial worker), so we need
deserialization.

`ExecBuildAggTrans` emits a slightly different expression: an
`EEOP_AGG_DESERIALIZE` step that calls deserialfn on the input
column before passing it to the combinefn. The mega-expression
looks roughly like:

```
state := MakeExpandedObjectReadOnly(state);     // existing
incoming_bytea := outer_plan_column;
incoming_state := deserialfn(incoming_bytea);
state := combinefn(state, incoming_state);
```

[verified-by-code] — see `EEOP_AGG_DESERIALIZE` in
`execExpr.c`/`execExprInterp.c`.

The first-time case (when the partial-agg state is NULL on the
first call to combinefn) gets a strict-combinefn handling
identical to the strict-transfn handling: directly assign the
incoming state without combining.

## The parallel-agg plan shape

```
Final Agg (AGGSPLIT_FINAL_DESERIAL)
  Gather (or GatherMerge)
    Partial Agg (AGGSPLIT_INITIAL_SERIAL)
      Parallel SeqScan (or Parallel Index Scan, etc.)
```

Each parallel worker:

1. Reads its portion of the table.
2. Runs partial-agg with combinefn=N/A, finalfn=N/A, serialfn=
   active. Output is one row per group (or one row total for
   non-grouped) containing the serialized trans-value as bytea.

The Gather node:

3. Receives all workers' outputs. Each tuple has the same column
   structure: `(group_cols..., serialized_state_bytea)`.

The Final Agg:

4. Sees rows with the bytea column. For each row, deserialfn(bytea)
   → trans-value, combinefn(running_state, trans-value) updates
   running state.
5. At end of input, finalfn(running_state) produces SQL result.

If grouping is involved, the partial Agg might use AGG_SORTED or
AGG_HASHED — the choice is independent of the partial/final
split. Multiple workers each independently aggregate their
input, the Final Agg then merges across the worker boundary.

## Planner — `make_partial_grouping_target` + parallel paths

The planner generates parallel-agg paths in two places:

- **`add_paths_to_grouping_rel`** (in `planner.c`) — when the
  RelOptInfo for the post-grouping relation supports parallelism,
  add a `gather + partial agg` path alongside the normal full-agg
  path.
- **`create_partial_grouping_paths`** — actually constructs the
  partial Path; sets `AGGSPLIT_INITIAL_SERIAL` and computes the
  partial target (replacing each Aggref with a
  `*_partial` variant that returns the trans-value or bytea).

The "make_partial_grouping_target" call rewrites the projection so
the partial Agg outputs intermediate states (one column per
aggregate of stype or bytea) instead of finalfn results. The Final
Agg's projection later applies the finalfns.

Cost-wise, the planner picks parallel-agg when:

- `parallel_setup_cost + parallel_tuple_cost * worker_count *
  rows_per_worker` < single-agg path cost.
- The aggregate's `aggcombinefn` exists.
- If trans-state is `internal`, both `aggserialfn` and
  `aggdeserialfn` exist.
- The query's `parallel_safe` flag chain leads to a parallel-safe
  aggregate.

## Aggregate function declarations — what enables partial agg

```sql
CREATE AGGREGATE my_agg(int8) (
    SFUNC      = my_trans,
    STYPE      = internal,
    COMBINEFUNC = my_combine,        -- required for parallel
    SERIALFUNC  = my_serial,         -- required if stype = internal
    DESERIALFUNC = my_deserial,
    FINALFUNC   = my_final,
    PARALLEL    = SAFE               -- explicit safety declaration
);
```

The `PARALLEL = SAFE` clause on `CREATE AGGREGATE` is the
declarative gate. Without it, the planner won't generate a
parallel-agg plan even if all functions exist. This is the
safety valve for hand-written aggregates that may have side
effects.

Built-in aggregates declare these in `pg_aggregate.dat`. For
example, `sum(int8)` has `aggcombinefn = int8pl` (just add) and
no serialfn needed (its stype is int8, a fixed-width pass-by-
value... wait, it's actually `int128` in v15+, but still doesn't
need serialfn).

`array_agg` has `aggcombinefn = array_agg_array_combine` (which
concatenates two arrays), `aggserialfn = array_agg_serialize`,
`aggdeserialfn = array_agg_deserialize` — internal trans-type
needs all three.

## Partition-wise aggregation

`enable_partitionwise_aggregate` GUC enables a different
decomposition: each child partition's RelOptInfo gets its own
partial-Agg path, and an Append above merges into a final-Agg.

```
Final Agg (AGGSPLIT_FINAL_DESERIAL)
  Append
    Partial Agg (AGGSPLIT_INITIAL_SERIAL) ← partition 1
      Scan partition_1
    Partial Agg (AGGSPLIT_INITIAL_SERIAL) ← partition 2
      Scan partition_2
    ...
```

Same plumbing as parallel — same AggSplit modes, same
combinefn/serialfn requirements. The only difference: Append
instead of Gather (no parallel workers per se; the partitions
just provide a natural N-way input stream that the planner can
exploit).

When partition-wise + parallel are combined, each partition's
partial-Agg becomes a Parallel Partial Agg with its own Gather.

## FDW pushdown

Postgres_fdw can push aggregation **into** a remote server. The
remote runs a partial agg (`AGGSPLIT_INITIAL_SERIAL`), the local
node runs the final (`AGGSPLIT_FINAL_DESERIAL`). The serialized
trans-value travels over the wire as bytea.

This is opt-in per aggregate (the FDW needs to know the
aggregate can be safely pushed); see `is_foreign_pathkey` and
related logic in `postgres_fdw/deparse.c`. Not all aggregates
qualify — those without combinefn definitely don't.

## Two-stage aggregation via subquery

Users can manually two-stage an aggregation:

```sql
SELECT sum(s) FROM (
    SELECT sum(x) AS s FROM big_table GROUP BY partition_key
) sub;
```

This is conceptually similar to AGGSPLIT but uses two regular
AGGSPLIT_SIMPLE Agg nodes — no serialization involved because
the outer query's input is already SQL `int8` (not internal).
The combinefn isn't used. This works for aggregates where the
combinefn is essentially the same as transfn (like sum, count) but
not for ones where they differ (like `avg`, which needs special
combinefn to merge sums and counts).

The AGGSPLIT decomposition is the planner's automatic two-stage
that handles cases where combinefn ≠ transfn.

## Pre-final "trans-state as state2" trick

Note that in the partial path, the per-tuple loop still uses
**transfn**, not combinefn. The partial node is processing **raw
input tuples**, so transfn (`transvalue, input_value`) is right.
The combinefn is only invoked at the FINAL node, where each
"input" is itself a serialized partial trans-value.

The names "INITIAL" and "FINAL" in `AGGSPLIT_INITIAL_SERIAL` /
`AGGSPLIT_FINAL_DESERIAL` reflect this: INITIAL processes raw
data; FINAL merges already-aggregated states.

## Invariants and races

1. **`AGGSPLIT_COMBINE` and `_DESERIALIZE` are always paired** in
   `AGGSPLIT_FINAL_DESERIAL`. The combinefn expects trans-values;
   incoming data is bytea; deserialization is mandatory.
   [verified-by-code] (`nodeAgg.c:3833-3838`).
2. **`AGGSPLIT_SKIPFINAL` is in both INITIAL_SERIAL** (output is
   trans-value, not final result) and is implied wherever the
   trans-value isn't to be finalized. [from comment + code].
3. **No combinefn → no parallel agg.** The planner won't even
   consider it. [verified-by-code in planner].
4. **`internal` trans-type → serialfn + deserialfn required for
   parallel.** Without both, can't cross worker boundary.
   [verified-by-code] (`nodeAgg.c:3827-3840`).
5. **Strict serialfn skipped on NULL input** — identical pattern
   to strict transfn. [verified-by-code] (`nodeAgg.c:1163-1167`).
6. **The Partial Agg's output target uses partial Aggref types**
   (stype or bytea), not the original SQL result type. The Final
   Agg's projection reapplies the finalfn.
7. **Parallel-agg requires `aggparallel = SAFE` on the aggregate
   declaration**. Restricted/unsafe aggregates aren't decomposed.
   [verified-by-code] (`pg_aggregate.h`).
8. **DISTINCT or ORDER BY inside an aggregate disables parallel
   agg** because global ordering/uniqueness can't be partial-
   computed. [from-comment] (`nodeAgg.c:33-40`).
9. **The same `Aggref` node** appears in both partial and final
   Agg plans, but its `aggsplit` field is different. The two Aggs
   share the function lookups via the catalog but use different
   parts of the support function set.
10. **Combinefn can modify its first argument in place** — same
    optimization as transfn. The "left input is either initial
    state or previous combinefn result" property holds.
    [from-comment] (`nodeAgg.c:86-99`).

## Useful greps

```bash
# AggSplit modes + bits:
grep -n "AGGSPLIT_\|AGGSPLITOP_\|DO_AGGSPLIT" \
       source/src/include/nodes/nodes.h

# Where aggsplit is set in the planner:
grep -rn "aggsplit = AGGSPLIT\|->aggsplit" \
       source/src/backend/optimizer/

# Serial/deserial fn resolution:
grep -n "serialfn_oid\|deserialfn_oid\|aggserialfn\|aggdeserialfn" \
       source/src/backend/executor/nodeAgg.c

# Combinefn invocation point in the mega-expression:
grep -rn "EEOP_AGG_COMBINE\|EEOP_AGG_DESERIALIZE\|EEOP_AGG_SERIALIZE" \
       source/src/backend/executor/

# Parallel-agg path generation:
grep -n "create_partial_grouping_paths\|make_partial_grouping_target" \
       source/src/backend/optimizer/plan/planner.c

# FDW pushdown agg support:
grep -rn "is_foreign_grouping\|deparse_agg" \
       source/contrib/postgres_fdw/
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| `src/backend/catalog/system_functions.sql` | — | aggregate creation syntax |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 16 | banner: "Other behaviors can be selected by the aggsplit mode." |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 1148 | finalize_partialaggregate (serializefn invocation) |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 3762 | ExecInitAgg serial/deserial fn resolution |
| [`src/backend/optimizer/plan/createplan.c`](../files/src/backend/optimizer/plan/createplan.c.md) | — | create_agg_plan + Path-to-Plan conversion sets aggsplit |
| [`src/backend/optimizer/plan/planner.c`](../files/src/backend/optimizer/plan/planner.c.md) | — | make_partial_grouping_target + parallel-agg path generation |
| [`src/include/catalog/pg_aggregate.h`](../files/src/include/catalog/pg_aggregate.h.md) | — | Form_pg_aggregate with aggcombinefn, aggserialfn, aggdeserialfn |
| [`src/include/nodes/nodes.h`](../files/src/include/nodes/nodes.h.md) | 370 | AggSplit enum + AGGSPLITOP_ bit definitions + DO_AGGSPLIT_ predicates |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md)
- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)
- [`add-new-hook`](../scenarios/add-new-hook.md)
- [`add-new-node-type`](../scenarios/add-new-node-type.md)
- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)

<!-- /scenarios:auto -->
## Cross-references

- [[aggregate-trans-state]] — transfunc/finalfunc machinery.
- [[aggregate-hash-vs-sort]] — execution strategies (orthogonal to AGGSPLIT).
- [[aggregate-grouping-sets]] — GROUPING SETS, also orthogonal.
- [[parallel-gather-merge]] — Gather/GatherMerge consumes partial outputs.
- [[parallel-hash-join]] — sibling parallel-executor mechanism.
- [[fdw-routine-callbacks]] — FDW aggregate pushdown hooks.
- `source/src/include/catalog/pg_aggregate.h` — the catalog row schema.
- `source/src/backend/catalog/system_functions.sql` — aggregate creation syntax.
