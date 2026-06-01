# gist/README — summary

- **Source path:** `source/src/backend/access/gist/README` (491 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Canonical narrative for **GiST (Generalized Search Tree)**. Hellerstein/Naughton/Pfeffer 1995 base, Kornacker/Mohan/Hellerstein 1997 concurrency. Modified for PostgreSQL: variable-length keys, single-pass insert, NULL-safe interface, compressed leaf keys, KNN ordering, recovery handling for uncompleted splits. [from-README, README:6-69]

## The ideas you must hold

1. **Single-pass downward insert with on-the-way downlink adjustment.** Unlike the textbook algorithm (descend, then propagate union up), PG GiST adjusts each downlink to cover the new key *during* the descent. By the time it reaches the leaf, no parent updates are needed except for split-downlinks. **Consequence:** crash recovery is dramatically simpler — the tree is self-consistent after any single page write. [from-README, README:119-156]
2. **F_FOLLOW_RIGHT + NSN solve the search/split race.** Split happens in two phases: (1) split the page and stamp left half with `F_FOLLOW_RIGHT`; (2) insert downlink into parent and clear the flag, stamping child's NSN with the parent-insert LSN. Searches use NSN-vs-parent-LSN comparison to decide whether to follow rightlink, avoiding the double-visit hazard. [from-README, README:268-296]
3. **Search returns one tuple at a time, queue-based.** Maintains a priority queue of unvisited items (heap-tuple-pointers + index-page-entries). Heap items returned immediately; index entries pop and trigger scan. Heap-tuples-first ordering = depth-first traversal favoring early LIMIT termination. For KNN search, queue is ordered by distance. [from-README, README:71-117]
4. **Crash recovery via F_FOLLOW_RIGHT detection on insert.** A leftover `F_FOLLOW_RIGHT` page after crash means the split's parent-insert never happened. The next inserter that sees the flag completes the split itself (calls `gistplacetopage` on parent). [from-README, README:286-296]
5. **Page split can recursively split into >2 pages.** Because variable-length keys / multi-key tuples mean `pickSplit` can't always promise the two halves fit. The `pageSplit` pseudocode (lines 236-256) shows the recursive split-the-right-page-too logic. [from-README, README:163-174, 236-256]
6. **Concurrency rule: child before parent, left before right.** "If you need to hold a lock on multiple pages at the same time, the locks should be acquired in the following order: child page before parent, and left-to-right at the same level." [from-README, README:260-265]
7. **Two-stage VACUUM with NSN-based split detection.** Stage 1 scans index in physical order, "jumping back" if a split moved a page we passed. Stage 2 unlinks empty leaf pages by re-finding their parent. Internal pages' last child is *never* deleted (insertion algorithm would break on empty internal pages). [from-README, README:440-486]
8. **Deleted page recycling uses XID gate (same idiom as nbtree/gin).** Page stamped with next-transaction-counter at deletion time; cannot recycle until that XID is invisible to everyone. [from-README, README:478-485]
9. **Buffering build for large inputs.** Internal nodes at multiples-of-`level_step` levels carry temp-file-backed buffers. Inserts cascade into buffers; when half-full, buffer emptied to next level. Converts random I/O of one-at-a-time inserts into mostly-sequential I/O. [from-README, README:297-423]
10. **Sorted build when opclass has `sortsupport`.** Bottom-up, B-tree-style build from sorted input. Fallback to buffered insert otherwise. Multidimensional opclasses can have poor linearization; that's handled by tuple buffering + multidim-aware `pickSplit`. [from-README, README:425-438]
11. **`findPath` + `gistFindCorrectParent`.** When a split needs to re-find the parent (which may have migrated due to its own concurrent split), `findPath` does a top-down search from root, and `gistFindCorrectParent` follows rightlinks at parent level first. [from-README, README:190-234]
12. **`gistplacetopage` is the workhorse.** One step of insert: try to fit, else split, returning new downlink tuples that caller must insert in parent. Root splits handled specially (allocate new children + new root in one operation). [from-README, README:176-187]

## Where each section is implemented

| README section | Implementing files |
|---|---|
| AM handler, insert top-level | `gist.c` |
| Search + KNN | `gistget.c` |
| Split-distribution heuristics + R-tree picksplits | `gistsplit.c`, `gistproc.c` |
| Buffering build | `gistbuild.c`, `gistbuildbuffers.c` |
| Scan setup / rescan | `gistscan.c` |
| Page utilities, NSN, key utilities | `gistutil.c` |
| VACUUM (2-stage) | `gistvacuum.c` |
| WAL replay | `gistxlog.c`, records in `gistxlog.h` |
| Opclass validation | `gistvalidate.c` |

## Highest-risk claims to spot-check

1. **"NSN comparison correctly catches the search-vs-split race"** — implemented in `gistget.c`'s scan iteration plus `gistutil.c::gistcheckpage`/`gistScanPage`. NSN is set inside the **parent** insert WAL emission, so the standby sees it at replay too. [from-README, README:268-284; verified-by-code in gistxlog.c handling]
2. **"Single-pass insert with on-the-way downlink adjustment"** — see `gist.c::gistdoinsert` and the stack-of-frames it maintains. Concretely: at each non-leaf step, if downlink doesn't cover new key, call `Union`, replace downlink, possibly split internal page. [from-README, README:127-144]
3. **"Split recursively if pickSplit halves don't fit"** — verified in `gistsplit.c::gistSplitByKey` recursion. [verified-by-code]
