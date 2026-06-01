# nbtsplitloc.c

- **Source path:** `source/src/backend/access/nbtree/nbtsplitloc.c` (1185 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtinsert.c` (the only caller — `_bt_split` calls `_bt_findsplitloc`), `nbtutils.c` (`_bt_keep_natts_fast` for the truncation-aware scoring).

## Purpose

Choose the split point during a leaf or internal page split. The decision is a multi-objective heuristic balancing:

1. **Even byte-balance** between left and right halves (the primary goal).
2. **Maximize suffix-truncation effectiveness** — pick a split point where the first non-equal attribute between `lastleft` and `firstright` appears as early as possible, so the new left high key (the future parent downlink) is as short as possible.
3. **Avoid breaking duplicate runs across pages** when possible — large groups of equal user keys should stay on one page so they can be deduplicated; if they can't, accept a heavily lopsided split.
4. **Special-case the "all-same-value" page** with the `SPLIT_SINGLE_VALUE` strategy (96% fillfactor on the left, near-empty right, anticipating that the right half will absorb more inserts of the same value).
5. **Apply `BTREE_DEFAULT_FILLFACTOR` only on rightmost-page splits**; non-rightmost splits split evenly. This keeps the right edge of the tree growing efficiently without leaving holes in the middle.

[from-README, README:158-164, 822-901; verified-by-code]

## Public surface

- `_bt_findsplitloc(rel, origpage, newitemoff, newitemsz, newitem, *newitemonleft)` (the one exported function) — returns the `OffsetNumber firstrightoff` (i.e. the offset of the first item that will end up on the right page after split) and sets `*newitemonleft`. Materializes split-point candidates into a stack-allocated array, scores each one according to the chosen `FindSplitStrat`, returns the best.

## Internal types

- `FindSplitStrat` enum: `SPLIT_DEFAULT`, `SPLIT_MANY_DUPLICATES`, `SPLIT_SINGLE_VALUE`.
- `SplitPoint` struct: free-space delta + `firstrightoff` + `newitemonleft`.
- A larger context struct (`FindSplitData` typedef around lines 41+) bundles the relation, original page, newitem details, and the materialized candidate list.

## Key invariants

- **The chosen split point must produce two pages that both fit their contents** even with the truncated/expanded high key. The check accounts for the possibility that `_bt_truncate` may **enlarge** a tuple by appending the tiebreaker heap-TID attribute (see `BTMaxItemSize` derivation comment in nbtree.h:155-169).
- **Internal-page splits cannot use suffix truncation**, so the heuristic for them is simpler: pick the split that produces the smallest pivot key for the parent. [from-README, README:877-887]
- The fillfactor distinction (90% leaf, 70% internal, 96% single-value) is hard-coded constants in nbtree.h. [from-comment, nbtree.h:190-203]

## Cross-references

- **Called by:** `nbtinsert.c:_bt_split` (line 1567 of that file).
- **Calls into:** `nbtutils.c:_bt_keep_natts_fast` (scoring the truncation depth at each candidate).
