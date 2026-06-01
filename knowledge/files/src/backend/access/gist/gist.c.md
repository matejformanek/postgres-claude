# gist.c

- **Source path:** `source/src/backend/access/gist/gist.c` (1747 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `gistget.c` (scan), `gistsplit.c` (multicol split), `gistxlog.c` (replay), `gistutil.c` (page utils), `gistbuild.c` (build paths).

## Purpose

The AM-handler module: defines `gisthandler` (`IndexAmRoutine`), the top-level insert path (`gistdoinsert`), and `gistplacetopage` — "the workhorse function that performs one step of the insertion." [from-README, README:176-187; from-comment, gist.c:1-13]

## Capability vtable (`gisthandler`)

- `amgettuple` = `gistgettuple`, `amgetbitmap` = `gistgetbitmap` (both supported)
- `amcanorder=false`, `amcanorderbyop=true` (KNN!), `amcanbackward=false`, `amcanunique=false`, `amcanmulticol=true`, `amsearchnulls=true`, `amparallelscan=true` (since v15+), `amclusterable=true`, `amsummarizing=false`.
- Build paths: `ambuild=gistbuild`, `ambuildphasename` set.

## Key entry points

| Function | Role |
|---|---|
| `gistinsert` | Per-row insert (AM slot) → `gistdoinsert` |
| `gistdoinsert` | Top-level: descend to leaf, adjusting downlinks on the way (the single-pass README §"Insert algorithm" path), then `gistplacetopage` |
| `gistplacetopage` | One page-step of insert: try to fit, else split, return new downlinks for caller to insert in parent |
| `gistdoCopyOnSplit` (and helpers) | Build the new page images for a split |
| `gistFindCorrectParent` | Re-find parent when the cached stack frame is stale due to concurrent parent-split (rightlink walk + fallback to `gistFindPath`) |
| `gistFindPath` | Top-down root re-traversal when rightlink walk insufficient |
| `gistNewBuffer` | Get a recyclable buffer via FSM, checking `gistPageRecyclable(page)` against `GlobalVisCheckRemovableFullXid(deleteXid)` |

## Insert algorithm (single-pass, README §"Insert Algorithm")

1. Stack-based descent from root. At each non-leaf step:
   - Did this page split since we saw its parent? (NSN vs parent-LSN). If so, retreat.
   - If leaf → done.
   - Otherwise pick subtree by `Penalty` (lowest score).
   - If the downlink doesn't cover the new key, compute `Union(downlink, newkey)` and **replace the downlink right now** (possibly causing internal split). This is the on-the-way adjustment.
   - Walk down.
2. At leaf, call `gistplacetopage` to insert; if it splits, walk back up the stack inserting downlinks for each new page.

This single-pass design means after any one page write the tree is self-consistent (rightlink protects against orphaned post-split state). [from-README, README:127-156]

## `gistplacetopage` split mechanics [HIGH-RISK]

- Calls `gistSplitByKey` (in `gistsplit.c`) which may split into more than 2 pages.
- Allocates new buffers via `gistNewBuffer`.
- For non-root splits: marks the leftmost split-result with **`F_FOLLOW_RIGHT`** before WAL — this is the "split not yet linked to parent" signal that searches use to know to follow the rightlink, and that future inserters use to detect a crashed split and complete it. [from-README, README:275-296]
- For root splits: allocates new children + new root in one atomic operation (no F_FOLLOW_RIGHT needed because the new root is logged with downlinks pre-installed). [from-README, README:184-187]
- Emits `XLOG_GIST_PAGE_SPLIT` registering all new pages.

## Locking — the hot section

- README rule: **child before parent, left-to-right same level**. [from-README, README:260-265]
- During descent: pin one page at a time, share-lock briefly per node. The leaf is exclusive-locked at insert.
- During split: the workhorse holds locks on all new pages until WAL is emitted; parent re-locking via `gistFindCorrectParent` may upgrade to exclusive.
- **Crashed-split recovery**: if `gistdoinsert` sees a page with `F_FOLLOW_RIGHT` set, it immediately tries to finish the split (insert downlink in parent). This is the only way to clear stray F_FOLLOW_RIGHT pages outside VACUUM. [from-README, README:286-296]

## WAL records emitted

- `XLOG_GIST_PAGE_UPDATE` — generic in-place modify: `(ntodelete, ntoinsert)` + offset array + tuple data. Special-case `(1,1)` uses `PageIndexTupleOverwrite`. May include "clear F_FOLLOW_RIGHT on child" as block 1.
- `XLOG_GIST_PAGE_SPLIT` — `npage` registered new pages; the first listed is the "original" page being held under lock throughout replay. Carries `orignsn` (the LSN to stamp into NSN), `origrlink`, `markfollowright`, `origleaf`.
- `XLOG_GIST_DELETE` — leaf-tuple delete with `snapshotConflictHorizon` (the AM's killed-tuples mechanism). [from-code at gistxlog.c:182-198]
- `XLOG_GIST_PAGE_DELETE` — VACUUM unlinks a leaf page (target leaf + parent block).
- `XLOG_GIST_PAGE_REUSE` — emitted at allocate-from-FSM time so a standby can resolve the conflict for any in-progress query.

## Cross-references

- **Called by:** `access/index/indexam.c` (insert/build), `commands/vacuum.c` (via AM slots → `gistvacuum.c`).
- **Calls into:** `gistutil.c` (NSN, follow-right macros, key utilities), `gistsplit.c` (multi-col split), `gistxlog.c` (WAL emission helpers).

## Open questions

- The exact interaction between `gistFindCorrectParent`'s rightlink-walk and a *concurrent* parent split (both can be walking rightlinks at the parent level). Comment in `gistFindCorrectParent` says safe-by-pin-of-parent + retry. [verified-by-code; the README is brief]
- KNN ordering's interaction with parallel scan was added later; whether some KNN paths still serialize is not analyzed. [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
