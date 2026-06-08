---
source_url: https://www.postgresql.org/docs/current/xindex.html
fetched_at: 2026-06-08T20:52:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter: Interfacing Extensions to Indexes

How a type author wires an index AM to a data type via **operator classes**
and **operator families**. The non-obvious axis is class-vs-family: a class is
single-type; a family is the container where *cross-type* operators legally
live so the planner can match mixed-type clauses to an index.

## Operator class vs. operator family

- **Operator class = one data type, one index method.** It bundles the
  strategy operators + support functions that make that type indexable. The
  most-useful class for a type/method pair is marked **`DEFAULT`** in
  `CREATE OPERATOR CLASS`. [from-docs]
- **Operator family = one or more classes + "loose" cross-type members.**
  Cross-data-type operators/support functions belong to the family, *not* any
  single class, and are attached with **`ALTER OPERATOR FAMILY ... ADD`**.
  [from-docs] [verified-by-code, via [[knowledge/idioms/catalog-conventions.md]]]
- Example: the built-in **`integer_ops`** family holds the `int2_ops`,
  `int4_ops`, `int8_ops` classes plus loose cross-type comparison procs like
  `btint82cmp(int8, int2)`. [from-docs]

## Strategy numbers (per AM — the AM defines their meaning)

- **B-tree:** fixed 5 — 1=`<` 2=`<=` 3=`=` 4=`>=` 5=`>`, all return boolean. [from-docs]
- **Hash:** fixed 1 — `=`. [from-docs]
- **GiST / SP-GiST / GIN / BRIN:** strategy numbers are **not fixed by the AM**;
  each opclass's support routines interpret them. [from-docs]

## Support-function numbers

- **B-tree:** 1=`order` (mandatory), 2=sortsupport, 3=in_range, 4=equalimage,
  5=options, 6=skipsupport. [from-docs] (cross-ref `btree` chapter)
- **Hash:** 1=32-bit hash (mandatory), 2=64-bit-hash-with-salt, 3=options. [from-docs]
- **GiST:** up to 12 — `consistent`(1), `union`(2), `compress`(3),
  `decompress`(4), `penalty`(5), `picksplit`(6), `distance`(8), `fetch`(9), … [from-docs]
- **GIN:** `compare`(1), `extractValue`(2), `extractQuery`(3),
  `consistent`(4) or `triConsistent`(6). [from-docs]

## Ordering operators — restrict vs. order

- A **search** operator restricts rows; an **ordering** operator returns rows
  in `ORDER BY indexed_col <op> constant` order and typically returns a
  non-boolean (e.g. `float8` distance). [from-docs]
- Declared against a btree family for the *result* ordering, e.g.
  `OPERATOR 15 <-> (point, point) FOR ORDER BY float_ops` — the canonical
  GiST nearest-neighbour (`<->`) wiring. [from-docs]
- In `pg_amop` the kind is recorded by **`amoppurpose`**: `'s'` = search,
  `'o'` = ordering. [from-docs]

## Family-level consistency rules

- In a btree family **all operators must sort compatibly**, and for each
  operator there must be a support function with the *same two input types*. [from-docs]
- In a hash family, cross-type hash support functions must return **the same
  hash code for values the family's `=` deems equal, even across types**. [from-docs]
- Implicit/binary-coercion casts among family types must **not change sort
  order** (this is why `float8` and `numeric` can't safely share one family:
  float precision loss breaks transitivity). [from-docs]

## System catalogs & wider planner use

- **`pg_opclass`** (classes), **`pg_opfamily`** (families), **`pg_amop`**
  (operator→strategy, with `amoppurpose`), **`pg_amproc`** (support
  function→slot). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/index/amvalidate.c.md]]]
- The system uses opclasses beyond indexing: the **default btree class's `=`**
  defines equality for `GROUP BY`/`DISTINCT`, and its order defines default
  `ORDER BY`. If no default btree class exists it falls back to a **default
  hash class** (equality only, no order) — hence `could not identify an
  ordering operator` errors on types lacking a btree class. [from-docs]
- **`STORAGE`** in `CREATE OPERATOR CLASS` lets the on-disk index entry use a
  different type than the column (e.g. `STORAGE box` for a polygon GiST class);
  GiST `compress`/`decompress` (and GIN `extractValue`/`extractQuery`) bridge
  the column type and the storage type. Lossy AMs (GiST/SP-GiST/GIN) set a
  **recheck** flag to force a post-index filter. [from-docs]

## Links into corpus
- [[knowledge/idioms/catalog-conventions.md]] — pg_opclass/pg_amop/pg_amproc .dat conventions.
- [[knowledge/files/src/backend/access/index/amvalidate.c.md]] — generic opclass-validation entry point.
- [[knowledge/files/src/backend/access/index/amapi.c.md]] — IndexAmRoutine registration.
- [[knowledge/docs-distilled/btree.md]] / [[knowledge/docs-distilled/indexam.md]] — AM-side companions.
- Skill: `access-method-apis` — strategy/support-number checklist for a new opclass.
- Skill: `catalog-conventions` — registering opclasses/operators in the .dat catalogs.

## Gaps / follow-ups
- The per-AM `amvalidate` checks (e.g. `btvalidate`, `hashvalidate`) enforce the
  family-consistency rules above at `CREATE`/`ALTER` time — cross-check the
  per-AM `*_validate.c` per-file docs when quoting which rule is enforced where.
