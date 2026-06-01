# heap/ READMEs (HOT and tuplock)

- **Source path:** `source/src/backend/access/heap/README.HOT`, `source/src/backend/access/heap/README.tuplock`
- **Lines:** 520 (HOT) + 233 (tuplock)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `pruneheap.c`, `heapam.c` (lock_tuple, update), `htup_details.h`

## Purpose

Two design documents that explain non-obvious heap-AM mechanisms:

- **README.HOT** — Heap-Only Tuples: how an UPDATE that does not change any indexed column can avoid creating new index entries by chaining the new tuple version on the *same page* via `t_ctid`, marking the new version `HEAP_ONLY_TUPLE` and the predecessor `HEAP_HOT_UPDATED`. Single-page vacuuming ("pruning") reclaims dead HOT-chain members and converts root line pointers into "redirecting" line pointers. [from-README]
- **README.tuplock** — Two-level row locking: store lock state in `xmax` + infomask bits (cheap), and serialize *waiters* through the heavyweight lock manager on a `LOCKTAG_TUPLE` (fairness). The four lock modes (KeyShare, Share, NoKeyExclusive, Exclusive) and their conflict matrix; how MultiXactIds encode concurrent lockers. [from-README]

## Top-of-file comment (HOT, first paragraph)

> "The Heap Only Tuple (HOT) feature eliminates redundant index entries and allows the re-use of space taken by DELETEd or obsoleted UPDATEd tuples without performing a table-wide vacuum. It does this by allowing single-page vacuuming, also called 'defragmentation' or 'pruning'." [from-README, README.HOT:4-8]

## Top-of-file comment (tuplock, first paragraph)

> "Locking tuples is not as easy as locking tables… we use a two-level mechanism. The first level is implemented by storing locking information in the tuple header… The second level [is] the standard lock manager." [from-README, README.tuplock:4-25]

## Key concepts to remember

- A HOT chain is fully contained on a single page; if an update needs a new page, it cannot be HOT. [from-README, README.HOT around the "single-page" clause]
- "Pruning" can run during ordinary page reads, not just VACUUM — see `heap_page_prune_opt`. [from-README]
- Redirecting line pointers (`LP_REDIRECT`) keep index TIDs valid after the original heap tuple is reclaimed. [from-README]
- Tuple lock modes form a 4×4 conflict matrix; `KEY SHARE` was added for FK enforcement (PG 9.3) so that key-stable UPDATEs do not block FK checks. [from-README, README.tuplock middle]
- MultiXactId is used whenever ≥2 transactions concurrently hold a lock on the same tuple, or a locker coexists with an updater. [from-README]

## Key invariants and locking

- HOT chain rules: every member after the root has `HEAP_ONLY_TUPLE`; every member that has been HOT-updated has `HEAP_HOT_UPDATED`; chain ends at a tuple whose `t_ctid` points to itself or at a non-HOT update. [from-README]
- Indexes must not store entries for `HEAP_ONLY_TUPLE` rows. [from-README]
- Pruning requires a buffer cleanup lock when it would move tuple data; an ordinary exclusive lock suffices when only LP_DEAD→LP_UNUSED transitions are made. [from-comment, heapam_xlog.h:303-310]

## Cross-references

- HOT mechanics live in `pruneheap.c` (`heap_prune_chain`, `heap_page_prune_execute`) and `heapam.c` (`heap_update` decides HOT-eligibility). [verified-by-code]
- Tuple-lock state machine lives in `heapam.c::heap_lock_tuple` and `heap_lock_updated_tuple`. [verified-by-code]
- MultiXact resolution: `multixact.c` (outside this directory). [inferred]

## Open questions

- Exact ordering of "drop pin, take cleanup lock, re-pin" sequences during prune — relies on bufmgr API but not summarised in README. [unverified]

## Confidence tag tally

`[verified-by-code]=2 [from-comment]=1 [from-readme]=8 [inferred]=1 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
