---
source_url: https://www.postgresql.org/docs/current/extend-how.html
fetched_at: 2026-06-21T00:00:00Z
anchor_sha: f25a07b2d94c
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §38.1: How Extensibility Works

The thesis statement for all of Part V (Extending SQL). One page, one big idea —
worth pinning because every extension skill in this repo (`extension-development`,
`catalog-conventions`, `access-method-apis`, `fmgr-and-spi`) is a downstream
consequence of it.

## The one idea: PostgreSQL is catalog-driven

- PG's operation is **catalog-driven**: the server's behavior is largely *read
  out of system catalogs at runtime* rather than hardcoded in C. `[from-docs]`
- Unlike a conventional RDBMS — whose catalogs store only tables/columns — PG's
  catalogs additionally store **data types, functions, operators, access
  methods, and so on**. Because those catalog rows can be *added* by users, and
  because the server dispatches off them, **users can extend the server without
  touching its source**. `[from-docs]`
- The contrast the page draws explicitly: a conventional DBMS "can only be
  extended by changing hardcoded procedures in the source code or by loading
  modules specially written by the DBMS vendor." PG inverts that — extension is
  the *normal* path, not a vendor privilege. `[from-docs]`

## What "stored in a catalog" buys you concretely

- Adding a **data type** = inserting a `pg_type` row (+ its I/O functions in
  `pg_proc`). Adding a **function** = a `pg_proc` row. An **operator** =
  `pg_operator`. An **index access method** = `pg_am` + opclass catalogs. None
  require recompiling the backend. `[inferred from §38.1 thesis + catalog-conventions]`
- This is why the `catalog-conventions` skill matters so much: editing a catalog
  *is* the extension mechanism, so OID policy / catversion / `.dat` discipline
  are the price of admission.

## Dynamic loading — the C escape hatch

- For behavior that can't be expressed in SQL, PG can **dynamically load
  user-written object code**: point it at a shared library implementing a new
  type or function and the server loads it on demand. `[from-docs]`
- The page notes **SQL-language extensions are even easier to add** than
  compiled ones — pure-SQL functions/types need no `.so` at all. `[from-docs]`

## Why the design exists

- The catalog-driven + dynamic-loading combination makes PG "uniquely suited for
  **rapid prototyping** of new applications and storage structures" — you can
  iterate on a new type/operator/AM without a server rebuild cycle. `[from-docs]`
- This is the conceptual root of the whole extension ecosystem (PostGIS, vector
  types, custom index AMs): they're not plugins bolted on, they're *catalog rows
  + loadable code* that the server was always designed to dispatch off. `[inferred]`

## Links into corpus

- Type-system extensibility (the next leaf, §38.2):
  [docs-distilled/extend-type-system.md](./extend-type-system.md)
- The catalog reference these rows live in:
  [docs-distilled/catalogs-overview.md](./catalogs-overview.md)
- Packaging the result as a distributable unit:
  [docs-distilled/extend-extensions.md](./extend-extensions.md),
  [docs-distilled/extend-pgxs.md](./extend-pgxs.md)
- Relevant skills: `extension-development`, `catalog-conventions`,
  `access-method-apis`, `fmgr-and-spi`.
