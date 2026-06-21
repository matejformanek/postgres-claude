---
source_url: https://www.postgresql.org/docs/current/xfunc-optimization.html
fetched_at: 2026-06-20T19:55:00Z
anchor_sha: dc5116780846
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Function Optimization Information — planner support functions (Extending SQL §38.11)

The "teach the planner about your function" leaf of §38. The declarative
`CREATE FUNCTION` annotations (volatility, parallel-safety, `COST`, `ROWS`)
only carry **constant** knowledge; a *planner support function* is the escape
hatch for **input-dependent** optimization knowledge that can't be expressed
declaratively. Distinct from `xoper-optimization.md` (which is about
`COMMUTATOR`/`NEGATOR`/`RESTRICT`/`JOIN` operator hints) — support functions
are attached to the **function**, are written in **C**, and field an
**extensible set of request structs**.

## What a support function is and how it attaches

- A planner support function is a **C function** attached to a *target
  function* via `CREATE FUNCTION target(...) ... SUPPORT supportfn`. The target
  function itself may be written in any language; only the support function must
  be C. [from-docs]
- Required SQL signature of the support function: `supportfn(internal) returns
  internal`. [from-docs] The lone `internal` argument is a pointer to one of the
  request node structs; the planner dispatches by `IsA(node, SupportRequest...)`.
- Default state without a support function: a function is a **black box** to the
  planner — it knows only the declarative `COST`/`ROWS`/volatility/parallel
  annotations. [from-docs]
- The API node structs are defined in `source/src/include/nodes/supportnodes.h`
  — the doc explicitly names this header as the authoritative API reference.
  [from-docs] [cite: src/include/nodes/supportnodes.h]
- **Return convention:** return `NULL` (a null `Datum`/pointer) for any request
  type the support function does not want to handle; the planner then falls back
  to its default behavior. The request set is extensible, so a support function
  must tolerate request structs it doesn't recognize. [inferred-from-docs]

## The five request types

- **`SupportRequestSimplify`** — fires during planning to let the function
  rewrite/fold its own call into a simpler parse tree. Classic example: the
  support function for `int4mul` turns `int4mul(n, 1)` (and the operator form
  `n * 1`) into bare `n`. The returned node must be **rigorously equivalent** to
  actually executing the target function — same result, same errors. Even when a
  simplification is possible, PostgreSQL gives **no guarantee** it won't still
  call the original target function, so the two paths must agree. [from-docs]
- **`SupportRequestSelectivity`** — for **boolean-returning** target functions
  used in `WHERE`: estimate the selectivity (fraction of rows passing) of the
  function-call qual. Replaces the planner's default fixed-selectivity guess for
  an opaque function predicate. [from-docs]
- **`SupportRequestCost`** — provide a **non-constant** per-call cost estimate
  when runtime depends heavily on the arguments; overrides the constant `COST`
  given in `CREATE FUNCTION`. [from-docs]
- **`SupportRequestRows`** — for **set-returning** target functions: provide a
  non-constant output-row-count estimate; overrides the constant `ROWS` given in
  `CREATE FUNCTION`. [from-docs]
- **`SupportRequestIndexCondition`** — convert a boolean function call in
  `WHERE` into an **indexable operator clause**, so an index scan can be used.
  Two modes: **exact** (the derived clause is logically identical to the
  function condition) and **lossy** (the derived clause is weaker / may admit
  false hits, so the planner inserts a **recheck** that re-runs the original
  function on each index-returned row). The optimization only happens if the
  support function implements this request. [from-docs]

## Gotchas

- The request set is explicitly **extensible**: "more things might be possible
  in future versions", so code defensively and don't assume the five above are
  all that can ever arrive. [from-docs]
- `SupportRequestSimplify` correctness is load-bearing for soundness, not just
  speed: a simplification that isn't strictly equivalent silently corrupts
  query results, because the planner may use *either* the simplified expression
  *or* a direct call. [from-docs]
- This is a deliberately advanced surface — "relatively few users" will write
  support functions; in-core ones (arithmetic identity-folding, `generate_series`
  row estimates, `LIKE`/regex index-condition derivation) are the reference
  implementations to read. [from-docs]

## Links into corpus

- `knowledge/subsystems/optimizer.md` — where these requests are consumed
  (path generation / selectivity / cost model).
- `knowledge/docs-distilled/planner-optimizer.md` — the planner-pipeline
  overview these hooks plug into.
- `knowledge/docs-distilled/xoper-optimization.md` — the **operator** side of
  optimizer hints (`RESTRICT`/`JOIN`/`COMMUTATOR`), the declarative cousin.
- `knowledge/docs-distilled/xfunc-c.md` — V1 C-function calling convention every
  support function obeys.
- `knowledge/docs-distilled/xfunc-volatility.md` — the declarative annotation
  layer support functions extend past.
- `knowledge/idioms/cost-units-gucs.md`, `knowledge/idioms/cost-scan-paths.md` —
  the cost machinery `SupportRequestCost` overrides.
- `knowledge/data-structures/restrictinfo.md`, `knowledge/data-structures/plannerinfo.md`
  — the planner state a support function manipulates.

## Citations

- All behavioral claims: source-URL anchor
  https://www.postgresql.org/docs/current/xfunc-optimization.html (PG18).
- API node structs: `source/src/include/nodes/supportnodes.h` (named by the doc
  as the authoritative reference; verify exact struct fields against anchor
  `dc5116780846` before quoting field names in a plan).
