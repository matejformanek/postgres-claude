---
source_url: https://www.postgresql.org/docs/current/typeconv-query.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §10.4: Value Storage

How an `INSERT`/`UPDATE` expression is coerced to the **target column's
type** — the only context that uses **assignment** casts (not just
implicit), and the one that introduces the *sizing cast* / `atttypmod`
machinery behind `varchar(n)`, `numeric(p,s)`, `char(n)`.

## The three steps

1. **Exact match** with the target type → done. `[from-docs]`
2. **Convert via an assignment cast**: if `pg_cast` has an assignment (or
   implicit) cast from the expression type to the target, apply it.
   **Special case:** an unknown-type literal is fed straight to the target
   type's **input function**. `[from-docs]`
3. **Apply a sizing cast** if one exists: a sizing cast is a **cast from a
   type to itself**. Its implementation function takes an extra `integer`
   argument receiving the column's **`atttypmod`** (usually the declared
   length, but interpretation is type-specific) and optionally a third
   `boolean` for explicit-vs-implicit. The function performs length
   semantics — size checking, truncation, padding. `[from-docs]`

## Why this matters for hackers

- `atttypmod` is the per-column type modifier stored on `pg_attribute`; the
  sizing-cast convention is how a type implements "length-parameterized"
  behavior without a distinct type per length. A new type that wants
  `mytype(n)` semantics must register a self-cast with the integer-modifier
  signature. `[inferred from §10.4 + extend-type-system]`
- This step is **value-storage-only** — sizing casts are not applied in
  function/operator/UNION resolution. `[from-docs]`

## Worked example

```sql
CREATE TABLE vv (v character(20));
INSERT INTO vv SELECT 'abc' || 'def';
SELECT v, octet_length(v) FROM vv;   -- 'abcdef' padded to 20 bytes
```

The sizing function `bpchar(bpchar, integer, boolean)` runs with
`atttypmod = 20`, padding to the declared length. `[from-docs]`

## Links into corpus

- Where casts come from: [docs-distilled/typeconv-overview.md](./typeconv-overview.md)
  (implicit vs assignment vs explicit contexts)
- Defining a type + its sizing cast:
  [docs-distilled/extend-type-system.md](./extend-type-system.md),
  [docs-distilled/xtypes.md](./xtypes.md)
- Relevant skills: `catalog-conventions` (`pg_cast.dat`, `pg_attribute`),
  `parser-and-nodes`.
