# spgxlog.c

- **Source path:** `source/src/backend/access/spgist/spgxlog.c` (1001 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/spgxlog.h` (record formats), `spgdoinsert.c` (emit sites for insert), `spgvacuum.c` (emit sites for VACUUM).

## Purpose

WAL replay (`spg_redo`), masking (`spg_mask`), and helper `fillFakeState` that builds a dummy `SpGistState` for replay (without going through the relcache). [from-comment, spgxlog.c:1-13]

## Record-to-handler table

| Info | Handler | Notes |
|---|---|---|
| `XLOG_SPGIST_ADD_LEAF` (0x10) | `spgRedoAddLeaf` | Insert a leaf tuple; optionally update parent downlink (if this was on a fresh leaf page) |
| `XLOG_SPGIST_MOVE_LEAFS` (0x20) | `spgRedoMoveLeafs` | Migrate a leaf chain to a new page; install REDIRECT in old location; update parent downlink |
| `XLOG_SPGIST_ADD_NODE` (0x30) | `spgRedoAddNode` | Extend inner tuple's node array. May move tuple to new inner page + leave PLACEHOLDER + update parent downlink |
| `XLOG_SPGIST_SPLIT_TUPLE` (0x40) | `spgRedoSplitTuple` | The radix prefix/postfix split |
| `XLOG_SPGIST_PICKSPLIT` (0x50) | `spgRedoPickSplit` | Leaf-page repartition: new inner tuple + redistribute leaf tuples |
| `XLOG_SPGIST_VACUUM_LEAF` (0x60) | `spgRedoVacuumLeaf` | Per-leaf-page VACUUM cleanup: convert REDIRECTs to PLACEHOLDERs, delete tail placeholders, mark dead tuples |
| `XLOG_SPGIST_VACUUM_ROOT` (0x70) | `spgRedoVacuumRoot` | Root-leaf-page VACUUM (special case: root-as-leaf only has LIVE tuples) |
| `XLOG_SPGIST_VACUUM_REDIRECT` (0x80) | `spgRedoVacuumRedirect` | Convert expired REDIRECTs to PLACEHOLDERs, delete tail PLACEHOLDERs. **The only spgist record with `snapshotConflictHorizon`** — line 871 calls `ResolveRecoveryConflictWithSnapshot` |

(`XLOG_SPGIST_CREATE_INDEX` 0x00 retired.)

## Recovery-correctness notes [HIGH-RISK]

### `spgRedoVacuumRedirect` is the only conflict-emitting record

The recycling of a REDIRECT/PLACEHOLDER slot may release a TID that the standby could still be using to look up an in-progress search. The conflict horizon is the XID at which the REDIRECT was created (carried in `snapshotConflictHorizon`). [verified-by-code, spgxlog.c:871]

Other VACUUM records (`VACUUM_LEAF`, `VACUUM_ROOT`) **do not** emit conflicts: heap pruning's `XLOG_HEAP2_PRUNE_VACUUM_SCAN` already published the cutoff for the heap TIDs being removed. The REDIRECT case is different because the conflict is about *index-internal* offsets being recycled, not about heap-TID visibility. [inferred]

### Multi-buffer records

Most records touch multiple buffers (target page + parent + sometimes a third). Replay processes them in WAL-record block-id order which corresponds to the primary's lock-acquisition order. The README's deadlock-avoidance rule (conditional-lock + restart) is a primary-only concern; replay is single-threaded against concurrent backends.

### `PICKSPLIT` replay

The most complex handler: re-initializes multiple new leaf pages from full-page images, installs a new inner tuple in the parent inner page (or moves it to a new inner page if it doesn't fit), and writes a REDIRECT at the old chain head. The record format carries the inner tuple's prefix + node array, the redistributed leaf-tuple sets, and the parent-downlink update.

### `ADD_NODE` replay corner

If the primary moved the inner tuple to a new inner page (because the extended-size inner tuple didn't fit on the old page), the replay must:
- Initialize a new inner page (block X).
- Leave a PLACEHOLDER on the old page where the tuple used to be.
- Update the parent's downlink to point at the new location.
- (No REDIRECT needed because PLACEHOLDERs are "no incoming links" — but the parent downlink update happens in the same WAL record, so atomicity holds.)

## Masking (`spg_mask`)

- LSN/checksum + hint bits standard.
- Unused space masked if `pd_lower` looks valid.
- (No special-flag masking like GiST's NSN — SP-GiST doesn't have analogous primary-only state.)

## Cross-references

- **Dispatched from:** `access/transam/rmgr.c` via `RM_SPGIST_ID`.
- **Calls into:** `xlogutils.c`, `standby.c::ResolveRecoveryConflictWithSnapshot`, `spgutils.c::SpGistInitPage` / redirect helpers.

## Open questions

- Whether the absence of conflict emission on `VACUUM_LEAF`/`VACUUM_ROOT` is fully correct when a TID being removed in the leaf is one a standby query had cached. The general PG invariant (heap pruning published the conflict) should cover it, but is not asserted in code. [inferred]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
