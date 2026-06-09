---
source_url: https://www.postgresql.org/docs/current/xaggr.html
fetched_at: 2026-06-08T21:06:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — User-Defined Aggregates

The state-machine model behind every aggregate, plus the four "modes" that
matter for performance and correctness: moving-aggregate (windows), partial
(parallel), ordered-set (WITHIN GROUP), and in-place state mutation. The
non-obvious parts are the inverse-transition punt, the `AggCheckCallContext`
in-place trick, and the `internal`-state serialization needed for parallelism.

## Core model

- An aggregate = **`stype` (state type) + `sfunc` (transition) + optional
  `ffunc` (final)**. The state type is independent of input/result —
  `avg(float8)` accumulates in `float8[]` (sum, count, …). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/executor/nodeAgg.c.md]]]
- **Strict `sfunc` + omitted `initcond`:** PG auto-seeds the state with the
  first non-null input and starts transitions at the second row (null inputs
  skipped). A non-strict `sfunc` must handle null state/inputs itself. [from-docs]

## Moving-aggregate mode (window frames)

- **`msfunc` / `minvfunc` / `mstype` / `minitcond`** enable a moving aggregate;
  the **inverse transition `minvfunc`** removes rows leaving the frame, turning
  O(n × frame) into O(n) for `ROWS`/`RANGE` windows. [from-docs]
- **`minvfunc` may return NULL to mean "can't reverse this case"** → the system
  recomputes the frame from scratch. This is how `sum(float8)` punts on the
  precision trap (adding 1 to 1e20 then subtracting 1e20 yields 0, not 1). [from-docs]

## In-place state mutation (the performance-critical trick)

- A transition function may **modify its state argument in place** *only* when
  running as an aggregate — detect with **`AggCheckCallContext(fcinfo, NULL)`**.
  Outside aggregate context, mutating an input is illegal. [from-docs]
- **`AggCheckCallContext(fcinfo, &aggcontext)`** returns the long-lived
  aggregate-state memory context; expanded-object states should live in a child
  of it and be returned unchanged on each call (the `array_append` pattern). [from-docs]
  [verified-by-code, via [[knowledge/idioms/memory-contexts.md]]]

## Partial / parallel aggregation

- **`combinefunc(state, state) → state`** merges two independent partial states,
  enabling parallel and partitionwise aggregation; it must be effectively
  associative/commutative (order-sensitive aggregates can't provide one). [from-docs]
- For **`internal` state types**, parallel transfer needs **`serialfunc`
  (`internal → bytea`)** and **`deserialfunc` (`bytea, internal → internal`)**.
  The aggregate must be marked **`PARALLEL SAFE`** (support-function markings are
  ignored). [from-docs]

## Ordered-set & hypothetical-set aggregates

- Declared with direct args before `ORDER BY`: e.g.
  `CREATE AGGREGATE percentile_disc(float8 ORDER BY anyelement)`, called as
  `percentile_disc(0.5) WITHIN GROUP (ORDER BY income)`. Direct args evaluated
  once; aggregated args vary per row. [from-docs]
- **They do NOT auto-sort** — the transition function manages its own
  `tuplesort` in (usually `internal`) state; the final function finishes the
  sort and reads results, injecting hypothetical rows as needed. Inspect the
  parse node via **`AggGetAggref()`** (see `orderedsetaggs.c`). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/utils/adt/orderedsetaggs.c.md]]]
- Ordered-set aggregates **can't be window functions** and have no
  moving-aggregate mode. [from-docs]

## Flags

- **`FINALFUNC_EXTRA`** passes dummy NULL args matching the aggregate's input
  types to the final function, so a polymorphic result type can be deduced when
  the state type is `internal`/non-polymorphic. [from-docs]
- **`FINALFUNC_MODIFY`** = `READ_ONLY` (default) / `SHAREABLE` / `READ_WRITE` —
  declares whether the final function mutates the transition state (needed so
  the executor knows if it can reuse state across grouping sets / DISTINCT). [from-docs]
- **Polymorphic aggregates:** `anycompatible` input + `anycompatiblearray`
  state, e.g. `array_accum`. [from-docs]
- **Variadic parsing gotcha:** `myagg(a ORDER BY a, b, c)` parses as one
  aggregate arg + three sort keys, not three aggregate args. [from-docs]

## Links into corpus
- [[knowledge/files/src/backend/executor/nodeAgg.c.md]] — the executor side that drives sfunc/combinefunc/ffunc.
- [[knowledge/files/src/backend/utils/adt/orderedsetaggs.c.md]] — ordered-set/hypothetical-set implementations + AggGetAggref.
- [[knowledge/files/src/backend/utils/adt/array_expanded.c.md]] — the expanded-object in-place state pattern.
- [[knowledge/idioms/memory-contexts.md]] — aggregate-context lifetime for state allocation.
- Skill: `fmgr-and-spi` — writing the C transition/final functions; `catalog-conventions` — pg_aggregate.dat.

## Gaps / follow-ups
- The exact `pg_aggregate` columns (`aggtransfn`, `aggfinalfn`, `aggcombinefn`,
  `aggmtransfn`, `aggminvtransfn`, `aggkind` n/o/h, `aggfinalmodify`) are named
  here only functionally; cross-check the catalog header when editing builtins.
