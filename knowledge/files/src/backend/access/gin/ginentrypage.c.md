# ginentrypage.c

- **Source path:** `source/src/backend/access/gin/ginentrypage.c` (774 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Entry-tree page mechanics: form/decode entry tuples (`GinFormTuple`, `GinReadTuple`), implement the entry-tree `GinBtree` vtable, and handle the leaf-tuple → posting-tree migration when an inline posting list grows too large. [from-comment, ginentrypage.c:1-13]

## Key entry points

- `GinFormTuple` — assembles a leaf key entry: builds a "normal" index tuple via `index_form_tuple`, then patches `t_tid` to encode the posting list offset/length OR a posting-tree pointer (via `GinSetPostingTree` magic). Handles the null category byte at the end of the index data area. Returns NULL if the tuple won't fit and `errorTooBig=false`. [from-comment, ginentrypage.c:32-46]
- `entryIsMoveRight` / `entryLocateEntry` / `entryFindChildPtr` / `entryGetLeftMostChild` — the vtable callbacks.
- `entryBeginPlaceToPage` / `entryExecPlaceToPage` — decide INSERT vs SPLIT for the entry tree, then commit.
- `entrySplitPage` (static) — compute the split point; sealed by `entryExecPlaceToPage`.
- `ginVacuumEntryPage` — called by `ginvacuum.c` to repack a leaf after dead TIDs are removed (may migrate inline posting list back to inline shape after a posting-tree vacuum).

## Tuple format invariants

Per the README §"Index structure" — leaf key tuples encode:
- Multi-column index: optional `int2` column-number prefix.
- Null category byte at next SHORTALIGN boundary (if `IndexTupleHasNulls`).
- Posting list (compressed varbyte) OR posting-tree pointer in `t_tid`.
- `GinItupIsCompressed` flag in `t_tid.ip_blkid` high bit.

`GinFormTuple` builds the inline-posting-list case. The pivoting between "inline list" and "separate posting tree" happens at insert time: if the new posting list won't fit, the caller in `gininsert.c::ginEntryInsert` creates a posting tree via `createPostingTree` (`gindatapage.c`) and replaces the leaf tuple with a posting-tree-pointer form.

## Split

Entry-tree splits compute a split point that approximately balances bytes. `entrySplitPage` (static) builds new-left and new-right page images; `ginbtree.c::ginPlaceToPage` then performs the atomic copy + WAL. As with all GIN splits, full-page images are forced. [from-comment, ginbtree.c:601-605]

## Locking

All driven by `ginbtree.c`; this file's logic runs inside CRIT.

Tags: [from-comment, ginentrypage.c:1-50]; structure cross-confirmed against README §"Index structure".
