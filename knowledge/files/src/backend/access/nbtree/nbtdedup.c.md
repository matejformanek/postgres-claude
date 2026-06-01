# nbtdedup.c

- **Source path:** `source/src/backend/access/nbtree/nbtdedup.c` (1105 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtinsert.c` (calls `_bt_dedup_pass` and `_bt_bottomupdel_pass` from `_bt_delete_or_dedup_one_page`), `nbtree.h` (`BTDedupStateData`, `BTDedupInterval`, `BTVacuumPostingData`), `nbtxlog.c` (`btree_xlog_dedup`).

## Purpose

Two related last-line-of-defense mechanisms before a leaf page split, both implemented here because they share infrastructure (the posting-list-merge state machine and the same `XLOG_BTREE_DEDUP`-shaped WAL primitive when relevant):

1. **Deduplication** (`_bt_dedup_pass`) — merge consecutive equal non-pivot tuples on a leaf into one posting-list tuple. Triggered just before a split would happen. Emits `XLOG_BTREE_DEDUP`.
2. **Bottom-up deletion** (`_bt_bottomupdel_pass`) — when version churn is suspected (executor hint `indexUnchanged`, or unique-index INSERT/DELETE churn), batch up duplicates and ask the tableam to confirm which TIDs are dead. Emits the same WAL records that simple deletion uses (`XLOG_BTREE_DELETE`).

[from-comment, nbtdedup.c:1-13; from-README, README:556-619, 889-988]

## Public surface

- `_bt_dedup_pass(rel, buf, newitem, newitemsz, bottomupdedup)` — full deduplication pass over the page. The `bottomupdedup` flag selects between two strategies (single-value vs general); the call from `_bt_delete_or_dedup_one_page` may set it true to indicate "we just failed bottom-up deletion, don't waste effort on single-value strategy".
- `_bt_bottomupdel_pass(rel, buf, heapRel, newitemsz)` — bottom-up deletion. Calls back into the tableam (`heap_index_delete_tuples`) which decides what's actually dead. Returns whether enough space was freed.
- `_bt_dedup_start_pending` / `_bt_dedup_save_htid` / `_bt_dedup_finish_pending` — the state-machine API used by both this file *and* `nbtsort.c` for build-time deduplication.
- `_bt_form_posting(base, htids, nhtids)` — build a posting-list tuple from an array of TIDs.
- `_bt_update_posting(vacposting)` — apply a partial-TID-deletion plan to an existing posting-list tuple, palloc-returning the rebuilt tuple. Used by VACUUM and `_bt_delitems_delete`.
- `_bt_swap_posting(newitem, oposting, postingoff)` — handle the "incoming tuple overlaps an existing posting list" case during insert. This is the function whose semantics are mirrored in `btree_xlog_insert(_POST)` and `btree_xlog_split`. See README §"Posting list splits".

## Key invariants

- **Deduplication is lazy**: only ever performed at the point where a split is otherwise imminent, after LP_DEAD-marked items have been removed and (sometimes) after a bottom-up deletion pass failed. [from-README, README:903-948]
- **LP_DEAD bits on posting-list tuples mean ALL TIDs in the list are dead.** Granular dead-TID removal happens via `_bt_update_posting` during VACUUM/delete, not via LP_DEAD setting. [from-README, README:545-555]
- **Posting-list tuples are recognized by `INDEX_ALT_TID_MASK | BT_IS_POSTING`** in the tuple header; `t_tid`'s block field stores the posting-list byte offset within the tuple, and `t_tid`'s offset field stores the count + status bits. See nbtree.h:441-549. [from-comment]
- **Deduplication is only safe when the index has `btm_allequalimage == true`** (all opclasses provide `BTEQUALIMAGE_PROC`). [from-comment, nbtree.h:130-148]
- **Posting-list compression (varbyte encoding like GIN) is explicitly rejected** because it would break the page-split space accounting and complicate partial-TID deletion. [from-README, README:930-941]

## Cross-references

- **Called by:** `nbtinsert.c` (`_bt_delete_or_dedup_one_page`), `nbtsort.c` (build-time dedup), `nbtpage.c` (`_bt_delitems_*` via `_bt_update_posting`), `nbtxlog.c` (`_bt_swap_posting` during REDO).
- **Calls into:** `access/tableam.h` callbacks (heap_index_delete_tuples), `storage/predicate.c` for SSI, `access/xloginsert.c` for WAL.
