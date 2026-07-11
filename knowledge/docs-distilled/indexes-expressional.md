---
source_url: https://www.postgresql.org/docs/current/indexes-expressional.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.7 Indexes on Expressions"
maps_to_skills: [executor-and-planner, fmgr-and-spi]
---

# 11.7 Indexes on Expressions

Distilled from §11.7. The asymmetry — expensive to maintain, cheap to search
— plus the immutability requirement and the exact-form matching rule that the
planner enforces.

## Non-obvious claims

- **An index column can be a computed expression** over one or more table
  columns, not just a bare column. Canonical case: `CREATE INDEX … ON test1
  (lower(col1))` to serve `WHERE lower(col1) = 'value'`. [from-docs §11.7]
- **The expression is stored, so search never recomputes it.** At query time
  "the system sees the query as just `WHERE indexedcolumn = 'constant'`" — the
  search speed equals any simple index lookup. [from-docs §11.7]
- **Maintenance is the cost:** "Index expressions are relatively expensive to
  maintain, because the derived expression(s) must be computed for each row
  insertion and non-HOT update." [from-docs §11.7] — the phrase *non-HOT
  update* ties the cost directly to whether the update qualified for HOT.
  [[knowledge/docs-distilled/storage-hot.md]]
- **The query must use the same expression form.** The planner matches the
  index only when the query's expression syntactically corresponds to the
  index's stored expression; it will not rewrite equivalents. [from-docs §11.7]
- **Expressions must be immutable.** (Implied by the excerpt, required in
  practice: a volatile/stable function would make stored index values
  inconsistent with recomputation.) [inferred §11.7 + index-correctness rules]
- **Verdict:** "indexes on expressions are useful when retrieval speed is
  more important than insertion and update speed." [from-docs §11.7]

## Links into corpus

- HOT vs non-HOT update determines whether the expression is recomputed:
  [[knowledge/docs-distilled/storage-hot.md]],
  [[knowledge/subsystems/access-heap.md]].
- Function volatility (why IMMUTABLE is required):
  [[knowledge/docs-distilled/xfunc-volatility.md]].
- Expression-index blind spot for index-only scans:
  [[knowledge/docs-distilled/indexes-index-only-scans.md]].
- fmgr call of the index expression at insert/update time:
  [[knowledge/subsystems/access-nbtree.md]], [[knowledge/docs-distilled/index-functions.md]].

## Citations

- All bullets: source-URL §11.7 (expression columns, store-not-recompute,
  per-insert/non-HOT-update maintenance cost, same-form matching, and the
  retrieval-vs-write verdict). Immutability is [inferred] per index
  correctness rules, flagged as such.
