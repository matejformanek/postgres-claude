---
source_url: https://www.postgresql.org/docs/current/typeconv-overview.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §10.1: Type Conversion Overview

The conceptual root for the four overload/coercion resolution algorithms PG
runs *in the parser* (not the executor). Anyone touching `parse_func.c`,
`parse_oper.c`, `parse_coerce.c`, or `pg_cast` lives in this chapter. The
key framing: PG resolves types by **general rules over catalog data**, not
ad-hoc heuristics — which is *why* a new `pg_cast`/`pg_proc` row changes
resolution behavior without a code change.

## The four conversion contexts (each has its own algorithm)

1. **Function calls** — overloading means the name alone doesn't identify
   the function; the parser picks based on argument types. (§10.3) `[from-docs]`
2. **Operators** — prefix (1-arg) and infix (2-arg), also overloaded; same
   selection problem as functions. (§10.2) `[from-docs]`
3. **Value storage** — `INSERT`/`UPDATE` expressions must be matched/converted
   to the target column type. (§10.4) `[from-docs]`
4. **UNION / CASE / and relatives** — branch results must collapse to one
   common type. (§10.5) `[from-docs]`

## Type categories and preferred types — the tie-breakers

- Types fall into **categories**: `boolean`, `numeric`, `string`,
  `bitstring`, `datetime`, `timespan`, `geometric`, `network`, plus
  user-defined. `[from-docs]`
- Within a category, one or more **preferred types** win when there's a
  choice (e.g. `text` is the preferred type of the `string` category — this
  is why unknown literals bias toward `text`). `[from-docs]`
- These two concepts (`typcategory`, `typispreferred` on `pg_type`) are the
  knobs every resolution algorithm consults at its tie-break steps. `[from-comment]`

## Casts live in the catalog

- `pg_cast` records which conversions exist and how to perform them; users
  add casts via `CREATE CAST`. `[from-docs]`
- Casts have a **context**: implicit (applied silently anywhere), assignment
  (applied only when storing into a column — §10.4), explicit (only on an
  explicit `CAST`/`::`). The resolution algorithms only ever auto-apply
  *implicit* casts; §10.4 value storage additionally uses *assignment*
  casts. `[inferred from §10.3/§10.4 + catalog-conventions]`

## The three design principles (why implicit conversion is conservative)

1. Implicit conversions must **never have surprising/unpredictable
   outcomes**. `[from-docs]`
2. **No parser/executor overhead** when no conversion is needed — a
   well-typed query introduces zero implicit-conversion calls. `[from-docs]`
3. If a user **defines a function with the exact argument types**, the
   parser must prefer it and stop doing implicit conversion to the old one.
   `[from-docs]` (This is the extensibility guarantee: your new overload
   wins.)

## Links into corpus

- Function resolution algorithm: [docs-distilled/typeconv-func.md](./typeconv-func.md)
- Operator resolution algorithm: [docs-distilled/typeconv-oper.md](./typeconv-oper.md)
- Value storage (assignment casts + sizing): [docs-distilled/typeconv-query.md](./typeconv-query.md)
- Common-type selection (UNION/CASE): [docs-distilled/typeconv-union-case.md](./typeconv-union-case.md)
- Relevant skills: `parser-and-nodes`, `fmgr-and-spi`, `catalog-conventions`
  (the `pg_cast`/`pg_proc`/`pg_operator` rows these algorithms read).
