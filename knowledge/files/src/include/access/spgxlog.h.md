# spgxlog.h

- **Source path:** `source/src/include/access/spgxlog.h` (259 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

WAL record formats for SP-GiST. [from-comment, spgxlog.h:1-9]

## Info bytes

```c
/* XLOG_SPGIST_CREATE_INDEX 0x00 retired */
XLOG_SPGIST_ADD_LEAF        0x10
XLOG_SPGIST_MOVE_LEAFS      0x20
XLOG_SPGIST_ADD_NODE        0x30
XLOG_SPGIST_SPLIT_TUPLE     0x40
XLOG_SPGIST_PICKSPLIT       0x50
XLOG_SPGIST_VACUUM_LEAF     0x60
XLOG_SPGIST_VACUUM_ROOT     0x70
XLOG_SPGIST_VACUUM_REDIRECT 0x80
```

## xl_spg_* structs

- `spgxlogAddLeaf` — `(newPage, storesNulls, offsetLeaf, offsetLeafParent, ...)` + leaf-tuple data.
- `spgxlogMoveLeafs` — `(nMoves, replaceDead, storesNulls, parentBlk, ...)` + tuple list + parent-downlink fix.
- `spgxlogAddNode` — `(parentBlk, offnumParent, ...)` + may move inner tuple to new page (placeholder left behind).
- `spgxlogSplitTuple` — prefix/postfix split data.
- `spgxlogPickSplit` — the most complex format: new inner tuple, leaf redistribution, parent-downlink fix, optional new-page inits.
- `spgxlogVacuumLeaf` — `(nDead, nPlaceholder, nMove, nChain, ...)` + tuple lists.
- `spgxlogVacuumRoot` — root-leaf cleanup (simpler).
- `spgxlogVacuumRedirect` — `(nToPlaceholder, firstPlaceholder, snapshotConflictHorizon, isCatalogRel, newestRedirectXid)`.

See `spgxlog.c.md` for replay semantics.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
