---
source_url: https://www.postgresql.org/docs/current/storage-hot.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §65.7: Heap-Only Tuples (HOT)

The optimization that lets an UPDATE avoid touching indexes and lets normal
SELECTs reclaim dead row versions without VACUUM. Distilled for the **two HOT
conditions, the chain/redirect mechanics, and the flag bits** a heap hacker needs.

## The two conditions for a HOT update

Both must hold or the update falls back to a normal (index-touching) update: [from-docs]

1. **No indexed column changed** — the update modifies no column referenced by any
   index (BRIN summarizing indexes are exempt — they may still need an update).
2. **The new version fits on the same page** as the old version.

When both hold, **no new index entry is created**; existing index entries keep
pointing at the page item identifier of the *original* row version. [from-docs]

## The HOT chain

- The new tuple is a **heap-only tuple**: reachable *only* by following the
  `t_ctid` forward pointer from the indexed root tuple, **never directly from an
  index**. An index lookup lands on the root and walks the chain to find the live
  version. [from-docs]
  [verified-by-code, source/src/include/access/htup_details.h — `HEAP_HOT_UPDATED`
  marks the *old* tuple, `HEAP_ONLY_TUPLE` marks the *new* heap-only tuple; via
  knowledge/subsystems/access-heap.md]
- `t_ctid` of each chain member points to the next version; the chain is what
  `heap_hot_search_buffer` walks. [from-comment] [verified-by-code,
  source/src/backend/access/heap/heapam.c]

## Pruning — dead-version cleanup without VACUUM

The headline payoff, happening during *ordinary page access*: [from-docs]

- When a page is pruned, the **root line pointer is converted to a `LP_REDIRECT`**
  pointing at the oldest still-possibly-visible version; intermediate
  no-longer-visible versions are removed and their **line pointers freed for
  reuse**. Indexes never learn about this — they still point at the (now redirect)
  root line pointer. [from-docs]
  [verified-by-code, source/src/include/storage/itemid.h — `LP_REDIRECT`,
  `LP_DEAD`, `LP_NORMAL`, `LP_UNUSED`; pruning in
  source/src/backend/access/heap/pruneheap.c]
- This is **single-page defragmentation**: dead heap tuples are reclaimed
  opportunistically on SELECT/UPDATE, so HOT-heavy workloads avoid both **index
  bloat** (no new index entries) and much **heap bloat** (pruning), deferring or
  shrinking VACUUM's job. [from-docs]

## The trade-off / failure mode

- HOT only helps when updates don't touch indexed columns. An update that changes
  an indexed column forces a non-HOT update (new index entries, no same-page
  chaining) — so **over-indexing a frequently-updated column defeats HOT** and is
  a common cause of update-heavy table bloat. [inferred, from-docs]

## Links into corpus

- [[knowledge/subsystems/access-heap.md]] — `heap_update`'s HOT path, pruning,
  the flag bits.
- [[knowledge/architecture/mvcc.md]] — why dead versions exist at all.
- [[knowledge/data-structures/heap-tuple-layout.md]] — `t_infomask2` flag bits and
  `t_ctid`.
- [[knowledge/docs-distilled/storage-vm.md]] — pruning interacts with VM bit
  clearing.
- [[knowledge/wiki-distilled/Hint_Bits.md]] — sibling "work done during ordinary
  reads" mechanism.

## Gaps / follow-ups

- No per-file corpus doc yet for `src/backend/access/heap/pruneheap.c`; the
  `LP_REDIRECT`/pruning cites are pointer-level. A direct read would pin the
  prune-vs-vacuum boundary and the `heap_page_prune_opt` trigger heuristic.
