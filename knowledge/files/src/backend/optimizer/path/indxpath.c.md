# indxpath.c — index path generation

- **Source:** `source/src/backend/optimizer/path/indxpath.c` (4461 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

For one baserel, decide which of its `indexlist` entries can serve which
quals/orderings, and add the resulting IndexPath / BitmapHeapPath /
BitmapAndPath / BitmapOrPath nodes via `add_path`. [verified-by-code]

## 2. Entry points

| Line | Function | Notes |
|---|---|---|
| 238 | `create_index_paths(root, rel)` | Top-level: classify quals, call match_clauses_to_index for each index, then `build_index_paths`. Considers parameterized paths against rels that lateral-precede this rel. [from-comment:225-235] |
| 3939 | `check_index_predicates(root, rel)` | Probe each *partial* index's predicate against the rel's baserestrictinfo + collected outer quals; sets `indrestrictinfo` and `predOK`. Recomputed because new restrictions may make a partial index newly applicable. [from-comment:3934-3940] |
| 4143 | `relation_has_unique_index_for(...)` | Used by join removal / Memoize: does some unique index cover all the clauses? Returns `extra_clauses` derived from baserestrictinfos used in the proof. |
| 4304 | `indexcol_is_bool_constant_for_query` | Handles `WHERE bool_col` (no `=true`) and `ORDER BY bool_col` for boolean index columns. [from-comment:4297-4303] |
| 4355 | `match_index_to_operand` | Exported helper used by selfuncs.c; does NOT check collation, caller's responsibility. [from-comment:4350-4353] |
| 4452 | `is_pseudo_constant_for_index` | Final-resort test for path-style index quals; cheaper `pull_varnos` is tried before volatility. |

## 3. Mental model

Quals are classified into *index clauses* (an op the index AM can
evaluate), *predicate clauses* (matching partial-index predicates), and
*order-by clauses* (driving pathkey generation). Bitmap scans differ:
they ignore ordering and combine via And/Or, costed against the
underlying heap scan. [inferred from include set + standard PG architecture]

## 4. Notable

- "Unparameterized" in comments here means "as far as the indexquals are
  concerned" — lateral-required rels are not counted. [from-comment:228-233]
- BitmapAnd/BitmapOr trees come from `choose_bitmap_and` /
  `generate_bitmap_or_paths` (later in the file).

## 5. Tags
`[verified-by-code]` ×3, `[from-comment]` ×6, `[inferred]` ×1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/bitmap-and-or-heap-executor.md](../../../../../idioms/bitmap-and-or-heap-executor.md)

