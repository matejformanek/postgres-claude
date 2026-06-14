# Heap-tuple update chain — HOT, t_ctid, and the chain-walk

When PostgreSQL updates a heap tuple, the old tuple is not
overwritten — a new tuple is written, and the old one's
`t_ctid` is updated to point at the new one. A series of
updates forms a **chain** of tuple versions on disk. The
update-chain machinery, plus the HOT (Heap-Only Tuple)
optimization, decides where the new version lands and whether
indexes need to be touched.

Anchors:
- `source/src/backend/access/heap/heapam.c` — `heap_update`
  [verified-by-code]
- `source/src/include/access/htup_details.h` — flag definitions
  + chain-walking inlines
- `source/src/backend/access/heap/pruneheap.c` — chain pruning
- `knowledge/data-structures/heap-tuple-layout.md` — tuple
  on-disk layout

## The chain shape

Every heap tuple has a `t_ctid` field. For the **latest live
version** in a chain, `t_ctid` points to itself (i.e. equals
its own location). For an **updated tuple**, `t_ctid` points at
the **successor** version — possibly on the same page (HOT),
possibly on a different page.

```
Page 5:
  offset 3: tuple v1 (xmin=100, xmax=200, t_ctid=(5,7))   ← old
  offset 7: tuple v2 (xmin=200, xmax=0,   t_ctid=(5,7))   ← latest
                                                              ^
                                                          self-pointer
```

[verified-by-code `htup_details.h:761` chain-test inline]

A chain walk starts at the chain's **root** (the tuple that
indexes point at) and follows `t_ctid` until the current
version is reached.

## Three flag bits on `t_infomask2`

[verified-by-code `htup_details.h:210, 295-296`]

| Flag | Meaning |
|---|---|
| `HEAP_UPDATED` | This tuple is the UPDATEd version (its xmin came from an UPDATE, not INSERT) |
| `HEAP_HOT_UPDATED` | This tuple was updated; the successor is a heap-only tuple (HOT) |
| `HEAP_ONLY_TUPLE` | This tuple is a HOT successor; index entries do NOT point at it |

The HOT condition for the update path: `use_hot_update = true`
iff no indexed column changed AND the new tuple fits on the same
page. When HOT applies, the new tuple gets `HEAP_ONLY_TUPLE`,
the old tuple gets `HEAP_HOT_UPDATED`, and no index entries are
emitted for the new tuple.

[verified-by-code `heapam.c:3209-3260` heap_update setup]

## The HOT win

Without HOT, every UPDATE writes new index entries for every
index on the table — even if the user only changed a non-indexed
column. With HOT:

- New tuple lives on the same page (one heap write, no index
  writes).
- Indexes continue to point at the chain root.
- Chain-walking inside the heap AM resolves the root pointer to
  the live successor.

The break-even is roughly 1 indexed column updated → HOT
disabled. For UPDATE-heavy workloads on wide tables with many
indexes, HOT is the dominant performance optimization.

## When HOT can't apply

[from-comment + verified-by-code `heapam.c:3197-3300`]

- **Indexed column changed.** Any index on the changed attribute
  forces a non-HOT path. `key_attrs` / `id_attrs` /
  `interesting_attrs` bitmapsets are computed pre-write to detect
  this.
- **Tuple doesn't fit on the page.** New tuple is too large for
  remaining free space on the old page — must move to a new
  page; old page may need pruning.
- **Cross-page update.** The successor's page is different from
  the predecessor's; per definition not HOT.
- **Summarizing index (BRIN, BLOOM) requires update.**
  `summarized_update` path triggers; HOT off.

## Chain walks: heap_prune_chain

The canonical chain-walk consumer is
`heap_prune_chain(maxoff, rootoffnum, prstate)` in
`source/src/backend/access/heap/pruneheap.c:1483`
[verified-by-code]. Called by VACUUM and on-demand-prune paths.
It:

1. Starts at the root offset.
2. Walks `t_ctid` forward, accumulating chain members.
3. Decides per-member: keep, redirect to next live, or remove.
4. Updates line pointers + chain links in one WAL-logged action.

The chain walk reads `t_ctid`'s offset within the same block:

```c
nextoffnum = ItemPointerGetOffsetNumber(&htup->t_ctid);
```

[verified-by-code `pruneheap.c:2332`]

