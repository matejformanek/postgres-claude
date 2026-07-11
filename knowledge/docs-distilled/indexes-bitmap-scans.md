---
source_url: https://www.postgresql.org/docs/current/indexes-bitmap-scans.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.5 Combining Multiple Indexes"
maps_to_skills: [executor-and-planner, buffer-manager]
---

# 11.5 Combining Multiple Indexes (bitmap scans)

Distilled from §11.5. The chapter is short but explains the executor's
`BitmapAnd`/`BitmapOr`/`Bitmap Heap Scan` node family and why a bitmap scan
loses index ordering — the reason a bitmap plan plus `ORDER BY` still needs
an explicit `Sort`.

## Non-obvious claims

- **Bitmap combination is a three-stage pipeline:** scan each index → build
  an in-memory bitmap of matching table-row locations (TIDs) → `AND`/`OR`
  the bitmaps per the query's boolean structure. [from-docs §11.5]
- **The heap is then visited in PHYSICAL order**, "because that is how the
  bitmap is laid out." Consequence: "any ordering of the original indexes is
  lost, and so a separate sort step will be needed if the query has an
  `ORDER BY` clause." This is the structural reason an ordered query on top
  of a bitmap plan shows a `Sort`. [from-docs §11.5]
- **A single index can be scanned multiple times and OR-ed:**
  `WHERE x=42 OR x=47 OR x=53 OR x=99` can become four scans of the index on
  `x`, OR-ed together — the "combine" feature is not limited to *distinct*
  indexes. [from-docs §11.5]
- **Multicolumn vs separate-index trade-off is workload-shaped:** a
  multicolumn `(x,y)` index is best when queries constrain both columns;
  separate indexes on `x` and `y` plus bitmap combination win when queries
  variously constrain one or the other. "Sometimes multicolumn indexes are
  best, but sometimes it's better to create separate indexes and rely on the
  index-combination feature." [from-docs §11.5]
- **Physical-order visiting is also what makes the heap access efficient**
  (sequential-ish rather than random), which is why bitmap scans beat plain
  index scans when a query matches many rows. [inferred from §11.5]

## Complements from sibling pages (not on §11.5 itself)

- The in-memory bitmap becomes **lossy** (stores whole-page bits instead of
  per-tuple TIDs) when it would exceed `work_mem`; lossy pages require a
  **recheck** of the original condition against each heap tuple. This is why
  `EXPLAIN` shows a `Recheck Cond` on `Bitmap Heap Scan`. [from-docs, §14.1
  worked examples / `work_mem` note — cross-referenced, not stated verbatim
  in §11.5] [[knowledge/docs-distilled/using-explain.md]]
- `BitmapAnd`/`BitmapOr` nodes report `actual rows=0` under
  `EXPLAIN ANALYZE` — a display limitation. [from-docs §14.1.3]
  [[knowledge/docs-distilled/using-explain.md]]

## Links into corpus

- Bitmap-scan executor nodes (`nodeBitmapAnd`/`nodeBitmapOr`/
  `nodeBitmapHeapscan`/`nodeBitmapIndexscan`):
  [[knowledge/subsystems/executor.md]], [[knowledge/docs-distilled/executor.md]].
- The `amgetbitmap` AM entry that produces per-index bitmaps:
  [[knowledge/docs-distilled/index-scanning.md]],
  [[knowledge/docs-distilled/index-api.md]].
- Heap-order page visiting ↔ buffer access strategy:
  [[knowledge/subsystems/storage-buffer.md]].
- Multicolumn-index comparison sibling:
  [[knowledge/docs-distilled/indexes-types.md]].

## Citations

- Combination mechanics + physical-order-loses-index-order + the OR example
  + multicolumn trade-off: source-URL §11.5.
- Lossy-bitmap / recheck and `BitmapAnd rows=0`: source-URL §14.1
  (cross-referenced), [[knowledge/docs-distilled/using-explain.md]].
