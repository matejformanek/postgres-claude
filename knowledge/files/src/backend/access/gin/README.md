# gin/README — summary

- **Source path:** `source/src/backend/access/gin/README` (563 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Canonical narrative for the **Generalized Inverted Index (GIN)** access method. Defines the index as a B-tree over *keys* (entry tree), where each leaf points to either an inline posting list or a separate "posting tree" of heap TIDs. Designed for full-text search and any case "where items contain many keys and the same key values appear in many different items." [from-README, README:8-31, 86-93]

## The ideas you must hold

1. **Two-level structure: entry tree + posting trees.** The entry tree is a Lehman-Yao B-tree keyed by index keys (lexemes, array elements, …). Each leaf key entry stores *either* an inline compressed posting list (if it fits) *or* a downlink to the root of a separate posting B-tree keyed by ItemPointer. The choice is encoded in `t_tid`'s `offset` field: `GIN_TREE_POSTING` magic = posting tree, else = posting list. [from-README, README:148-188]
2. **No deletion from the entry tree.** "The set of distinct words in a large corpus changes very slowly." Posting trees do support page deletion; the entry tree only mutates posting lists or migrates a list to a tree. [from-README, README:28-31, 391-394]
3. **Fastupdate pending list.** With `fastupdate=on`, new entries go to a singly-linked list of "pending" pages anchored from the metapage, instead of into the entry tree. Searches must scan the pending list linearly and OR with the main tree result. A "cleanup" pass (triggered at threshold or vacuum) merges pending entries into the entry tree in bulk. The win is amortizing the per-key descend cost. [from-README, README:97-105, 201-216]
4. **Internal-page tuple packing is non-nbtree.** GIN groups `(P_i, K_{i+1})` per tuple (vs nbtree's `(K_i, P_i)` with separated highkey). The downlink and the *upper bound* of the child travel together; on the rightmost page the upper-bound key is "infinity". [from-README, README:218-245]
5. **Compressed posting lists (varbyte delta encoding).** Heap TIDs are sorted; deltas combine `(block<<11)|offset` (11 bits = `MaxHeapTuplesPerPageBits`) into a 43-bit integer encoded varbyte (≤ 6 bytes). First TID is uncompressed for random-skip seed. Posting tree leaf pages contain *multiple segments* (independent compressed lists) so a search can skip to the right segment without decoding the whole page. [from-README, README:277-305]
6. **Concurrency: descend with pin+S-lock coupling, step right under both locks.** Search holds pin+S on one page at a time during descent (release-before-acquire); during right-link traversal it acquires the new page's lock *before* releasing the old one, so the deletion algorithm cannot reclaim a page out from under a stepper. [from-README, README:318-345]
7. **Insert keeps pins on parents.** While descending to insert, GIN keeps pins (not locks) on root + internal parents — for cheap re-descent if a split must be propagated. The leaf is re-locked exclusive on arrival. If a split happens, the parent is exclusive-locked *before* releasing the left child, so split + parent-insert are not separable WAL-wise (unlike nbtree). [from-README, README:355-387]
8. **Vacuum never deletes entry-tree pages or entry-tree tuples.** It only walks entry-tree leaves to find posting trees and shrink/clean them. Posting trees are vacuumed in two stages: stage 1 removes dead TIDs from leaves; stage 2, only if stage 1 found an empty leaf, runs `ginScanPostingTreeToDelete` which takes a *full cleanup lock* on the posting-tree root and depth-first deletes empty pages. [from-README, README:389-403]
9. **Page deletion locking pattern: left-sibling lock retained during descent.** The deletion algorithm keeps E-locks on the *left siblings* of pages on the current path. This pre-locks anything needed to unlink (downlink edit + sibling rightlink edit) and avoids right→left deadlock with concurrent steppers. [from-README, README:413-417]
10. **Deleted pages cannot be reused immediately.** A concurrent descender may have read the downlink before deletion. Pages are stamped with the newest XID that might still need them; recycling waits until that XID is globally invisible. [from-README, README:419-433, 455-470]
11. **Predicate locking is on entry-leaf-pages + posting-tree-roots + the metapage.** The metapage lock interlocks with fastupdate (since a pending entry could logically belong anywhere). With `fastupdate=on`, every scan effectively grabs a full-index lock — many false positive serialization conflicts. [from-README, README:476-509]
12. **Three null categories.** `GIN_CAT_NORM_KEY`(1), `GIN_CAT_NULL_KEY`(2 = "ordinary null extracted from a non-null item"), `GIN_CAT_EMPTY_ITEM`(3 = "placeholder for an item with zero keys"), `GIN_CAT_NULL_ITEM`(4) — actually 4 codes in `gin_private.h`. The README enumerates the design rationale: empty/null items must produce *some* index entry so full scans don't miss them. [from-README, README:122-135; cross-check: `access/gin_private.h` GIN_CAT_*]

## Where each section is implemented

| README section | Implementing files |
|---|---|
| Entry-tree btree mechanics | `ginbtree.c` (the internal B-tree framework) |
| Entry-leaf format + insertion into entry tree | `ginentrypage.c` |
| Posting-tree pages (internal + leaf) + segments | `gindatapage.c` |
| Varbyte posting-list compression | `ginpostinglist.c` |
| Fastupdate pending list | `ginfast.c` |
| Insert top-level | `gininsert.c` |
| Build (sorted load via tuplesort) | `gininsert.c` (`ginbuild`) + `ginbulk.c` (accumulator) |
| Scan setup + key extraction | `ginscan.c` |
| Scan iteration over keys | `ginget.c` |
| Tri-state consistent evaluation | `ginlogic.c` |
| VACUUM | `ginvacuum.c` |
| WAL replay | `ginxlog.c`, record formats in `ginxlog.h` |
| Opclass validation | `ginvalidate.c` |
| Misc utilities (page flags, metapage init, opclass lookup) | `ginutil.c` |
| amcheck-style integrity (when present) | `gincheck.c` (note: in some branches lives in contrib/amcheck instead) |

## Highest-risk claims to spot-check

1. **"During step-right we hold both pin+lock"** — verified by source comment at `ginbtree.c` step-right loop. [from-README, README:341-345; verified-by-code]
2. **"Insert holds parent pin (not lock) during descent, but during split holds parent exclusive before releasing child"** — see `ginbtree.c::ginInsertValue` + `ginPlaceToPage`. Subtle: this is *different* from nbtree's "split as a separate WAL record" pattern; GIN's split + parent-insert is **atomic in one WAL record** (or several records emitted under all locks held). [from-README, README:355-387; verified-by-code, ginxlog.c]
3. **"Fastupdate interlock = metapage S-lock during scan"** — yes; `ginScanBeginning` takes share lock on metapage and the cleanup process takes exclusive. [from-README, README:501-508; verified-by-code]
