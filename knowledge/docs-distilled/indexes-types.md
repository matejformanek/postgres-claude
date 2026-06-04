---
source_url: https://www.postgresql.org/docs/current/indexes-types.html
fetched_at: 2026-06-03T19:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §11.2: Index Types

The six built-in index access methods, what operators each indexes, and the
data shapes each suits. The non-obvious axis is *which operators an opclass can
answer* — that, not the data type, is what decides whether an index gets used.

## The six AMs at a glance

| AM | `USING` clause | Answers | Shape it suits |
|---|---|---|---|
| B-tree | (default) | `< <= = >= >`, `BETWEEN`, `IN`, `IS [NOT] NULL`, anchored `LIKE`/`~` | sortable scalar columns |
| Hash | `USING hash` | `=` only | equality on large/wide keys |
| GiST | `USING gist` | opclass-defined (geometry, FTS, ranges, **KNN**) | overlapping/spatial/exclusion |
| SP-GiST | `USING spgist` | opclass-defined (partitioned trees) | non-balanced: quadtree, k-d, radix/trie |
| GIN | `USING gin` | element containment (`@> <@ && =`) | composite values: arrays, jsonb, FTS |
| BRIN | `USING brin` | `< <= = >= >` via block summaries | huge, physically-ordered tables |

[from-docs]

## Non-obvious claims per AM

- **B-tree pattern matching is anchor-sensitive.** `LIKE`/`~` use the index
  *only* when the pattern is a constant anchored to the start (`col LIKE 'foo%'`,
  `col ~ '^foo'`); `'%bar'` cannot. `ILIKE`/`~*` qualify only if the pattern
  begins with a non-alphabetic, case-stable character. **Caveat:** these
  index-usable patterns require the index to have been built in the **C locale**
  (or with a `text_pattern_ops`-family opclass) — the docs note this elsewhere
  and it is the classic "why isn't my LIKE index used" gotcha. [from-docs]
- **B-tree is the only AM that returns rows in sorted order** — so it backs
  `ORDER BY`, `MIN`/`MAX`, and merge joins, not just lookups. [from-docs]
  [verified-by-code, via knowledge/subsystems/access-nbtree.md — `btcanreturn`
  and ordered-scan support]
- **Hash indexes are WAL-logged and crash-safe since PG 10.** Before that they
  weren't replicated/recovered and were effectively deprecated. They store a
  *32-bit hash code* of the value, so the index never holds the value itself —
  great for very wide keys, useless for ranges/sorting. [from-docs]
- **GiST "is not one index" — it is infrastructure.** Each opclass implements a
  strategy (R-tree-like for geometry, signatures for FTS, range overlap, etc.).
  GiST uniquely supports **nearest-neighbor (KNN)** ordering:
  `ORDER BY location <-> point '(101,456)' LIMIT 10` walks the index in
  distance order. It also backs **exclusion constraints**. [from-docs]
- **SP-GiST** = *space-partitioned* GiST: non-balanced, disk-based partitioned
  search trees — quadtrees, k-d trees, and **radix tries** for text. Suits data
  with a natural recursive partitioning where the regions don't overlap. Also
  does KNN. [from-docs]
- **GIN is an inverted index:** one index entry per *component* value, with a
  posting list of rows containing it. That is why one GIN index answers
  "array/jsonb/tsvector contains element X" efficiently — it is built for
  many-keys-per-row data. Trade-off (from the GIN chapter, not repeated here):
  slower, larger updates; mitigated by the pending-list / `fastupdate`. [from-docs]
- **BRIN stores summaries per *block range*, not per row** — for a linear-order
  type, the min/max of each range. Index size is therefore tiny (kilobytes for a
  multi-GB table). It only helps when the column value **correlates with physical
  row order** (e.g. an append-only timestamp); on randomly-ordered data every
  range covers the whole domain and BRIN prunes nothing. The summary granularity
  is `pages_per_range`. [from-docs]

## Cross-cutting facts

- **Operator class, not data type, decides usability.** A query predicate is
  index-usable only if its operator is in the index's opclass strategy set. This
  is why `=` works on a hash index but `<` doesn't, and why a geometry GiST index
  answers `&&` but not `=`. [from-docs]
  [verified-by-code, via knowledge/idioms/catalog-conventions.md — pg_opclass /
  pg_amop strategy numbers]
- **Multicolumn support varies:** B-tree/GiST/GIN/BRIN support multicolumn
  indexes; the leading-column rule (B-tree uses the index for a predicate only if
  it constrains a prefix of the columns) is the planner-facing consequence.
  [from-docs]

## Links into corpus

- [[knowledge/architecture/access-methods.md]] — PG-wide AM overview (heap +
  index AMs, the `IndexAmRoutine` dispatch).
- [[knowledge/subsystems/access-nbtree.md]] — the B-tree implementation
  (892-line synthesis): ordered scans, `btcanreturn`, dedup, split logic.
- [[knowledge/files/src/backend/storage/freespace/indexfsm.c.md]] — index FSM
  used by these AMs for free-page tracking.
- Skill: `access-method-apis` — `IndexAmRoutine` callbacks to implement when
  adding/modifying an index AM.
- [[knowledge/idioms/catalog-conventions.md]] — registering an opclass
  (`pg_opclass`, `pg_amop`, `pg_amproc`) so a new operator becomes index-usable.

## Gaps / follow-ups

- Each non-B-tree AM has its own dedicated docs chapter (`gist`, `spgist`,
  `gin`, `brin`) already queued in `progress/_queues/docs.md` — those carry the
  opclass-author detail (support functions, `consistent`/`compress`/`penalty`)
  this overview omits.
- The C-locale / `text_pattern_ops` requirement for indexed `LIKE` is asserted
  `[from-docs]` from the broader indexes chapter; worth a `[verified-by-code]`
  confirmation against `varlena.c` pattern-selectivity in a backfill run.
  [unverified]
</content>
