# Aggregate transition state — transvalue / transfunc / finalfunc

PostgreSQL aggregates are **fold operations**: a per-group
`transvalue` is initialized from `initcond`, then updated
by `transfunc(transvalue, input...)` for every input
tuple, and finally `finalfunc(transvalue, direct_args...)`
produces the output. Understanding the trans-state machinery
— who allocates it, when it's reset, and how partial /
ordered / hashed flavors deviate — is the cost of admission
for aggregate work (custom aggregates, parallel aggregation,
ordered-set quirks).

Anchors:
- `source/src/backend/executor/nodeAgg.c:5-15` — the
  transvalue model [verified-by-code]
- `source/src/backend/executor/nodeAgg.c:16-27` — aggsplit
  / combinefunc / serialize [verified-by-code]
- `source/src/backend/executor/nodeAgg.c:37-46` — strict
  transfunc handling [verified-by-code]
- `source/src/backend/executor/nodeAgg.c:61-78` —
  aggcontext + tmpcontext discipline [verified-by-code]
- `source/src/backend/executor/nodeAgg.c:709` —
  advance_transition_function [verified-by-code]
- `knowledge/data-structures/datum-nullabledatum.md` —
  transvalue is a Datum
- `knowledge/data-structures/tupletableslot.md` — input
  tuples come via slot
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The basic flow

[verified-by-code `nodeAgg.c:6-14`]

> transvalue = initcond
> foreach input_tuple do
>    transvalue = transfunc(transvalue, input_value(s))
> result = finalfunc(transvalue, direct_argument(s))
>
> If a finalfunc is not supplied then the result is just
> the ending value of transvalue.

Three pg_aggregate columns drive this:
- `aggtransfn` (required) — folds a tuple into the state.
- `agginitval` (text; parsed into trans-type) — initial.
- `aggfinalfn` (optional) — turns final state into result.

The transvalue's type is `agg_state_type` (or
`anyelement` for polymorphic) — distinct from the input
type AND from the result type.

## aggsplit — partial vs final aggregation

[verified-by-code `nodeAgg.c:16-27`]

> Other behaviors can be selected by the "aggsplit" mode,
> which exists to support partial aggregation. It is
> possible to:
> * Skip running the finalfunc, so that the output is
>   always the final transvalue state.
> * Substitute the combinefunc for the transfunc, so that
>   transvalue states (propagated up from a child partial-
>   aggregation step) are merged rather than processing raw
>   input rows.
> * Apply the serializefunc to the output values...
> * Apply the deserializefunc to the input values...

The four split modes:
- **simple** — full local aggregation.
- **partial** — local trans, no finalfunc; emit raw
  transvalue.
- **combine** — receive partial trans-states, merge with
  combinefunc.
- **final** — combine + apply finalfunc.

For parallel aggregation: each worker does partial; the
Gather's parent does combine + final. Trans-states cross
the worker boundary via `serialfn` (`bytea`).

## Strict transfunc — the NULL-initcond shortcut

[verified-by-code `nodeAgg.c:37-41`]

> If transfunc is marked "strict" in pg_proc and initcond
> is NULL, then the first non-NULL input_value is assigned
> directly to transvalue, and transfunc isn't applied until
> the second non-NULL input_value. The agg's first input
> type and transtype must be the same in this case!

A common pattern: declaring transfunc as STRICT + leaving
initcond NULL lets the aggregate "start with the first
real value". E.g., `max(int)` works this way — initcond
NULL, transfunc strict, "first row's value becomes the
running max".

## NULL input handling

[verified-by-code `nodeAgg.c:43-46`]

> If transfunc is marked "strict" then NULL input_values
> are skipped, keeping the previous transvalue. If
> transfunc is not strict then it is called for every input
> tuple and must deal with NULL initcond or NULL
> input_values for itself.

Strict transfuncs: `count(x)` skips NULLs (giving non-NULL
row count); `count(*)` is non-strict (counts all rows).

## Memory contexts — the two-tier model

[verified-by-code `nodeAgg.c:61-78`]

> We compute aggregate input expressions and run the
> transition functions in a temporary econtext
> (aggstate->tmpcontext). This is reset at least once per
> input tuple, so when the transvalue datatype is
> pass-by-reference, we have to be careful to copy it into
> a longer-lived memory context, and free the prior value
> to avoid memory leakage. We store transvalues in another
> set of econtexts, aggstate->aggcontexts (one per
> grouping set, see below), which are also used for the
> hashtable structures in AGG_HASHED mode.

