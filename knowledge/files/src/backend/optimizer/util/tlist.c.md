# tlist.c — targetlist manipulation utilities

- **Source:** 1341 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Public surface

- `add_to_flat_tlist` (140), `get_tlist_exprs(tlist, includeJunk)` (171),
  `count_nonjunk_tlist_entries` (194).
- `tlist_same_exprs` (226), `tlist_same_collations` (290),
  `tlist_same_datatypes` (256) — structural comparisons that ignore
  resname/resjunk labeling (intermediate nodes often have those unset).
  [from-comment:218-227]
- `apply_tlist_labeling(dest_tlist, src_tlist)` (326) — copy
  TargetEntry labeling attributes back onto a plan's output tlist.
  [from-comment:320-325]
- `get_sortgroupclause_expr` (387), `get_sortgrouplist_exprs` (400) —
  sortgroupref-based lookup.
- `extract_grouping_ops` (471) / `extract_grouping_collations` (497) —
  arrays of equality-op OIDs / collations.
- `grouping_is_sortable` (548) / `grouping_is_hashable` (later).

## Tag tally
`[verified-by-code]` ×4, `[from-comment]` ×2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
