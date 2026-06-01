# parse_collate.c

- **Source:** `source/src/backend/parser/parse_collate.c` (1060 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top + design comment)

## Purpose

Post-pass over a fully-built expression tree that **assigns collation**
information to each node. Done as a separate pass (rather than during
expression build-up) because tracking the collation state on-the-fly would
require keeping extra fields on every parse-node permanently. Doing it in
a recursive walk lets the state live in local variables. [from-comment]
`:5-12`

## What it actually stores

Two distinct concepts per node — both are needed (one collation is
insufficient): [from-comment] `:13-26`

1. **Output collation** — what collation the node's result value carries
   (or `InvalidOid` if uncollatable / indeterminate). Stored on most
   expression nodes that *can* be collated (e.g. `OpExpr.opcollid`,
   `FuncExpr.funccollid`).

2. **Input/function collation** — which collation the executing
   function should *use* (passed to it via `fcinfo->fncollation`). Stored
   on the same nodes via `inputcollid`. Differs from output collation when
   a function takes collatable inputs but returns a non-collatable type
   (e.g. `<`, which returns bool).

## Entry

- `assign_query_collations(pstate, query)` — the top-level call. Invoked
  from each `transformFooStmt` in `analyze.c` once everything else is in
  place.
- `assign_expr_collations(pstate, expr)` — the recursive helper.

## Conflict handling

When sub-expressions have differently-marked explicit collations the result
is an error (`collation conflict`). When the conflict is only implicit
(both come from column refs of different collations), the result is
`InvalidOid` (= "indeterminate"); the function will then error at runtime
if it actually needs the collation. The walker carries a `CollateStrength`
enum to record which side of that distinction we're on.

## Related

- `pg_collation` catalog.
- `parse_type.c` — produces the column collations the walker consumes.
- `Query.collations` and the per-node `*collid` fields in
  `primnodes.h` — the storage targets.
