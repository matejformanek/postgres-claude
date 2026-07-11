---
source_url: https://www.postgresql.org/docs/current/indexes-collations.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.11 Indexes and Collations"
maps_to_skills: [collation-provider, executor-and-planner]
---

# 11.11 Indexes and Collations

Distilled from §11.11. Short but sharp: an index column carries exactly one
collation, so a `COLLATE`-qualified query that differs from the index's
collation cannot use it — the sibling constraint to §11.10's one-opclass rule.

## Non-obvious claims

- **One collation per index column.** An index built on a `text`/`varchar`
  column bakes in a single collation for the ordering it encodes. [from-docs §11.11]
- **A bare comparison uses the column's default collation**, so an ordinary
  `WHERE content > 'constant'` matches an index built with the column's
  collation. [from-docs §11.11]
- **An explicit `COLLATE` that differs from the index collation defeats the
  index:** `… WHERE content > 'constant' COLLATE "y"` cannot use an index
  built in the column's default collation — "This index cannot accelerate
  queries that involve some other collation." [from-docs §11.11]
- **Fix = a second index built with that collation:**
  `CREATE INDEX … ON test1c (content COLLATE "y")`. So one column may need
  several indexes, one per collation a workload queries under. [from-docs §11.11]
- **This is the direct analogue of the one-opclass rule (§11.10):** collation
  and operator class both parameterize the ordering an index physically
  stores, and each index fixes one of each. [inferred, §11.10 + §11.11]

## Links into corpus

- Collation providers (builtin / ICU / libc) and where the collation of a
  comparison is resolved: [[knowledge/docs-distilled/collation.md]],
  [[knowledge/docs-distilled/locale.md]].
- Byte-vs-collation comparison choice (`text_pattern_ops`):
  [[knowledge/docs-distilled/indexes-opclass.md]].
- B-tree encodes the collation-dependent order:
  [[knowledge/subsystems/access-nbtree.md]], [[knowledge/docs-distilled/btree.md]].
- Encoding layer under collation: [[knowledge/docs-distilled/multibyte.md]].

## Citations

- All bullets: source-URL §11.11 (one-collation-per-column, the default-vs-
  explicit-COLLATE example, and the second-index remedy).