Two distinct contexts:
- **`tmpcontext`** — short-lived; reset per-tuple. The
  transfunc's *return value* is allocated here.
- **`aggcontext`** — long-lived; reset at group boundaries.
  The *persistent transvalue* is copied here after each
  transfn call.

The copy + free dance is the source of most "memory leak
in aggregate" bugs. Pass-by-value transtypes (`int8`,
`float8`, etc.) sidestep it; pass-by-ref types
(`numeric`, `internal`) must manage.

## Hashed vs sorted aggregation

Two execution strategies:
- **AGG_PLAIN** — single group, no GROUP BY.
- **AGG_SORTED** — input pre-sorted by group key; emit on
  group-boundary detection.
- **AGG_HASHED** — hash-table keyed by group; one
  transvalue per bucket.
- **AGG_MIXED** — sorted + hashed for grouping sets.

`AGG_HASHED` spills to disk via `hashagg_spill_*`
machinery when the hash table exceeds `work_mem`.

## Ordered-set aggregates — the DIRECT arg twist

[verified-by-code `nodeAgg.c:55-58`]

> Ordered-set aggregates are treated specially in one
> other way: we evaluate any "direct" arguments and pass
> them to the finalfunc along with the transition value.

`percentile_cont(0.95) WITHIN GROUP (ORDER BY x)`:
- `0.95` is the "direct argument" — evaluated once.
- `x` is the per-row input — folded into transvalue.
- The finalfunc receives both.

WITHIN GROUP aggregates don't support partial.

## DISTINCT + ORDER BY inside aggregate calls

```sql
SELECT count(DISTINCT x), array_agg(y ORDER BY z) ...
```

PG sorts the input tuples and dedupes (if DISTINCT)
*before* the trans loop. Pre-sort is a separate executor
step; the aggregate transfunc then sees ordered input. NOT
parallel-safe (sort-before-trans wouldn't agree across
workers).

## advance_aggregates — the per-input dispatcher

```c
static void advance_aggregates(AggState *aggstate);
```

Called for every input tuple. Computes each aggregate's
input arguments via ExprState, then dispatches to
`advance_transition_function` for each. Handles strict
shortcut, manages tmpcontext / aggcontext.

## Common review-time concerns

- **Pass-by-ref transvalue MUST be copied** to aggcontext;
  forgetting = memory leak per group.
- **Strict transfunc + NULL initcond** = first-value
  shortcut; transtype must match input type.
- **aggsplit must be consistent** across parent-child Agg
  nodes; planner sets this.
- **Hashed aggregation spills** at work_mem; serialize
  carefully.
- **Custom aggregates with internal transtype** must
  declare serial/deserial funcs for parallel.
- **DISTINCT/ORDER BY inside agg** disables parallel.

## Invariants

- **[INV-1]** transvalue type = aggtranstype; distinct
  from input + result.
- **[INV-2]** Strict transfunc → NULL inputs skipped;
  + NULL initcond → first-value shortcut.
- **[INV-3]** Pass-by-ref transvalue lives in aggcontext;
  per-tuple results in tmpcontext.
- **[INV-4]** Partial / combine / final modes are planner-
  chosen; aggstate has matching dispatcher.
- **[INV-5]** Ordered-set aggregates can't be partial.

## Useful greps

- The dispatch:
  `grep -n 'advance_transition_function\|advance_aggregates' source/src/backend/executor/nodeAgg.c | head -10`
- Partial mode:
  `grep -RIn 'AGGSPLIT_INITIAL\|AGGSPLIT_FINAL\|AGGSPLIT_SIMPLE' source/src/backend/executor | head -10`
- Hashagg spill:
  `grep -n 'hashagg_spill\|hash_disk_used' source/src/backend/executor/nodeAgg.c | head -10`

## Cross-references

- `knowledge/data-structures/datum-nullabledatum.md` —
  transvalue is a Datum (+ isnull).
- `knowledge/data-structures/tupletableslot.md` — input
  arrives via slot.
- `knowledge/idioms/expression-evaluator-flow.md` — agg
  input args evaluated via ExprState.
- `knowledge/idioms/parallel-worker-coordination.md` —
  partial-aggregation handshake.
- `knowledge/subsystems/executor.md` — executor overview.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `.claude/skills/fmgr-and-spi/SKILL.md` — transfunc /
  finalfunc are fmgr-called.
- `source/src/backend/executor/nodeAgg.c` — full source.
- `source/src/include/catalog/pg_aggregate.h` — catalog
  schema.
