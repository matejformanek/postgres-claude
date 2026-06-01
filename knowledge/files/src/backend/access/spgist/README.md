# spgist/README — summary

- **Source path:** `source/src/backend/access/spgist/README` (390 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Canonical narrative for **SP-GiST (Space-Partitioned GiST)**: generalized framework for disk-based space-partitioned trees — quadtrees, k-d trees, radix tries. Maps a non-balanced in-memory pointer-tree onto disk pages with high fanout. [from-README, README:1-13]

## The ideas you must hold

1. **Inner tuples vs leaf tuples.** Inner tuple = optional `prefix` + array of `(label, pointer)` nodes. Leaf tuple = leaf value + heap TID + nextOffset (intra-page chain) + optional null mask + optional INCLUDE columns. **Inner and leaf tuples cannot be intermixed on the same page** (separate "inner pages" and "leaf pages"). [from-README, README:17-89]
2. **One inner tuple per inner page (except root).** Once root has been split, root has exactly one inner tuple. Other inner pages also typically contain one inner tuple. (Inner pages may also carry placeholder/redirect tuples.) [from-README, README:35-40, 131-136]
3. **Leaf chains on a single page.** "The list of leaf tuples reached from a single inner-tuple node all be stored on the same index page." Cap chain length so it never crosses pages — lets `nextOffset` be a 2-byte OffsetNumber. [from-README, README:27-33]
4. **Three insert outcomes from `chooseFn`**: `MatchNode` (descend), `AddNode` (extend the inner tuple's node array, retry), `SplitTuple` (split prefix into prefix+postfix for tries like radix). PickSplit is invoked when a leaf page is full and no other action works. [from-README, README:114-127]
5. **The radix split-tuple walkthrough (README lines 158-194)** is the canonical example: how a prefix that doesn't match gets split into a "prefix tuple" stored in place + a new "postfix tuple" stored elsewhere. The core invariant: **prefix-tuple-after-split ≤ size of old inner tuple**, so it can be written in place without page split. [from-README, README:194-202]
6. **Separate "nulls tree".** Nulls live in their own disjoint SP-GiST subtree with its own root (off the same metapage). The nulls tree uses hardwired logic, not the opclass. This means opclasses never need to handle NULL inputs. [from-README, README:92-103]
7. **Triple-parity page assignment.** "If inner tuple is on page with BlockNumber N, then its child tuples should be placed on the same page, or else on a page with BlockNumber M where `(N+1) mod 3 == M mod 3`." This reduces (but doesn't eliminate) cross-branch deadlocks during insert. [from-README, README:234-244]
8. **Insert uses conditional locking + restart on deadlock risk.** Insert holds exclusive locks on two levels at a time (parent+child). If lock acquisition would block, **release both and restart from root**. Triple-parity makes this rare. [from-README, README:217-244]
9. **Search holds only one page at a time.** Solves deadlock-free but introduces a race: a concurrent insert may have moved the target chain to another page. Resolved by the **redirect tuple** mechanism. [from-README, README:252-266]
10. **Four leaf-tuple states**: `SPGIST_LIVE` (normal), `SPGIST_REDIRECT` (link to new location of moved chain), `SPGIST_DEAD` (entry-point still needed for downlink validity but no live data), `SPGIST_PLACEHOLDER` (dead, no incoming link, slot reusable). Inner tuples can be LIVE, REDIRECT, or PLACEHOLDER (never DEAD). [from-README, README:269-318]
11. **VACUUM = single sequential scan + pending list.** A normal sequential scan; concurrent PickSplit/MoveLeafs can move tuples to already-scanned pages. The fix: when VACUUM sees a REDIRECT created *during* the current run, add the target to a pending list and re-visit it. Pending list never shrinks until end of run, so termination is bounded. [from-README, README:321-368]
12. **Last-used-page cache in metapage, NOT WAL-logged.** Four entries: one leaf + three inner (one per triple-parity group), separately for main tree and nulls tree. Stale cache is harmless (allocate a new page). [from-README, README:376-383]

## Where each section is implemented

| README section | Implementing files |
|---|---|
| AM handler, build, insert top-level | `spgist.c`, `spginsert.c` |
| Insert decision tree (descend + chooseFn + splittuple + picksplit) | `spgdoinsert.c` (the workhorse, ~2300 lines) |
| Scan, ordered (KNN) search | `spgscan.c` |
| WAL replay | `spgxlog.c`, records in `spgxlog.h` |
| VACUUM (with pending list) | `spgvacuum.c` |
| Page/utility helpers (`SpGistInitPage`, redirect machinery, last-used-page cache) | `spgutils.c` |
| Built-in radix opclass (text) | `spgtextproc.c` |
| Built-in quadtree opclass (point/box) | `spgquadtreeproc.c` |
| Built-in k-d tree opclass (point) | `spgkdtreeproc.c` |
| Common helpers across opclasses | `spgproc.c` |
| Opclass validation | `spgvalidate.c` |

## Highest-risk claims to spot-check

1. **"Conditional locking + restart"** in insert — see `spgdoinsert.c` calls to `ConditionalLockBuffer` and the "restart" `goto`s. [from-README, README:228-232]
2. **"REDIRECT tuple → eventually PLACEHOLDER → reusable"** chain managed by VACUUM via XID horizon. [from-README, README:273-289; verified-by-code in spgvacuum.c]
3. **"Triple-parity invariant is best-effort, not strict"** — README admits "it's impractical to preserve this invariant in every case". So deadlocks are still possible; restart is the safety net. [from-README, README:242-244]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
