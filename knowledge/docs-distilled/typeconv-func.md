---
source_url: https://www.postgresql.org/docs/current/typeconv-func.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §10.3: Function Type Resolution

The exact overload-resolution algorithm the parser runs against `pg_proc`
(implemented in `parse_func.c` `func_select_candidate`). Pin this when a
patch adds an overloaded builtin or debugs an "function is not unique"
error.

## Step 1 — gather candidates from `pg_proc`

- Unqualified name → functions with matching name + argument count visible
  in the **search path**; qualified name → only that schema. `[from-docs]`
- **1a (path dedup):** if the path finds multiple functions with *identical*
  argument types, only the **earliest in the path** is considered.
  Different-arg-type functions compete equally regardless of path position.
  `[from-docs]`
- **1b (VARIADIC expansion):** a `VARIADIC array` parameter called without
  the `VARIADIC` keyword is treated as if the array were replaced by N
  occurrences of its element type. If expansion ties a non-variadic
  function, the **earlier-in-path** one wins, or the **non-variadic** one if
  same schema. `[from-docs]`
- **1c (defaults):** functions with parameter defaults match calls omitting
  the defaultable trailing positions; ties → earliest in path. `[from-docs]`

## Step 2 — exact match

- A function accepting **exactly** the input types is used. There can be at
  most one exact match in the candidate set. `[from-docs]`

## Step 3 — the type-conversion-request special case

- If no exact match AND the call has **one argument** AND the function name
  equals the **internal name of a data type**, AND the argument is an
  unknown literal / binary-coercible to that type / convertible via that
  type's I/O functions (to-or-from a string type), the call is treated as a
  `CAST`. `[from-docs]` (This is why `int4(x)` works like `x::int4`.)

## Step 4 — best match (the tie-break ladder)

Run in order; stop as soon as one candidate remains:

- **4a:** discard candidates whose inputs can't be reached by **implicit
  conversion**. `unknown` literals are assumed convertible to anything.
  `[from-docs]`
- **4b:** a **domain** input is treated as its **base type** for all
  remaining steps. `[from-docs]`
- **4c:** keep candidates with the **most exact-type matches**. `[from-docs]`
- **4d:** keep candidates accepting **preferred types** (of the input's
  category) at the most to-be-converted positions. `[from-docs]`
- **4e (unknown literals):** at each `unknown` position, prefer the
  **`string`** category if any candidate accepts it (a literal looks like a
  string); else if **all** remaining candidates accept the **same category**,
  pick it; **else fail (ambiguous)**. Then drop candidates not accepting the
  chosen category, and if any candidate takes a preferred type there, drop
  the non-preferred ones. `[from-docs]`
- **4f (mixed unknown/known):** if there are both `unknown` and known args
  AND all known args share one type, assume the `unknown` args are that type
  too; if **exactly one** candidate accepts it, use it, **else fail**.
  `[from-docs]`

## Worked-example takeaways

- `round(4, 4)` → the lone `round(numeric, integer)` coerces the integer 4
  to numeric (4a). `[from-docs]`
- `variadic_example(0)` with both `(int)` and `(VARIADIC numeric[])` present
  → the **exact `(int)` wins** over variadic expansion; the explicit
  `VARIADIC` keyword also defends against malicious function shadowing.
  `[from-docs]`
- `substr('1234', 3)` resolves to `text` (string-category preference, 4e);
  `substr(1234, 3)` **errors** — integer has no implicit cast to text.
  `[from-docs]`

## Links into corpus

- Operator analogue (nearly identical ladder):
  [docs-distilled/typeconv-oper.md](./typeconv-oper.md)
- Categories / preferred types context:
  [docs-distilled/typeconv-overview.md](./typeconv-overview.md)
- Relevant skills: `fmgr-and-spi` (declaring the overloaded SRF/scalar),
  `catalog-conventions` (the `pg_proc.dat` rows), `parser-and-nodes`.
