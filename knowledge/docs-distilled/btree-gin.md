---
source_url: https://www.postgresql.org/docs/current/btree-gin.html
fetched_at: 2026-07-13T20:49:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.5 btree_gin — GIN operator classes with B-tree behavior"
maps_to_skill: access-method-apis
---

# Docs distilled — btree_gin (B-tree semantics inside a GIN index)

The GIN analogue of `btree_gist`: scalar-type GIN opclasses whose real value is
letting a *single multicolumn GIN index* mix a B-tree-ish column (an int, a
date, a text) with a genuinely GIN-native column (`tsvector`, array, `jsonb`),
so the planner avoids bitmap-ANDing two separate indexes. First corpus coverage
of this module; complements `access-method-apis`.

## Non-obvious claims

- **Type coverage is even broader than btree_gist.** Opclasses for
  `int2/int4/int8`, `float4/float8`, `timestamp[tz]`, `time[tz]`, `date`,
  `interval`, `oid`, `money`, `"char"`, `varchar`, `text`, `bytea`, `bit`,
  `varbit`, `macaddr/macaddr8`, `inet`, `cidr`, `uuid`, `name`, `bool`,
  `bpchar`, and **all enum types**. [from-docs]
- **The load-bearing use case is multicolumn-GIN avoidance of bitmap AND.** The
  docs state it plainly: for a query filtering *both* a GIN-indexable column and
  a B-tree-indexable column, one multicolumn GIN index using a btree_gin opclass
  "might be more efficient … than to create two separate indexes that would have
  to be combined via bitmap ANDing." [from-docs] This is the discriminator vs
  just using a normal B-tree on the scalar column.
- **Inequality/range queries do work through it.** Unlike a naive GIN opclass
  (equality-only), btree_gin implements the comparison operators, so
  `WHERE a < 10` can use the GIN index. [from-docs] (Under the hood this is the
  GIN "partial match" mechanism scanning a contiguous key range — the same
  machinery `access-nbtree`-style ordered keys enable.)
- **Two things it still cannot do: order output, or enforce uniqueness.** GIN
  produces a bitmap, not an ordered stream, and has no unique-constraint path.
  If you need `ORDER BY col` from the index or a unique constraint, this is the
  wrong tool — use a real B-tree. [from-docs]
- **Trusted extension.** Non-superuser installable with `CREATE`. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/btree-gist.md]] — the GiST sibling (this run); use
  btree_gist when you also need exclusion constraints or KNN, btree_gin when the
  companion column is GIN-native (tsvector/array/jsonb).
- [[knowledge/docs-distilled/gin.md]] — the GIN extractValue/extractQuery/
  consistent contract these opclasses satisfy, plus partial-match.
- [[knowledge/docs-distilled/indexes-types.md]] — GIN's place among index types
  and the multicolumn-index discussion.
- [[knowledge/docs-distilled/xindex.md]] — opclass/strategy registration.

## Confidence

Entirely [from-docs] (btree-gin.html) — the module is a thin per-type opclass
generator with no distinct algorithmic prose beyond the type list and the
multicolumn-GIN rationale. The "range queries via GIN partial match" mechanism
note is [inferred] from the documented inequality support combined with GIN's
known partial-match path; not independently code-cited this run.
