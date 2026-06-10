---
path: src/backend/access/rmgrdesc/gindesc.c
anchor_sha: 4b0bf0788b0
loc: 222
depth: deep
---

# gindesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/gindesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 222

## Purpose

rmgr descriptor routines for the GIN resource manager (`RM_GIN_ID`,
records from `access/gin/ginxlog.c` / `access/ginxlog.h`). Renders the
9 GIN WAL opcodes for `pg_waldump`, including the
posting-list-recompression segment stream that GIN leaf updates carry.
[from-comment, gindesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `gin_desc(buf, record)` | `gindesc.c:71` | render one GIN record |
| `gin_identify(info)` | `gindesc.c:185` | opcode → short name |

## Internal landmarks

- **`desc_recompress_leaf` (gindesc.c:20)** — static helper that walks a
  `ginxlogRecompressDataLeaf`'s action stream (`nactions` entries, each
  a `segno`+`action` byte pair, optionally followed by an inline
  `GinPostingList` for INSERT/REPLACE or an item array for ADDITEMS).
  Shared by the leaf-insert (gindesc.c:110) and
  `XLOG_GIN_VACUUM_DATA_LEAF_PAGE` (gindesc.c:148) cases. The
  `walbuf` cursor arithmetic at gindesc.c:38-47 is the on-disk segment
  format spec.
- **`XLOG_GIN_INSERT` (gindesc.c:82)** is the most branchy case: an
  internal-page insert appends `children:` blocknos from the inline
  payload; a leaf entry-tree insert prints `isdelete`; a leaf data-tree
  insert recurses into `desc_recompress_leaf`.

## Invariants & gotchas

- **Block-data is decoded only when there is NO full-page image** — the
  guard is the *inverted* `if (!XLogRecHasBlockImage(record, 0))`
  (gindesc.c:102, 143), not the `XLogRecHasBlockData` form the heap/btree
  descs use. Rationale: when an FPI is present the recompress stream was
  folded into the image and is not separately replayable, so there is
  nothing to render. Easy to misread when scanning across descriptors.
- **Unknown recompress action bails the whole helper** — the `default:`
  in `desc_recompress_leaf` (gindesc.c:63) prints `unknown action ???`
  and `return`s, because subsequent segments can't be located once an
  action's length is unknown. Correct defensive behavior.
- **`gin_desc` has no `default:`** — unknown opcode → empty string;
  `gin_identify` returns `NULL` for unknowns.

## Cross-refs

- Record structs + `XLOG_GIN_*` opcodes + `GIN_SEGMENT_*` actions:
  `[[src/include/access/ginxlog.h]]`, `[[src/include/access/gin_private.h]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
