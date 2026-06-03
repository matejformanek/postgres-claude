# nbtsearch.c

- **Source path:** `source/src/backend/access/nbtree/nbtsearch.c` (2237 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtreadpage.c` (the per-page read loop and array-key advancement — extracted from this file), `nbtinsert.c` (uses `_bt_search`, `_bt_moveright`, `_bt_binsrch_insert`), `nbtpreprocesskeys.c` (consumes the preprocessed scan keys).

## Purpose

Tree-descent code for nbtree: `_bt_search` (the recursive descent from root to leaf), `_bt_moveright` (the L&Y right-walk on detection of a concurrent split), `_bt_binsrch` and `_bt_binsrch_insert` (per-page binary search returning an offset number), `_bt_compare` (the three-way compare between an insertion scankey and a page item), and the scan-iteration entry points `_bt_first` (initial positioning) / `_bt_next` (subsequent items) / `_bt_steppage` (cross to sibling). The actual reading of a leaf page into the `BTScanPosData` cache lives in `nbtreadpage.c`. [from-comment, nbtsearch.c:1-14; verified-by-code]

## Function map

- `_bt_search` (100) — descend from root to leaf. Returns the descent stack (parent offsets at each level) so the caller can use it for parent-downlink insertion on a future split.
- `_bt_moveright` (242) — walk right while the current page's high key is `< scankey` (`<=` for `nextkey`). Optionally finishes incomplete splits when in write mode. Cycle-safe: bails via ERROR `"fell off the end of index"` if it sees `P_IGNORE` past the end. [verified-by-code, nbtsearch.c:317-319]
- `_bt_binsrch` (344, static) — per-page binary search for search/descent. Returns the first item `>= key` (or `>` if `nextkey`) on a leaf, or the last item `<= key` on an internal page (pivot tuples are strictly less than the subtree below them).
- `_bt_binsrch_insert` (475) — variant used by insert path; uses cached `BTInsertStateData.bounds_valid` to skip a binary search when consecutive insertions hit the same range.
- `_bt_binsrch_posting` (603, static) — find the right slot *inside* a posting-list tuple when the insertion key falls within one.
- `_bt_compare` (689) — three-way compare honouring DESC, NULLS FIRST, scantid tie-break, truncated-attribute "minus infinity" rule. The single most-called function in nbtree at runtime.
- `_bt_first` (883) — initial scan positioning. Builds the insertion scankey from the search keys, descends via `_bt_search`, then hands off to `_bt_readfirstpage`.
- `_bt_next` (1586) — return the next item from the cached `BTScanPosData`; if exhausted, calls `_bt_steppage`.
- `_bt_returnitem` (1622, static) — push the current `BTScanPosItem` into `scan->xs_heaptid` (and `scan->xs_itup` for index-only).
- `_bt_steppage` (1647, static) — cross to sibling page (forward = follow `nextPage` cached from previous `_bt_readpage`; backward = follow `prevPage` with the move-left recovery dance via `_bt_lock_and_validate_left`).
- `_bt_readfirstpage` / `_bt_readnextpage` (1747 / 1840, static) — wrappers that call `_bt_readpage` (in nbtreadpage.c) and handle parallel-scan coordination.
- `_bt_lock_and_validate_left` (1975, static) — the move-left algorithm from README §"Page deletion and backwards scans". Handles concurrent splits of the left sibling and concurrent deletion of the page we just came from.
- `_bt_get_endpoint` (2092) — leftmost or rightmost leaf, used by ordered scans without quals.
- `_bt_endpoint` (2178, static) — feed the endpoint to the scan as the initial page.

## Key invariants

- **Descent holds at most one buffer lock at a time** (`_bt_relandgetbuf` at line 183 is the only buffer transition in `_bt_search`'s loop). This is the L&Y promise that makes nbtree readers cheap. [verified-by-code, nbtsearch.c:182-186]
- **Lock-mode upgrade on the level above the leaf for write descents**: at level 1 with `access == BT_WRITE`, the next acquired buffer is taken with `BT_WRITE` directly (line 179-180) — saving a release/reacquire cycle for the common write-leaf case. [verified-by-code]
- **Move-right is unbounded but must always terminate**: the right-walk follows `btpo_next`; pages along the way may be `P_IGNORE` (half-dead or deleted). Since pages are never re-renamed and the rightmost page has `btpo_next == P_NONE`, the walk terminates. [from-comment, nbtsearch.c:265-272]
- **`_bt_moveright` finishes incomplete splits opportunistically** when `forupdate` is true: if it sees `P_INCOMPLETE_SPLIT(opaque)` on a page it will land on, it upgrades to write lock if needed and calls `_bt_finish_split` (nbtinsert.c). [verified-by-code, nbtsearch.c:283-305]
- **Drop-pin policy** (`_bt_drop_lock_and_maybe_pin`, line 55): always drop the lock between page accesses; drop the pin too iff `so->dropPin`. The `dropPin` decision was set once by `btrescan` and never changes mid-scan. [verified-by-code]
- **Backward scans on the leaf level use `_bt_lock_and_validate_left`**, not a naive `prev` follow. The validation is: after taking the left-link, the page we landed on must have `btpo_next == lastcurrblkno` (or we re-walk right). If the page was deleted, we move further right. See README §"Page deletion and backwards scans". [from-README, README:330-360; from-comment, nbtsearch.c:1975-2091]

## Cross-references

- **Called by:** `nbtinsert.c` (`_bt_search`, `_bt_moveright`, `_bt_binsrch_insert`, `_bt_compare`), `nbtpage.c` (`_bt_search` from `_bt_pagedel`), `nbtree.c` (`_bt_first`, `_bt_next` from `btgettuple`/`btgetbitmap`), `nbtutils.c` (`_bt_compare` from `_bt_check_natts`).
- **Calls into:** `nbtpage.c` (every buffer-lock primitive), `nbtreadpage.c` (`_bt_readpage`, array advancement), `nbtutils.c` (`_bt_mkscankey`, `_bt_killitems`).

## Open questions

- The interaction between `_bt_moveright(forupdate=true)` finishing a split and a concurrent inserter that is *also* in `_bt_finish_split` is documented as safe (idempotent under buffer-lock serialization) but not formally argued in code. [unverified]
- `_bt_compare` rules around backward scans with truncated -inf attributes are subtle (see comment at lines 437-446: "during backward scans `_bt_compare()` interprets omitted scan key attributes as == corresponding truncated -inf attributes instead"). The cited claim that VACUUM relies on this guarantee when re-finding a page undergoing deletion was not traced. [unverified — but it is the citation for `_bt_lock_subtree_parent`'s downlink lookup, see nbtpage.c]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/access-nbtree.md](../../../../../subsystems/access-nbtree.md)