If `t_ctid` points outside the current block, the chain
crosses pages and prune stops at the boundary — cross-page
chain walks are the consumer's job, not pruneheap's.

## Visibility during a chain walk

`HeapTupleSatisfies*` visibility functions are called per chain
member:

- `HeapTupleSatisfiesMVCC(htup, snapshot, buffer)` for queries.
- `HeapTupleSatisfiesUpdate(htup, ...)` for UPDATE/DELETE
  attempting to update this row.
- `HeapTupleSatisfiesVacuum(htup, OldestXmin, buffer)` for VACUUM
  / prune decisions.

Each looks at xmin/xmax + the appropriate horizon and returns a
visibility verdict. The chain-walker uses the verdict to decide
whether to follow `t_ctid` to the next member.

## The chain-end test

```c
HeapTupleHeaderIsHotUpdated(tup):
    (t_infomask2 & HEAP_HOT_UPDATED) != 0 &&
    (t_infomask  & HEAP_XMAX_INVALID) == 0 &&
    !HeapTupleHeaderXminInvalid(tup)
```

[verified-by-code `htup_details.h:525-532`]

A tuple is "HOT-updated" — i.e. has a HOT successor on this page
— iff:
1. The HEAP_HOT_UPDATED bit is set.
2. Its xmax is not marked invalid (the updater actually
   committed, or is still pending).
3. Its xmin is not marked invalid (the inserter committed).

If any of the three fails, the chain ends here.

## Common review-time concerns

- **HOT requires careful chain-walk on index lookup.** If you
  add a new "lookup by TID" path, walk the chain to find the
  current live version. `heap_get_latest_tid` is the canonical
  helper.
- **Adding a new summary index AM** (like BRIN/BLOOM): set
  `amsummarizing = true` in the AM's `IndexAmRoutine`.
  `heap_update` checks this; if any summary index covers the
  row, HOT is disabled.
- **VACUUM redirects must preserve chain ends.** When
  pruneheap.c replaces a chain root with a redirect line
  pointer, the redirect's target must be the live successor.
  Mis-pointing produces "row not found via index" errors.
- **Replica identity uses `id_attrs`.** For logical replication,
  the chain walk also looks at `id_attrs` (REPLICA IDENTITY).
  Changing a REPLICA-IDENTITY column disables HOT.

## Invariants

- **[INV-1]** A live tuple has `t_ctid` pointing at itself (its
  own location).
- **[INV-2]** Chain root must remain reachable from indexes;
  pruning replaces but never removes the root line pointer.
- **[INV-3]** HOT (HEAP_ONLY_TUPLE) tuples have NO index entries
  — indexes still point at the chain root.
- **[INV-4]** Cross-page updates always emit index entries for
  the new tuple.
- **[INV-5]** `HeapTupleHeaderIsHotUpdated` test is the canonical
  chain-continues predicate; don't reimplement.

## Useful greps

- All chain-walking consumers:
  `grep -RIn 'HEAP_HOT_UPDATED\|HEAP_ONLY_TUPLE\|HeapTupleHeaderIsHotUpdated' source/src/backend/access/heap`
- HOT decisions in heap_update:
  `grep -n 'use_hot_update' source/src/backend/access/heap/heapam.c`
- The flag bits:
  `grep -n 'HEAP_HOT_UPDATED\|HEAP_ONLY_TUPLE\|HEAP_UPDATED' source/src/include/access/htup_details.h`

## Cross-references

- `knowledge/data-structures/heap-tuple-layout.md` — tuple
  header layout including the `t_ctid` field.
- `knowledge/subsystems/access-heap.md` — heap AM at large;
  VACUUM, pruning, freezing.
- `knowledge/idioms/visibility-map-update.md` — VM bits the
  prune path clears on chain modification.
- `.claude/skills/locking/SKILL.md` — heap_update lock-mode
  selection (`*lockmode` output parameter).
- `.claude/skills/wal-and-xlog/SKILL.md` — `xl_heap_update` WAL
  record; replay re-creates the chain modification.
- `source/src/backend/access/heap/heapam.c` — `heap_update`,
  `heap_get_latest_tid`.
- `source/src/backend/access/heap/pruneheap.c` —
  `heap_prune_chain`.
- `source/src/include/access/htup_details.h` — flag inlines.
